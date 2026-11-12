"""Scripted-session and model-bench tests. No camera, no window, no model:
the camera is a function that returns a grey picture, the performer is
nobody, and time is a number the test moves."""
import json

import numpy as np
import yaml

from cockaigne_sensing.actions import FakeModel
from cockaigne_sensing.tools.bench_actions import ask_all, load_rows, make_crops, report
from cockaigne_sensing.tools.script_session import DEFAULT_SCRIPT, build_steps, draw, run_session


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def small_script():
    return {"ready_s": 1, "move_s": 2, "hold_s": 6, "settle_s": 2, "still_every_s": 2,
            "blocks": [{"posture": "standing", "where": ["near mark", "far mark"],
                        "facing": ["facing the camera"]}],
            "actions": [{"label": "none", "say": "Nothing."},
                        {"label": "phone", "say": "Look at your phone."}]}


def run(tmp_path, script, grab, stop_after=None):
    clock, shown, sounds = Clock(), [], []

    def show(step, phase, left, index, total):
        shown.append((index, phase))
        return stop_after is None or len(shown) < stop_after

    steps = build_steps(script)
    tally = run_session(steps, script, grab, tmp_path, show,
                        lambda step, phase: sounds.append((step["action"], phase)),
                        clock=clock, sleep=clock.sleep, spawn=lambda job: job())
    return steps, tally, shown, sounds, clock


def test_the_shipped_script_is_whole_and_fits_a_session():
    with open(DEFAULT_SCRIPT, encoding="utf-8") as f:
        script = yaml.safe_load(f)
    steps = build_steps(script)
    assert len(steps) == 55 and sum(s["moved"] for s in steps) == 11
    assert {s["action"] for s in steps} == {"none", "phone", "drink", "eat"}
    seconds = sum(script["hold_s"] + (script["move_s"] if s["moved"] else script["ready_s"])
                  for s in steps)
    assert seconds < 20 * 60                              # a performer's patience
    assert draw(steps[0], "hold", 3.2, 0, len(steps)).shape == (1080, 1920, 3)


def test_a_session_saves_stills_labelled_by_the_step_being_held(tmp_path):
    script = small_script()
    grey = np.full((216, 384, 3), 128, np.uint8)
    steps, tally, shown, sounds, clock = run(tmp_path, script, lambda: grey)
    assert tally == {"saved": 8, "missed": 0, "stopped": False}   # two per hold, at 2 s and 4 s
    assert sounds[:4] == [("none", "ready"), ("none", "hold"), ("phone", "ready"), ("phone", "hold")]
    rows = load_rows(tmp_path)
    assert [r["action"] for r in rows] == ["none", "none", "phone", "phone"] * 2
    assert [r["where"] for r in rows] == ["near mark"] * 4 + ["far mark"] * 4
    assert all((tmp_path / r["file"]).is_file() for r in rows)
    # Moving to a new mark is given the longer time: 2 + 6, 1 + 6, 2 + 6, 1 + 6, then the last wait.
    assert 30.0 <= clock.now <= 33.5


def test_a_session_counts_missed_stills_and_stops_on_request(tmp_path):
    script = small_script()
    steps, tally, shown, _, _ = run(tmp_path, script, lambda: None)
    assert tally["saved"] == 0 and tally["missed"] == 8
    steps, tally, shown, sounds, _ = run(tmp_path, script, lambda: None, stop_after=5)
    assert tally["stopped"] and sounds == [("none", "ready")]


def test_bench_scores_each_model_against_the_script(tmp_path):
    script = small_script()
    picture = np.full((216, 384, 3), 128, np.uint8)
    run(tmp_path, script, lambda: picture)
    rows = load_rows(tmp_path)
    whole_frame = lambda frame: [((10.0, 10.0, 60.0, 200.0), 0.9), ((5.0, 5.0, 20.0, 40.0), 0.5)]
    crops = make_crops(rows, tmp_path, whole_frame, 0.25, 448)
    assert len(crops) == 8 and crops[0][1].shape[0] > 150      # the larger person was taken
    assert make_crops(rows, tmp_path, lambda frame: [], 0.25, 448) == []

    perfect = FakeModel(["none", "none", "phone", "phone"])
    text = report("perfect", ask_all(perfect, crops))
    assert "right 8 of 8 (100%)" in text and "mistakes: none" in text
    careless = FakeModel(["phone"])                            # sees a phone in every hand
    text = report("careless", ask_all(careless, crops))
    assert "right 4 of 8 (50%)" in text
    assert "none 0/4 (0%)" in text and "phone 4/4 (100%)" in text
    assert "none called phone 4" in text
    silent = report("silent", ask_all(FakeModel([None]), crops))
    assert "right 0 of 8" in silent and "no answer 8" in silent
