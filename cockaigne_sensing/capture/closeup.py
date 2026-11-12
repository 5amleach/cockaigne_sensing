"""Close-up crops of people, cut from one full-size picture.

Detection runs on the small sub-stream, where a person is too small to show
what they are holding. This file fetches one full-size still picture from a
camera and cuts out the rectangles it is asked for. The live chain receives
only those rectangles: the whole picture stays inside capture, which is the
privacy rule in ARCHITECTURE.md enforced by where the code sits.

A Reolink camera serves a still over HTTP (cmd=Snap), once HTTP is switched
on in the camera's web interface. A camera entry that names a video file
has no such address, so the newest frame of the file stands in.
"""
from __future__ import annotations

import cv2
import numpy as np
import requests

from .source import camera_password


def fetch_still(cam: dict, timeout_s: float) -> np.ndarray | None:
    """One full-size picture from a Reolink camera, or None when the camera
    does not answer with a picture. The password comes from this machine
    (see camera_password) and is never logged: a failure reports nothing but None, because the
    library's own error text would repeat the address with the password in it."""
    try:
        reply = requests.get(
            f"http://{cam['ip']}/cgi-bin/api.cgi",
            params={"cmd": "Snap", "channel": 0, "rs": "cockaigne",
                    "user": cam.get("user", "admin"),
                    "password": camera_password()},
            timeout=timeout_s)
        reply.raise_for_status()
    except requests.RequestException:
        return None
    # A refused request comes back as a short piece of text, not a picture;
    # decoding that gives None, which is the right answer.
    return cv2.imdecode(np.frombuffer(reply.content, np.uint8), cv2.IMREAD_COLOR)


def cut(frame: np.ndarray, boxes: list, box_size: tuple[int, int],
        pad: float, max_px: int) -> list[np.ndarray | None]:
    """Cut each box out of the frame, one crop per box, in order.

    The boxes are [x1, y1, x2, y2] in the pixels of a picture box_size wide
    and high (the detector's small frame). Each is scaled to this frame,
    widened by pad on every side to forgive the moment between the two
    pictures, clipped to the frame, and shrunk so its longer side is at most
    max_px. A box that falls outside the frame gives None.
    """
    fh, fw = frame.shape[:2]
    sx, sy = fw / box_size[0], fh / box_size[1]
    crops: list[np.ndarray | None] = []
    for x1, y1, x2, y2 in boxes:
        dx, dy = pad * (x2 - x1), pad * (y2 - y1)
        left, right = int(max(0, (x1 - dx) * sx)), int(min(fw, (x2 + dx) * sx))
        top, bottom = int(max(0, (y1 - dy) * sy)), int(min(fh, (y2 + dy) * sy))
        if right - left < 2 or bottom - top < 2:
            crops.append(None)
            continue
        crop = frame[top:bottom, left:right]
        longest = max(crop.shape[:2])
        if longest > max_px:
            scale = max_px / longest
            crop = cv2.resize(crop, (max(1, round(crop.shape[1] * scale)),
                                     max(1, round(crop.shape[0] * scale))),
                              interpolation=cv2.INTER_AREA)
        crops.append(crop.copy())   # a copy, so the whole frame can be let go
    return crops


class Closeups:
    """Hands out crops for one camera at a time. This is all the actions
    module ever sees of a picture."""

    def __init__(self, cameras: list[dict], actions_cfg: dict, newest_frame=None):
        """newest_frame(name) returns the newest frame of a camera entry that
        is a video file, or None. Real cameras are asked for a still."""
        self.cameras = {cam["name"]: cam for cam in cameras}
        self.pad = actions_cfg["crop_pad"]
        self.max_px = actions_cfg["crop_max_px"]
        self.timeout_s = actions_cfg["still_timeout_s"]
        self.newest_frame = newest_frame or (lambda name: None)

    def crops(self, camera: str, get_boxes) -> list[np.ndarray | None] | None:
        """Crops from this camera for the boxes get_boxes() returns, or None
        when no picture could be had. get_boxes is called after the picture
        arrives and returns (boxes, (width, height)), so the boxes are as
        fresh as the picture."""
        cam = self.cameras.get(camera)
        if cam is None:
            return None
        frame = (self.newest_frame(camera) if cam.get("file")
                 else fetch_still(cam, self.timeout_s))
        if frame is None:
            return None
        boxes, box_size = get_boxes()
        return cut(frame, boxes, box_size, self.pad, self.max_px)
