"""Publishes messages over a WebSocket on the local machine, and only there.

Every client that connects (the controller, the data wall) receives every
message; a client that wants only one stream ignores the rest. Anything a
client sends back (the controller's clip decisions, Contract 3) is
rebroadcast to every other client, so the data wall needs one socket for
the whole installation. The bus refuses to bind to anything but the local
machine: nothing leaving the computer is a privacy rule enforced in code,
not by configuration habit.
"""
from __future__ import annotations

import asyncio
import json

from websockets.asyncio.server import serve

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class Publisher:
    """A WebSocket fan-out: start() it, then publish() each message."""

    def __init__(self, host: str, port: int):
        if host not in LOCAL_HOSTS:
            raise ValueError(f"the bus binds to the local machine only, not {host!r}; "
                             "see the privacy rules in ARCHITECTURE.md")
        self.host = host
        self.port = port
        self.clients: set = set()
        self._server = None

    async def start(self) -> int:
        """Open the socket. Returns the port actually bound (port 0 asks the
        system for a free one, which the tests use)."""
        self._server = await serve(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def _handle(self, websocket) -> None:
        """One connected client: remember it until it goes away, and pass on
        whatever it sends. The bus does not inspect a client's messages; it
        carries them, one trusted process to another on the same machine."""
        self.clients.add(websocket)
        try:
            async for data in websocket:
                await self._send_all(data, exclude=websocket)
        finally:
            self.clients.discard(websocket)

    async def publish(self, message: dict) -> None:
        """Send one message to every connected client."""
        await self._send_all(json.dumps(message, separators=(",", ":")))

    async def _send_all(self, data: str, exclude=None) -> None:
        """Send to every client but the excluded one. A client that has died
        mid-send is dropped without disturbing the others."""
        targets = [c for c in list(self.clients) if c is not exclude]
        if targets:
            await asyncio.gather(*(c.send(data) for c in targets),
                                 return_exceptions=True)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
