"""cockaigne_controller: decides the next clip and tells Resolume.

The second package in this repository, beside the sensing package
(DECISIONS.md, 2026-10-05). It reads the crowd state (Contract 2) from the
bus, decides where the wall goes next, fires the clip in Resolume over OSC,
and publishes its decision (Contract 3) back through the bus. The full
brief is BRIEF.md in this folder; every adjustable number is in
config/controller.yaml. The decision logic is loop.py; the live loop with
its fail-safes is run.py:
    python -m cockaigne_controller.run --layout pool.json
"""
from .clipmap import ClipMap, parse_clip_name
from .clock import ClipClock
from .loop import Controller

__all__ = ["ClipMap", "parse_clip_name", "ClipClock", "Controller"]
