# Runbook

How to run Cockaigne's sensing and control, what failures look like, and what to do. Written for the operator, not the programmer.

## What runs where

Everything runs on one computer, the render PC, which also runs Resolume. The four cameras sit on their own wired network with the PoE switch and talk to nobody but this machine. Nothing here touches the internet.

Three of our processes run in the gallery, each in its own terminal:

1. **The sensing chain** — cameras in, people list and crowd state out, published on the bus. *The single live launcher for the whole chain is not written yet*; today each stage runs from a recording for development, and the live launcher is the next piece of plumbing. The bus half exists: `python -m cockaigne_sensing.bus.run <recording>` serves a recording exactly as the live chain will.
2. **The controller** — `python -m cockaigne_controller.run`. Reads the crowd state from the bus, fires one clip a minute in Resolume, publishes each decision.
3. **Resolume** — started like any other day; it must be open with the Cockaigne composition loaded before the controller starts, because the controller reads the clip list from it and refuses to start if clips are missing (it prints which ones).

The data wall is an HTML page; it opens one connection to `ws://127.0.0.1:8765` and shows whatever arrives.

Stopping anything: Ctrl-C in its terminal. Starting order barely matters — the controller retries Resolume's clip list at start-up and the bus every five seconds — but the comfortable order is Resolume, then sensing, then the controller.

## Desk rehearsal, no cameras and no Resolume

```
python -m cockaigne_sensing.tools.fake_room --scenario day --out day.jsonl
python -m cockaigne_sensing.features.run day.jsonl --out full.jsonl
python -m cockaigne_sensing.bus.run full.jsonl            (terminal 1)
python -m cockaigne_controller.fake_resolume              (terminal 2)
python -m cockaigne_controller.run --layout pool.json     (terminal 3)
```

The fake Resolume prints every clip fire it receives. `--layout` is a saved clip list, used because there is no Resolume to ask; no `pool.json` is checked in, so generate one first (a JSON list of clip names covering the map — the tests' `full_pool()` in `tests/helpers.py` is the model).

## What failure looks like, and what to do

**The wall sits on one clip and the data screen shows no new decisions.** The controller has died; what the wall shows meanwhile is Resolume's own behaviour (typically the current clip looping or holding). Restart the controller. It starts at Barren and climbs again; beliefs learned earlier that day are lost, which is acceptable.

**The wall drains to Barren over a few minutes, one ring per minute, while people are clearly in the room.** The controller is running blind: the crowd state's own clock has not advanced for thirty seconds (nothing arriving, or the same stale message repeating), so it steps the displayed position's ring down each cycle until Barren rather than guessing. The sensing chain or the bus has died — look at those two terminals, restart whichever has stopped. The log line reads `running blind, stepping the ring down each cycle`, and `crowd state is back` when it recovers.

**The wall plays sensibly but the data screen is stale.** The bus has died (the controller will also be logging `bus unreachable; retrying in 5 s` while carrying on). Restart the bus; the controller reconnects within five seconds by itself, and the data wall page may need a reload.

**A clip fires but the wrong picture shows.** The controller checks, within two seconds of every fire, that Resolume actually connected the intended clip; on a mismatch it warns in the log, fires once more, and if still unconfirmed publishes the decision marked unconfirmed and keeps its position where the wall really is — the fire path itself cannot crash the controller. Repeated `layer shows clip X, wanted Y` warnings mean the composition in Resolume no longer matches what the controller read at start-up — probably someone edited it — so restart the controller.

**The controller refuses to start, printing `missing:` lines.** The clip pool in Resolume lacks clips the map needs (a loop, a collapse, a route). Fix the composition or hand the list to Sam; this is deliberate — better to not start than to dead-end mid-show.

**Everything runs but the numbers look mad.** The thresholds are in `config/sensing.yaml` and `config/controller.yaml`, every one with a comment. Change the number, restart the affected process. Nothing in the code carries its own copy of any number.

## Logs, and where to look afterwards

- **The ledger**, `ledger.jsonl` next to where the bus was started: one line per event — day start and personality, ring changes, detected actions, every clip decision, every outcome. Append-only, never wiped; this is the record of what the machine did and why.
- **The controller log**, `controller.log` (path in `config/controller.yaml`): everything the controller printed, including every fire, blind periods, bus reconnects and fire-confirmation warnings.
- **The terminals** of the sensing chain and the bus show their own chatter; nothing sensing-side writes video or pictures to disk, ever, unless a developer passed `--record`, which the gallery configuration never does.

## The fail-safes, in one place

- Crowd clock stale for 30 s → the controller cycles on its own clock, stepping the displayed ring down to Barren, and logs it.
- Bus gone, or a malformed message on it → the reader logs and survives, retries every 5 s, and the clock keeps firing; unpublished decisions are logged.
- Fire not confirmed → one warning, one retry, the decision published marked unconfirmed, the wall's position held; the fire path never raises.
- Missing clips → the controller refuses to start and names them.
- The bus binds only to this machine; recording only happens with an explicit `--record`.
