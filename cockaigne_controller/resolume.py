"""Talks to Resolume: read the composition, fire a clip, set a volume.

The composition (which clip sits where) is read once at start-up over
Resolume's REST API; no clip index is ever typed by hand. Clips are fired
and volumes set over OSC on UDP. The controller never asks Resolume where
the playhead is: it owns the clock. Both ports are on the local machine.
"""
from __future__ import annotations

import requests
from pythonosc.udp_client import SimpleUDPClient


def layout_from_composition(data: dict) -> dict[str, tuple[int, int]]:
    """Clip name -> (layer, clip index), both 1-based as OSC counts them.

    Resolume's JSON nests the name as {"name": {"value": ...}}; a plain
    string is accepted too so a saved layout file can be simpler.
    """
    layout: dict[str, tuple[int, int]] = {}
    for layer_i, layer in enumerate(data.get("layers", []), start=1):
        for clip_i, clip in enumerate(layer.get("clips", []), start=1):
            name = clip.get("name")
            if isinstance(name, dict):
                name = name.get("value")
            if name:
                layout.setdefault(str(name).strip().lower(), (layer_i, clip_i))
    return layout


def connected_from_layer(data: dict) -> int | None:
    """The 1-based index of the connected clip in one layer's JSON, or None.

    Resolume reports connection as a parameter whose value is a boolean or
    a string beginning "Connected"; both readings are accepted."""
    for i, clip in enumerate(data.get("clips", []), start=1):
        value = clip.get("connected")
        if isinstance(value, dict):
            value = value.get("value")
        if value is True or (isinstance(value, str)
                             and value.lower().startswith("connected")):
            return i
    return None


class Resolume:
    """One OSC client and one REST endpoint, both local."""

    def __init__(self, host: str, osc_port: int, rest_port: int):
        self.host = host
        self.rest_port = rest_port
        self._osc = SimpleUDPClient(host, osc_port)

    def read_layout(self) -> dict[str, tuple[int, int]]:
        r = requests.get(f"http://{self.host}:{self.rest_port}/api/v1/composition",
                         timeout=5)
        r.raise_for_status()
        return layout_from_composition(r.json())

    def connected_clip(self, layer: int) -> int | None:
        """Which clip the layer reports as connected, 1-based, over REST."""
        r = requests.get(f"http://{self.host}:{self.rest_port}/api/v1/composition"
                         f"/layers/{layer}", timeout=1)
        r.raise_for_status()
        return connected_from_layer(r.json())

    def fire_clip(self, layer: int, index: int) -> bool:
        """Send the connect message. Never raises; says whether it was sent."""
        try:
            self._osc.send_message(f"/composition/layers/{layer}/clips/{index}/connect", 1)
            return True
        except Exception:
            return False

    def set_volume(self, layer: int, volume: float) -> bool:
        """Send a volume change. Never raises; says whether it was sent."""
        try:
            self._osc.send_message(f"/composition/layers/{layer}/audio/volume", float(volume))
            return True
        except Exception:
            return False
