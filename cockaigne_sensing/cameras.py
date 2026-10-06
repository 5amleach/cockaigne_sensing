"""One thread per camera: open, read, detect, and report health.

A CameraWorker owns one FrameSource and one PersonTracker. It reads frames
continuously, remembers when the last one arrived (the launcher reads that
as health), and runs detection on the newest frame at up to detect_fps,
putting each Contract 0 message on a queue for the floor stage.

A camera that fails to open is reported and retried every camera_retry_s
rather than stopping the show. A camera entry may name a video file instead
of an address; the file is read at its own frame rate, so it stands in for
a camera at a desk, and loops unless the entry says otherwise. Frames are
stamped with the machine clock either way, so four sources share one
timeline. A stream whose shape does not match its calibration is disabled
with an error naming the camera: the wrong calibration must not place
people on the wrong part of the floor.
"""
from __future__ import annotations

import os
import threading
import time

from .capture import FrameSource, reolink_url
from .detect import tracks_message


def camera_uri(cam: dict) -> tuple[str, bool]:
    """The source for one camera entry: (uri, is_file). An entry gives either
    `file:` (a recorded clip) or `ip:` (a Reolink camera; the password comes
    from the environment, never from the config file)."""
    if cam.get("file"):
        return str(cam["file"]), True
    password = os.environ.get("COCKAIGNE_RTSP_PASSWORD", "")
    return reolink_url(cam["ip"], cam.get("user", "admin"), password,
                       cam.get("stream", "sub")), False


class CameraWorker(threading.Thread):
    """Reads one camera forever; the launcher watches last_frame_at."""

    def __init__(self, cam: dict, cfg: dict, out_queue, log,
                 tracker_factory=None, calibration_size=None):
        super().__init__(name=f"camera-{cam['name']}", daemon=True)
        self.cam_name = cam["name"]
        self.uri, self.is_file = camera_uri(cam)
        self.loop_file = cam.get("loop", True)
        self.detect_period = 1.0 / cfg["launcher"]["detect_fps"]
        self.open_retry_s = cfg["launcher"]["camera_retry_s"]
        self.read_retry_s = cfg["capture"]["retry_s"]
        self.calibration_size = calibration_size
        self.queue = out_queue
        self.log = log
        det = cfg["detector"]
        self.tracker_factory = tracker_factory or (lambda: _real_tracker(det))
        self.tracker = None
        self.started_at = time.monotonic()
        self.last_frame_at: float | None = None
        self.disabled = False
        self._stop = threading.Event()

    def age(self, now: float) -> float:
        """Seconds since the last frame (or since launch, before the first)."""
        return now - (self.last_frame_at if self.last_frame_at is not None
                      else self.started_at)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                source = FrameSource(self.uri, self.cam_name, retry_s=self.read_retry_s)
            except RuntimeError as e:
                self.log.warning(f"{e}; retrying in {self.open_retry_s} s")
                self._stop.wait(self.open_retry_s)
                continue
            if not self._shape_matches(source):
                self.disabled = True
                source.close()
                return
            if self.tracker is None:
                self.tracker = self.tracker_factory()
            self._read(source)
            source.close()
            if self.is_file and not self.loop_file:
                self.log.info(f"camera {self.cam_name}: file ended")
                return
            # A looped file starts again; a live source only returns from
            # _read when the worker is stopping.

    def _shape_matches(self, source: FrameSource) -> bool:
        if not self.calibration_size:
            return True
        cw, ch = self.calibration_size
        if abs(cw / ch - source.width / source.height) > 0.01:
            self.log.error(f"camera {self.cam_name}: stream {source.width}x{source.height} "
                           f"does not match its calibration's {cw}x{ch} shape; "
                           "camera disabled until recalibrated")
            return False
        return True

    def _read(self, source: FrameSource) -> None:
        frame_dt = 1.0 / source.fps if self.is_file else 0.0
        next_frame = time.monotonic()
        last_detect = float("-inf")
        for _, frame in source.frames():
            if self._stop.is_set():
                return
            now = time.monotonic()
            self.last_frame_at = now
            if now - last_detect >= self.detect_period:
                tracks = self.tracker.update(frame, now)
                self.queue.put(tracks_message(now, self.cam_name,
                                              source.width, source.height, tracks))
                last_detect = now
            if frame_dt:   # pace a file to its own rate, like a real camera
                next_frame += frame_dt
                delay = next_frame - time.monotonic()
                if delay > 0:
                    self._stop.wait(delay)


def _real_tracker(det: dict):
    from .detect import PersonTracker
    return PersonTracker(det["model"], det["imgsz"], det["conf"], det["tracker"],
                         det["device"], det["min_track_age_s"], det["forget_after_s"])
