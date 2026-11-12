"""Actions tests: crops, votes, who is due, the worker's rounds and its health.

No model, no camera and no network: a scripted fake answers the questions,
the pictures are arrays made here, and time is a number the test moves.
"""
import json
import logging

import cv2
import numpy as np
import pytest
import requests

from cockaigne_sensing.actions import ActionsWorker, FakeModel, Votes, due_people, make_model
from cockaigne_sensing.actions.model import OllamaModel, local_only
from cockaigne_sensing.capture import Closeups, cut, fetch_still
from cockaigne_sensing.config import load

LOG = logging.getLogger("test_actions")


def actions_cfg(**over):
    cfg = load()["actions"]
    cfg.update(over)
    return cfg


class Clock:
    """Time the test controls. Waiting moves it forward at once."""

    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def person(pid, camera="cam1", age=10.0, box=(100, 50, 160, 250), seen=True):
    view = {"camera": camera, "track": pid, "box": list(box), "w": 640, "h": 360, "conf": 0.9}
    return {"id": pid, "age": age, "view": view if seen else None,
            "actions": {"phone": 0.0, "drink": 0.0, "eat": 0.0}}


def people_msg(t, *people):
    return {"stream": "people", "t": t, "people": list(people)}


def make_worker(model, clock, frame=None, **over):
    cfg = actions_cfg(**over)
    if frame is None:
        frame = np.full((2160, 3840, 3), 90, np.uint8)
    cams = [{"name": "cam1", "file": "x"}, {"name": "cam2", "file": "y"}]
    closeups = Closeups(cams, cfg, lambda name: frame if name == "cam1" else None)
    return ActionsWorker(cfg, closeups, model, LOG, clock=clock, sleep=clock.sleep)


# ---------- crops ----------

def test_cut_scales_pads_clips_and_shrinks():
    frame = np.zeros((2160, 3840, 3), np.uint8)
    # A box in the detector's 640 x 360 frame is six times larger in the still.
    # Padded by a quarter it runs off the top, so it is clipped there.
    crop, gone = cut(frame, [[100, 50, 160, 250], [700, 400, 760, 600]], (640, 360), 0.25, 448)
    assert gone is None                       # a box outside the picture gives no crop
    assert crop.shape[0] == 448               # 1800 px tall, shrunk to the limit
    assert crop.shape[1] == round(540 * 448 / 1800)
    small = cut(frame, [[100, 100, 110, 120]], (640, 360), 0.0, 448)[0]
    assert small.shape[:2] == (120, 60)       # already small: scaled, never enlarged


# ---------- votes ----------

def test_two_agreeing_answers_start_an_action_and_two_end_it():
    v = Votes(actions_cfg())
    v.add(1, "phone", 0.0)
    assert v.scores(1, 0.0)["phone"] == 0.0             # one answer is not enough
    v.add(1, "phone", 3.0)
    assert v.scores(1, 3.0) == {"phone": 1.0, "drink": 0.0, "eat": 0.0}
    v.add(1, "none", 6.0)
    assert v.scores(1, 6.0)["phone"] == pytest.approx(0.67, abs=0.01)   # one stray answer does not end it
    v.add(1, "phone", 7.0)
    assert v.scores(1, 7.0)["phone"] == 0.75
    v.add(1, "none", 10.0)
    v.add(1, "none", 13.0)
    assert v.scores(1, 13.0)["phone"] == 0.0            # two agreeing answers end it


def test_old_answers_fade_and_leavers_are_forgotten():
    v = Votes(actions_cfg(reading_stale_s=20.0))
    v.add(1, "drink", 0.0)
    v.add(1, "drink", 3.0)
    v.add(2, "eat", 3.0)
    assert v.scores(1, 10.0)["drink"] == 1.0
    assert v.scores(1, 30.0)["drink"] == 0.0            # nobody has looked for too long
    v.keep_only({1})
    assert not v.unsettled(2) and v.scores(2, 3.0)["eat"] == 0.0


def test_unsettled_means_the_newest_answer_differs_from_the_one_before():
    v = Votes(actions_cfg())
    v.add(1, "none", 0.0)
    assert not v.unsettled(1)
    v.add(1, "phone", 3.0)
    assert v.unsettled(1)
    v.add(1, "phone", 4.0)
    assert not v.unsettled(1)


# ---------- who is due ----------

