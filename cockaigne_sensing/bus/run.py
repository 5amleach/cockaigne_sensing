"""Serve a recording over the WebSocket bus, as the gallery would see it live.

Usage:
    python -m cockaigne_sensing.bus.run recording.jsonl [--config config/sensing.yaml]
                                        [--record copy.jsonl] [--loop]

Reads any recording (tracks, people, crowd, mixed), re-emits each message on
ws://127.0.0.1:8765 when its time comes due, and appends ledger entries
(day_start at startup, then ring_change and action as they happen). --loop
starts the recording again at the end, for leaving a data wall running on a
desk. --record also writes every published message to a file; recording is
for development only and the gallery configuration never passes it.

Stop it with Ctrl-C.
"""
from __future__ import annotations

import argparse
import asyncio
import time

from ..config import load
from .ledger import Ledger, LedgerEvents
from .publish import Publisher
from .record import Recorder, replay


async def serve_recording(path: str, cfg: dict, record: str | None = None,
                          loop: bool = False) -> None:
    bus_cfg = cfg["bus"]
    publisher = Publisher(bus_cfg["host"], bus_cfg["port"])
    await publisher.start()
    ledger = Ledger(bus_cfg["ledger_path"])
    events = LedgerEvents(ledger, cfg["actions"]["count_min"])
    ledger.append("day_start", note=f"bus serving {path}")
    recorder = Recorder(record) if record else None
    print(f"serving ws://{publisher.host}:{publisher.port} from {path}"
          + (" (looping)" if loop else ""))
    served = 0
    try:
        while True:
            start = time.monotonic()
            t0 = None
            passed = 0
            for msg in replay(path):
                if t0 is None:
                    t0 = msg["t"]
                delay = (msg["t"] - t0) - (time.monotonic() - start)
                if delay > 0:
                    await asyncio.sleep(delay)
                events.observe(msg)
                await publisher.publish(msg)
                if recorder:
                    recorder.write(msg)
                passed += 1
            served += passed
            if passed == 0:
                print(f"{path} holds no messages; stopping")
                break
            if not loop:
                print(f"recording finished; served {served} messages")
                break
    finally:
        if recorder:
            recorder.close()
        ledger.close()
        await publisher.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording")
    ap.add_argument("--config")
    ap.add_argument("--record", help="also write every published message to this file (development only)")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args()
    try:
        asyncio.run(serve_recording(args.recording, load(args.config),
                                    record=args.record, loop=args.loop))
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
