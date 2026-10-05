"""Draw a people-list recording as paths on the floor plan, for checking by eye.

Usage:
    python -m cockaigne_sensing.tools.plan_view people.jsonl --out plan.png [--title "..."]
                                                [--camera X Y] [--min-steps 10]

One line per person id, in a fixed set of colours, labelled with the id at the
path's start. The data wall is at the bottom (y = 0), the closed end of the U
at the top. Short-lived ids (fewer than --min-steps positions) are drawn
faint and unlabelled so flickers do not clutter the picture.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..bus import replay

# Fixed categorical colours, assigned in order and never cycled past eight.
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#8a63d2", "#6b6b6b"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("people")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--camera", nargs=2, type=float, metavar=("X", "Y"), help="mark the camera position")
    ap.add_argument("--min-steps", type=int, default=10)
    args = ap.parse_args()

    paths = defaultdict(list)
    floor = None
    for msg in replay(args.people, stream="people"):
        floor = msg["floor"]
        for p in msg["people"]:
            paths[p["id"]].append((p["x"], p["y"]))
    W, L = floor["w"], floor["h"]

    fig, ax = plt.subplots(figsize=(6, 6 * L / W + 0.8), dpi=150)
    ax.set_facecolor("#f6f5f1")
    ax.add_patch(plt.Rectangle((0, 0), W, L, fill=False, lw=1.5, ec="#333"))
    ax.text(W / 2, -0.25, "data wall", ha="center", va="top", fontsize=8, color="#555")
    ax.text(W / 2, L + 0.15, "closed end of the U", ha="center", va="bottom", fontsize=8, color="#555")
    long_ids = [pid for pid, pts in paths.items() if len(pts) >= args.min_steps]
    for k, pid in enumerate(sorted(long_ids)):
        pts = paths[pid]
        colour = COLOURS[k % len(COLOURS)] if k < len(COLOURS) else "#9a9a9a"
        xs, ys = zip(*pts)
        ax.plot(xs, ys, lw=1.4, color=colour, alpha=0.9)
        ax.plot(xs[0], ys[0], "o", ms=5, color=colour, mec="white", mew=1)
        ax.text(xs[0] + 0.08, ys[0] + 0.08, str(pid), fontsize=7, color="#222")
    for pid, pts in paths.items():
        if pid not in long_ids:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, lw=0.8, color="#bbb", alpha=0.6)
    if args.camera:
        ax.plot(args.camera[0], args.camera[1], marker=(3, 0, 0), ms=9, color="#222")
        ax.text(args.camera[0] + 0.12, args.camera[1], "camera", fontsize=7, color="#222", va="center")
    ax.set_xlim(-0.6, W + 0.6)
    ax.set_ylim(-0.7, L + 0.7)
    ax.set_aspect("equal")
    ax.set_xlabel("x, metres along the data wall", fontsize=8)
    ax.set_ylabel("y, metres from the data wall", fontsize=8)
    ax.tick_params(labelsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if args.title:
        ax.set_title(args.title, fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(args.out)
    print(f"{len(long_ids)} paths drawn ({len(paths) - len(long_ids)} short ones faint) -> {args.out}")


if __name__ == "__main__":
    main()
