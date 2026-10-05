"""Picture position to floor position, one homography per camera.

A homography is a 3x3 matrix that converts a point on one flat surface (the
camera's picture) to a point on another (the gallery floor). It is produced
once per camera by a calibration tool and saved as JSON in config/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def load_homography(path: str | Path) -> np.ndarray:
    data = json.loads(Path(path).read_text())
    return np.array(data["H"], dtype=float)


def feet_point(box) -> tuple[float, float]:
    """Bottom centre of a person's rectangle: roughly where their feet touch the floor."""
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, y2


def pixel_to_floor(H: np.ndarray, u: float, v: float) -> tuple[float, float]:
    """Convert one picture point to metres on the floor."""
    x, y, w = H @ np.array([u, v, 1.0])
    if abs(w) < 1e-9:
        return float("nan"), float("nan")
    return float(x / w), float(y / w)
