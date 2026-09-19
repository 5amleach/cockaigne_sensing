"""detect: finds people in a frame and follows them from frame to frame.

Input: a frame from capture. Output: a Contract 0 message, one per camera per
frame, listing rectangles with stable track ids. Pixel coordinates only. This
module knows nothing about the floor.
"""
from .tracker import PersonTracker, tracks_message

__all__ = ["PersonTracker", "tracks_message"]
