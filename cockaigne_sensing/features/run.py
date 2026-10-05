"""Run the features module over a recording of people messages.

Usage:
    python -m cockaigne_sensing.features.run people.jsonl --out out.jsonl [--config config/sensing.yaml]

Reads Contract 1 messages, fills in posture, arousal and valence, and writes
the messages back out together with a Contract 2 crowd message about once a
second. The output file is what the bus would publish, so it can feed the
controller or the data wall directly.
"""
from __future__ import annotations

import argparse

from ..bus import Recorder, replay
from ..config import load
from . import FeatureStage


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("people")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    args = ap.parse_args()

    stage = FeatureStage(load(args.config))
    rec = Recorder(args.out)
    n_people = n_crowd = 0
    max_ring = 0
    last = None
    for msg in replay(args.people, stream="people"):
        people_msg, crowd = stage.push(msg)
        rec.write(people_msg)
        n_people += 1
        if crowd:
            rec.write(crowd)
            n_crowd += 1
            max_ring = max(max_ring, crowd["ring_target"])
            last = crowd
    rec.close()
    print(f"{n_people} people messages, {n_crowd} crowd messages -> {args.out}")
    if last:
        print(f"highest ring {max_ring}; at the end: n={last['n']}, "
              f"cohesion_smooth={last['cohesion_smooth']}, "
              f"accumulator={last['accumulator']}, ring={last['ring_target']}, "
              f"moods={last['moods']}")


if __name__ == "__main__":
    main()
