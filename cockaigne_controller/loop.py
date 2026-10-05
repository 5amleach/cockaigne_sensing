"""The decision logic: crowd state in, one clip decision per cycle out.

The controller keeps two positions. `displayed` is where the wall actually
is: it advances only when a fire was confirmed (or sent, when there is no
REST to ask). A decision is a plan; routing, holding and the blind descent
all start from `displayed`, so a failed fire is retried from reality rather
than from an imagined position.

The ring comes from `ring_target` in the latest crowd state. The arm comes
from the bandit (controller.arm_chooser "fixed" pins it instead). Holding a
ring never leaves the ring: a loop clip where one exists, otherwise a
sideways move to another arm along ring-preserving clips. Barren probes out
to Ring 1 and returns.

Freshness is the crowd message's own clock: if `t` has not advanced for
blind_after_s on the controller's clock, the controller is blind and steps
the displayed position's ring down by one each cycle, along the displayed
arm, until Barren. The day's personality resets the beliefs, the pending
reward and the action lean; the ledger is never reset.

This file holds the logic only; the live loop around it is run.py.
"""
from __future__ import annotations

import datetime
import random

from .bandit import ActionBias, Bandit, reward_from_delta
from .clipmap import BARREN, ClipMap, node_name, node_ring
from .personality import personality_for, priors


