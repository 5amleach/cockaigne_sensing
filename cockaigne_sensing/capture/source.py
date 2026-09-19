"""One frame source, live or recorded.

A FrameSource wraps OpenCV's VideoCapture. Given an RTSP address it reads a
live camera. Given a file path it reads a recording. Either way, calling
frames() yields (t, frame) pairs where t is seconds and frame is a BGR image.

For a file, t is the frame's position in the file, so a replay is repeatable.
For a live camera, t is time.monotonic() at the moment the frame arrived.
"""
from __future__ import annotations

import os
import time
from typing import Iterator

import cv2
import numpy as np

# Ask OpenCV's FFmpeg backend to use TCP for RTSP. UDP drops packets on a
# busy switch and the picture tears. Must be set before VideoCapture opens.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


def reolink_url(ip: str, user: str, password: str, stream: str = "sub") -> str:
    """Build the RTSP address for a Reolink camera.

    The path names say h264 but the camera sends whatever it is set to
    (the bench camera sent H.265). The name still works.
    """
    path = "h264Preview_01_main" if stream == "main" else "h264Preview_01_sub"
    return f"rtsp://{user}:{password}@{ip}:554/{path}"


class FrameSource:
    """Yields frames from a camera or a file at a chosen rate."""

    def __init__(self, uri: str, name: str = "cam", every_nth: int = 1):
        """uri is an RTSP address or a file path.

        every_nth keeps one frame in every n. Detection does not need every
        frame; five a second is plenty for tracking people walking.
        """
        self.uri = uri
        self.name = name
        self.every_nth = max(1, int(every_nth))
        self.live = uri.lower().startswith("rtsp://")
        self.cap = cv2.VideoCapture(uri, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            raise RuntimeError(f"could not open {name}: {uri}")
        if self.live:
            # Keep the smallest buffer so a slow consumer sees fresh frames,
            # not a growing backlog.
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def frames(self) -> Iterator[tuple[float, np.ndarray]]:
        """Yield (t, frame) until the source ends or is closed."""
        index = 0
        while True:
            ok, frame = self.cap.read()
            if not ok:
                if self.live:
                    # A live stream that drops is reopened rather than ended.
                    time.sleep(0.5)
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
                    continue
                return
            if index % self.every_nth == 0:
                t = time.monotonic() if self.live else index / self.fps
                yield t, frame
            index += 1

    def close(self) -> None:
        self.cap.release()
