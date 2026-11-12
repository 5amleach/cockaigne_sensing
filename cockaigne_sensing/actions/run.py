"""Run the actions module over a recording of people messages and its video.

Usage:
    python -m cockaigne_sensing.actions.run people.jsonl --video cam1=clip.mkv
                                            --out people_actions.jsonl
                                            [--model fake] [--config config/sensing.yaml]

Reads Contract 1 messages, cuts each person's crop from the matching moment
of the video, asks the model, and writes the messages back with the action
scores and the sense's health filled in. Time is read from the recording,
so the pace of the questions is what it would be live, however fast or slow
this machine is. --model fake needs no graphics card and answers "none".
"""
from __future__ import annotations

import argparse
import logging

import cv2

from ..bus import Recorder, replay
from ..capture import Closeups
from ..config import load
from .model import make_model
from .worker import ActionsWorker


class FileClock:
    """Time as the recording tells it. Waiting moves it forward at once."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("people")
    ap.add_argument("--video", action="append", default=[], metavar="CAMERA=FILE",
                    help="the clip this camera's boxes came from; repeat for each camera")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", help="override config actions.model")
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load(args.config)["actions"]
    if args.model:
        cfg["model"] = args.model
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    clock = FileClock()
    videos = dict(entry.split("=", 1) for entry in args.video)
    captures = {name: cv2.VideoCapture(path) for name, path in videos.items()}

    def frame_at_clock(name: str):
        """The frame of this camera's clip at the recording's current time."""
        cap = captures[name]
        cap.set(cv2.CAP_PROP_POS_MSEC, clock.now * 1000.0)
        ok, frame = cap.read()
        return frame if ok else None

    closeups = Closeups([{"name": n, "file": p} for n, p in videos.items()], cfg, frame_at_clock)
    worker = ActionsWorker(cfg, closeups, make_model(cfg), logging.getLogger("actions"),
                           clock=clock, sleep=clock.sleep)
    rec = Recorder(args.out)
    n = 0
    seen: dict[str, int] = {}
    for msg in replay(args.people, stream="people"):
        worker.offer(msg)
        if msg["t"] >= clock.now:   # a round's waiting may have run ahead of the recording
            clock.now = msg["t"]
            worker.step()
        worker.fill(msg)
        rec.write(msg)
        n += 1
        for p in msg["people"]:
            for action, score in p["actions"].items():
                if score >= cfg["count_min"]:
                    seen[action] = seen.get(action, 0) + 1
    rec.close()
    for cap in captures.values():
        cap.release()
    print(f"{n} people messages, {worker.asked} questions asked -> {args.out}")
    print("person-moments counted as doing each action:", seen or "none")


if __name__ == "__main__":
    main()
