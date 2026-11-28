"""Crowd cohesion, the reservoir and the ring (Contract 2), from the people list alone.

Clustering (gathered more than chance) and coordination (attentive and still,
or moving the same way) say how much the crowd acts as a group; their
geometric mean is relational cohesion C. When there is nobody to be relational
with, a proxy score A stands in (time in the room, stillness, place).

The two are blended, never switched: S = (1 - w) A + w C, with the weight w
following the smoothed headcount (the single-viewer behaviour, DECISIONS.md
2026-09-19). Two guards keep the top ring collective (2026-10-05): in the
blend C counts as 0.0 below two people (the reported cohesion_relational is
displayed, not the driver), and the blend sits under a headcount-following
ceiling, 0.72 up to two people. The smoothed score feeds a reservoir that
rises slowly and drains more slowly; its level picks the ring, with hysteresis.
"""
from __future__ import annotations

import math

from .agreement import mood_agreement, social_synchrony
from .attention import AttentionMemory


def _speed(p: dict) -> float:
    return math.hypot(p["vx"], p["vy"])


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _round(v: float | None) -> float | None:   # None means n/a: could not be measured
    return None if v is None else round(v, 3)


def _alpha(dt: float, time_constant_s: float) -> float:
    """The step fraction for an exponentially weighted average."""
    if dt <= 0 or time_constant_s <= 0:
        return 0.0
    return 1.0 - math.exp(-dt / time_constant_s)


