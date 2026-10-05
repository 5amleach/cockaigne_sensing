"""Follows people on the floor plan and gives each one a room-wide id.

Input, each step: a list of floor sightings for one instant, already merged
across cameras. Output: the people list for Contract 1.

The method is the plain one. Each known person is predicted forward along
their velocity. Sightings are matched to predictions nearest first, within a
gate. Matched people keep their id and are updated. An unmatched person is still
reported at their predicted position for up to coast_s (their age keeps
counting), then goes quiet, and is dropped if unseen for drop_after_s.
Leftover sightings become new people. Velocity is the smoothed change in position over about a
second. No Kalman filter: the floor is flat and people are slow.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class Sighting:
    x: float
    y: float
    box_ratio: float   # width / height of the rectangle in the best camera view
    box_h: float       # that rectangle's height in pixels
    conf: float


@dataclass
class Person:
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0
    box_ratio: float = 0.5
    box_h: float = 0.0
    history: list = field(default_factory=list)  # (t, x, y), recent only


class FloorTracker:
    def __init__(self, merge_distance_m=0.5, drop_after_s=3.0, velocity_window_s=1.0,
                 gate_m=1.2, coast_s=1.0, bounds=None):
        self.merge_distance_m = merge_distance_m
        self.drop_after_s = drop_after_s
        self.velocity_window_s = velocity_window_s
        self.gate_m = gate_m
        self.coast_s = coast_s
        self.bounds = bounds  # (floor width, floor length); coasted positions stay inside it
        self.people: dict[int, Person] = {}
        self._next_id = 1

    def merge(self, sightings: list[Sighting]) -> list[Sighting]:
        """Collapse sightings of the same person seen by more than one camera.

        Closest-to-camera first (tallest rectangle), absorbing anything within
        merge_distance_m. The absorbed sightings' positions are averaged.
        """
        pending = sorted(sightings, key=lambda s: -s.box_h)
        merged: list[Sighting] = []
        while pending:
            lead = pending.pop(0)
            group = [lead]
            rest = []
            for s in pending:
                if (s.x - lead.x) ** 2 + (s.y - lead.y) ** 2 <= self.merge_distance_m ** 2:
                    group.append(s)
                else:
                    rest.append(s)
            pending = rest
            n = len(group)
            merged.append(Sighting(sum(g.x for g in group) / n, sum(g.y for g in group) / n,
                                   lead.box_ratio, lead.box_h, max(g.conf for g in group)))
        return merged

    def update(self, t: float, sightings: list[Sighting]) -> list[Person]:
        sightings = self.merge(sightings)
        # Predict where each known person should be now.
        predicted = {}
        for pid, p in self.people.items():
            dt = max(0.0, t - p.last_seen)
            predicted[pid] = (p.x + p.vx * dt, p.y + p.vy * dt)
        # Match nearest pairs first, within the gate.
        pairs = []
        for i, s in enumerate(sightings):
            for pid, (px, py) in predicted.items():
                d2 = (s.x - px) ** 2 + (s.y - py) ** 2
                if d2 <= self.gate_m ** 2:
                    pairs.append((d2, i, pid))
        pairs.sort()
        used_s, used_p = set(), set()
        for _, i, pid in pairs:
            if i in used_s or pid in used_p:
                continue
            used_s.add(i)
            used_p.add(pid)
            self._observe(self.people[pid], t, sightings[i])
        # New people for the leftovers.
        for i, s in enumerate(sightings):
            if i not in used_s:
                p = Person(self._next_id, s.x, s.y, first_seen=t, last_seen=t,
                           box_ratio=s.box_ratio, box_h=s.box_h, history=[(t, s.x, s.y)])
                self._next_id += 1
                self.people[p.id] = p
        # Drop anyone unseen too long.
        for pid in [pid for pid, p in self.people.items() if t - p.last_seen > self.drop_after_s]:
            del self.people[pid]
        # A person missed this step is still reported at their predicted
        # position for up to coast_s, so a moment of occlusion does not make
        # them vanish from the people list. Their age keeps counting.
        out = []
        for p in self.people.values():
            unseen = t - p.last_seen
            if unseen < 1e-6:
                out.append(p)
            elif unseen <= self.coast_s:
                out.append(self._coasted(p, t))
        return out

    def _coasted(self, p: Person, t: float) -> Person:
        """A copy of a missed person, carried forward along their velocity.

        The copy is for this step's output only; the stored person stays
        anchored where they were last seen. Nobody is off the floor, so the
        prediction is held inside the floor rectangle when its size is known.
        """
        dt = t - p.last_seen
        x, y = p.x + p.vx * dt, p.y + p.vy * dt
        if self.bounds:
            x = min(max(x, 0.0), self.bounds[0])
            y = min(max(y, 0.0), self.bounds[1])
        return replace(p, x=x, y=y)

    def _observe(self, p: Person, t: float, s: Sighting) -> None:
        p.x, p.y = s.x, s.y
        p.box_ratio, p.box_h = s.box_ratio, s.box_h
        p.last_seen = t
        p.history.append((t, s.x, s.y))
        p.history = [h for h in p.history if t - h[0] <= self.velocity_window_s]
        t0, x0, y0 = p.history[0]
        if t - t0 > 0.2:
            vx, vy = (s.x - x0) / (t - t0), (s.y - y0) / (t - t0)
            p.vx, p.vy = 0.5 * p.vx + 0.5 * vx, 0.5 * p.vy + 0.5 * vy  # light smoothing


def people_message(t: float, floor_w: float, floor_l: float, people: list[Person]) -> dict:
    """Shape the tracker's people into a Contract 1 message.

    Posture, actions, arousal and valence are placeholders here; features
    and actions fill them in downstream.
    """
    return {
        "stream": "people", "t": round(t, 3),
        "floor": {"w": floor_w, "h": floor_l},
        "people": [
            {"id": p.id, "x": round(p.x, 2), "y": round(p.y, 2),
             "vx": round(p.vx, 2), "vy": round(p.vy, 2),
             "age": round(t - p.first_seen, 1),
             "box_ratio": round(p.box_ratio, 2), "box_h": round(p.box_h),
             "posture": "standing",
             "actions": {"phone": 0.0, "drink": 0.0, "eat": 0.0},
             "arousal": 0.5, "valence": 0.0}
            for p in sorted(people, key=lambda p: p.id)
        ],
    }
