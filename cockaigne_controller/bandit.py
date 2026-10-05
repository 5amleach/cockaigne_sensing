"""The bandit: one belief per arm per occupancy context, and the action lean.

A belief is a Beta distribution, a running tally of how often choosing this
arm in this kind of room was followed by cohesion rising. At decision time
one sample is drawn from each arm's belief (Thompson sampling), the action
bias is added, and the highest total wins. Wide beliefs explore; sharp ones
commit. The bias leans; it never selects: it is a bounded addition to the
draw, so it tilts close calls and is reported as the reason only when it
actually changed the outcome.

Reward is the change in cohesion_smooth over the clip's later part, mapped
to 0..1 by a clamp around zero (no change scores 0.5), and applied as a
fractional Bernoulli update: a reward of r adds r to the Beta's successes
and 1 - r to its failures.
"""
from __future__ import annotations

import math
import random


def reward_from_delta(delta: float, scale: float) -> float:
    """A cohesion change of +scale maps to 1.0, -scale to 0.0, nothing to 0.5."""
    return max(0.0, min(1.0, 0.5 + delta / (2.0 * scale)))


class Beta:
    def __init__(self, a: float, b: float):
        self.a = max(a, 0.05)
        self.b = max(b, 0.05)

    def sample(self, rng: random.Random) -> float:
        return rng.betavariate(self.a, self.b)

    def update(self, reward: float) -> None:
        reward = max(0.0, min(1.0, reward))
        self.a += reward
        self.b += 1.0 - reward


class Bandit:
    """Beliefs live per (context, arm); reset() starts a new day's priors."""

    def __init__(self, arms: list[str], contexts: list[str],
                 rng: random.Random | None = None):
        self.arms = list(arms)
        self.contexts = list(contexts)
        self.rng = rng or random.Random()
        self.reset({arm: (1.0, 1.0) for arm in self.arms})

    def reset(self, priors: dict[str, tuple[float, float]]) -> None:
        self.beliefs = {(ctx, arm): Beta(*priors[arm])
                        for ctx in self.contexts for arm in self.arms}

    def choose(self, context: str, bias: dict[str, float]) -> tuple[str, str]:
        """One Thompson draw plus the lean. Returns (arm, reason), the reason
        being "action_bias" only when the lean changed the winner."""
        draws = {arm: self.beliefs[(context, arm)].sample(self.rng)
                 for arm in self.arms}
        plain = max(draws, key=draws.get)
        biased = max(draws, key=lambda arm: draws[arm] + bias.get(arm, 0.0))
        return biased, ("action_bias" if biased != plain else "bandit")

    def update(self, context: str, arm: str, reward: float) -> None:
        self.beliefs[(context, arm)].update(reward)


class ActionBias:
    """The lean from what individual people are doing.

    For each action the excess above its usual rate, max(0, rate - 1), is
    remembered and decays with a half-life after it was last seen. Sitting
    has no rate in Contract 2 (the crowd state carries only a count), so the
    controller keeps its own baseline for the sitting fraction, the same way
    the sensing side does for the other actions.
    """

    def __init__(self, cfg: dict, band_size: dict):
        self.cfg = cfg
        self.band_size = band_size
        self.level = {action: 0.0 for action in cfg["targets"]}
        self.sitting_baseline = 0.0
        self._t_prev: float | None = None

    def observe(self, crowd: dict) -> None:
        t = crowd["t"]
        dt = 0.0 if self._t_prev is None else max(0.0, t - self._t_prev)
        self._t_prev = t
        decay = 0.5 ** (dt / self.cfg["half_life_s"])
        rates = dict(crowd.get("action_rates", {}))
        rates["sitting"] = self._sitting_rate(crowd, dt)
        for action in self.level:
            excess = max(0.0, rates.get(action, 0.0) - 1.0)
            self.level[action] = max(excess, self.level[action] * decay)

    def _sitting_rate(self, crowd: dict, dt: float) -> float:
        n = crowd.get("n", 0)
        fraction = crowd.get("actions", {}).get("sitting", 0) / n if n else 0.0
        alpha = 1.0 - math.exp(-dt / self.cfg["sitting_baseline_s"]) if dt > 0 else 0.0
        self.sitting_baseline += alpha * (fraction - self.sitting_baseline)
        return fraction / max(self.sitting_baseline, self.cfg["sitting_baseline_floor"])

    def bias(self, band: str) -> dict[str, float]:
        """The lean per arm name, scaled by one over the band's typical size."""
        size = self.band_size[band]
        out: dict[str, float] = {}
        for action, arm in self.cfg["targets"].items():
            lean = self.cfg["weights"][action] * self.level[action] / size
            out[arm] = out.get(arm, 0.0) + lean
        return out
