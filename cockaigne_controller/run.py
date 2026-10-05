"""Run the controller: the live loop around the decision logic in loop.py.

Usage:
    python -m cockaigne_controller.run [--config ...] [--layout pool.json] [--record out.jsonl]

Reads crowd state from the bus, fires one clip per cycle in Resolume,
publishes each decision back through the bus and appends ledger entries.
Fail-safes, all logged to the terminal and to controller.log_path:

- Resolume's REST not ready at start-up: retried every reconnect_s.
- A clip pool with gaps stops the controller before the first fire.
- Crowd state stale (its own clock stuck for blind_after_s): the ring steps
  down from the displayed position each cycle until Barren.
- Bus connection down: retried every reconnect_s while the clock keeps
  firing; unpublished decisions are logged. A malformed or incomplete bus
  message is logged and ignored; no message can kill the reader.
- A fire that Resolume does not confirm is retried once, the decision is
  published with confirmed false, and the displayed position stays put.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import math
import time

# Recorder and Ledger are the bus module's public face; the controller
# shares the ledger file by design (BRIEF.md, "The ledger").
from cockaigne_sensing.bus import Ledger, Recorder

from . import audio
from .clipmap import ClipMap
from .clock import ClipClock
from .config import load
from .loop import Controller
from .resolume import Resolume, layout_from_composition

CROWD_FIELDS = ("t", "n", "n_smooth", "ring_target", "cohesion_smooth")


def make_logger(path: str) -> logging.Logger:
    log = logging.getLogger("cockaigne_controller")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(path)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def load_layout(path: str) -> dict[str, tuple[int, int]]:
    """A saved layout for running without Resolume: a JSON list of clip
    names (indices assigned in order on layer 1), a {name: [layer, index]}
    map, or a saved copy of the REST composition."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {str(n).strip().lower(): (1, i) for i, n in enumerate(data, start=1)}
    if "layers" in data:
        return layout_from_composition(data)
    return {str(k).strip().lower(): (int(v[0]), int(v[1])) for k, v in data.items()}


def valid_crowd(msg: dict) -> bool:
    """A crowd message the controller may act on: the required fields are
    present and are finite numbers."""
    return all(isinstance(msg.get(k), (int, float)) and math.isfinite(msg[k])
               for k in CROWD_FIELDS)


async def fire_confirmed(resolume: Resolume, layer: int, index: int,
                         log: logging.Logger, confirm_s: float, poll_s: float) -> bool:
    """Fire, then check over REST that the layer connected the intended clip.
    Returns whether the clip can be taken as showing. Never raises: a failed
    OSC send is retried once; an unreachable REST counts the fire as shown
    (there is nothing to disagree with); a REST that disagrees after one
    retry returns False and the caller keeps the displayed position put."""
    if not resolume.fire_clip(layer, index):
        log.warning(f"OSC send for layer {layer} clip {index} failed; retrying once")
        if not resolume.fire_clip(layer, index):
            log.warning("OSC send failed twice; clip not fired")
            return False
    if confirm_s <= 0:
        return True
    got = None
    for attempt in (1, 2):
        deadline = time.monotonic() + confirm_s
        while time.monotonic() < deadline:
            await asyncio.sleep(poll_s)
            try:
                got = await asyncio.to_thread(resolume.connected_clip, layer)
            except Exception as e:
                log.warning(f"cannot confirm over REST ({e}); counting the fire as shown")
                return True
            if got == index:
                return True
        if attempt == 1:
            log.warning(f"layer {layer} shows clip {got}, wanted {index}; firing again")
            if not resolume.fire_clip(layer, index):
                log.warning("OSC send failed on the retry; clip not fired")
                return False
        else:
            log.warning(f"layer {layer} still shows clip {got}, wanted {index}")
    return False


class BusLink:
    """Keeps one connection to the bus alive, reconnecting forever. No bus
    message, however malformed, can end the reader: bad ones are logged and
    ignored, and any connection-level error leads back to the retry loop."""

    def __init__(self, url: str, controller: Controller, log: logging.Logger,
                 reconnect_s: float):
        self.url = url
        self.controller = controller
        self.log = log
        self.reconnect_s = reconnect_s
        self.ws = None

    async def keep_connected(self) -> None:
        from websockets.asyncio.client import connect
        while True:
            try:
                async with connect(self.url) as ws:
                    self.ws = ws
                    self.log.info(f"bus connected at {self.url}")
                    async for raw in ws:
                        self._take(raw)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.log.warning(f"bus reader error: {e!r}")
            self.ws = None
            self.log.warning(f"bus unreachable; retrying in {self.reconnect_s} s")
            await asyncio.sleep(self.reconnect_s)

    def _take(self, raw) -> None:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            self.log.warning(f"unreadable message on the bus, ignored: {raw[:120]!r}")
            return
        if not isinstance(msg, dict) or msg.get("stream") != "crowd":
            return
        if not valid_crowd(msg):
            self.log.warning(f"crowd message missing or bad fields, ignored: {str(msg)[:120]}")
            return
        self.controller.observe(msg, time.monotonic())

    async def send(self, message: dict) -> None:
        if self.ws is None:
            self.log.warning(f"bus away; decision {message['clip']} fired but not published")
            return
        try:
            await self.ws.send(json.dumps(message))
        except Exception:
            self.log.warning(f"bus closed mid-send; decision {message['clip']} not published")


