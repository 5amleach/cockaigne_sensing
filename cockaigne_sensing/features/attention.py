"""Attention: how much of the last minute people gave the wall their attention.

A person counts as attentive when they stand still and are not doing any of
the actions named in cohesion.inattentive_actions: the phone, and
back_turned, which the action sense reports when actions.facing is on and a
person's back is turned to cam1 and so to the main screen. Before 28 Nov 2026
attention was simply the share of people standing still, so someone still
with their back to the wall, or still and scrolling a phone, counted as
attentive (Sam, 28 Nov 2026: they should not).

Only movement and the action sense's answers are used. Nothing here looks at
a face or tells one person from another.
"""
from __future__ import annotations

import math
from collections import deque


def is_attentive(p: dict, still_speed: float, inattentive_actions: list[str],
                 count_min: float) -> bool:
    """True when this person is still and doing none of the inattentive actions.
    An action counts once its score reaches count_min, the same bar the crowd
    counts use."""
    if math.hypot(p["vx"], p["vy"]) >= still_speed:
        return False
    return all(p["actions"].get(a, 0.0) < count_min for a in inattentive_actions)


class AttentionMemory:
    """Attention over time (Sam, 28 Nov 2026), so one glance at a phone does not
    flip the figure from 100 to 0. Each person's attention is the share of
    their sightings in the last window_s seconds in which they were attentive;
    the room's attention is the average over the people present. A glance of
    a few seconds costs a few percent; a whole window on the phone reaches 0.

    Between the action sense's looks a person keeps their last phone and
    facing scores, so a reading holds until the next one. A new tracking id
    has no past: it starts from what that person is doing now. Someone who
    leaves is forgotten.
    """

    def __init__(self, window_s: float):
        self.window_s = window_s
        self._seen: dict[int, deque] = {}   # person id -> (t, attentive), oldest first

    def update(self, people: list[dict], t: float, still_speed: float,
               inattentive_actions: list[str], count_min: float) -> float:
        """Record this moment for everyone present; return the room's attention, 0 when empty."""
        present = {p["id"] for p in people}
        for gone in [i for i in self._seen if i not in present]:
            del self._seen[gone]
        shares = []
        for p in people:
            seen = self._seen.setdefault(p["id"], deque())
            seen.append((t, is_attentive(p, still_speed, inattentive_actions, count_min)))
            while seen[0][0] < t - self.window_s:
                seen.popleft()
            shares.append(sum(a for _, a in seen) / len(seen))
        return sum(shares) / len(shares) if shares else 0.0
