"""Record messages to a file and play them back.

The file format is one JSON message per line (see CONTRACTS.md, "Recording
format"). Any module can be fed from such a file instead of from the module
above it, which is how the system is tested at a desk.

Recording is for development only. Nothing in the gallery configuration
creates a Recorder.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterator


class Recorder:
    """Appends messages to a .jsonl file. Call write() for each message, close() at the end."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "a", encoding="utf-8")

    def write(self, message: dict) -> None:
        self._f.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._f.flush()  # a crash loses nothing already written

    def close(self) -> None:
        self._f.close()


def replay(path: str | Path, stream: str | None = None, realtime: bool = False) -> Iterator[dict]:
    """Yield the messages in a recording, in order.

    stream, if given, keeps only messages of that kind ("tracks", "people", ...).
    realtime, if true, waits between messages so they arrive at the pace they
    were recorded, which is what a live consumer expects.
    """
    start_wall = time.monotonic()
    start_t = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if stream and msg.get("stream") != stream:
                continue
            if realtime:
                if start_t is None:
                    start_t = msg["t"]
                due = start_wall + (msg["t"] - start_t)
                delay = due - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            yield msg
