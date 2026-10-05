"""Audio stems, stubbed behind one function as the brief asks.

The full design: four stems per arm on four audio layers, in two banks so
an arm change can crossfade, the outgoing bank ramping down and the
incoming up over the five-second lead, stem volumes within a bank following
the ring. For now set_stems sets bank A's four layers to one volume that
follows the ring; the banks and the ramp come later.
"""
from __future__ import annotations


def set_stems(resolume, cfg: dict, ring: int) -> None:
    """Called once per cycle at the audio lead, with the incoming decision's ring."""
    volume = ring / cfg["map"]["rings"]
    for layer in cfg["resolume"]["audio_bank_a"]:
        resolume.set_volume(layer, volume)
