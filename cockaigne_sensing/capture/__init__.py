"""capture: opens a camera stream or a video file and hands out frames.

Everything downstream receives (timestamp, frame) pairs and does not know
whether they came from a live camera or a recording. That is what lets the
whole system be tested against a file.
"""
from .source import FrameSource, reolink_url

__all__ = ["FrameSource", "reolink_url"]
