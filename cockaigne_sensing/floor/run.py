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
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from ..bus import Recorder, replay
from ..config import load
from .homography import feet_point, load_homography, pixel_to_floor
from .tracker import FloorTracker, Sighting, people_message


class FloorStage:
    """Holds one tracker and one homography per camera. Feed it Contract 0, get Contract 1."""

    def __init__(self, cfg: dict):
        ft = cfg["floor_tracker"]
        self.W = cfg["floor"]["width_m"]
        self.L = cfg["floor"]["length_m"]
        self.margin = ft["margin_m"]
        self.bucket_s = ft["bucket_s"]
        self.warn_every_s = ft["warn_every_s"]
        self.tracker = FloorTracker(ft["merge_distance_m"], ft["drop_after_s"],
                                    ft["velocity_window_s"], gate_m=ft["gate_m"],
                                    coast_s=ft["coast_s"], bounds=(self.W, self.L),
                                    same_camera_iou=ft["same_camera_iou"])
        self.log = logging.getLogger("cockaigne_sensing.floor")
        self.H: dict[str, tuple[np.ndarray, tuple[int, int] | None]] = {}
        self.polygon: dict[str, np.ndarray | None] = {}
        self._warned: dict[str, float] = {}
        for cam in cfg["cameras"]:
            path = Path(cam.get("homography", ""))
            if path.is_file():
                self.H[cam["name"]] = load_homography(path)
                poly = cam.get("floor_polygon") or []
                self.polygon[cam["name"]] = np.array(poly, dtype=np.float32) if poly else None
        self._bucket_t = None
        self._bucket: list[Sighting] = []

    def _warn(self, camera: str, text: str) -> None:
        """A camera problem, said at most once every warn_every_s per camera."""
        now = time.monotonic()
        if now - self._warned.get(camera, float("-inf")) >= self.warn_every_s:
            self._warned[camera] = now
            self.log.warning(text)

    def sightings(self, msg: dict) -> list[Sighting]:
        """Floor sightings from one camera message, with off-floor points dropped.

        Pixel coordinates are scaled when the message's frame size differs
        from the size the camera was calibrated at; a different aspect ratio
        means the wrong calibration, so that camera is skipped with a warning.
        """
        camera = msg["camera"]
        if camera not in self.H:
            self._warn(camera, f"{camera}: no calibration loaded; its tracks are ignored")
            return []
        H, size = self.H[camera]
        scale = 1.0
        if size and (msg["w"], msg["h"]) != size:
            if abs(size[0] / size[1] - msg["w"] / msg["h"]) > 0.01:
                self._warn(camera, f"{camera}: frame {msg['w']}x{msg['h']} does not match "
                                   f"the calibration's {size[0]}x{size[1]} shape; skipped")
                return []
            scale = size[0] / msg["w"]
        poly = self.polygon.get(camera)
        out = []
        for tr in msg["tracks"]:
            u, v = feet_point(tr["box"])
            if poly is not None and cv2.pointPolygonTest(poly, (float(u), float(v)), False) < 0:
                continue
            x, y = pixel_to_floor(H, u * scale, v * scale)
            if not (-self.margin <= x <= self.W + self.margin and -self.margin <= y <= self.L + self.margin):
                continue  # feet off the floor: wall imagery, or a lens-edge error
            x1, y1, x2, y2 = tr["box"]
            out.append(Sighting(x, y, (x2 - x1) / max(1.0, y2 - y1), y2 - y1, tr["conf"],
                                camera=camera, det_id=tr["id"], box=tuple(tr["box"])))
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
        n_people += len(out["people"])
        ids.update(p["id"] for p in out["people"])
    rec.close()
    print(f"{n_msgs} people messages, {len(ids)} distinct ids, "
          f"{n_people / max(n_msgs, 1):.2f} people per message on average -> {args.out}")


if __name__ == "__main__":
    main()
