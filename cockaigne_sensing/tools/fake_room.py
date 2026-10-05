"""A made-up room: scripted people messages for building without a camera.

Writes Contract 1 people messages at ten a second, exactly as the floor
module would emit them, so features, the bus, the controller and the data
wall can all be fed a believable room at a desk.

Scenarios:
  lone     one viewer enters, wanders with pauses, then settles on the
           viewing spot and stays (180 s)
  group    six people arrive, gather in a ring near the viewing spot, stand
           together, then scatter and leave (120 s)
  sitting  one person walks in, stops, and sits down (60 s)
  leaving  three people stand near the spot, then leave one by one and the
           room stays empty (90 s)
  day      all four, one after another (490 s)

People walk along straight lines between waypoints, so the emitted velocity
is exactly the slope of the path, as a downstream consumer expects. A little
seeded jitter is added to positions so nothing is unnaturally exact. The door
is assumed to be in the corner at the closed end of the U until the real
floor plan says otherwise.

Usage:
    python -m cockaigne_sensing.tools.fake_room --scenario lone --out fake_people.jsonl
"""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, replace

from ..bus import Recorder
from ..config import load

DOOR = (0.6, 7.1)
SPOT = (3.05, 3.5)


@dataclass
class Actor:
    """One scripted person: where they are at any time, and what they do."""
    pid: int
    waypoints: list            # (t, x, y); straight lines between; holds still outside them
    enters: float              # present from this time...
    leaves: float = math.inf   # ...until this one
    sits_at: float | None = None
    box_h: float = 600.0       # their standing rectangle height in pixels

    def state(self, t: float) -> tuple[float, float, float, float]:
        """Position and velocity at time t: (x, y, vx, vy)."""
        wp = self.waypoints
        if t <= wp[0][0]:
            return wp[0][1], wp[0][2], 0.0, 0.0
        for (t0, x0, y0), (t1, x1, y1) in zip(wp, wp[1:]):
            if t <= t1:
                f = (t - t0) / (t1 - t0)
                vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
                return x0 + f * (x1 - x0), y0 + f * (y1 - y0), vx, vy
        return wp[-1][1], wp[-1][2], 0.0, 0.0


def shifted(actor: Actor, by_s: float) -> Actor:
    """The same actor, with everything moved later by by_s seconds."""
    return replace(actor,
                   waypoints=[(t + by_s, x, y) for t, x, y in actor.waypoints],
                   enters=actor.enters + by_s,
                   leaves=actor.leaves + by_s,
                   sits_at=None if actor.sits_at is None else actor.sits_at + by_s)


def lone() -> tuple[float, list[Actor]]:
    """A viewer wanders with pauses, then settles on the viewing spot."""
    a = Actor(1, enters=5.0, waypoints=[
        (5, *DOOR), (9, 1.4, 5.0), (21, 1.4, 5.0), (28, 4.8, 5.6), (43, 4.8, 5.6),
        (52, 4.4, 1.6), (64, 4.4, 1.6), (72, 2.0, 2.4), (82, 2.0, 2.4),
        (88, *SPOT), (180, *SPOT)])
    return 180.0, [a]


def group() -> tuple[float, list[Actor]]:
    """Six people gather in a ring near the viewing spot, then scatter and leave."""
    corners = [(0.5, 0.8), (5.6, 0.8), (0.5, 6.6), (5.6, 6.6), (1.0, 3.5), (5.1, 3.5)]
    actors = []
    for i in range(6):
        angle = 2 * math.pi * i / 6
        ring = (SPOT[0] + 0.9 * math.cos(angle), SPOT[1] + 0.9 * math.sin(angle))
        enters = 2.0 + 3.0 * i
        actors.append(Actor(i + 1, enters=enters, leaves=103.0 + 2.0 * i,
                            box_h=540 + 20 * i,
                            waypoints=[(enters, *DOOR), (enters + 14, *ring), (85, *ring),
                                       (95, *corners[i]), (103 + 2 * i, *DOOR)]))
    return 120.0, actors


def sitting() -> tuple[float, list[Actor]]:
    """One person walks in, stops, and sits down."""
    a = Actor(1, enters=3.0, sits_at=24.0,
              waypoints=[(3, *DOOR), (18, 4.6, 5.2), (60, 4.6, 5.2)])
    return 60.0, [a]


def leaving() -> tuple[float, list[Actor]]:
    """Three people stand near the spot, leave one by one; the room stays empty."""
    posts = [(2.4, 3.2), (3.7, 3.2), (3.05, 4.4)]
    actors = [Actor(i + 1, enters=0.0, leaves=33.0 + 10.0 * i, box_h=560 + 30 * i,
                    waypoints=[(0, *posts[i]), (25 + 10 * i, *posts[i]),
                               (33 + 10 * i, *DOOR)])
              for i in range(3)]
    return 90.0, actors


def day() -> tuple[float, list[Actor]]:
    """The four scenarios one after another with gaps, 490 seconds in all.

    Each scenario's actors leave when their scenario ends and carry ids from
    their own block of one hundred, so the combined day keeps the people
    contract: one id is always one person, and nobody lingers forever."""
    actors, at = [], 0.0
    for block, build in enumerate((lone, group, sitting, leaving)):
        duration, scene = build()
        for a in scene:
            moved = shifted(a, at)
            moved.pid = a.pid + 100 * block
            moved.leaves = min(moved.leaves, at + duration)
            actors.append(moved)
        at += duration + 10.0
    return at, actors


SCENARIOS = {"lone": lone, "group": group, "sitting": sitting,
             "leaving": leaving, "day": day}


def messages(duration: float, actors: list[Actor], floor_w: float, floor_l: float,
             dt: float = 0.1, seed: int = 0):
    """Yield Contract 1 messages for the scripted room, ten a second."""
    rng = random.Random(seed)
    for i in range(int(duration / dt) + 1):
        t = round(i * dt, 2)
        people = []
        for a in actors:
            if not (a.enters <= t < a.leaves):
                continue
            x, y, vx, vy = a.state(t)
            is_sitting = a.sits_at is not None and t >= a.sits_at
            people.append({
                "id": a.pid,
                "x": round(x + rng.uniform(-0.02, 0.02), 2),
                "y": round(y + rng.uniform(-0.02, 0.02), 2),
                "vx": round(vx, 2), "vy": round(vy, 2),
                "age": round(t - a.enters, 1),
                "box_ratio": 0.9 if is_sitting else 0.4,
                "box_h": round(a.box_h * (0.62 if is_sitting else 1.0)),
                "posture": "standing",
                "actions": {"phone": 0.0, "drink": 0.0, "eat": 0.0},
                "arousal": 0.5, "valence": 0.0,
            })
        yield {"stream": "people", "t": t,
               "floor": {"w": floor_w, "h": floor_l}, "people": people}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--config")
    args = ap.parse_args()

    floor = load(args.config)["floor"]
    duration, actors = SCENARIOS[args.scenario]()
    rec = Recorder(args.out)
    n = 0
    for msg in messages(duration, actors, floor["width_m"], floor["length_m"],
                        seed=args.seed):
        rec.write(msg)
        n += 1
    rec.close()
    print(f"{args.scenario}: {n} people messages over {duration:.0f} s -> {args.out}")


if __name__ == "__main__":
    main()
