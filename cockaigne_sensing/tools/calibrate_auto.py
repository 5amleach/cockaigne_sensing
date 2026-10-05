"""Approximate camera calibration from the people in a recording.

For footage shot before any floor markers exist. The idea: a standing person
is about 1.7 m tall, so the height of their rectangle in the picture says how
far away they are, and where their feet sit in the picture says the same
thing in a different way. Many such observations pin down the camera's
height above the floor and how far it tips down. One more known point, the
place where the far wall meets the floor in the middle of the picture, fixes
the scale. From those the tool writes the homography the floor module needs.

Usage:
    python -m cockaigne_sensing.tools.calibrate_auto bench/fixtures/venue_A_tracks.jsonl \
        --camera cam1 --facing into_u --far-wall-centre 1875 1790 \
        [--cam-x 3.05] [--hfov 87] [--person-height 1.7] [--out config/homography_cam1.json]

--facing: "into_u" for a camera at the data-wall end looking into the U,
"to_data_wall" for a camera at the closed end looking back.
--far-wall-centre: pixel position of the floor line at the middle of the far
wall. Read it off a frame. --extra adds more known points, for example the
far corners of the floor: pixel u v, then metres x y.
--cam-x: where the camera sits along its wall, in metres. Defaults to the
middle of the floor, which is right when the far wall looks centred.

Accuracy: a quarter to half a metre near the middle of the picture, worse
at the edges where the wide lens bends straight lines. Good enough for
building and testing. Replace with tools.calibrate (four measured markers)
once cameras are mounted for real.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from ..bus import replay
from ..config import load
from ..floor.camera import Camera, focal_from_hfov, homography_from_camera


def collect_boxes(tracks_path, image_w, image_h, min_conf=0.6):
    """Feet pixel (u, v) and box height for confident, fully visible people."""
    obs = []
    for msg in replay(tracks_path, stream="tracks"):
        for tr in msg["tracks"]:
            x1, y1, x2, y2 = tr["box"]
            if tr["conf"] < min_conf:
                continue
            if y2 > image_h - 10 or y1 < 10:
                continue  # cut off by the frame edge: height is not the person's
            if x1 < 0.08 * image_w or x2 > 0.92 * image_w:
                continue  # near the edge, where the lens distorts most
            obs.append(((x1 + x2) / 2, y2, y2 - y1))
    return np.array(obs)


def predicted_box_height(cam: Camera, u, v_feet, person_h):
    """Pixel height a person of person_h would have with feet at (u, v_feet)."""
    f, cy = cam.f_px, cam.cy
    pitch = math.radians(cam.pitch_deg)
    down = pitch + np.arctan((v_feet - cy) / f)          # ray angle below horizontal
    down = np.clip(down, 1e-3, None)
    d = cam.height / np.tan(down)                          # horizontal distance to feet
    head_down = np.arctan((cam.height - person_h) / d)     # ray angle to the head
    v_head = cy + f * np.tan(head_down - pitch)
    return v_feet - v_head


def fit(obs, known_px, known_floor, image_size, facing, floor_w, floor_l, hfov, person_h, cam_x):
    """known_px / known_floor: a few picture points whose floor positions are known."""
    w, h = image_size
    f = focal_from_hfov(w, hfov)
    known_px = np.asarray(known_px, dtype=float)
    known_floor = np.asarray(known_floor, dtype=float)

    def make(p):
        height, pitch, setback = p
        cam_y = setback if facing == "into_u" else floor_l - setback
        return Camera(cam_x, cam_y, height, pitch, 0.0, facing, f, w / 2, h / 2)

    def residual(p):
        cam = make(p)
        r_box = (predicted_box_height(cam, obs[:, 0], obs[:, 1], person_h) - obs[:, 2]) / 100.0
        r_known = ((cam.project(known_floor) - known_px) / 20.0).ravel()  # few points, weighted up
        return np.concatenate([r_box / math.sqrt(len(obs)), r_known])

    res = least_squares(residual, x0=[2.0, 10.0, 0.5],
                        bounds=([0.8, -10.0, -1.0], [6.0, 70.0, 4.0]))
    cam = make(res.x)
    box_err = predicted_box_height(cam, obs[:, 0], obs[:, 1], person_h) - obs[:, 2]
    known_err = np.linalg.norm(cam.project(known_floor) - known_px, axis=1)
    return cam, float(np.median(np.abs(box_err))), [float(e) for e in known_err]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tracks", help="a tracks.jsonl recording from this camera")
    ap.add_argument("--camera", required=True)
    ap.add_argument("--facing", choices=["into_u", "to_data_wall"], required=True)
    ap.add_argument("--far-wall-centre", nargs=2, type=float, required=True, metavar=("U", "V"))
    ap.add_argument("--extra", nargs=4, type=float, action="append", default=[], metavar=("U", "V", "X", "Y"),
                    help="another picture point with a known floor position, e.g. a far corner")
    ap.add_argument("--cam-x", type=float)
    ap.add_argument("--hfov", type=float, default=87.0)
    ap.add_argument("--person-height", type=float, default=1.7)
    ap.add_argument("--out")
    args = ap.parse_args()

    cfg = load()["floor"]
    W, L = cfg["width_m"], cfg["length_m"]
    first = next(replay(args.tracks, stream="tracks"))
    image_size = (first["w"], first["h"])
    obs = collect_boxes(args.tracks, *image_size)
    if len(obs) < 20:
        raise SystemExit(f"only {len(obs)} usable boxes; need a recording with people walking about")
    cam_x = args.cam_x if args.cam_x is not None else W / 2
    far_y = L if args.facing == "into_u" else 0.0
    known_px = [args.far_wall_centre] + [e[:2] for e in args.extra]
    known_floor = [[W / 2, far_y]] + [e[2:] for e in args.extra]
    cam, box_err, known_err = fit(obs, known_px, known_floor, image_size, args.facing,
                                  W, L, args.hfov, args.person_height, cam_x)
    H = homography_from_camera(cam, W, L)
    out = Path(args.out or f"config/homography_{args.camera}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "camera": args.camera, "method": "auto_from_people", "image_size": list(image_size),
        "H": H.tolist(),
        "fit": {"x_m": round(cam.x, 2), "y_m": round(cam.y, 2), "height_m": round(cam.height, 2),
                "pitch_deg": round(cam.pitch_deg, 1), "facing": args.facing, "hfov_deg": args.hfov,
                "boxes_used": int(len(obs)), "median_box_error_px": round(box_err, 1),
                "known_point_errors_px": [round(e, 1) for e in known_err]},
    }, indent=1))
    print(f"{args.camera}: at x={cam.x:.2f} m, y={cam.y:.2f} m, height {cam.height:.2f} m, "
          f"pitch {cam.pitch_deg:.1f} deg down. {len(obs)} boxes, median box error {box_err:.0f} px, "
          f"known point errors {[round(e) for e in known_err]} px")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
