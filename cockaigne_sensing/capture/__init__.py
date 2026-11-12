"""capture: opens a camera stream or a video file and hands out frames.

Everything downstream receives (timestamp, frame) pairs and does not know
whether they came from a live camera or a recording. That is what lets the
whole system be tested against a file. closeup.py adds the one other thing
capture gives out: small crops of single people, cut from a full-size still.
"""
from .closeup import Closeups, cut, fetch_still
from .source import FrameSource, camera_password, reolink_url

__all__ = ["FrameSource", "reolink_url", "camera_password", "Closeups", "cut", "fetch_still"]
