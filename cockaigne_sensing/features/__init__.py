"""features: crowd cohesion and per-person mood, from the people list alone.

Built 5 October 2026. Pure arithmetic on Contract 1 messages; no models, no
pictures, nothing that needs a GPU.

Crowd, about once a second (crowd.py): clustering, synchrony and stillness
combine by geometric mean into relational cohesion C. A proxy score A (time
in the room, stillness, distance from the viewing spot) stands in when the
room is nearly empty. The two blend by a weight that follows the smoothed
headcount: S = (1 - w) A + w C, with C counting as zero below two people,
and the blend held under a headcount-following ceiling (0.72 for one or two
people) so the top ring stays collective. There is no solo mode; the blend
is the single-viewer behaviour settled in DECISIONS.md (2026-09-19, guards
2026-10-05). The smoothed score feeds a reservoir that rises slowly, falls
more slowly, and is never reset; the reservoir level picks the ring, with a
higher bar going up than coming down. Output is Contract 2.

Per person, on every message (person.py): posture from the rectangle's shape
and whether the person has stopped; arousal from speed; valence from slump
against the person's own standing height and from movement roughness; a mood
label (happy, sad, bored, annoyed) held for a dwell time so it cannot
flicker. These overwrite the placeholders the floor module emits in
Contract 1. The thresholds are starting guesses in config/sensing.yaml,
to be tuned on site.

Run it from a recording:
    python -m cockaigne_sensing.features.run people.jsonl --out out.jsonl
"""
from .crowd import CrowdState
from .person import PersonScorer


class FeatureStage:
    """Feed it people messages; get each back augmented, plus a crowd message
    about once a second (None in between)."""

    def __init__(self, cfg: dict):
        self.people = PersonScorer(cfg)
        self.crowd = CrowdState(cfg)

    def push(self, msg: dict) -> tuple[dict, dict | None]:
        labels = self.people.update(msg)
        return msg, self.crowd.update(msg, labels)


__all__ = ["FeatureStage", "CrowdState", "PersonScorer"]
