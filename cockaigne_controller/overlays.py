"""Quick answers on the wall: falling chairs when someone sits, a pig when a phone is used.

A landscape move takes a minute, so a visitor cannot tell that what they did
counted. An overlay is a short clip on its own layer above the landscape. It
starts within a second or two of the sighting, plays once and clears, and the
landscape underneath carries on. Each overlay has a rest time, so the wall does
not fill with chairs while someone stays seated. Clip names, the action that
triggers each one and its rest time are under `overlays:` in
config/controller.yaml.
"""
from __future__ import annotations


class Overlays:
    """Decides, from each crowd message, which overlay clips to fire now."""

    def __init__(self, cfg: dict, layout: dict[str, tuple[int, int]]):
        self.items = []
        self.missing = []
        for name, item in (cfg or {}).items():
            where = layout.get(str(item["clip"]).strip().lower())
            if where is None:
                self.missing.append(f"{name}: clip {item['clip']!r} is not in the composition")
                continue
            self.items.append({"name": name, "action": item["action"],
                               "rest_s": float(item["rest_s"]), "says": item["says"],
                               "where": where, "last": None})

    def due(self, crowd: dict, now: float) -> list[dict]:
        """The overlays to fire for this crowd message: someone is doing the
        action now, and the overlay has rested long enough since it last ran."""
        doing = crowd.get("actions") or {}
        fire = []
        for item in self.items:
            if (doing.get(item["action"]) or 0) < 1:
                continue
            if item["last"] is not None and now - item["last"] < item["rest_s"]:
                continue
            item["last"] = now
            fire.append(item)
        return fire
