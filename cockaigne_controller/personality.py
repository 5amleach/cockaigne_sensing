"""Daily personality: the same machine with a different temperament each day.

A personality is four numbers (config/controller.yaml, personalities:):
prior strength (how many pseudo-observations the day starts with, so how
fast it commits), the Storm prior (risk appetite), the reward scaling, and
patience (when the reward window opens). At day start the bandit's beliefs
reset to the day's priors; the ledger is never reset.

The date picks the personality: the day of the year, modulo the number of
presets, indexes personality_order. The brief says "chosen by the date"
without giving the rule, so this one is an assumption, logged in
DECISIONS.md, and trivially replaced by a calendar in config if Sam wants
particular days.
"""
from __future__ import annotations

import datetime


def personality_for(date: datetime.date, cfg: dict) -> tuple[str, dict]:
    order = cfg["personality_order"]
    name = order[date.timetuple().tm_yday % len(order)]
    return name, cfg["personalities"][name]


def priors(params: dict, arm_names: list[str]) -> dict[str, tuple[float, float]]:
    """Beta priors per arm: every arm starts at a mean of 0.5, Storm at the
    day's storm_prior, all with prior_strength pseudo-observations."""
    strength = params["prior_strength"]
    out = {}
    for arm in arm_names:
        mean = params["storm_prior"] if arm == "storm" else 0.5
        out[arm] = (strength * mean, strength * (1.0 - mean))
    return out
