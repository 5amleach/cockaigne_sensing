"""The action sense at work: who to ask about, the asking, and the scores.

A worker thread runs beside the launcher's main loop and never holds it up.
The main loop offers it the newest people list and takes back the current
scores; the worker, in its own time, picks whoever is due, gets close-up
crops of them from one camera, and asks the model about each.

The graphics card that answers these questions also plays the video wall,
so the worker asks at most max_asks_per_s questions a second however full
the room is, one at a time. In a quiet room everyone is asked every
interval_s. In a full room the gap between questions to any one person
stretches by itself.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .votes import Votes


def due_people(people: list[dict], asked_at: dict, votes: Votes, now: float,
               cfg: dict) -> list[dict]:
    """The people who should be asked about now, longest-waiting first.

    A person no camera saw this step is skipped, and so is a new arrival.
    A person whose newest answer differs from the one before is due again
    after recheck_s, so a first "phone" is checked at once instead of
    waiting the full interval.
    """
    due = []
    for p in people:
        if not p.get("view") or p["age"] < cfg["min_age_s"]:
            continue
        last = asked_at.get(p["id"])
        wait = cfg["recheck_s"] if votes.unsettled(p["id"]) else cfg["interval_s"]
        if last is None or now - last >= wait:
            due.append((float("-inf") if last is None else last, p["id"], p))
    return [p for _, _, p in sorted(due, key=lambda entry: entry[:2])]


class ActionsWorker(threading.Thread):
    """Asks the model about people in the room and keeps their scores."""

    def __init__(self, actions_cfg: dict, closeups, model, log,
                 clock=time.monotonic, sleep=time.sleep):
        """clock and sleep are the machine's own when live; a replay passes
        ones that follow the recording's time instead."""
        super().__init__(name="actions", daemon=True)
        self.cfg = actions_cfg
        self.closeups, self.model, self.log = closeups, model, log
        self.clock, self.sleep = clock, sleep
        self.votes = Votes(actions_cfg)
        self.asked = 0                      # questions put to the model so far
        self._lock = threading.Lock()
        self._people: list[dict] = []       # the newest people list, only the fields needed
        self._asked_at: dict[int, float] = {}
        self._next_ask = float("-inf")
        self._last_answer: float | None = None
        self._warned_at = clock()
        self._halt = threading.Event()
        self._blank = np.zeros((64, 64, 3), np.uint8)

    def offer(self, people_msg: dict) -> None:
        """Take note of who is in the room now and where each was last seen."""
        people = [{"id": p["id"], "age": p["age"], "view": p.get("view")}
                  for p in people_msg["people"]]
        with self._lock:
            self._people = people

    def fill(self, people_msg: dict) -> dict:
        """Write the current scores into a people message, with the sense's
        own health beside the cameras' so a reader can tell "nobody is on a
        phone" from "I cannot tell"."""
        now = self.clock()
        with self._lock:
            for p in people_msg["people"]:
                p["actions"].update(self.votes.scores(p["id"], now))
            people_msg["actions_health"] = self.health(now)
        return people_msg

    def health(self, now: float) -> dict:
        """Alive means the model answered a question within fail_warn_s."""
        if self._last_answer is None:
            return {"alive": False, "age_s": None}
        age = now - self._last_answer
        return {"alive": age <= self.cfg["fail_warn_s"], "age_s": round(age, 1)}

    def step(self) -> int:
        """One round: pick who is due, get their crops from one camera, ask
        about each. Returns how many people it tried to ask about."""
        now = self.clock()
        with self._lock:
            present = {p["id"] for p in self._people}
            self.votes.keep_only(present)
            self._asked_at = {i: t for i, t in self._asked_at.items() if i in present}
            due = due_people(self._people, self._asked_at, self.votes, now, self.cfg)
        if not due:
            self._heartbeat(now)
            return 0
        camera = due[0]["view"]["camera"]
        batch = [p["id"] for p in due if p["view"]["camera"] == camera]
        batch = batch[:self.cfg["batch_max"]]
        picked: list[int] = []

        def fresh_boxes():
            """Called once the picture has arrived, so the boxes are current."""
            with self._lock:
                views = {p["id"]: p["view"] for p in self._people
                         if p.get("view") and p["view"]["camera"] == camera}
            picked.extend(i for i in batch if i in views)
            size = (views[picked[0]]["w"], views[picked[0]]["h"]) if picked else (1, 1)
            return [views[i]["box"] for i in picked], size

        crops = self.closeups.crops(camera, fresh_boxes)
        with self._lock:
            # Everyone in the batch counts as asked even if no picture came,
            # so a camera that will not answer is retried at the usual pace.
            for person in batch:
                self._asked_at[person] = now
        if crops is None:
            self._warn(now, f"no close-up picture from {camera}")
            return len(batch)
        for person, crop in zip(picked, crops):
            if crop is None or self._halt.is_set():
                continue
            word, t = self._question(crop)
            with self._lock:
                self._asked_at[person] = t
                if word is not None:
                    self.votes.add(person, word, t)
        self._warn(self.clock())
        return len(batch)

    def _question(self, crop: np.ndarray) -> tuple[str | None, float]:
        """Put one question, no sooner than the budget allows."""
        wait = self._next_ask - self.clock()
        if wait > 0:
            self.sleep(wait)
        self._next_ask = self.clock() + 1.0 / self.cfg["max_asks_per_s"]
        word = self.model.ask(crop)
        self.asked += 1
        t = self.clock()
        if word is not None:
            self._last_answer = t
        return word, t

    def _heartbeat(self, now: float) -> None:
        """With nobody to ask about, a blank question now and then proves the
        model is alive and keeps it loaded, so an empty room still reports a
        working sense and the first visitor does not wait for a cold start."""
        if self._last_answer is None or now - self._last_answer >= self.cfg["heartbeat_s"]:
            self._question(self._blank)
            self._warn(self.clock())

    def _warn(self, now: float, problem: str | None = None) -> None:
        """Say what is wrong, at most once every fail_warn_s."""
        if problem is None and not self.health(now)["alive"]:
            problem = "the action model is not answering; scores are fading to zero"
        if problem and now - self._warned_at >= self.cfg["fail_warn_s"]:
            self._warned_at = now
            self.log.warning(f"actions: {problem}")

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                busy = self.step()
            except Exception:   # this sense must not die quietly, nor take the chain with it
                self.log.exception("actions: a round failed")
                busy = 0
            if not busy:
                self._halt.wait(self.cfg["idle_s"])
