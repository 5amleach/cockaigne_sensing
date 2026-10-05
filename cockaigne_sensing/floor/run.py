"""Run the floor module over a recording of camera tracks.

Usage:
    python -m cockaigne_sensing.floor.run tracks.jsonl --out people.jsonl [--config config/sensing.yaml]

Reads Contract 0 messages (one per camera per frame), converts every
rectangle's feet point to metres with that camera's homography, drops any
point that is not on the floor, merges the cameras, tracks people, and writes
Contract 1 messages. Messages from different cameras within bucket_s of each
other count as the same instant.

Each camera named in a message must have a homography file listed under
cameras: in the config. A camera without one is skipped with a warning.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from ..bus import Recorder, replay
from ..config import load
from .homography import feet_point, load_homography, pixel_to_floor
from .tracker import FloorTracker, Sighting, people_message


class FloorStage:
    """Holds one tracker and one homography per camera. Feed it Contract 0, get Contract 1."""

    def __init__(self, cfg: dict, bucket_s: float = 0.1, margin_m: float = 0.3):
        self.W = cfg["floor"]["width_m"]
        self.L = cfg["floor"]["length_m"]
        self.margin = margin_m
        self.bucket_s = bucket_s
        ft = cfg["floor_tracker"]
        self.tracker = FloorTracker(ft["merge_distance_m"], ft["drop_after_s"], ft["velocity_window_s"])
        self.H: dict[str, np.ndarray] = {}
        self.polygon: dict[str, np.ndarray | None] = {}
        for cam in cfg["cameras"]:
            path = Path(cam.get("homography", ""))
            if path.is_file():
                self.H[cam["name"]] = load_homography(path)
                poly = cam.get("floor_polygon") or []
                self.polygon[cam["name"]] = np.array(poly, dtype=np.float32) if poly else None
        self._bucket_t = None
        self._bucket: list[Sighting] = []

    def sightings(self, msg: dict) -> list[Sighting]:
        """Floor sightings from one camera message, with off-floor points dropped."""
        H = self.H.get(msg["camera"])
        if H is None:
            return []
        poly = self.polygon.get(msg["camera"])
        out = []
        for tr in msg["tracks"]:
            u, v = feet_point(tr["box"])
            if poly is not None and cv2.pointPolygonTest(poly, (float(u), float(v)), False) < 0:
                continue
            x, y = pixel_to_floor(H, u, v)
            if not (-self.margin <= x <= self.W + self.margin and -self.margin <= y <= self.L + self.margin):
                continue  # feet off the floor: wall imagery, or a lens-edge error
            x1, y1, x2, y2 = tr["box"]
            out.append(Sighting(x, y, (x2 - x1) / max(1.0, y2 - y1), y2 - y1, tr["conf"]))
        return out

    def push(self, msg: dict) -> dict | None:
        """Add one camera message. Returns a people message when an instant is complete."""
        result = None
        if self._bucket_t is not None and msg["t"] - self._bucket_t > self.bucket_s:
            result = self.flush()
        if self._bucket_t is None:
            self._bucket_t = msg["t"]
        self._bucket.extend(self.sightings(msg))
        return result

    def flush(self) -> dict | None:
        if self._bucket_t is None:
            return None
        people = self.tracker.update(self._bucket_t, self._bucket)
        out = people_message(self._bucket_t, self.W, self.L, people)
        self._bucket_t, self._bucket = None, []
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tracks")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load(args.config)
    stage = FloorStage(cfg)
    missing = {c["name"] for c in cfg["cameras"]} - set(stage.H)
    if missing:
        print(f"warning: no homography for {sorted(missing)}; their tracks are ignored", file=sys.stderr)
    rec = Recorder(args.out)
    n_msgs = n_people = 0
    ids = set()
    for msg in replay(args.tracks, stream="tracks"):
        out = stage.push(msg)
        if out:
            rec.write(out)
            n_msgs += 1
            n_people += len(out["people"])
            ids.update(p["id"] for p in out["people"])
    out = stage.flush()
    if out:
        rec.write(out)
        n_msgs += 1
    rec.close()
    print(f"{n_msgs} people messages, {len(ids)} distinct ids, "
          f"{n_people / max(n_msgs, 1):.2f} people per message on average -> {args.out}")


if __name__ == "__main__":
    main()