def test_due_people_longest_waiting_first_and_skips_the_unseeable():
    cfg = actions_cfg(interval_s=3.0, recheck_s=1.0, min_age_s=3.0)
    v = Votes(cfg)
    people = [person(1), person(2), person(3), person(4, seen=False), person(5, age=1.0),
              person(6)]
    asked_at = {1: 96.0, 2: 90.0, 6: 99.0}             # 3 has never been asked
    assert [p["id"] for p in due_people(people, asked_at, v, 100.0, cfg)] == [3, 2, 1]
    v.add(6, "none", 98.0)
    v.add(6, "phone", 99.0)                             # a change: worth a second look at once
    assert [p["id"] for p in due_people(people, asked_at, v, 100.0, cfg)] == [3, 2, 1, 6]


# ---------- the worker ----------

def test_a_round_asks_within_budget_and_two_rounds_report_a_phone():
    clock = Clock()
    model = FakeModel(["phone"])
    worker = make_worker(model, clock, max_asks_per_s=2.0)
    msg = people_msg(clock.now, person(1), person(2))
    worker.offer(msg)
    assert worker.step() == 2 and model.asked == 2
    assert clock.now == pytest.approx(100.5)            # the second question waited half a second
    assert worker.fill(msg)["people"][0]["actions"]["phone"] == 0.0
    assert worker.step() == 0                           # nobody is due again yet
    clock.sleep(3.0)
    worker.step()
    filled = worker.fill(people_msg(clock.now, person(1), person(2)))
    assert [p["actions"]["phone"] for p in filled["people"]] == [1.0, 1.0]
    assert filled["people"][0]["actions"]["drink"] == 0.0
    assert filled["actions_health"]["alive"]


def test_an_empty_room_still_proves_the_model_is_alive():
    clock = Clock()
    model = FakeModel(["none"])
    worker = make_worker(model, clock, heartbeat_s=10.0)
    worker.offer(people_msg(clock.now))
    assert worker.health(clock.now) == {"alive": False, "age_s": None}   # nothing has answered yet
    worker.step()
    assert model.asked == 1 and worker.health(clock.now)["alive"]
    worker.step()
    assert model.asked == 1                             # no second blank question so soon
    clock.sleep(10.0)
    worker.step()
    assert model.asked == 2


def test_a_silent_model_turns_the_sense_blind_and_scores_fade(caplog):
    clock = Clock()
    model = FakeModel(["phone"])                        # answers twice below, then falls silent
    worker = make_worker(model, clock, fail_warn_s=30.0, reading_stale_s=20.0)
    worker.offer(people_msg(clock.now, person(1)))
    worker.step()
    clock.sleep(3.0)
    worker.step()
    assert worker.fill(people_msg(clock.now, person(1)))["people"][0]["actions"]["phone"] == 1.0
    model.words = [None]
    with caplog.at_level(logging.WARNING):
        for _ in range(12):
            clock.sleep(3.0)
            worker.step()
    filled = worker.fill(people_msg(clock.now, person(1)))
    assert filled["actions_health"]["alive"] is False
    assert filled["people"][0]["actions"]["phone"] == 0.0   # no answer is not "none", but old answers fade
    assert any("not answering" in r.message for r in caplog.records)


def test_no_picture_means_no_question_and_no_tight_loop():
    clock = Clock()
    model = FakeModel(["phone"])
    worker = make_worker(model, clock)
    worker.offer(people_msg(clock.now, person(1, camera="cam2")))   # cam2 gives no picture
    assert worker.step() == 1 and model.asked == 0
    worker.step()
    assert model.asked == 1                             # only the blank heartbeat; the person waits their turn


def test_a_person_who_moved_out_of_view_is_not_cut_from_the_old_box():
    clock = Clock()
    model = FakeModel(["phone"])
    worker = make_worker(model, clock)
    worker.offer(people_msg(clock.now, person(1), person(2)))
    # By the time the picture arrives, person 2 is no longer seen by cam1.
    original = worker.closeups.newest_frame

    def frame_then_change(name):
        worker.offer(people_msg(clock.now, person(1), person(2, seen=False)))
        return original(name)

    worker.closeups.newest_frame = frame_then_change
    worker.step()
    assert model.asked == 1


# ---------- the model and the camera, with the network stood in for ----------

