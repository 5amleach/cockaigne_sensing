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

    def rank(self, context: str, bias: dict[str, float]) -> tuple[list[str], str]:
        """One Thompson draw plus the lean, every arm in order of its total.
        The reason is "action_bias" only when the lean changed the winner;
        the runner-up serves the lateral move when the winner is the arm
        the wall is already on."""
        draws = {arm: self.beliefs[(context, arm)].sample(self.rng)
                 for arm in self.arms}
        plain = max(draws, key=draws.get)
        order = sorted(self.arms, key=lambda arm: draws[arm] + bias.get(arm, 0.0),
                       reverse=True)
        return order, ("action_bias" if order[0] != plain else "bandit")

    def choose(self, context: str, bias: dict[str, float]) -> tuple[str, str]:
        """The winning arm alone, when the full ranking is not needed."""
        order, reason = self.rank(context, bias)
        return order[0], reason

    def update(self, context: str, arm: str, reward: float) -> None:
        self.beliefs[(context, arm)].update(reward)


class ActionBias:
    """The lean from what individual people are doing.

    For each action the excess above its usual rate, max(0, rate - 1), is
    remembered and decays with a half-life on the controller's own clock,
    so it fades even when messages stop. Rates are capped at rate_cap; every
    rate is treated as 1.0 (no excess) until baseline_warmup_s of crowd
    history has been seen, because a baseline built on seconds of data makes
    the first sitter look like a stampede. The final lean per arm is capped
    at lean_cap, half a Thompson draw, so it leans and can never select by
    itself. Sitting has no rate in Contract 2, so a baseline for the sitting
    fraction is kept here, the way sensing keeps the others.
    """

    def __init__(self, cfg: dict, band_size: dict):
        self.cfg = cfg
        self.band_size = band_size
        self.level = {action: 0.0 for action in cfg["targets"]}
        self.sitting_baseline = 0.0
        self._at: float | None = None      # controller clock of the last observe
        self._warm = 0.0                   # seconds of crowd history seen
        self._t_prev: float | None = None  # message clock, for the baselines

    def clear(self) -> None:
        """Day start: yesterday's excesses do not lean on today."""
        self.level = {action: 0.0 for action in self.level}

    def _decayed(self, action: str, now: float) -> float:
        if self._at is None:
            return self.level[action]
        return self.level[action] * 0.5 ** ((now - self._at) / self.cfg["half_life_s"])

    def observe(self, crowd: dict, now: float) -> None:
        t = crowd["t"]
        dt = 0.0 if self._t_prev is None else max(0.0, min(t - self._t_prev, 10.0))
        self._t_prev = t
        self._warm += dt
        rates = dict(crowd.get("action_rates", {}))
        rates["sitting"] = self._sitting_rate(crowd, dt)
        for action in self.level:
            if self._warm < self.cfg["baseline_warmup_s"]:
                excess = 0.0   # the baselines are too young to trust
            else:
                excess = max(0.0, min(rates.get(action, 0.0), self.cfg["rate_cap"]) - 1.0)
            self.level[action] = max(excess, self._decayed(action, now))
        self._at = now

    def _sitting_rate(self, crowd: dict, dt: float) -> float:
        n = crowd.get("n", 0)
        fraction = crowd.get("actions", {}).get("sitting", 0) / n if n else 0.0
        alpha = 1.0 - math.exp(-dt / self.cfg["sitting_baseline_s"]) if dt > 0 else 0.0
        self.sitting_baseline += alpha * (fraction - self.sitting_baseline)
        return fraction / max(self.sitting_baseline, self.cfg["sitting_baseline_floor"])

    def bias(self, band: str, now: float) -> dict[str, float]:
        """The lean per arm name, scaled by the band's typical size and
        capped at lean_cap."""
        size = self.band_size[band]
        out: dict[str, float] = {}
        for action, arm in self.cfg["targets"].items():
            lean = self.cfg["weights"][action] * self._decayed(action, now) / size
            out[arm] = out.get(arm, 0.0) + lean
        return {arm: min(v, self.cfg["lean_cap"]) for arm, v in out.items()}
