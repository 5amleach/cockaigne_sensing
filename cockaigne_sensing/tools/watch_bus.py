"""Watch the bus in plain text: one line a second, until the data wall exists.

Usage:
    python -m cockaigne_sensing.tools.watch_bus [--url ws://127.0.0.1:8765]

Connects to the bus like any other client and prints the latest state:
headcount, ring, the Coherence Index (cohesion_relational), the smoothed
score, the reservoir, the mood tally, and each camera's health. A dropped
bus is retried every two seconds. Ctrl-C to stop. It writes nothing to disk.
"""
from __future__ import annotations

import argparse
import asyncio
import json


def format_line(crowd: dict | None, cameras: dict | None) -> str:
    """One readable line from the latest crowd state and camera health."""
    if crowd is None:
        return "waiting for a crowd message..."
    moods = crowd.get("moods", {})
    parts = [
        f"n={crowd['n']}",
        f"ring={crowd['ring_target']}",
        f"C={crowd.get('cohesion_relational', 0.0):.2f}",
        f"smooth={crowd['cohesion_smooth']:.2f}",
        f"reservoir={crowd.get('accumulator', 0.0):.2f}",
        " ".join(f"{m} {moods.get(m, 0)}" for m in ("happy", "sad", "bored", "annoyed")),
    ]
    if cameras:
        parts.append(" ".join(
            f"{name} {'ok' if c.get('alive') else 'LOST'} {c.get('age_s', 0):.1f}s"
            for name, c in sorted(cameras.items())))
    return "  |  ".join(parts)


async def watch(url: str) -> None:
    from websockets.asyncio.client import connect
    crowd, cameras = None, None
    while True:
        try:
            async with connect(url) as ws:
                print(f"watching {url}")

                async def read():
                    nonlocal crowd, cameras
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except (json.JSONDecodeError, TypeError, ValueError):
                            continue
                        if msg.get("stream") == "crowd":
                            crowd = msg
                        elif msg.get("stream") == "people" and "cameras" in msg:
                            cameras = msg["cameras"]

                reader = asyncio.create_task(read())
                try:
                    while not reader.done():
                        print(format_line(crowd, cameras))
                        await asyncio.sleep(1.0)
                finally:
                    reader.cancel()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        print("bus away; retrying in 2 s")
        await asyncio.sleep(2.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="ws://127.0.0.1:8765")
    args = ap.parse_args()
    try:
        asyncio.run(watch(args.url))
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
