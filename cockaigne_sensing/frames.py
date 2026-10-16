"""Serves each camera's newest frame to the data wall, from memory only.

A FrameStore holds the latest JPEG bytes per camera. A FrameServer offers
them over HTTP so the data wall page can draw the room: GET /frame/cam1.jpg
is the newest picture from cam1, GET /cameras lists the camera names. The
server binds to this machine only and refuses any other host, the same rule
as the bus. Frames live in memory and are overwritten by the next frame;
nothing here ever touches the disk.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FrameStore:
    """The latest JPEG bytes and arrival time per camera, in memory only."""

    def __init__(self, cameras: list[str] | None = None):
        self._lock = threading.Lock()
        self._frames: dict[str, tuple[bytes, float] | None] = {
            name: None for name in (cameras or [])}

    def put(self, camera: str, jpeg: bytes) -> None:
        with self._lock:
            self._frames[camera] = (jpeg, time.monotonic())

    def get(self, camera: str) -> tuple[bytes, float] | None:
        """The newest (jpeg, time) for a known camera, or None before its first frame."""
        with self._lock:
            return self._frames.get(camera)

    def known(self, camera: str) -> bool:
        with self._lock:
            return camera in self._frames

    def cameras(self) -> list[str]:
        with self._lock:
            return sorted(self._frames)


class _Handler(BaseHTTPRequestHandler):
    """One GET handler; the store is attached by FrameServer."""

    store: FrameStore

    def log_message(self, *args) -> None:
        pass  # one line per request would drown the terminal

    def _reply(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # The wall page is opened from a file, so the browser only draws the
        # frame when the server says any origin may read it. The server still
        # speaks only to this machine.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/cameras":
            self._reply(200, "application/json", json.dumps(self.store.cameras()).encode())
            return
        if self.path.startswith("/frame/") and self.path.endswith(".jpg"):
            camera = self.path[len("/frame/"):-len(".jpg")]
            if not self.store.known(camera):
                self._reply(404, "text/plain", b"unknown camera")
                return
            entry = self.store.get(camera)
            if entry is None:
                self._reply(503, "text/plain", b"no frame yet")
                return
            self._reply(200, "image/jpeg", entry[0])
            return
        self._reply(404, "text/plain", b"not found")


class FrameServer(threading.Thread):
    """Serves a FrameStore on 127.0.0.1 until stopped. Port 0 picks a free one."""

    def __init__(self, store: FrameStore, port: int, host: str = "127.0.0.1"):
        if host != "127.0.0.1":
            raise ValueError(f"the frame server binds to the local machine only, not {host!r}; "
                             "see the privacy rules in ARCHITECTURE.md")
        super().__init__(name="frame-server", daemon=True)
        handler = type("Handler", (_Handler,), {"store": store})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.port = self.httpd.server_address[1]

    def run(self) -> None:
        self.httpd.serve_forever()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
