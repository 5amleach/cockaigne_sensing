"""The lens bend and the camera's place in the room, for calibrations that record them.

The Reolink lens is wide and bends straight lines, most of all near the edges
of the picture. A homography (homography.py) cannot follow a bend, so a
calibration can also record the bend and where the camera hangs. With those,
the floor stage straightens each feet point before the homography, and can
ask whether a rectangle is the right size to be a person standing there.

A calibration file that lacks them works as before. Fields, when present:
  "lens": {"f": focal length in pixels, "k1": how strongly the lens bends}
  "pose": [x, y, height in metres, yaw, pitch down, roll in degrees]
Both are in the pixels of the calibration's "image_size". Yaw 0 looks along
the floor's y axis (away from the data wall); 180 looks back toward it.
The homography in such a file maps straightened pixels to metres.

The bend is one number, k1: a point at distance r from the picture centre
(measured in focal lengths) is moved outward by the factor 1 + k1 * r * r.
"""
from __future__ import annotations

import math

import numpy as np


def straighten(u: float, v: float, lens: dict, size: tuple[int, int]) -> tuple[float, float]:
    """Where a picture point would be if the lens did not bend."""
    f, k1 = lens["f"], lens["k1"]
    cx, cy = size[0] / 2, size[1] / 2
    xn, yn = (u - cx) / f, (v - cy) / f
    s = 1 + k1 * (xn * xn + yn * yn)
    return cx + f * xn * s, cy + f * yn * s


def _axes(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Rows are the camera's right, down and forward directions in floor coordinates."""
    y, p, r = (math.radians(a) for a in (yaw, pitch, roll))
    fwd = np.array([math.sin(y), math.cos(y), 0.0])
    right = np.array([math.cos(y), -math.sin(y), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    fwd_p = math.cos(p) * fwd - math.sin(p) * up
    down_p = -(math.sin(p) * fwd + math.cos(p) * up)
    return np.vstack([math.cos(r) * right + math.sin(r) * down_p,
                      -math.sin(r) * right + math.cos(r) * down_p, fwd_p])


def picture_height(pose: list, lens: dict, size: tuple[int, int],
                   x: float, y: float, z: float) -> float | None:
    """The picture row (with the lens bend) of a point z metres above floor
    point (x, y), or None when the point is behind the camera."""
    cam = (np.array([x, y, z]) - np.array(pose[:3])) @ _axes(*pose[3:6]).T
    if cam[2] <= 0.1:
        return None
    xu, yu = cam[0] / cam[2], cam[1] / cam[2]
    xd, yd = xu, yu
    for _ in range(8):   # undo the bend a step at a time; it settles quickly
        s = 1 + lens["k1"] * (xd * xd + yd * yd)
        xd, yd = xu / s, yu / s
    return size[1] / 2 + lens["f"] * yd


def fits_a_person(box, x: float, y: float, pose: list, lens: dict, size: tuple[int, int],
                  low_m: float, high_m: float, slack_px: float) -> bool:
    """True when the rectangle is as tall as a figure low_m to high_m tall
    standing at floor point (x, y) would look. Figures in the wall imagery
    are many times too tall for where their feet land; a crouching or
    seated visitor is shorter, which is why low_m is generous."""
    bottom = picture_height(pose, lens, size, x, y, 0.0)
    top_low = picture_height(pose, lens, size, x, y, low_m)
    top_high = picture_height(pose, lens, size, x, y, high_m)
    if bottom is None or top_low is None or top_high is None:
        return False
    height = box[3] - box[1]
    return (bottom - top_low) - slack_px <= height <= (bottom - top_high) + slack_px
