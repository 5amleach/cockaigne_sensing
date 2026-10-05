"""bus: moves messages between modules and out to the controller and data wall.

Contains the recorder (writes messages to a .jsonl file, development only),
the replayer (reads such a file back at its original pace), the WebSocket
publisher (publish.py; binds to the local machine only, enforced in code,
and rebroadcasts anything a client sends to every other client)
and the ledger (ledger.py; append-only, never wiped).

Serve a recording live:
    python -m cockaigne_sensing.bus.run recording.jsonl
"""
from .ledger import Ledger, LedgerEvents
from .publish import Publisher
from .record import Recorder, replay

__all__ = ["Ledger", "LedgerEvents", "Publisher", "Recorder", "replay"]
