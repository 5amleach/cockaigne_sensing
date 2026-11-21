"""Sound: one mastered file per clip, started ahead of its picture.

Karl Willebrant's sound for a clip is twelve seconds longer than the clip:
six seconds of fade-in that play under the end of the clip before, and six
of fade-out that play under the start of the clip after. So two sounds
overlap around every cut, and one layer cannot play both. Two sound layers
take turns: each new sound starts on the layer the last one is not using.

A clip's sound sits in the same column as the clip, on both sound layers;
`load_sounds` puts them there. The controller starts the sound at the
audio lead and the picture when the lead has run. This replaces the stem
banks of the brief, because the delivered sound is one mix per clip.
"""
from __future__ import annotations


class Sound:
    """Remembers whose turn it is among the sound layers."""

    def __init__(self, layers: list[int]):
        self.layers = list(layers)
        self._turn = 0

    def start(self, resolume, index: int) -> int | None:
        """Start the sound in column `index` on the next layer in turn.
        Returns the layer used, or None when there are no sound layers or
        the message could not be sent."""
        if not self.layers:
            return None
        layer = self.layers[self._turn]
        self._turn = (self._turn + 1) % len(self.layers)
        return layer if resolume.fire_clip(layer, index) else None
