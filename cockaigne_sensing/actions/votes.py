"""From the model's answers to a score per person per action.

One answer is weak evidence: a small model looking at a small infrared crop
is sometimes wrong. So each person keeps their last few answers, and an
action is only reported once the newest answers agree on it. It then stays
reported until the newest answers agree on something else, so one stray
answer in the middle neither starts an action nor ends one.

The score is the share of the kept answers that name the action: two out of
two is 1.0, three out of four is 0.75. Old answers are forgotten, so a
person who can no longer be asked fades to zero.
"""
from __future__ import annotations

from collections import deque


class Votes:
    """Each person's recent answers and the action they are held to be doing."""

    def __init__(self, cfg: dict):
        self.actions = list(cfg["enabled"])
        self.agree = cfg["agree_readings"]
        self.keep = cfg["history_readings"]
        self.stale_s = cfg["reading_stale_s"]
        self._answers: dict[int, deque] = {}   # person id -> (word, t), oldest first
        self._doing: dict[int, str] = {}       # person id -> the action currently held

    def add(self, person: int, word: str, t: float) -> None:
        """Record one answer and settle what the person is held to be doing."""
        answers = self._answers.setdefault(person, deque(maxlen=self.keep))
        answers.append((word, t))
        newest = [w for w, _ in list(answers)[-self.agree:]]
        if len(newest) == self.agree and len(set(newest)) == 1:
            if newest[0] in self.actions:
                self._doing[person] = newest[0]
            else:
                self._doing.pop(person, None)

    def unsettled(self, person: int) -> bool:
        """True when the newest answer differs from the one before it, which
        is when a second look is worth more than waiting the full interval."""
        answers = self._answers.get(person)
        return bool(answers) and len(answers) >= 2 and answers[-1][0] != answers[-2][0]

    def scores(self, person: int, now: float) -> dict[str, float]:
        """This person's score for every action, 0 to 1."""
        out = {action: 0.0 for action in self.actions}
        answers = self._answers.get(person)
        while answers and now - answers[0][1] > self.stale_s:
            answers.popleft()
        if not answers:
            self._doing.pop(person, None)
            return out
        doing = self._doing.get(person)
        if doing:
            share = sum(1 for word, _ in answers if word == doing) / len(answers)
            out[doing] = round(share, 2)
        return out

    def keep_only(self, present: set[int]) -> None:
        """Forget everyone who has left the room."""
        for person in [p for p in self._answers if p not in present]:
            del self._answers[person]
            self._doing.pop(person, None)
