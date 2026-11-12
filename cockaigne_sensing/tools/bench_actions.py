"""Compare candidate models for the actions module on a scripted session.

Usage:
    python -m cockaigne_sensing.tools.bench_actions bench/sessions/shed1
                --models objects,qwen3-vl:4b-instruct,gemma4:e2b,gemma3:4b
                [--config config/studio.yaml] [--out bench/2026-11-20-actions.md]

Reads the stills and the right answers that a scripted session saved
(tools.script_session). Finds the person in each still, cuts the crop
exactly as the live chain would, and puts the same question to each model.
The name "objects" is not a language model. It is the person detector's
own object classes run on the crop: a phone, a cup or a piece of food seen in
it becomes the answer. It is far cheaper than a language model, and it is
scored the same way, so the two can be compared directly.
Reports, per model: how often it was right, for each action, each way of
facing and each mark; what it mistook for what; and how long an answer
took. The time decides how many questions a second the gallery can afford.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import cv2

from ..actions import OllamaModel
from ..capture import cut
from ..config import load

# The detector was trained on the COCO set of 80 everyday things. These are
# the ones that mean an action. Anything else it sees counts as nothing.
OBJECT_ACTIONS = {"cell phone": "phone",
                  "cup": "drink", "bottle": "drink", "wine glass": "drink",
                  **{food: "eat" for food in ("banana", "apple", "sandwich", "orange",
                                               "hot dog", "pizza", "donut", "cake")}}


def answer_from_objects(found: list[tuple[str, float]], enabled: list[str]) -> str:
    """The action whose object the detector is surest it sees, or "none".
    found is (class name, confidence) for everything seen in one crop."""
    hits = [(conf, OBJECT_ACTIONS[name]) for name, conf in found
            if OBJECT_ACTIONS.get(name) in enabled]
    return max(hits)[1] if hits else "none"


class ObjectCheck:
    """Answers like a model, from what find(crop) says is in the picture."""

    def __init__(self, find, enabled: list[str]):
        self.find, self.enabled = find, list(enabled)

    def ask(self, crop) -> str:
        return answer_from_objects(self.find(crop), self.enabled)


def yolo_objects(weights: str, conf: float, device: str):
    """find(crop) for ObjectCheck: everything the detector sees in a crop."""
    from ultralytics import YOLO   # here, so the report code runs without the detector
    yolo = YOLO(weights)

    def find(crop):
        boxes = yolo.predict(crop, conf=conf, device=None if device == "auto" else device,
                             verbose=False)[0].boxes
        if boxes is None:
            return []
        return [(yolo.names[int(k)], float(c)) for k, c in zip(boxes.cls.tolist(), boxes.conf.tolist())]
    return find


def load_rows(session: Path) -> list[dict]:
    """One row per saved still: the file and what the performer was doing."""
    with open(session / "session.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def make_crops(rows: list[dict], session: Path, find_people, pad: float, max_px: int) -> list:
    """(row, crop) for every still in which a person was found. The largest
    person in the picture is taken to be the performer."""
    out = []
    for row in rows:
        frame = cv2.imread(str(session / row["file"]))
        people = find_people(frame) if frame is not None else []
        if not people:
            continue
        box = max(people, key=lambda p: (p[0][2] - p[0][0]) * (p[0][3] - p[0][1]))[0]
        crop = cut(frame, [box], (frame.shape[1], frame.shape[0]), pad, max_px)[0]
        if crop is not None:
            out.append((row, crop))
    return out


def ask_all(model, crops: list) -> list[tuple[dict, str | None, float]]:
    """Every crop put to one model: (row, its answer, seconds taken)."""
    results = []
    for row, crop in crops:
        start = time.monotonic()
        word = model.ask(crop)
        results.append((row, word, time.monotonic() - start))
    return results


def tally(results: list, key: str) -> str:
    """Right answers out of asked, for each value of one column."""
    right, asked = Counter(), Counter()
    for row, word, _ in results:
        asked[row[key]] += 1
        right[row[key]] += word == row["action"]
    return "; ".join(f"{value} {right[value]}/{n} ({100 * right[value] // n}%)"
                     for value, n in asked.items())


def report(name: str, results: list) -> str:
    """The plain-text verdict on one model."""
    if not results:
        return f"## {name}\nno crops to ask about\n"
    right = sum(word == row["action"] for row, word, _ in results)
    silent = sum(word is None for _, word, _ in results)
    times = sorted(seconds for _, _, seconds in results)
    mistakes = Counter(f"{row['action']} called {word}" for row, word, _ in results
                       if word is not None and word != row["action"])
    return "\n".join([
        f"## {name}",
        f"right {right} of {len(results)} ({100 * right // len(results)}%); "
        f"no answer {silent}; median {statistics.median(times):.2f} s, "
        f"slowest tenth above {times[int(0.9 * (len(times) - 1))]:.2f} s",
        f"- by action: {tally(results, 'action')}",
        f"- by facing: {tally(results, 'facing')}",
        f"- by mark: {tally(results, 'where')}",
        f"- by posture: {tally(results, 'posture')}",
        "- mistakes: " + ("; ".join(f"{m} {n}" for m, n in mistakes.most_common()) or "none"),
        ""])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help="the folder tools.script_session wrote")
    ap.add_argument("--models", required=True,
                    help="Ollama model tags, comma separated; 'objects' for the detector's object check")
    ap.add_argument("--config")
    ap.add_argument("--out", help="also write the report to this file")
    args = ap.parse_args()

    cfg = load(args.config)
    acts, det = cfg["actions"], cfg["detector"]
    from ..detect import PersonTracker   # here, so the report code runs without the detector
    finder = PersonTracker(det["model"], det["imgsz"], det["conf"], det["tracker"], det["device"])
    session = Path(args.session)
    rows = load_rows(session)
    crops = make_crops(rows, session, finder.detect, acts["crop_pad"], acts["crop_max_px"])
    lines = [f"# Actions model bench, {session.name}", "",
             f"{len(rows)} stills, a person found in {len(crops)}. Crops padded by "
             f"{acts['crop_pad']} and shrunk to {acts['crop_max_px']} px, as live.", ""]
    for name in (m.strip() for m in args.models.split(",") if m.strip()):
        if name == "objects":
            model = ObjectCheck(yolo_objects(det["model"], det["conf"], det["device"]), acts["enabled"])
        else:
            model = OllamaModel(dict(acts, model=name))
        # The first question loads the model into the graphics card. It is not timed.
        if crops and model.ask(crops[0][1]) is None:
            lines.append(f"## {name}\nno answer to the first question. Is Ollama running, "
                         f"and is the model pulled (ollama pull {name})?\n")
        else:
            lines.append(report(name, ask_all(model, crops)))
        print(lines[-1])
    if args.out:
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
        print(f"report written to {args.out}")


if __name__ == "__main__":
    main()
