"""The decision loop: crowd state in from the bus, clip decisions out.

Every 60 seconds (the clock's clip length) the controller decides where the
wall goes next: the ring comes from `ring_target` in the latest crowd state
and nothing else, and the arm comes from the arm chooser. At the audio lead
(5 seconds before the video) the decision is made and the stems are started;
at the boundary the clip is fired, the decision is published back through
the bus for the data wall, and a ledger entry is appended.

Build step 3: the arm is fixed from config (controller.default_arm). The
bandit replaces `choose_arm` in build step 4.

Run it against the fake room and the fake Resolume:
    python -m cockaigne_sensing.bus.run fake_people_and_crowd.jsonl   (terminal 1)
    python -m cockaigne_controller.fake_resolume                      (terminal 2)
    python -m cockaigne_controller.loop --layout pool.json            (terminal 3)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import time

# Recorder and Ledger are the bus module's public face; the controller
# shares its ledger file by design (BRIEF.md, "The ledger").
from cockaigne_sensing.bus import Ledger, Recorder

from .clipmap import BARREN, ClipMap, node_name
from .clock import ClipClock
from .config import load
from .resolume import Resolume, layout_from_composition


class Controller:
    """Holds the wall's position and turns crowd state into decisions.

    decide() is pure bookkeeping plus the map: it never touches the network,
    so the tests drive it directly.
    """

    def __init__(self, cfg: dict, clipmap: ClipMap, layout: dict):
        self.cfg = cfg
        self.map = clipmap
        self.layout = layout
        self.arms = cfg["map"]["arms"]
        self.node = BARREN
        self.ring = 0
        self.n = 0
        self.n_smooth = 0.0
        self.cohesion = 0.0
        self._t_prev: float | None = None

    # --- crowd state ---

    def observe(self, crowd: dict) -> None:
        self.ring = crowd["ring_target"]
        self.n = crowd["n"]
        self.cohesion = crowd["cohesion_smooth"]
        t = crowd["t"]
        dt = 0.0 if self._t_prev is None else max(0.0, min(t - self._t_prev, 5.0))
        self._t_prev = t
        tau = self.cfg["occupancy"]["smooth_window_s"]
        alpha = 1.0 - math.exp(-dt / tau) if dt > 0 else 0.0
        self.n_smooth += alpha * (self.n - self.n_smooth)

    def context(self) -> str:
        """The occupancy band, from the smoothed headcount."""
        band = self.cfg["occupancy"]["bands"][0][1]
        for edge, name in self.cfg["occupancy"]["bands"]:
            if self.n_smooth >= edge:
                band = name
        return band

    # --- choosing ---

    def choose_arm(self) -> tuple[str, str]:
        """The arm letter and the reason. Fixed from config until the bandit
        (build step 4) takes over."""
        wanted = self.cfg["controller"]["default_arm"]
        letter = next(l for l, name in self.arms.items() if name == wanted)
        return letter, "ring"

    def _probe_from(self, frm: str, arm_letter: str) -> str:
        """Where to go when staying put and the node has no loop clip.

        From Barren, probe out to the chosen arm's Ring 1 and come back next
        cycle (the brief). A node off Barren without a loop bounces to a
        same-arm neighbour, downward by preference so the wall never shows a
        ring the crowd has not earned, except at Ring 1, where bouncing down
        would blink to Barren, so it bounces up instead. The brief gives
        loops only to Ring 4 and Barren; this bounce is the stopgap and is
        flagged in the build report.
        """
        if frm == BARREN:
            return node_name(arm_letter, 1)
        letter, ring = frm[0], int(frm[1])
        order = (ring - 1, ring + 1) if ring >= 2 else (ring + 1, ring - 1)
        for r in order:
            candidate = BARREN if r == 0 else node_name(letter, r)
            if r <= self.map.rings and self.map.clip_for(frm, candidate):
                return candidate
        return self.map.neighbours(frm)[0]

    def decide(self, t: float) -> tuple[dict, tuple[int, int]]:
        """One decision: the Contract 3 message and the (layer, index) to fire."""
        arm_letter, base_reason = self.choose_arm()
        target = BARREN if self.ring == 0 else node_name(arm_letter, self.ring)
        frm = self.node
        if target == frm:
            if self.map.clip_for(frm, frm):
                to, reason = frm, "loop"
            else:
                to, reason = self._probe_from(frm, arm_letter), "probe"
        elif self.map.clip_for(frm, target):
            to, reason = target, base_reason
        else:
            to, reason = self.map.next_step(frm, target), "path"
        clip = self.map.clip_for(frm, to)
        layer, index = self.layout[clip]
        self.node = to
        arm_name = "barren" if to == BARREN else self.arms[to[0]]
        decision = {
            "stream": "decision", "t": round(t, 2),
            "from": frm, "to": to, "clip": clip, "resolume_index": index,
            "arm": arm_name, "reason": reason,
            "context": self.context(), "ring_target": self.ring,
        }
        return decision, (layer, index)


def load_layout(path: str) -> dict[str, tuple[int, int]]:
    """A saved layout for running without Resolume: a JSON list of clip names
    (indices assigned in order on layer 1), a {name: [layer, index]} map, or
    a saved copy of the REST composition."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {str(n).strip().lower(): (1, i) for i, n in enumerate(data, start=1)}
    if "layers" in data:
        return layout_from_composition(data)
    return {str(k).strip().lower(): (int(v[0]), int(v[1])) for k, v in data.items()}


