"""A scripted session in front of a camera, to build a labelled set of pictures.

Usage:
    python -m cockaigne_sensing.tools.script_session --out bench/sessions/shed1
                [--config config/studio.yaml] [--camera cam1]
                [--script config/session_script.yaml] [--speak] [--no-window]

To choose a model for the actions module we need pictures where the right
answer is known. This tool supplies the answer by telling the performer what
to do. It fills the screen with one instruction at a time and a countdown:
where to stand, which way to face, and what to do. While each action is held
it saves a full-size still from the camera every few seconds and writes the
instruction beside it in session.jsonl, so nobody labels anything afterwards.

A low beep means a new instruction; a high beep means hold it now. --speak
also reads each instruction aloud, for the steps that face away from the
screen. Esc stops the session and keeps what was saved.

This is a development tool. It writes pictures to disk, which nothing in the
gallery ever does, and it is never part of the gallery configuration.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from ..capture import fetch_still
from ..config import load

DEFAULT_SCRIPT = Path(__file__).resolve().parents[2] / "config" / "session_script.yaml"
FONT = cv2.FONT_HERSHEY_DUPLEX
PLACE = ("where", "facing", "posture")


def build_steps(script: dict) -> list[dict]:
    """Every block at each mark, each facing, each action, in walking order.
    `moved` marks a step that starts somewhere new, which is given longer."""
    steps = [{"where": where, "facing": facing, "posture": block["posture"],
              "action": action["label"], "say": action["say"]}
             for block in script["blocks"] for where in block["where"]
             for facing in block["facing"] for action in script["actions"]]
    for before, step in zip([None] + steps, steps):
        step["moved"] = before is None or any(step[k] != before[k] for k in PLACE)
    return steps


def put_fitted(img: np.ndarray, text: str, y: int, scale: float, colour, thick: int) -> None:
    """Write one centred line, made smaller if it would not fit the width."""
    width = cv2.getTextSize(text, FONT, scale, thick)[0][0]
    scale = min(scale, scale * (img.shape[1] - 160) / max(width, 1))
    width = cv2.getTextSize(text, FONT, scale, thick)[0][0]
    cv2.putText(img, text, ((img.shape[1] - width) // 2, y), FONT, scale, colour, thick, cv2.LINE_AA)


def draw(step: dict, phase: str, left: float, index: int, total: int) -> np.ndarray:
    """The whole screen for one moment: amber while getting ready, white in a
    green frame while holding, readable from the far end of a room."""
    img = np.zeros((1080, 1920, 3), np.uint8)
    holding = phase == "hold"
    colour = (255, 255, 255) if holding else (0, 190, 255)
    if holding:
        cv2.rectangle(img, (0, 0), (1919, 1079), (0, 200, 0), 40)
    put_fitted(img, "HOLD IT" if holding else "NEXT, GET READY", 150, 2.6, colour, 4)
    put_fitted(img, step["say"].upper(), 430, 5.0, colour, 9)
    put_fitted(img, ", ".join(step[k] for k in PLACE).upper(), 600, 2.6, colour, 4)
    put_fitted(img, str(max(0, int(np.ceil(left)))), 900, 9.0, colour, 16)
    cv2.putText(img, f"STEP {index + 1} OF {total}", (70, 1030), FONT, 1.4, (140, 140, 140), 2,
                cv2.LINE_AA)
    return img


def beep(high: bool) -> None:
    """A low beep for a new instruction, a high one for hold."""
    try:
        import winsound
        winsound.Beep(1200 if high else 600, 250)
    except (ImportError, RuntimeError):   # not Windows, or no sound device
        print("\a", end="", flush=True)


def speak(text: str) -> None:
    """Read a line aloud in the computer's own voice, where it has one."""
    safe = "".join(ch for ch in text if ch.isalnum() or ch in " ,.")
    try:
        if sys.platform == "win32":
            subprocess.Popen(["powershell", "-NoProfile", "-Command",
                              "Add-Type -AssemblyName System.Speech; (New-Object "
                              f"System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')"])
        elif sys.platform == "darwin":
            subprocess.Popen(["say", safe])
    except OSError:
        pass


def in_background(job) -> None:
    """Fetching a still takes a moment; the countdown must not wait for it."""
    threading.Thread(target=job, daemon=True).start()


