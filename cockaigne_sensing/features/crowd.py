"""Crowd cohesion, the reservoir and the ring, from the people list alone.

This file is the arithmetic behind Contract 2. It has no models and no camera
knowledge; its only input is the people list (Contract 1).

Three relational signals say how much the crowd is acting as a group:
clustering (gathered more than chance would place them), synchrony (moving the
same way) and stillness (stopped at the same time). Their geometric mean is
relational cohesion C, so a low score on any one signal pulls the whole down.

When there is nobody to be relational with, a proxy score A stands in, built
from each person's time in the room, their stillness, and their distance from
the viewing spot. A is capped at proxy_ceiling so the top ring always needs
relational evidence.

The two are blended, never switched: S = (1 - w) A + w C, where the weight w
follows the smoothed headcount. This is the settled single-viewer behaviour
(DECISIONS.md, 2026-09-19).

The smoothed score feeds a reservoir, a level that rises slowly while the
score sits above it and drains more slowly while the score sits below. The
reservoir level picks the ring, with a higher bar for going up than for coming
down so the wall does not flicker at a boundary. The reservoir is never reset.
"""
from __future__ import annotations

import math


def _speed(p: dict) -> float:
    return math.hypot(p["vx"], p["vy"])


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _alpha(dt: float, time_constant_s: float) -> float:
    """The step fraction for an exponentially weighted average."""
    if dt <= 0 or time_constant_s <= 0:
        return 0.0
    return 1.0 - math.exp(-dt / time_constant_s)


def clustering_score(people: list[dict], floor_w: float, floor_l: float,
                     zero_at_ratio: float) -> float:
    """How gathered the crowd is, 0 to 1, judged against chance.

    The mean distance from each person to their nearest neighbour is compared
    with what random placement would give for the same headcount on this floor
    (about 0.5 * sqrt(area / n)). Random spacing scores 0.5; spacing at
    zero_at_ratio times random scores 0; a tight huddle scores near 1. One
    person scores 1.0, because a set of one contains no disagreement.
    """
    n = len(people)
    if n < 2:
        return 1.0
    nearest = []
    for i, p in enumerate(people):
        d2 = min((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2
                 for j, q in enumerate(people) if j != i)
        nearest.append(math.sqrt(d2))
    expected = 0.5 * math.sqrt(floor_w * floor_l / n)
    ratio = (sum(nearest) / n) / expected
    return _clamp01(1.0 - ratio / zero_at_ratio)


def synchrony_score(people: list[dict], still_speed: float) -> float:
    """How aligned the movement is, 0 to 1.

    The length of the sum of the movers' velocity vectors, divided by the sum
    of their speeds: 1 when everyone walks the same way, near 0 when movement
    cancels out. People standing still are left out. Fewer than two movers
    means there is no disagreement to measure, so the score is 1.0.
    """
    movers = [p for p in people if _speed(p) >= still_speed]
    if len(movers) < 2:
        return 1.0
    sx = sum(p["vx"] for p in movers)
    sy = sum(p["vy"] for p in movers)
    total = sum(_speed(p) for p in movers)
    return _clamp01(math.hypot(sx, sy) / total)


def stillness_score(people: list[dict], still_speed: float) -> float:
    """The fraction of people standing still."""
    if not people:
        return 0.0
    return sum(1 for p in people if _speed(p) < still_speed) / len(people)


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
    per-person scores are averaged over everyone present and capped at
    proxy_ceiling, which is what keeps Ring 4 out of reach without
    relational evidence.
    """
    if not people:
        return 0.0
    per_person = []
    for p in people:
        dwell = _clamp01(p["age"] / cohesion_cfg["proxy_dwell_full_s"])
        still = 1.0 if _speed(p) < cohesion_cfg["still_speed_mps"] else 0.0
        position = spot_score(p["x"], p["y"], cohesion_cfg)
        per_person.append((dwell + still + position) / 3.0)
    return min(sum(per_person) / len(per_person), cohesion_cfg["proxy_ceiling"])


def blend_weight(n_eff: float, table: list[list[float]]) -> float:
    """The weight on relational cohesion, read from [[headcount, weight], ...].

    Piecewise linear between the table's points; flat beyond its ends.
    """
    if n_eff <= table[0][0]:
        return table[0][1]
    for (n0, w0), (n1, w1) in zip(table, table[1:]):
        if n_eff <= n1:
            return w0 + (w1 - w0) * (n_eff - n0) / (n1 - n0)
    return table[-1][1]


def relational_cohesion(signals: dict[str, float], enabled: list[str]) -> float:
    """Geometric mean of the enabled signals. Any zero pulls the whole to zero."""
    values = [signals[name] for name in enabled]
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
            signals = {"clustering": 0.0, "synchrony": 0.0, "stillness": 0.0}
            relational = 0.0
        else:
            signals = {
                "clustering": clustering_score(people, msg["floor"]["w"], msg["floor"]["h"],
                                               c["clustering_zero_at_ratio"]),
                "synchrony": synchrony_score(people, c["still_speed_mps"]),
                "stillness": stillness_score(people, c["still_speed_mps"]),
                "spare1": 1.0, "spare2": 1.0,
            }
            # A set of one contains no disagreement; the blend weight keeps it
            # from counting. The data wall shows the 100% and Population 1
            # side by side on purpose.
            relational = 1.0 if n == 1 else relational_cohesion(signals, c["signals"])

        proxy = proxy_score(people, c)
        w = blend_weight(self.n_eff, c["blend_weight_by_n"])
        raw = (1.0 - w) * proxy + w * relational

        self.smooth += _alpha(dt, c["smooth_window_s"]) * (raw - self.smooth)
        level = self.reservoir.step(self.smooth, dt)
        self.ring = ring_from_level(level, self.ring, c["ring_up"], c["ring_down"])
        self._update_action_rates(people, dt)

        if self._t_emit is not None and t - self._t_emit < c["crowd_interval_s"]:
            return None
        self._t_emit = t
        return self._message(t, n, signals, raw, people, labels)

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

    def _message(self, t: float, n: int, signals: dict, raw: float,
                 people: list[dict], labels: dict[int, str]) -> dict:
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
            "clustering": round(signals["clustering"], 3),
            "synchrony": round(signals["synchrony"], 3),
            "stillness": round(signals["stillness"], 3),
            "cohesion_raw": round(raw, 3),
            "cohesion_smooth": round(self.smooth, 3),
            "accumulator": round(self.reservoir.level, 3),
            "ring_target": self.ring,
            "moods": moods, "actions": counts, "action_rates": rates,
        }