def clustering_score(people: list[dict], floor_w: float, floor_l: float,
                     zero_at_ratio: float) -> float | None:
    """How gathered the crowd is, 0 to 1, judged against chance.

    The mean distance from each person to their nearest neighbour is compared
    with what random placement would give for the same headcount on this floor
    (about 0.5 * sqrt(area / n)). Random spacing scores 0.5; spacing at
    zero_at_ratio times random scores 0; a tight huddle scores near 1. With
    fewer than two people there is nothing to measure: None, shown as n/a.
    """
    n = len(people)
    if n < 2:
        return None
    nearest = []
    for i, p in enumerate(people):
        d2 = min((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2
                 for j, q in enumerate(people) if j != i)
        nearest.append(math.sqrt(d2))
    expected = 0.5 * math.sqrt(floor_w * floor_l / n)
    ratio = (sum(nearest) / n) / expected
    return _clamp01(1.0 - ratio / zero_at_ratio)


def synchrony_score(people: list[dict], still_speed: float) -> float | None:
    """How aligned the movement is, 0 to 1.

    The length of the sum of the movers' velocity vectors, divided by the sum
    of their speeds: 1 when everyone walks the same way, near 0 when movement
    cancels out. People standing still are left out. Fewer than two movers
    means there is nothing to measure: None, shown as n/a (28 Nov 2026).
    """
    movers = [p for p in people if _speed(p) >= still_speed]
    if len(movers) < 2:
        return None
    sx = sum(p["vx"] for p in movers)
    sy = sum(p["vy"] for p in movers)
    total = sum(_speed(p) for p in movers)
    return _clamp01(math.hypot(sx, sy) / total)


def stillness_score(people: list[dict], still_speed: float) -> float:
    """The fraction of people standing still."""
    if not people:
        return 0.0
    return sum(1 for p in people if _speed(p) < still_speed) / len(people)


def coordination_score(held: float, stillness: float, synchrony: float | None) -> float:
    """The share of people held (still, or from 28 Nov attentive: attention.py)
    plus the movers' share times their synchrony. Someone still but not
    attentive adds nothing, nor does a lone walker (synchrony None)."""
    return _clamp01(held + (1.0 - stillness) * (synchrony or 0.0))


def spot_score(x: float, y: float, cohesion_cfg: dict) -> float:
    """Position scored by distance from the viewing spot.

    Full within proxy_spot_full_m of the spot, zero at proxy_spot_zero_m or
    further, falling in a straight line between. The spot is where the work
    is best seen (DECISIONS.md, 2026-09-19).
    """
    d = math.hypot(x - cohesion_cfg["proxy_spot_x_m"], y - cohesion_cfg["proxy_spot_y_m"])
    full, zero = cohesion_cfg["proxy_spot_full_m"], cohesion_cfg["proxy_spot_zero_m"]
    if d <= full:
        return 1.0
    if d >= zero:
        return 0.0
    return (zero - d) / (zero - full)


def proxy_score(people: list[dict], cohesion_cfg: dict) -> float:
    """The fallback score A: what the estimator leans on when the room is near empty.

    For each person: time in the room (full after proxy_dwell_full_s),
    stillness (1 when stopped) and position (spot_score), averaged. The
    per-person scores are averaged over everyone present. The ceiling that
    keeps the top ring out of reach is applied to the blended score, not
    here (score_ceiling_by_n).
    """
    if not people:
        return 0.0
    per_person = []
    for p in people:
        dwell = _clamp01(p["age"] / cohesion_cfg["proxy_dwell_full_s"])
        still = 1.0 if _speed(p) < cohesion_cfg["still_speed_mps"] else 0.0
        position = spot_score(p["x"], p["y"], cohesion_cfg)
        per_person.append((dwell + still + position) / 3.0)
    return sum(per_person) / len(per_person)


def interp_by_n(n_eff: float, table: list[list[float]]) -> float:
    """A value that follows the smoothed headcount, read from
    [[headcount, value], ...]: piecewise linear between the table's points,
    flat beyond its ends. Used for the blend weight and the score ceiling."""
    if n_eff <= table[0][0]:
        return table[0][1]
    for (n0, w0), (n1, w1) in zip(table, table[1:]):
        if n_eff <= n1:
            return w0 + (w1 - w0) * (n_eff - n0) / (n1 - n0)
    return table[-1][1]


def relational_cohesion(signals: dict[str, float], enabled: list[str]) -> float:
    """Geometric mean of the enabled signals that could be measured (n/a ones
    are left out). Any zero pulls the whole to zero."""
    values = [signals[name] for name in enabled if signals[name] is not None]
    product = math.prod(values)
    return product ** (1.0 / len(values)) if product > 0 else 0.0


class Reservoir:
    """A level that chases the score and never jumps.

    While the score is above the level, the level rises toward it at
    rise_rate per second; while below, it falls at the slower fall_rate.
    It is never reset when people arrive or leave.
    """

    def __init__(self, rise_rate: float, fall_rate: float):
        self.rise = rise_rate
        self.fall = fall_rate
        self.level = 0.0

    def step(self, score: float, dt: float) -> float:
        if score > self.level:
            self.level = min(score, self.level + self.rise * dt)
        else:
            self.level = max(score, self.level - self.fall * dt)
        self.level = _clamp01(self.level)
        return self.level


def ring_from_level(level: float, current: int, ring_up: list, ring_down: list) -> int:
    """The ring the reservoir level asks for, remembering the current ring.

    Going up needs level at or above ring_up for the next ring; coming down
    happens only when level falls below ring_down for the current one. The
    gap between the two lists is the hysteresis that stops flicker.
    """
    ring = current
    while ring < len(ring_up) and level >= ring_up[ring]:
        ring += 1
    while ring > 0 and level < ring_down[ring - 1]:
        ring -= 1
    return ring


class CrowdState:
    """Feed it every people message; it returns a Contract 2 message about once
    a second and None in between. All smoothing happens at the incoming rate."""

    def __init__(self, cfg: dict):
        self.cfg = cfg["cohesion"]
        self.actions_cfg = cfg["actions"]
        self.reservoir = Reservoir(self.cfg["rise_rate_per_s"], self.cfg["fall_rate_per_s"])
        self.attention = AttentionMemory(self.cfg["attention_window_s"])
        self.n_eff = 0.0
        self.smooth = 0.0
        self.ring = 0
        self._t_prev: float | None = None
        self._t_emit: float | None = None
        self._rates = {a: {"current": 0.0, "baseline": 0.0}
                       for a in self.actions_cfg["enabled"]}

    def update(self, msg: dict, labels: dict[int, str]) -> dict | None:
        c = self.cfg
        t, people = msg["t"], msg["people"]
        n = len(people)
        dt = 0.0 if self._t_prev is None else max(0.0, min(t - self._t_prev, 1.0))
        self._t_prev = t

        # Effective occupancy: the headcount smoothed so one person stepping
        # through the door does not flip the room in one frame.
        self.n_eff += _alpha(dt, c["occupancy_window_s"]) * (n - self.n_eff)

        if n == 0:
            signals = {"clustering": 0.0, "synchrony": 0.0, "stillness": 0.0,
                       "attention": 0.0, "coordination": 0.0, "mood_agreement": None}
            relational = 0.0
        else:
            stillness = stillness_score(people, c["still_speed_mps"])
            synchrony = synchrony_score(people, c["still_speed_mps"])
            attention = self.attention.update(people, t, c["still_speed_mps"], c["inattentive_actions"],
                                              self.actions_cfg["count_min"])
            held = attention if c["coordination_from"] == "attention" else stillness
            signals = {
                "clustering": clustering_score(people, msg["floor"]["w"], msg["floor"]["h"],
                                               c["clustering_zero_at_ratio"]),
                "synchrony": synchrony, "stillness": stillness, "attention": attention,
                "coordination": coordination_score(held, stillness, synchrony),
                "mood_agreement": mood_agreement(people, labels), "spare1": 1.0, "spare2": 1.0,
            }
            # For one person clustering is n/a, so this is their coordination alone (Sam, 28 Nov 2026).
            relational = relational_cohesion(signals, c["signals"])

        proxy = proxy_score(people, c)
        w = interp_by_n(self.n_eff, c["blend_weight_by_n"])
        # In the blend, relational evidence needs two people.
        raw = (1.0 - w) * proxy + w * (relational if n >= 2 else 0.0)
        # The ceiling that keeps the top ring collective: 0.72 for one or two, none from four up.
        raw = min(raw, interp_by_n(self.n_eff, c["score_ceiling_by_n"]))

        self.smooth += _alpha(dt, c["smooth_window_s"]) * (raw - self.smooth)
        level = self.reservoir.step(self.smooth, dt)
        ring = ring_from_level(level, self.ring, c["ring_up"], c["ring_down"])
        # A bored room may not climb past bored_ring_cap (Sam, 27 Nov 2026); a ring already higher is held, not dropped.
        bored = n > 0 and sum(1 for m in labels.values() if m == "bored") >= c["bored_cap_share"] * n
        self.ring = min(ring, max(self.ring, c["bored_ring_cap"])) if bored else ring
        self._update_action_rates(people, dt)

        if self._t_emit is not None and t - self._t_emit < c["crowd_interval_s"]:
            return None
        self._t_emit = t
        return self._message(t, n, signals, relational, raw, people, labels)

    def _update_action_rates(self, people: list[dict], dt: float) -> None:
        """Track each action's frequency per person: a short average (the
        current rate) and a long one (the baseline it is judged against)."""
        ac = self.actions_cfg
        n = len(people)
        for action, r in self._rates.items():
            doing = sum(1 for p in people if p["actions"].get(action, 0.0) >= ac["count_min"])
            inst = doing / n if n else 0.0
            r["current"] += _alpha(dt, ac["rate_window_s"]) * (inst - r["current"])
            r["baseline"] += _alpha(dt, ac["baseline_window_s"]) * (inst - r["baseline"])

    def _message(self, t: float, n: int, signals: dict, relational: float,
                 raw: float, people: list[dict], labels: dict[int, str]) -> dict:
        moods = {"happy": 0, "sad": 0, "bored": 0, "annoyed": 0}
        for label in labels.values():
            if label in moods:
                moods[label] += 1
        ac = self.actions_cfg
        counts = {a: sum(1 for p in people if p["actions"].get(a, 0.0) >= ac["count_min"])
                  for a in ac["enabled"]}
        counts["sitting"] = sum(1 for p in people if p["posture"] == "sitting")
        rates = {}
        for action, r in self._rates.items():
            # The floor under the baseline stops a first action in a quiet room
            # reading as an infinite spike.
            rates[action] = round(r["current"] / max(r["baseline"], ac["baseline_floor"]), 2)
        return {
            "stream": "crowd", "t": round(t, 3), "n": n,
            "n_smooth": round(self.n_eff, 2),
            "clustering": _round(signals["clustering"]),
            "synchrony": _round(signals["synchrony"]),
            "mood_agreement": _round(signals["mood_agreement"]),
            "social_synchrony": _round(social_synchrony(signals["synchrony"], signals["mood_agreement"])),
            "stillness": round(signals["stillness"], 3),
            "attention": round(signals["attention"], 3),
            "coordination": round(signals["coordination"], 3),
            "cohesion_relational": round(relational, 3),
            "cohesion_raw": round(raw, 3),
            "cohesion_smooth": round(self.smooth, 3),
            "accumulator": round(self.reservoir.level, 3),
            "ring_target": self.ring,
            "moods": moods, "actions": counts, "action_rates": rates,
        }