def run_session(steps: list[dict], script: dict, grab, out_dir: Path, show, announce,
                clock=time.monotonic, sleep=time.sleep, spawn=in_background) -> dict:
    """Walk the performer through every step and save labelled stills.

    grab() returns one full-size picture or None. show(step, phase, seconds
    left, index, total) puts the instruction in front of the performer and
    returns False to stop. announce(step, phase) makes the sounds.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tally = {"saved": 0, "missed": 0, "stopped": False}
    lock = threading.Lock()
    log = open(out_dir / "session.jsonl", "a", encoding="utf-8")

    def save(number: int, index: int, step: dict) -> None:
        asked = clock()
        frame = grab()
        name = f"{number:04d}.jpg"
        with lock:
            if log.closed or frame is None or not cv2.imwrite(str(out_dir / name), frame):
                tally["missed"] += 1
                return
            tally["saved"] += 1
            line = {"file": name, "step": index, "took_s": round(clock() - asked, 2),
                    **{k: step[k] for k in ("action", "say") + PLACE}}
            log.write(json.dumps(line) + "\n")
            log.flush()

    number = 0
    for index, step in enumerate(steps):
        ready = script["move_s"] if step["moved"] else script["ready_s"]
        for phase, length in (("ready", ready), ("hold", script["hold_s"])):
            if tally["stopped"]:
                break
            announce(step, phase)
            start = clock()
            next_still = script["settle_s"]
            while (elapsed := clock() - start) < length and not tally["stopped"]:
                if not show(step, phase, length - elapsed, index, len(steps)):
                    tally["stopped"] = True
                elif phase == "hold" and next_still <= elapsed < length - 0.5:
                    number += 1
                    next_still += script["still_every_s"]
                    spawn(lambda n=number, i=index, s=step: save(n, i, s))
                sleep(0.1)
        if tally["stopped"]:
            break
    sleep(script["still_every_s"])   # let the last still land before the file closes
    with lock:
        log.close()
    return tally


def time_stills(grab, count: int) -> tuple[list[float], tuple[int, int] | None]:
    """How long the camera takes to hand over a still, and how big it is."""
    times, size = [], None
    for _ in range(count):
        start = time.monotonic()
        frame = grab()
        if frame is not None:
            times.append(time.monotonic() - start)
            size = (frame.shape[1], frame.shape[0])
    return times, size


def file_grabber(path: str):
    """Stand-in for a camera at a desk: the next frame of a clip, looped."""
    cap = cv2.VideoCapture(path)

    def grab():
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        return frame if ok else None
    return grab


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="folder for the stills and session.jsonl")
    ap.add_argument("--config")
    ap.add_argument("--camera", default="cam1")
    ap.add_argument("--script", default=str(DEFAULT_SCRIPT))
    ap.add_argument("--speak", action="store_true", help="read each instruction aloud")
    ap.add_argument("--no-window", action="store_true", help="print instructions instead")
    args = ap.parse_args()

    cfg = load(args.config)
    with open(args.script, encoding="utf-8") as f:
        script = yaml.safe_load(f)
    cam = next(c for c in cfg["cameras"] if c["name"] == args.camera)
    timeout = cfg["actions"]["still_timeout_s"]
    grab = file_grabber(cam["file"]) if cam.get("file") else (lambda: fetch_still(cam, timeout))

    times, size = time_stills(grab, script["time_stills"])
    if not times:
        print(f"No still picture came back from {args.camera}. Check, in this order:\n"
              "  1. HTTP is switched on in the camera's port settings.\n"
              "  2. The password is in camera_password.txt in the repo folder.\n"
              "  3. The camera's address in the config file is right.")
        raise SystemExit(2)
    print(f"camera answers with a {size[0]} x {size[1]} still in {statistics.median(times):.2f} s "
          f"(slowest {max(times):.2f} s, {len(times)} of {script['time_stills']} arrived)")

    steps = build_steps(script)
    seconds = sum(script["hold_s"] + (script["move_s"] if s["moved"] else script["ready_s"])
                  for s in steps)
    print(f"{len(steps)} steps, about {seconds / 60:.0f} minutes. "
          f"WRITING PICTURES TO DISK in {args.out}")
    input("Phone, cup and food within reach of each mark? Press Enter to start. ")

    def announce(step, phase):
        beep(high=phase == "hold")
        if args.speak and phase == "ready":
            place = ", ".join(step[k] for k in PLACE) + ". " if step["moved"] else ""
            speak(place + step["say"])

    printed = []

    def show_text(step, phase, left, index, total):
        if printed[-1:] != [(index, phase)]:
            printed.append((index, phase))
            print(f"[{index + 1}/{total}] {phase.upper():5} "
                  f"{', '.join(step[k] for k in PLACE)}: {step['say']}")
        return True

    def show_window(step, phase, left, index, total):
        cv2.imshow("session", draw(step, phase, left, index, total))
        return cv2.waitKey(1) & 0xFF != 27   # Esc stops

    if not args.no_window:
        cv2.namedWindow("session", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("session", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    tally = run_session(steps, script, grab, Path(args.out),
                        show_text if args.no_window else show_window, announce)
    if not args.no_window:
        cv2.destroyAllWindows()
    print(f"{tally['saved']} stills saved, {tally['missed']} missed"
          + (", stopped early" if tally["stopped"] else "") + f" -> {args.out}")


if __name__ == "__main__":
    main()
