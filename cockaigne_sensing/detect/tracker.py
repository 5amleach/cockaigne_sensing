"""Person detection plus tracking, using Ultralytics YOLO with ByteTrack.

YOLO looks at one frame and returns a rectangle around each person it finds.
ByteTrack compares those rectangles with the ones from the previous frame and
assigns each person a number that stays the same while they remain in view.
Both come from the Ultralytics library, so this file is mostly bookkeeping.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

PERSON_CLASS = 0  # index of "person" in the COCO classes YOLO was trained on


@dataclass
class Track:
    id: int
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    conf: float
    first_seen: float  # t when this id first appeared


class PersonTracker:
    """Wraps one YOLO model and one ByteTrack state, for one camera.

    Use one PersonTracker per camera. The tracker's memory of who is who is
    per camera, and mixing cameras would confuse it.
    """

    def __init__(self, model: str = "yolo11s.pt", imgsz: int = 1280, conf: float = 0.25,
                 tracker: str = "bytetrack.yaml", device: str = "auto",
                 min_track_age_s: float = 1.0):
        self.model = YOLO(model)
        self.imgsz = imgsz
        self.conf = conf
        self.tracker = tracker
        self.device = None if device == "auto" else device
        self.min_track_age_s = min_track_age_s
        self._first_seen: dict[int, float] = {}
        self._last_seen: dict[int, float] = {}

    def update(self, frame: np.ndarray, t: float) -> list[Track]:
        """Run detection on one frame and return the tracks that are old enough to trust."""
        result = self.model.track(
            frame, persist=True, imgsz=self.imgsz, conf=self.conf, classes=[PERSON_CLASS],
            tracker=self.tracker, device=self.device, verbose=False,
        )[0]
        boxes = result.boxes
        tracks: list[Track] = []
        if boxes is not None and boxes.id is not None:
            for tid, xyxy, c in zip(boxes.id.tolist(), boxes.xyxy.tolist(), boxes.conf.tolist()):
                tid = int(tid)
                first = self._first_seen.setdefault(tid, t)
                self._last_seen[tid] = t
                if t - first < self.min_track_age_s:
                    continue  # too new; a one-frame flicker never gets this far
                tracks.append(Track(tid, tuple(xyxy), float(c), first))
        # Forget ids unseen for a while, so the dictionaries do not grow forever.
        # ByteTrack may hide an id for a few frames and bring it back, so the
        # age clock is kept for a few seconds rather than reset at once.
        for tid, last in list(self._last_seen.items()):
            if t - last > 5.0:
                del self._last_seen[tid]
                self._first_seen.pop(tid, None)
        return tracks


def tracks_message(t: float, camera: str, w: int, h: int, tracks: list[Track]) -> dict:
    """Shape a list of tracks into a Contract 0 message."""
    return {
        "stream": "tracks", "t": round(t, 3), "camera": camera, "w": w, "h": h,
        "tracks": [
            {"id": tr.id, "box": [round(v, 1) for v in tr.box], "conf": round(tr.conf, 3)}
            for tr in tracks
        ],
    }
