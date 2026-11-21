"""Put each clip's sound file into the composition, once.

Usage, with Resolume open and the composition loaded:
    python -m cockaigne_controller.load_sounds [--config ...] [--dry-run]

For every clip on the video layer it finds the sound file whose name holds
the clip's name, and opens it in the same column on each sound layer, set
to play through once. It then turns the sound layers up to full. Nothing is
saved: look at the result in Resolume and save the composition yourself.
Files are matched by name only, so a clip with no file is listed, not guessed.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import quote

import requests

from .config import load
from .resolume import layout_from_composition


def find_sounds(folder: str, name_pattern: str, renames: dict) -> tuple[dict, list]:
    """Clip name -> sound file, from the file names under `folder`. A path
    ending listed in `renames` takes the clip name given there. Returns the
    map and a list of complaints (two files for one clip, unreadable names)."""
    found: dict[str, Path] = {}
    complaints: list[str] = []
    for path in sorted(Path(folder).rglob("*.wav")):
        tail = next((clip for ending, clip in renames.items()
                     if path.as_posix().lower().endswith(ending.lower())), None)
        match = re.search(name_pattern, path.name.lower())
        clip = tail or (match.group(1) if match else None)
        if clip is None:
            complaints.append(f"no clip name in {path.name}")
        elif clip in found:
            complaints.append(f"two files for {clip}: {found[clip].name} and {path.name}")
        else:
            found[clip] = path
    return found, complaints


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--dry-run", action="store_true", help="list what would be loaded, change nothing")
    args = ap.parse_args()
    cfg = load(args.config)
    res, snd = cfg["resolume"], cfg["sound"]
    base = f"http://{res['host']}:{res['rest_port']}/api/v1/composition"
    layout = layout_from_composition(requests.get(base, timeout=res["rest_timeout_s"]).json())
    clips = {name: index for name, (layer, index) in layout.items() if layer == res["video_layer"]}
    sounds, complaints = find_sounds(snd["folder"], snd["name_pattern"], snd.get("renames") or {})
    for line in complaints:
        print("CHECK:", line)
    for name in sorted(set(clips) - set(sounds)):
        print("NO SOUND FOR CLIP:", name)
    for name in sorted(set(sounds) - set(clips)):
        print("NO CLIP FOR SOUND:", sounds[name].name)
    todo = sorted((index, sounds[name]) for name, index in clips.items() if name in sounds)
    print(f"{len(todo)} of {len(clips)} clips have a sound; layers {res['sound_layers']}")
    if args.dry_run:
        return
    mode = {"transport": {"controls": {"playmode": {"value": snd["play_mode"]}}}}
    for layer in res["sound_layers"]:
        for index, path in todo:
            clip_url = f"{base}/layers/{layer}/clips/{index}"
            uri = "file:///" + quote(path.resolve().as_posix(), safe="/:")
            requests.post(clip_url + "/open", data=uri, timeout=30).raise_for_status()
        for index, _ in todo:  # after the opens, so every file has had time to load
            requests.put(f"{base}/layers/{layer}/clips/{index}", json=mode, timeout=30).raise_for_status()
        requests.put(f"{base}/layers/{layer}", json={"audio": {"volume": {"value": 0.0}}},
                     timeout=30).raise_for_status()
        print(f"layer {layer}: {len(todo)} sounds loaded, volume at 0 dB")
    print("Done. Check a few in Resolume, then save the composition.")


if __name__ == "__main__":
    main()
