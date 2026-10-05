"""The ledger: an append-only record of what the installation did and saw.

One JSON line per event (see CONTRACTS.md, "Ledger entries"). The data wall
reads it; it is never wiped. Append is the only operation this code offers,
which is how "never wiped" is enforced rather than promised.

The bus writes three kinds itself: day_start when it comes up, ring_change
when the crowd state's ring moves, and action when a person's action score
crosses the reporting threshold. decision and outcome entries belong to the
controller, which appends lines to the same file from its own process; an
append of one line is safe from two programs at once.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Ledger:
    """Appends events to the ledger file. There is no way to remove one."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "a", encoding="utf-8")

    def append(self, kind: str, **fields) -> dict:
        entry = {"t_wall": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "kind": kind, **fields}
        self._f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        self._f.flush()
        return entry

    def close(self) -> None:
        self._f.close()


class LedgerEvents:
    """Watches the messages passing through the bus and writes the ledger
    entries the bus is responsible for.

    ring_change is written when a crowd message's ring differs from the last
    one seen (the room starts at ring 0, so the first entry is the first real
    change). action is written when a person's score for an action rises past
    count_min, once per continuous stretch of doing it.
    """

    def __init__(self, ledger: Ledger, count_min: float):
        self.ledger = ledger
        self.count_min = count_min
        self._ring = 0
        self._acting: set[tuple[int, str]] = set()

    def observe(self, msg: dict) -> None:
        stream = msg.get("stream")
        if stream == "crowd":
            ring = msg["ring_target"]
            if ring != self._ring:
                self.ledger.append("ring_change", ring=ring, n=msg["n"])
                self._ring = ring
        elif stream == "people":
            acting_now = set()
            for p in msg["people"]:
                for action, conf in p["actions"].items():
                    if conf >= self.count_min:
                        acting_now.add((p["id"], action))
                        if (p["id"], action) not in self._acting:
                            self.ledger.append("action", person=p["id"],
                                               action=action, conf=round(conf, 2))
            self._acting = acting_now
