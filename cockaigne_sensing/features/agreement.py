"""Social synchrony: how far people agree, in where they walk and in mood.

Sam, 28 Nov 2026: synchrony should also say whether people's moods are the
same. Each person already carries one mood label (happy, sad, bored or
annoyed, from person.py), so mood agreement is the share of people who share
the most common mood. Social synchrony, the figure on the data wall, is the
average of walking agreement (synchrony_score in crowd.py) and mood
agreement, taking whichever of the two can be measured.

A figure that cannot be measured is None, which the data wall shows as n/a:
mood agreement needs two people with a mood, walking agreement two walkers.
"""
from __future__ import annotations

from collections import Counter


def mood_agreement(people: list[dict], labels: dict[int, str]) -> float | None:
    """The share of people with a mood who share the most common one."""
    moods = [labels[p["id"]] for p in people if labels.get(p["id"])]
    if len(moods) < 2:
        return None
    return Counter(moods).most_common(1)[0][1] / len(moods)


def social_synchrony(walking: float | None, mood: float | None) -> float | None:
    """The average of the two agreements that could be measured, or None."""
    parts = [v for v in (walking, mood) if v is not None]
    return sum(parts) / len(parts) if parts else None
