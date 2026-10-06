"""Run the live sensing chain with one command: cameras in, bus out.

Usage:
    python -m cockaigne_sensing.run [--config config/sensing.yaml] [--record DIR]

One process. Each configured camera gets its own thread (cameras.py), which
reads frames and detects people at up to launcher.detect_fps. The main loop
merges the cameras on the floor, scores the crowd, and publishes the people
list and the crowd state on the bus at ws://127.0.0.1:8765. A camera entry
may give `file:` instead of `ip:`, so recorded clips stand in for cameras
at a desk, looped.

Health is part of the output: every people message carries a "cameras"
field saying whether each camera is alive and how old its last frame is; a
camera lost or returning is logged and written to the ledger. The floor
flushes on a timer, so an empty room still reports itself ten times a second.

Start-up refuses to run, naming the camera, when a configured camera has no
calibration file; a stream whose shape disagrees with its calibration is
disabled with an error when it opens. --record DIR writes every tracks,
people and crowd message to DIR; without it no recording is written. The
ledger and sensing.log are always kept: they are the operating record, and
they contain no pictures.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import queue
import time
from pathlib import Path

from .bus import Ledger, LedgerEvents, Publisher, Recorder
from .cameras import CameraWorker
from .config import load
from .features import FeatureStage
from .floor.homography import load_homography
from .floor.run import FloorStage


def make_logger(path: str) -> logging.Logger:
    log = logging.getLogger("cockaigne_sensing")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(path)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def calibration_sizes(cfg: dict) -> dict[str, tuple[int, int] | None]:
    """Each camera's calibrated frame size. Refuses the launch, naming the
    camera, when a calibration file is missing: a camera without one would
    silently see an empty room."""
    sizes, problems = {}, []
    for cam in cfg["cameras"]:
        path = Path(cam.get("homography", ""))
        if not path.is_file():
            problems.append(f"camera {cam['name']}: no calibration file at '{path}'")
            continue
        _, sizes[cam["name"]] = load_homography(path)
    if problems:
        for p in problems:
            print(f"refusing to start: {p}")
        raise SystemExit(f"{len(problems)} camera(s) without calibration")
    return sizes


class Launcher:
    """The whole sensing chain in one object, so tests can hold it."""

    def __init__(self, cfg: dict, record_dir: str | None = None, tracker_factory=None):
        self.cfg = cfg
        self.record_dir = record_dir
        self.tracker_factory = tracker_factory
        self.port: int | None = None
        self.publisher: Publisher | None = None

    async def run(self) -> None:
        cfg = self.cfg
        log = make_logger(cfg["launcher"]["log_path"])
        sizes = calibration_sizes(cfg)
        floor = FloorStage(cfg)
        features = FeatureStage(cfg)
        self.publisher = Publisher(cfg["bus"]["host"], cfg["bus"]["port"])
        self.port = await self.publisher.start()
        ledger = Ledger(cfg["bus"]["ledger_path"])
        events = LedgerEvents(ledger, cfg["actions"]["count_min"])
        ledger.append("day_start", note="sensing chain up")
        recorders = {}
        if self.record_dir:
            out = Path(self.record_dir)
            recorders = {s: Recorder(out / f"{s}.jsonl")
                         for s in ("tracks", "people", "crowd")}

        tracks_queue: queue.Queue = queue.Queue()
        workers = [CameraWorker(cam, cfg, tracks_queue, log,
                                tracker_factory=self.tracker_factory,
                                calibration_size=sizes.get(cam["name"]))
                   for cam in cfg["cameras"]]
        for w in workers:
            w.start()
        alive = {w.cam_name: True for w in workers}
        stale_s = cfg["launcher"]["camera_stale_s"]
        log.info(f"sensing on ws://{self.publisher.host}:{self.port}, "
                 f"{len(workers)} camera(s)")

        async def put(msg: dict) -> None:
            if msg["stream"] in recorders:
                recorders[msg["stream"]].write(msg)
            if msg["stream"] in ("people", "crowd"):
                events.observe(msg)
                await self.publisher.publish(msg)

        last_people = 0.0
        try:
            while True:
                now = time.monotonic()
                for w in workers:
                    ok = w.age(now) <= stale_s and not w.disabled
                    if ok != alive[w.cam_name]:
                        alive[w.cam_name] = ok
                        if ok:
                            log.info(f"camera {w.cam_name} is back")
                            ledger.append("camera_back", camera=w.cam_name)
                        else:
                            log.warning(f"camera {w.cam_name} lost "
                                        f"(no frame for {stale_s} s)")
                            ledger.append("camera_lost", camera=w.cam_name)
                emitted = []
                while True:
                    try:
                        msg = tracks_queue.get_nowait()
                    except queue.Empty:
                        break
                    if not alive.get(msg["camera"], False):
                        continue   # a lost camera's leftover tracks are dropped
                    await put(msg)
                    out = floor.push(msg)
                    if out:
                        emitted.append(out)
                if not emitted and now - last_people >= floor.bucket_s:
                    out = floor.tick(now)
                    if out:
                        emitted.append(out)
                for people_msg in emitted:
                    last_people = now
                    people_msg["cameras"] = {
                        w.cam_name: {"alive": alive[w.cam_name],
                                     "age_s": round(min(w.age(now), 999.0), 1)}
                        for w in workers}
                    people_msg, crowd = features.push(people_msg)
                    await put(people_msg)
                    if crowd:
                        await put(crowd)
                await asyncio.sleep(floor.bucket_s / 2)
        finally:
            for w in workers:
                w.stop()
            for rec in recorders.values():
                rec.close()
            ledger.close()
            await self.publisher.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--record", help="write tracks, people and crowd recordings to this "
                                     "directory (development only; never in the gallery)")
    args = ap.parse_args()
    try:
        asyncio.run(Launcher(load(args.config), record_dir=args.record).run())
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