async def read_layout_until_ready(resolume: Resolume, log: logging.Logger,
                                  retry_s: float) -> dict:
    while True:
        try:
            return resolume.read_layout()
        except Exception as e:
            log.warning(f"Resolume REST not ready ({e}); retrying in {retry_s} s")
            await asyncio.sleep(retry_s)


async def run(cfg: dict, layout_path: str | None = None, record: str | None = None) -> None:
    log = make_logger(cfg["controller"]["log_path"])
    res_cfg = cfg["resolume"]
    resolume = Resolume(res_cfg["host"], res_cfg["osc_port"], res_cfg["rest_port"])
    if layout_path:
        layout = load_layout(layout_path)
        confirm_s = 0.0
        log.info("layout from file; fire confirmation off (no REST to ask)")
    else:
        layout = await read_layout_until_ready(resolume, log, cfg["controller"]["reconnect_s"])
        confirm_s = res_cfg["confirm_s"]
    # The map is built from the video layer only; stems and idents elsewhere
    # in the composition cannot shadow a move clip.
    names = [n for n, (layer, _) in layout.items() if layer == res_cfg["video_layer"]] \
        if not layout_path else list(layout)
    clipmap = ClipMap(names, cfg["map"]["arms"], cfg["map"]["rings"])
    missing = clipmap.missing()
    if missing:
        for m in missing:
            log.error(f"missing: {m}")
        raise SystemExit(f"{len(missing)} gaps in the clip pool; refusing to start")

    controller = Controller(cfg, clipmap, layout)
    clock = ClipClock(cfg["clock"]["clip_s"], cfg["clock"]["audio_lead_s"])
    ledger = Ledger(cfg["ledger_path"])
    recorder = Recorder(record) if record else None
    link = BusLink(cfg["bus"]["url"], controller, log, cfg["controller"]["reconnect_s"])
    link_task = asyncio.create_task(link.keep_connected())
    pending = None
    was_blind = False
    log.info(f"{len(layout)} clips, {len(clipmap.moves)} moves, {len(clipmap.loops)} loops")

    try:
        while True:
            now = time.monotonic()
            controller.ensure_day(datetime.date.today(), ledger)
            blind = controller.is_blind(now)
            if blind and not was_blind:
                log.warning(f"crowd clock stale for {cfg['controller']['blind_after_s']} s; "
                            "running blind, stepping the displayed ring down each cycle")
            if not blind and was_blind:
                log.info("crowd state is back")
            was_blind = blind
            if clock.started is None or clock.clip_due(now):
                if clock.started is not None:
                    late = now - clock.started - clock.clip_s
                    if late > 1.0:
                        log.warning(f"firing {late:.1f} s late")
                if pending is None:  # the very first clip has no audio lead
                    pending = controller.decide(now)
                decision, (layer, index) = pending
                pending = None
                clock.start(now)
                controller.settle_reward()  # the previous clip ran its full length
                ok = await fire_confirmed(resolume, layer, index, log,
                                          confirm_s, res_cfg["confirm_poll_s"])
                decision["confirmed"] = ok
                if ok:
                    controller.confirm_fired(decision, now)
                else:
                    log.warning(f"fire of {decision['clip']} unconfirmed; "
                                f"the wall stays at {controller.displayed}")
                await link.send(decision)
                if controller.last_outcome:
                    ledger.append("outcome", **controller.last_outcome)
                    controller.last_outcome = None
                ledger.append("decision", arm=decision["arm"], ring=decision["ring_target"],
                              n=controller.n, clip=decision["clip"],
                              reason=decision["reason"], confirmed=ok)
                if recorder:
                    recorder.write(decision)
                log.info(f"fired {decision['clip']:>8}  {decision['from']} -> "
                         f"{decision['to']}  ring {decision['ring_target']}  "
                         f"({decision['reason']}, {decision['context']}"
                         f"{'' if ok else ', UNCONFIRMED'})")
            elif clock.audio_due(now):
                pending = controller.decide(now)
                audio.set_stems(resolume, cfg, pending[0]["ring_target"])
                clock.mark_audio()
            for w in controller.warnings:
                log.warning(w)
            controller.warnings.clear()
            await asyncio.sleep(cfg["controller"]["tick_s"])
    finally:
        link_task.cancel()
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
