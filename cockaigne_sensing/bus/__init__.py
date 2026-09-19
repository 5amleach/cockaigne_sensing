"""bus: moves messages between modules and out to the controller and data wall.

Contains the recorder (writes messages to a .jsonl file, development only),
the replayer (reads such a file back at its original pace), the WebSocket
publisher (not yet written) and the ledger (not yet written).
"""
from .record import Recorder, replay

__all__ = ["Recorder", "replay"]
