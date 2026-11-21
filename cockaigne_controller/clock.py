"""The 60-second cycle. The controller owns time; Resolume is never asked.

ClipClock remembers when the current clip was fired. The caller supplies
"now" on every question, so tests can run the clock at any speed and the
live loop can pass its event-loop time.

Each clip's sound starts audio_lead_s before its picture. That holds for
the very first clip too: at start-up the sound goes first and the first
picture follows when the lead has run.
"""
from __future__ import annotations


class ClipClock:
    def __init__(self, clip_s: float, audio_lead_s: float):
        self.clip_s = clip_s
        self.audio_lead_s = audio_lead_s
        self.started: float | None = None
        self._audio_done = False
        self._audio_at = 0.0

    def start(self, now: float) -> None:
        """The moment a clip was fired."""
        self.started = now
        self._audio_done = False

    def clip_due(self, now: float) -> bool:
        """True when the current clip has run its length. Before the first
        clip, true once the first sound has had its lead."""
        if self.started is None:
            return self._audio_done and now - self._audio_at >= self.audio_lead_s
        return now - self.started >= self.clip_s

    def audio_due(self, now: float) -> bool:
        """True once per clip, at the audio lead before the next fire, and
        at once when nothing has been fired yet."""
        if self.started is None or self._audio_done:
            return self.started is None and not self._audio_done
        return now - self.started >= self.clip_s - self.audio_lead_s

    def mark_audio(self, now: float) -> None:
        self._audio_done = True
        self._audio_at = now