class Controller:
    """Turns crowd state into decisions. decide() never touches the network
    and never advances `displayed`; run.py confirms fires."""

    def __init__(self, cfg: dict, clipmap: ClipMap, layout: dict,
                 rng: random.Random | None = None):
        self.cfg = cfg
        self.map = clipmap
        self.layout = layout
        self.arms = cfg["map"]["arms"]
        self.displayed = BARREN     # what the wall shows, as far as we know
        self.ring = 0
        self.n = 0
        self.n_smooth = 0.0
        self.cohesion = 0.0
        self._last_msg_t = float("-inf")
        self._fresh_at: float | None = None
        self.rng = rng or random.Random()
        contexts = [name for _, name in cfg["occupancy"]["bands"]]
        self.bandit = Bandit(list(self.arms.values()), contexts, self.rng)
        self.action_bias = ActionBias(cfg["action_bias"], cfg["occupancy"]["band_size"])
        self.personality: str | None = None
        self.reward_scale = cfg["bandit"]["reward_scale"]
        self.patience = cfg["bandit"]["reward_delay_s"]
        self._day: datetime.date | None = None
        self._pending_reward: dict | None = None
        self.last_outcome: dict | None = None
        self.warnings: list[str] = []   # run.py drains these into the log

    # --- crowd state ---

    def observe(self, crowd: dict, now: float | None = None) -> None:
        """One validated crowd message. `now` is the controller's own clock;
        it defaults to the message's t, the same clock when sensing runs live
        on this machine. Freshness requires the message's own t to advance."""
        now = crowd["t"] if now is None else now
        self.ring = crowd["ring_target"]
        self.n = crowd["n"]
        self.n_smooth = crowd.get("n_smooth", crowd["n"])
        self.cohesion = crowd["cohesion_smooth"]
        self.action_bias.observe(crowd, now)
        if crowd["t"] > self._last_msg_t:
            self._last_msg_t = crowd["t"]
            self._fresh_at = now
        # The reward window opens patience seconds into the clip.
        p = self._pending_reward
        if p and p["c_start"] is None and now >= p["t_fired"] + self.patience:
            p["c_start"] = self.cohesion

    def context(self) -> str:
        band = self.cfg["occupancy"]["bands"][0][1]
        for edge, name in self.cfg["occupancy"]["bands"]:
            if self.n_smooth >= edge:
                band = name
        return band

    def is_blind(self, now: float) -> bool:
        """True when no crowd message with an advancing clock has arrived
        for blind_after_s: a repeated or stale message does not count."""
        return (self._fresh_at is None
                or now - self._fresh_at > self.cfg["controller"]["blind_after_s"])

    # --- the day ---

    def ensure_day(self, date: datetime.date, ledger=None) -> None:
        """At day start: new personality, beliefs reset to its priors, the
        pending reward and the action lean cleared. The ledger is never reset."""
        if date == self._day:
            return
        self._day = date
        name, params = personality_for(date, self.cfg)
        self.personality = name
        self.reward_scale = params["reward_scale"]
        self.patience = params["patience_s"]
        self.bandit.reset(priors(params, list(self.arms.values())))
        self._pending_reward = None
        self.action_bias.clear()
        if ledger:
            ledger.append("day_start", personality=name)

    # --- fires and rewards ---

    def confirm_fired(self, decision: dict, t: float) -> None:
        """The clip is confirmed showing: the wall is now at its destination,
        and the clip starts earning its reward."""
        self.displayed = decision["to"]
        self._pending_reward = {"arm": decision["arm"], "context": decision["context"],
                                "t_fired": t, "c_start": None}

    def settle_reward(self) -> None:
        """Called at the moment the next clip fires, so the whole clip counts:
        the reward is the cohesion now against cohesion when the window
        opened. Barren is nobody's arm; an unconfirmed clip never had a
        pending reward to settle."""
        p, self._pending_reward = self._pending_reward, None
        if not p or p["arm"] == "barren" or p["c_start"] is None:
            return
        delta = self.cohesion - p["c_start"]
        reward = reward_from_delta(delta, self.reward_scale)
        self.bandit.update(p["context"], p["arm"], reward)
        self.last_outcome = {"arm": p["arm"], "delta_cohesion": round(delta, 3),
                             "reward": round(reward, 2), "context": p["context"]}

    # --- choosing ---

    def ranked_arms(self, now: float) -> tuple[list[str], str]:
        """Arm letters in order of preference, and the chooser's reason."""
        if self.cfg["controller"]["arm_chooser"] == "fixed":
            wanted = self.cfg["controller"]["default_arm"]
            order = [wanted] + [a for a in self.arms.values() if a != wanted]
            reason = "ring"
        else:
            context = self.context()
            order, reason = self.bandit.rank(context, self.action_bias.bias(context, now))
        by_name = {name: letter for letter, name in self.arms.items()}
        return [by_name[name] for name in order], reason

    def _hold(self, frm: str, ranked: list[str]) -> tuple[str, str]:
        """Spend a cycle without leaving the node's ring: the loop clip where
        one exists, otherwise sideways to another arm along this ring."""
        if self.map.clip_for(frm, frm):
            return frm, "loop"
        if frm == BARREN:
            return node_name(ranked[0], 1), "probe"
        ring = node_ring(frm)
        lateral_letter = next(l for l in ranked if l != frm[0])
        lateral = node_name(lateral_letter, ring)
        if self.map.clip_for(frm, lateral):
            return lateral, "lateral"
        step = self.map.next_step_on_ring(frm, lateral, ring)
        if step is not None:
            return step, "lateral"
        # A validated pool cannot reach here; say so and stay as close as we can.
        self.warnings.append(f"no ring-preserving move from {frm}; leaving the ring")
        return self.map.next_step(frm, lateral) or frm, "lateral"

    def decide(self, t: float) -> tuple[dict, tuple[int, int]]:
        """One plan: the Contract 3 message and the (layer, index) to fire.
        The wall's position is advanced by confirm_fired(), not here."""
        frm = self.displayed
        ranked, base_reason = self.ranked_arms(t)
        if self.is_blind(t):
            # Step down from where the wall actually is, along its own arm.
            self.ring = max(0, node_ring(frm) - 1)
            arm_letter = frm[0] if frm != BARREN else ranked[0]
            base_reason = "ring"
        else:
            arm_letter = ranked[0]
            if frm != BARREN and frm[0] == arm_letter:
                base_reason = "ring"
        target = BARREN if self.ring == 0 else node_name(arm_letter, self.ring)
        if target == frm:
            to, reason = self._hold(frm, ranked)
        elif self.map.clip_for(frm, target):
            to, reason = target, base_reason
        else:
            to, reason = self.map.next_step(frm, target), "path"
        clip = self.map.clip_for(frm, to) if to else None
        if clip is None:
            # A validated pool cannot reach here either; take any way out
            # rather than crash the show.
            self.warnings.append(f"no clip from {frm} toward {to or target}; improvising")
            to = self.map.neighbours(frm)[0]
            clip, reason = self.map.clip_for(frm, to), "path"
        layer, index = self.layout[clip]
        arm_name = "barren" if to == BARREN else self.arms[to[0]]
        decision = {
            "stream": "decision", "t": round(t, 2),
            "from": frm, "to": to, "clip": clip, "resolume_index": index,
            "arm": arm_name, "reason": reason,
            "context": self.context(), "ring_target": self.ring,
            "personality": self.personality,
        }
        return decision, (layer, index)