class Reply:
    def __init__(self, body=None, content=b""):
        self._body, self.content = body, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_the_model_server_must_be_this_machine():
    assert local_only("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    with pytest.raises(ValueError):
        local_only("http://192.168.1.50:11434")
    with pytest.raises(ValueError):
        OllamaModel(actions_cfg(ollama_url="https://example.com"))


def test_ollama_question_and_answer(monkeypatch):
    sent = {}

    def post(url, json=None, timeout=None):
        sent.update(url=url, body=json, timeout=timeout)
        return Reply({"message": {"content": '{"answer": "drink"}'}})

    monkeypatch.setattr(requests, "post", post)
    model = OllamaModel(actions_cfg(model="some-model", no_think=True))
    assert model.ask(np.zeros((40, 20, 3), np.uint8)) == "drink"
    assert sent["url"] == "http://127.0.0.1:11434/api/chat"
    body = sent["body"]
    assert body["model"] == "some-model" and body["think"] is False and body["stream"] is False
    assert body["format"]["properties"]["answer"]["enum"] == ["phone", "drink", "eat", "none"]
    assert len(body["messages"][0]["images"][0]) > 100   # the crop travelled as a JPEG in memory

    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: Reply({"message": {"content": "I think maybe"}}))
    assert model.ask(np.zeros((40, 20, 3), np.uint8)) is None   # not an answer, and not "none"

    def refuse(*a, **k):
        raise requests.ConnectionError("nobody home")

    monkeypatch.setattr(requests, "post", refuse)
    assert model.ask(np.zeros((40, 20, 3), np.uint8)) is None


def test_fake_models_from_config():
    assert make_model(actions_cfg(model="fake")).ask(None) == "none"
    turns = make_model(actions_cfg(model="fake:phone, none"))
    assert [turns.ask(None) for _ in range(3)] == ["phone", "none", "phone"]


def test_fetch_still_returns_a_picture_or_nothing(monkeypatch):
    monkeypatch.setenv("COCKAIGNE_RTSP_PASSWORD", "hunter2")
    seen = {}
    ok, jpeg = cv2.imencode(".jpg", np.full((90, 160, 3), 200, np.uint8))

    def get(url, params=None, timeout=None):
        seen.update(url=url, params=params)
        return Reply(content=jpeg.tobytes())

    monkeypatch.setattr(requests, "get", get)
    cam = {"name": "cam1", "ip": "192.168.1.101", "user": "admin"}
    assert fetch_still(cam, 3.0).shape == (90, 160, 3)
    assert seen["url"] == "http://192.168.1.101/cgi-bin/api.cgi"
    assert seen["params"]["cmd"] == "Snap" and seen["params"]["password"] == "hunter2"

    # A refusal arrives as text, not a picture.
    monkeypatch.setattr(requests, "get", lambda *a, **k: Reply(content=b'[{"cmd":"Snap","code":1}]'))
    assert fetch_still(cam, 3.0) is None

    def unreachable(*a, **k):
        raise requests.ConnectionError("http://admin:hunter2@192.168.1.101 unreachable")

    monkeypatch.setattr(requests, "get", unreachable)
    assert fetch_still(cam, 3.0) is None                # and the password went nowhere


# ---------- the replay entry point ----------

def test_replay_fills_actions_from_a_recording_and_its_video(tmp_path, monkeypatch, capsys):
    video = tmp_path / "cam1.avi"
    out = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"XVID"), 10, (320, 180))
    assert out.isOpened()
    for _ in range(100):
        out.write(np.full((180, 320, 3), 120, np.uint8))
    out.release()
    recording = tmp_path / "people.jsonl"
    with open(recording, "w") as f:
        for i in range(100):
            f.write(json.dumps(people_msg(i / 10, person(7, age=5.0 + i / 10))) + "\n")
    result = tmp_path / "out.jsonl"
    from cockaigne_sensing.actions import run
    monkeypatch.setattr("sys.argv", ["actions.run", str(recording), "--video", f"cam1={video}",
                                     "--out", str(result), "--model", "fake:phone"])
    run.main()
    messages = [json.loads(line) for line in open(result)]
    assert len(messages) == 100
    assert messages[0]["people"][0]["actions"]["phone"] == 0.0
    assert messages[-1]["people"][0]["actions"]["phone"] == 1.0
    assert messages[-1]["actions_health"]["alive"]
    assert "questions asked" in capsys.readouterr().out
