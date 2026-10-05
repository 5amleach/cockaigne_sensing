"""The decision logic: crowd state in, one clip decision per cycle out.

Every clip length (60 seconds) the controller decides where the wall goes
next. The ring comes from `ring_target` in the latest crowd state and
nothing else. The arm comes from the bandit: a Thompson draw per arm in the
current occupancy band, plus the action lean. Setting controller.arm_chooser
to "fixed" pins the arm from config instead, which is how the ring
mechanics are tested and how one arm can be soaked on site.

Holding a ring is a sideways move: Rings 1 to 3 have no loop clips, so
staying at a ring goes to the chosen arm at the same ring (the runner-up
when the chooser picked the arm the wall is already on), reason "lateral".
Loops play only where loop clips exist, Ring 4 and Barren; Barren without
a loop probes out to Ring 1 and returns.

If no crowd message has arrived for blind_after_s, the controller is
running blind: it keeps cycling on its own clock and steps the ring down
by one each cycle until Barren. Each day starts with a personality: the
beliefs reset to its priors and the ledger notes who woke up.

This file holds the logic only; the live loop around it is run.py.
"""
from __future__ import annotations

import datetime
import random

from .bandit import ActionBias, Bandit, reward_from_delta
from .clipmap import BARREN, ClipMap, node_name
from .personality import personality_for, priors


class Controller:
    """Holds the wall's position and turns crowd state into decisions.

    decide() is bookkeeping plus the map: it never touches the network, so
    the tests drive it directly with made-up times.
    """

    def __init__(self, cfg: dict, clipmap: ClipMap, layout: dict,
                 rng: random.Random | None = None):
        self.cfg = cfg
        self.map = clipmap
        self.layout = layout
        self.arms = cfg["map"]["arms"]
        self.node = BARREN
        self.ring = 0
        self.n = 0
        self.n_smooth = 0.0
        self.cohesion = 0.0
        self.last_crowd: float | None = None
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

    # --- crowd state ---

    def observe(self, crowd: dict, now: float | None = None) -> None:
        """A crowd message arrived. `now` is the controller's own clock at
        receipt; it defaults to the message's t, which is the same clock
        when sensing runs live on this machine, but differs under replay."""
        self.ring = crowd["ring_target"]
        self.n = crowd["n"]
        # Smoothing happens once, in features; old recordings without
        # n_smooth fall back to the raw headcount.
        self.n_smooth = crowd.get("n_smooth", crowd["n"])
        self.cohesion = crowd["cohesion_smooth"]
        self.action_bias.observe(crowd)
        now = crowd["t"] if now is None else now
        self.last_crowd = now
        # The reward window opens patience seconds into the clip: remember
        # the cohesion there, so the clip is judged on what followed it.
        p = self._pending_reward
        if p and p.get("t_fired") is not None and p["c_start"] is None \
                and now >= p["t_fired"] + self.patience:
            p["c_start"] = self.cohesion

    def context(self) -> str:
        """The occupancy band, from the crowd state's smoothed headcount."""
        band = self.cfg["occupancy"]["bands"][0][1]
        for edge, name in self.cfg["occupancy"]["bands"]:
            if self.n_smooth >= edge:
                band = name
        return band

    def is_blind(self, now: float) -> bool:
        """True when the sensing side has gone quiet."""
        return (self.last_crowd is None
                or now - self.last_crowd > self.cfg["controller"]["blind_after_s"])

    # --- the day ---

    def ensure_day(self, date: datetime.date, ledger=None) -> None:
        """At day start: pick the personality, reset the beliefs to its
        priors, note it in the ledger. The ledger itself is never reset."""
        if date == self._day:
            return
        self._day = date
        name, params = personality_for(date, self.cfg)
        self.personality = name
        self.reward_scale = params["reward_scale"]
        self.patience = params["patience_s"]
        self.bandit.reset(priors(params, list(self.arms.values())))
        if ledger:
            ledger.append("day_start", personality=name)

    # --- the reward for the clip just played ---

    def fired(self, t: float) -> None:
        """The loop calls this at the moment the clip actually starts."""
        if self._pending_reward:
            self._pending_reward["t_fired"] = t

    def _settle_reward(self) -> None:
        """The clip is over: judge it by how cohesion moved and update the
        belief it was drawn from. Barren is nobody's arm and gets none."""
        p, self._pending_reward = self._pending_reward, None
        if not p or p["arm"] == "barren" or p.get("c_start") is None:
            return
        delta = self.cohesion - p["c_start"]
        reward = reward_from_delta(delta, self.reward_scale)
        self.bandit.update(p["context"], p["arm"], reward)
        self.last_outcome = {"arm": p["arm"], "delta_cohesion": round(delta, 3),
                             "reward": round(reward, 2), "context": p["context"]}

    # --- choosing ---

    def ranked_arms(self) -> tuple[list[str], str]:
        """Arm letters in order of preference, and the chooser's reason."""
        if self.cfg["controller"]["arm_chooser"] == "fixed":
            wanted = self.cfg["controller"]["default_arm"]
            order = [wanted] + [a for a in self.arms.values() if a != wanted]
            reason = "ring"
        else:
            context = self.context()
            order, reason = self.bandit.rank(context, self.action_bias.bias(context))
        by_name = {name: letter for letter, name in self.arms.items()}
        return [by_name[name] for name in order], reason

    def decide(self, t: float) -> tuple[dict, tuple[int, int]]:
        """One decision: the Contract 3 message and the (layer, index) to fire."""
        self._settle_reward()
        if self.is_blind(t):
            self.ring = max(0, self.ring - 1)  # run.py logs the blindness
        ranked, base_reason = self.ranked_arms()
        arm_letter = ranked[0]
        # Staying in the current arm while the ring moves is a ring story,
        # whatever the chooser said; its reason belongs to arm changes.
        if self.node != BARREN and self.node[0] == arm_letter:
            base_reason = "ring"
        target = BARREN if self.ring == 0 else node_name(arm_letter, self.ring)
        frm = self.node
        if target == frm:
            if self.map.clip_for(frm, frm):
                to, reason = frm, "loop"
            elif frm == BARREN:
                to, reason = node_name(arm_letter, 1), "probe"
            else:
                # Holding a ring is a sideways move to another arm.
                lateral_letter = next(l for l in ranked if l != frm[0])
                lateral = node_name(lateral_letter, int(frm[1]))
                to = lateral if self.map.clip_for(frm, lateral) \
                    else self.map.next_step(frm, lateral)
                reason = "lateral"
        elif self.map.clip_for(frm, target):
            to, reason = target, base_reason
        else:
            to, reason = self.map.next_step(frm, target), "path"
        clip = self.map.clip_for(frm, to)
        layer, index = self.layout[clip]
        self.node = to
        arm_name = "barren" if to == BARREN else self.arms[to[0]]
        decision = {
            "stream": "decision", "t": round(t, 2),
            "from": frm, "to": to, "clip": clip, "resolume_index": index,
            "arm": arm_name, "reason": reason,
            "context": self.context(), "ring_target": self.ring,
            "personality": self.personality,
        }
        self._pending_reward = {"arm": arm_name, "context": decision["context"],
                                "t_fired": None, "c_start": None}
        return decision, (layer, index)
