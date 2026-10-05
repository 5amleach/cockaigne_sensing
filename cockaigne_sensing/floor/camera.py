"""A simple model of where a camera is and which way it looks.

Used by the calibration tools to turn a few known floor points into a
homography (the 3x3 conversion between picture and floor). The floor module
itself only ever uses the homography, so this file is calibration-time only.

The model is a pinhole camera: a point on the floor projects to the picture
through a single centre, with no lens distortion. The Reolink's wide lens does
bend straight lines near the edges, so positions near the frame edge are
rougher than positions near the middle. Good enough until the cameras are
mounted for real and calibrated from floor markers.

Floor coordinates follow CONTRACTS.md: x along the data wall, y from the data
wall (0) toward the closed end of the U, z up.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Camera:
    x: float          # metres along the data wall
    y: float          # metres from the data wall
    height: float     # metres above the floor
    pitch_deg: float  # degrees looking down from horizontal
    yaw_deg: float    # degrees turned left (positive) from the base direction
    facing: str       # "into_u" (looking away from the data wall) or "to_data_wall"
    f_px: float       # focal length in pixels
    cx: float         # picture centre, x
    cy: float         # picture centre, y

    def rotation(self) -> np.ndarray:
        """Rows are the camera's right, down and forward axes in floor coordinates."""
        if self.facing == "into_u":
            forward = np.array([0.0, 1.0, 0.0])
            right = np.array([1.0, 0.0, 0.0])
        else:
            forward = np.array([0.0, -1.0, 0.0])
            right = np.array([-1.0, 0.0, 0.0])
        up = np.array([0.0, 0.0, 1.0])
        # Yaw: turn left by yaw_deg about the vertical axis.
        yaw = math.radians(self.yaw_deg)
        forward, right = (math.cos(yaw) * forward - math.sin(yaw) * right,
                          math.sin(yaw) * forward + math.cos(yaw) * right)
        # Pitch: tip the forward axis down by pitch_deg.
        pitch = math.radians(self.pitch_deg)
        fwd_p = math.cos(pitch) * forward - math.sin(pitch) * up
        up_p = math.sin(pitch) * forward + math.cos(pitch) * up
        return np.vstack([right, -up_p, fwd_p])

    def project(self, floor_xy: np.ndarray) -> np.ndarray:
        """Floor points (n, 2) in metres to picture points (n, 2) in pixels."""
        pts = np.column_stack([floor_xy[:, 0], floor_xy[:, 1], np.zeros(len(floor_xy))])
        rel = pts - np.array([self.x, self.y, self.height])
        cam = rel @ self.rotation().T
        z = np.where(np.abs(cam[:, 2]) < 1e-6, 1e-6, cam[:, 2])
        u = self.cx + self.f_px * cam[:, 0] / z
        v = self.cy + self.f_px * cam[:, 1] / z
        return np.column_stack([u, v])


def focal_from_hfov(image_width: int, hfov_deg: float) -> float:
    """Focal length in pixels from the lens's horizontal field of view."""
    return (image_width / 2) / math.tan(math.radians(hfov_deg) / 2)


def homography_from_camera(cam: Camera, floor_w: float, floor_l: float) -> np.ndarray:
    """The 3x3 matrix that maps picture pixels to floor metres for this camera.

    Built by projecting four floor points that lie in front of the camera
    (the two far corners and two points 1.5 m ahead of it) and asking OpenCV
    for the perspective transform that undoes the projection. A homography is
    one conversion for the whole floor, so which four points define it does
    not matter as long as they are in view and not in a line.
    """
    import cv2
    if cam.facing == "into_u":
        near_y, far_y = cam.y + 1.5, floor_l
    else:
        near_y, far_y = cam.y - 1.5, 0.0
    pts = np.array([[0, near_y], [floor_w, near_y], [floor_w, far_y], [0, far_y]], dtype=np.float32)
    px = cam.project(pts).astype(np.float32)
    return cv2.getPerspectiveTransform(px, pts)
