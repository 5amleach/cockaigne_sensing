"""Run detection and tracking over a video file and report.

Usage:
    python -m cockaigne_sensing.tools.bench_detect CLIP [--out DIR] [--fps 5]
                                                   [--model yolo11s.pt] [--imgsz 1280]
                                                   [--device auto] [--snap 10]

Prints one line per second: how many people were found and their track ids.
Saves an annotated frame every --snap seconds to DIR so a person can look.
Writes every Contract 0 message to DIR/tracks.jsonl for the floor module to
replay. Ends with a summary of how many distinct ids appeared and how long
each lived, which is the quickest measure of tracking quality: ideally one
id per real person, each living the whole time that person is in view.
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from pathlib import Path

import cv2

from ..bus import Recorder
from ..capture import FrameSource
from ..config import load
from ..detect import PersonTracker, tracks_message


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--out", default="bench/out")
    ap.add_argument("--fps", type=float, default=5.0, help="frames per second to analyse")
    ap.add_argument("--model", help="override config detector.model")
    ap.add_argument("--imgsz", type=int, help="override config detector.imgsz")
    ap.add_argument("--device", help="override config detector.device (auto, cpu, 0)")
    ap.add_argument("--snap", type=int, default=10, help="save an annotated frame every N seconds")
    ap.add_argument("--camera", default="cam1")
    args = ap.parse_args()

    cfg = load()["detector"]
    model = args.model or cfg["model"]
    imgsz = args.imgsz or cfg["imgsz"]
    device = args.device or cfg["device"]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    src = FrameSource(args.clip, name=args.camera)
    src.every_nth = max(1, round(src.fps / args.fps))  # the file's own rate decides the stride
    tracker = PersonTracker(model, imgsz, cfg["conf"], cfg["tracker"], device, cfg["min_track_age_s"])
    rec = Recorder(out / "tracks.jsonl")

    life: dict[int, list[float]] = defaultdict(list)
    last_printed = -1
    last_snap = -args.snap
    n_frames = 0
    t_start = time.time()
    for t, frame in src.frames():
        tracks = tracker.update(frame, t)
        rec.write(tracks_message(t, args.camera, src.width, src.height, tracks))
        n_frames += 1
        for tr in tracks:
            life[tr.id].append(t)
        sec = int(t)
        if sec != last_printed:
            ids = sorted(tr.id for tr in tracks)
            confs = [round(tr.conf, 2) for tr in tracks]
            print(f"t={t:6.1f}s  people={len(tracks)}  ids={ids}  conf={confs}")
            last_printed = sec
        if t - last_snap >= args.snap:
            ann = frame.copy()
            for tr in tracks:
                x1, y1, x2, y2 = (int(v) for v in tr.box)
                cv2.rectangle(ann, (x1, y1), (x2, y2), (255, 128, 0), 3)
                cv2.putText(ann, f"{tr.id} {tr.conf:.2f}", (x1, max(0, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 128, 0), 2)
            h = 720
            ann = cv2.resize(ann, (int(ann.shape[1] * h / ann.shape[0]), h))
            cv2.imwrite(str(out / f"snap_{sec:04d}s.jpg"), ann)
            last_snap = t
    rec.close()
    src.close()

    elapsed = time.time() - t_start
    print(f"\n{n_frames} frames in {elapsed:.0f}s ({elapsed / max(n_frames, 1):.2f}s per frame, "
          f"model={model}, imgsz={imgsz}, device={device})")
    print(f"distinct track ids: {len(life)}")
    for tid, ts in sorted(life.items()):
        print(f"  id {tid:3d}: {ts[0]:6.1f}s to {ts[-1]:6.1f}s  ({len(ts)} frames)")
    print(f"\nmessages written to {out / 'tracks.jsonl'}; snapshots in {out}")


if __name__ == "__main__":
    main()