async def run(cfg: dict, layout_path: str | None = None, record: str | None = None) -> None:
    from websockets.asyncio.client import connect

    res_cfg = cfg["resolume"]
    resolume = Resolume(res_cfg["host"], res_cfg["osc_port"], res_cfg["rest_port"])
    layout = load_layout(layout_path) if layout_path else resolume.read_layout()
    clipmap = ClipMap(list(layout), cfg["map"]["arms"], cfg["map"]["rings"])
    missing = clipmap.missing()
    if missing:
        for m in missing:
            print(f"missing: {m}")
        raise SystemExit(f"{len(missing)} gaps in the clip pool; refusing to start")

    controller = Controller(cfg, clipmap, layout)
    clock = ClipClock(cfg["clock"]["clip_s"], cfg["clock"]["audio_lead_s"])
    ledger = Ledger(cfg["ledger_path"])
    recorder = Recorder(record) if record else None
    pending = None

    async with connect(cfg["bus"]["url"]) as ws:
        print(f"controller on {cfg['bus']['url']}, {len(layout)} clips, "
              f"{len(clipmap.moves)} moves, {len(clipmap.loops)} loops")

        async def read_bus():
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("stream") == "crowd":
                    controller.observe(msg)

        from websockets.exceptions import ConnectionClosed

        reader = asyncio.create_task(read_bus())
        try:
            while True:
                now = time.monotonic()
                if clock.started is None or clock.clip_due(now):
                    if pending is None:  # the very first clip has no audio lead
                        pending = controller.decide(now)
                    decision, (layer, index) = pending
                    pending = None
                    resolume.fire_clip(layer, index)
                    try:
                        await ws.send(json.dumps(decision))
                    except ConnectionClosed:
                        print("bus went away; stopping")
                        return
                    ledger.append("decision", arm=decision["arm"],
                                  ring=decision["ring_target"], n=controller.n,
                                  clip=decision["clip"], reason=decision["reason"])
                    if recorder:
                        recorder.write(decision)
                    clock.start(now)
                    print(f"fired {decision['clip']:>8}  {decision['from']} -> "
                          f"{decision['to']}  ring {decision['ring_target']}  "
                          f"({decision['reason']}, {decision['context']})")
                elif clock.audio_due(now):
                    pending = controller.decide(now)
                    # Audio stems for the incoming arm start here (build step 6).
                    clock.mark_audio()
                await asyncio.sleep(cfg["controller"]["tick_s"])
        finally:
            reader.cancel()
            ledger.close()
            if recorder:
                recorder.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--layout", help="JSON layout file, for running without Resolume's REST API")
    ap.add_argument("--record", help="also write every decision to this file (development only)")
    args = ap.parse_args()
    try:
        asyncio.run(run(load(args.config), layout_path=args.layout, record=args.record))
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
