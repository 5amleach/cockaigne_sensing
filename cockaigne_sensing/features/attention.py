"""Attention: the share of people giving the wall their attention.

A person counts as attentive when they stand still and are not doing any of
the actions named in cohesion.inattentive_actions (the phone, from 28 Nov
2026). Before that date attention was simply the share of people standing
still, so someone still with their back to the wall, or still and scrolling a
phone, counted as attentive (Sam, 28 Nov 2026: they should not).

Only movement and the action sense's answers are used. Nothing here looks at
a face or tells one person from another.
"""
from __future__ import annotations

import math


def is_attentive(p: dict, still_speed: float, inattentive_actions: list[str],
                 count_min: float) -> bool:
    """True when this person is still and doing none of the inattentive actions.
    An action counts once its score reaches count_min, the same bar the crowd
    counts use."""
    if math.hypot(p["vx"], p["vy"]) >= still_speed:
        return False
    return all(p["actions"].get(a, 0.0) < count_min for a in inattentive_actions)


def attention_score(people: list[dict], still_speed: float,
                    inattentive_actions: list[str], count_min: float) -> float:
    """The fraction of people who are attentive; 0 for an empty room."""
    if not people:
        return 0.0
    attentive = sum(1 for p in people
                    if is_attentive(p, still_speed, inattentive_actions, count_min))
    return attentive / len(people)
