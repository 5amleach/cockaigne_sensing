"""A stand-in for Resolume: listens on the OSC port and prints what arrives.

Run it in one terminal with Resolume closed, run the controller in another,
and every clip fire and volume change is printed as it happens. The tests
use the same listener on a system-chosen port.

Usage:
    python -m cockaigne_controller.fake_resolume [--port 7000]
"""
from __future__ import annotations

import argparse
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer


class FakeResolume:
    """Collects (address, args) for every OSC message it receives."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, quiet: bool = False):
        self.quiet = quiet
        self.received: list[tuple[str, tuple]] = []
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._on_message)
        self._server = ThreadingOSCUDPServer((host, port), dispatcher)
        self.port = self._server.server_address[1]
        self._thread: threading.Thread | None = None

    def _on_message(self, address: str, *args) -> None:
        self.received.append((address, args))
        if not self.quiet:
            print(f"{address} {' '.join(str(a) for a in args)}")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=7000)
    args = ap.parse_args()
    fake = FakeResolume(port=args.port)
    print(f"fake Resolume listening on udp {args.port}; Ctrl-C to stop")
    try:
        fake._server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
