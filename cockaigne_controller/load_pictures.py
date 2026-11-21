"""Point every clip slot at its full-size picture file, once.

Usage, with Resolume open and a COPY of the show composition loaded:
    python -m cockaigne_controller.load_pictures [--config ...] [--dry-run]

For every clip on the video layer it finds the picture file whose name starts
with the clip's name, opens it in the clip's own slot, gives the slot its
clip name back (Resolume renames a slot after the file, and the controller
finds clips by name) and sets it to fit the composition. A clip with no file
keeps the picture it had and is listed. Nothing is saved: look at the result
in Resolume and save the composition yourself.
"""
from __future__ import annotations

import argparse
from urllib.parse import quote

import requests

from .config import load
from .load_sounds import find_sounds
from .resolume import layout_from_composition


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--dry-run", action="store_true", help="list what would be loaded, change nothing")
    args = ap.parse_args()
    cfg = load(args.config)
    res, pic = cfg["resolume"], cfg["picture"]
    base = f"http://{res['host']}:{res['rest_port']}/api/v1/composition"
    layout = layout_from_composition(requests.get(base, timeout=res["rest_timeout_s"]).json())
    clips = {name: index for name, (layer, index) in layout.items() if layer == res["video_layer"]}
    files, complaints = find_sounds(pic["folders"], pic["name_pattern"], {}, pic["glob"])
    for line in complaints:
        print("CHECK:", line)
    for name in sorted(set(clips) - set(files)):
        print("NO FULL-SIZE FILE FOR CLIP (keeps its present picture):", name)
    todo = sorted((index, name, files[name]) for name, index in clips.items() if name in files)
    print(f"{len(todo)} of {len(clips)} clips have a full-size file")
    if args.dry_run:
        return
    layer = res["video_layer"]
    for index, name, path in todo:
        uri = "file:///" + quote(path.resolve().as_posix(), safe="/:")
        requests.post(f"{base}/layers/{layer}/clips/{index}/open", data=uri, timeout=60).raise_for_status()
    settings = {"video": {"resize": {"value": pic["resize"]}}}
    for index, name, _ in todo:  # after the opens, so every file has had time to load
        body = dict(settings, name={"value": name})
        requests.put(f"{base}/layers/{layer}/clips/{index}", json=body, timeout=60).raise_for_status()
    after = layout_from_composition(requests.get(base, timeout=60).json())
    wrong = sorted(name for index, name, _ in todo if after.get(name) != (layer, index))
    for name in wrong:
        print("NAME NOT RESTORED, the controller will not find this clip:", name)
    print(f"Done: {len(todo) - len(wrong)} clips loaded. Check a few in Resolume, then save the composition.")


if __name__ == "__main__":
    main()
