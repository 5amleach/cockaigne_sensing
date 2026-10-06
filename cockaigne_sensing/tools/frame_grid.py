"""Save one frame with a labelled pixel grid, for reading positions by eye.

Calibration needs a few pixel positions read off a picture — above all the
floor line at the middle of the far wall. This saves one frame from a video
file or a live camera with a line every 200 pixels and the pixel coordinates
written at the edges, so those positions can be read like a map reference.

Usage:
    python -m cockaigne_sensing.tools.frame_grid SOURCE [--at 5.0] [--out grid.png] [--step 200]

SOURCE is a video file path or an RTSP address (any password in it is hidden
in everything this tool prints). --at picks the moment in a file, in seconds;
a live camera gives its next frame and --at is ignored.
"""
from __future__ import annotations

import argparse

import cv2

from ..capture.source import public_uri


def grid_frame(frame, step: int = 200):
    """The frame with its grid and labels drawn on."""
    h, w = frame.shape[:2]
    colour, shadow = (0, 255, 255), (0, 0, 0)
    for x in range(step, w, step):
        cv2.line(frame, (x, 0), (x, h), colour, 1)
        for y_text in (20, h - 10):
            cv2.putText(frame, str(x), (x + 4, y_text),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, shadow, 3)
            cv2.putText(frame, str(x), (x + 4, y_text),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 1)
    for y in range(step, h, step):
        cv2.line(frame, (0, y), (w, y), colour, 1)
        for x_text in (6, w - 70):
            cv2.putText(frame, str(y), (x_text, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, shadow, 3)
            cv2.putText(frame, str(y), (x_text, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 1)
    return frame


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="a video file or an rtsp:// address")
    ap.add_argument("--at", type=float, default=0.0, help="seconds into a file")
    ap.add_argument("--out", default="grid.png")
    ap.add_argument("--step", type=int, default=200, help="pixels between grid lines")
    args = ap.parse_args()

    shown = public_uri(args.source)
    live = args.source.lower().startswith("rtsp://")
    cap = cv2.VideoCapture(args.source, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise SystemExit(f"could not open {shown}")
    if not live and args.at > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, args.at * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"no frame at {args.at:.1f} s in {shown}")
    frame = grid_frame(frame, args.step)
    if not cv2.imwrite(args.out, frame):
        raise SystemExit(f"could not write {args.out}")
    h, w = frame.shape[:2]
    where = "next live frame" if live else f"{args.at:.1f} s"
    print(f"{shown} ({w}x{h}), {where} -> {args.out}; grid every {args.step} px")


if __name__ == "__main__":
    main()
