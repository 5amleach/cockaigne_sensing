"""Set every picture clip to hold its last frame when it ends, once per composition.

Usage, with Resolume open and the show composition loaded:
    python -m cockaigne_controller.hold_pictures [--config ...] [--dry-run]

Resolume's default play mode is Loop. Every picture clip is exactly sixty
seconds, and the controller fires the next clip a few hundredths of a second
after that, so a looping clip shows its own first frame for a frame or two:
a flash of the place the move started from. Held on its last frame instead,
the clip waits on the picture the next clip starts with, and the change is
seamless. The play mode is `picture: play_mode` in config/controller.yaml.
Nothing is saved: save the composition in Resolume afterwards.
"""
from __future__ import annotations

import argparse

import requests

from .config import load
from .resolume import layout_from_composition


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--dry-run", action="store_true", help="count the clips, change nothing")
    args = ap.parse_args()
    cfg = load(args.config)
    res, mode = cfg["resolume"], cfg["picture"]["play_mode"]
    base = f"http://{res['host']}:{res['rest_port']}/api/v1/composition"
    layer = res["video_layer"]
    layout = layout_from_composition(requests.get(base, timeout=res["rest_timeout_s"]).json())
    indexes = sorted(index for (lay, index) in layout.values() if lay == layer)
    print(f"{len(indexes)} picture clips on layer {layer} will be set to {mode!r}")
    if args.dry_run:
        return
    body = {"transport": {"controls": {"playmode": {"value": mode}}}}
    for index in indexes:
        requests.put(f"{base}/layers/{layer}/clips/{index}", json=body, timeout=30).raise_for_status()
    print("Done. Save the composition in Resolume.")


if __name__ == "__main__":
    main()
