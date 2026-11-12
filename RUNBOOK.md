# Runbook

How to run Cockaigne's sensing and control, what failures look like, and what to do. Written for the operator, not the programmer.

## What runs where

Everything runs on one computer, the render PC, which also runs Resolume. The four cameras sit on their own wired network with the PoE switch and talk to nobody but this machine. Nothing here touches the internet.

Three of our processes run in the gallery, each in its own terminal:

1. **The sensing chain** — `python -m cockaigne_sensing.run`. One command: cameras in, people list and crowd state out, published on the bus it opens itself at `ws://127.0.0.1:8765`. The camera password is the first line of `camera_password.txt` in the repo folder, a file git ignores so it never leaves this machine (the environment variable `COCKAIGNE_RTSP_PASSWORD` still works and wins if set). It refuses to start if a configured camera has no calibration file, naming the camera; a camera that is down at start is retried every ten seconds while the rest run. (`python -m cockaigne_sensing.bus.run <recording>` still serves recordings for desk work.)
2. **The controller** — `python -m cockaigne_controller.run`. Reads the crowd state from the bus, fires one clip a minute in Resolume, publishes each decision.
3. **Resolume** — started like any other day; it must be open with the Cockaigne composition loaded before the controller starts, because the controller reads the clip list from it and refuses to start if clips are missing (it prints which ones).

The data wall is an HTML page, `datawall/index.html`: open it in Chrome while the sensing chain runs, F11 for full screen. It opens one connection to `ws://127.0.0.1:8765` and shows whatever arrives. Its camera panel reads each camera's latest frame from `http://127.0.0.1:8766` — served from memory, to this machine only, never written to disk. Because of that rule the page must run on this PC: give the wall its own screen on a spare output of the graphics card, extend the Windows desktop onto it, keep Resolume's output on the video screens, and drag Chrome to the wall's screen before pressing F11. Two switches go on the end of the address: `?spot=x,y` draws the viewing spot, and `?blind=bluff` makes the wall keep its last Tech adoption figure instead of showing "?" when the action sense cannot see.

A fourth process joins these once a model has been chosen and `actions.live` is set to true: **Ollama**, the local server for the model that reads phones, drinks and food. Start it before the sensing chain. Without it the chain still runs and the action sense reports itself blind.

Stopping anything: Ctrl-C in its terminal. Starting order barely matters — the controller retries Resolume's clip list at start-up and the bus every five seconds — but the comfortable order is Resolume, then sensing, then the controller.

## Desk rehearsal, no cameras and no Resolume

```
python -m cockaigne_sensing.tools.fake_room --scenario day --out day.jsonl
python -m cockaigne_sensing.features.run day.jsonl --out full.jsonl
python -m cockaigne_sensing.bus.run full.jsonl            (terminal 1)
python -m cockaigne_controller.fake_resolume              (terminal 2)
python -m cockaigne_controller.run --layout pool.json     (terminal 3)
```

The live launcher can also rehearse from footage: give a camera entry `file:`
with a recorded clip instead of `ip:` and it plays as a camera, looped.
Terminal 1 then becomes `python -m cockaigne_sensing.run`. In any rehearsal,
`python -m cockaigne_sensing.tools.watch_bus` in its own terminal prints the
room's state once a second — headcount, ring, Coherence Index, reservoir,
moods, camera health — which is how to see the system working before the
data wall exists.

## The studio shed, one real camera

`config/studio.yaml` is the shed: a 3.5 x 7.0 m floor, the viewing spot on
the centre line 3.5 m in, cam1 on its sub-stream facing into the room.

```
python -m cockaigne_sensing.tools.frame_grid rtsp://... --out grid.png   (read the far wall's floor line off the grid)
python -m cockaigne_sensing.tools.bench_detect CLIP --out bench/shed     (a clip of someone walking about)
python -m cockaigne_sensing.tools.calibrate_auto bench/shed/tracks.jsonl --camera cam1        --facing into_u --far-wall-centre U V --config config/studio.yaml
python -m cockaigne_sensing.run --config config/studio.yaml              (the live chain)
python -m cockaigne_sensing.tools.watch_bus                              (watch it work)
```

## Choosing the actions model: the scripted session

Before the first run, switch on HTTP in the camera's port settings, put tape on the floor at three marks, and have a phone, a cup and something to eat within reach.

```
python -m cockaigne_sensing.tools.script_session --out bench/sessions/shed1 --config config/studio.yaml --speak
python -m cockaigne_sensing.tools.bench_actions bench/sessions/shed1 --config config/studio.yaml --models qwen3-vl:4b-instruct,gemma4:e2b,gemma3:4b,qwen2.5vl:3b,moondream --out bench/actions-shed1.md
```

The first command times ten stills from the camera and prints how long they took, then fills the screen with one instruction at a time and a countdown: amber means get ready, white in a green frame means hold it. A low beep is a new instruction and a high beep is hold. It takes about eighteen minutes and saves about 275 full-size stills of the performer, each labelled with the instruction. Esc stops it. The steps and timings are in `config/session_script.yaml`. The second command needs Ollama running with each model pulled; it prints, per model, how often it was right and how long an answer took. These two tools write pictures to disk and are for the shed only.

The fake Resolume prints every clip fire it receives. `--layout` is a saved clip list, used because there is no Resolume to ask; no `pool.json` is checked in, so generate one first (a JSON list of clip names covering the map — the tests' `full_pool()` in `tests/helpers.py` is the model).

## What failure looks like, and what to do

**The wall sits on one clip and the data screen shows no new decisions.** The controller has died; what the wall shows meanwhile is Resolume's own behaviour (typically the current clip looping or holding). Restart the controller. It starts at Barren and climbs again; beliefs learned earlier that day are lost, which is acceptable.

**The wall drains to Barren over a few minutes, one ring per minute, while people are clearly in the room.** The controller is running blind: the crowd state's own clock has not advanced for thirty seconds, so it steps the displayed position's ring down each cycle until Barren rather than guessing. The sensing process has died — restart `python -m cockaigne_sensing.run`. If sensing is up but a camera is down, the wall keeps running on the remaining cameras and `sensing.log` and the data screen's camera health say which one to fix. The log line reads `running blind, stepping the ring down each cycle`, and `crowd state is back` when it recovers.

**Tech adoption on the data screen shows "?".** The action sense cannot see: the model has not answered for half a minute. `sensing.log` says `action sense has gone blind` and the ledger has a note. Check that Ollama is running and that the model named in `actions.model` is pulled; the sense recovers by itself within seconds and logs `action sense is answering`. A "?" is also what the wall shows whenever `actions.live` is false. Nothing else is affected.

**The wall plays sensibly but the data screen is stale.** The bus has died (the controller will also be logging `bus unreachable; retrying in 5 s` while carrying on). Restart the bus; the controller reconnects within five seconds by itself, and the data wall page may need a reload.

**A clip fires but the wrong picture shows.** The controller checks, within two seconds of every fire, that Resolume actually connected the intended clip; on a mismatch it warns in the log, fires once more, and if still unconfirmed publishes the decision marked unconfirmed and keeps its position where the wall really is — the fire path itself cannot crash the controller. Repeated `layer shows clip X, wanted Y` warnings mean the composition in Resolume no longer matches what the controller read at start-up — probably someone edited it — so restart the controller.

**The controller refuses to start, printing `missing:` lines.** The clip pool in Resolume lacks clips the map needs (a loop, a collapse, a route). Fix the composition or hand the list to Sam; this is deliberate — better to not start than to dead-end mid-show.

**Everything runs but the numbers look mad.** The thresholds are in `config/sensing.yaml` and `config/controller.yaml`, every one with a comment. Change the number, restart the affected process. Nothing in the code carries its own copy of any number.

## Logs, and where to look afterwards

- **The ledger**, `ledger.jsonl` next to where the bus was started: one line per event — day start and personality, ring changes, detected actions, every clip decision, every outcome. Append-only, never wiped; this is the record of what the machine did and why.
- **The controller log**, `controller.log` (path in `config/controller.yaml`): everything the controller printed, including every fire, blind periods, bus reconnects and fire-confirmation warnings.
- **The sensing log**, `sensing.log` (path in `config/sensing.yaml`): the launcher's record — cameras lost and back, calibration complaints, start-up refusals.
- **The terminals** of the sensing chain and the bus show their own chatter; nothing sensing-side writes video or pictures to disk, ever, unless a developer passed `--record`, which the gallery configuration never does.

## The fail-safes, in one place

- Crowd clock stale for 30 s → the controller cycles on its own clock, stepping the displayed ring down to Barren, and logs it.
- Bus gone, or a malformed message on it → the reader logs and survives, retries every 5 s, and the clock keeps firing; unpublished decisions are logged.
- Fire not confirmed → one warning, one retry, the decision published marked unconfirmed, the wall's position held; the fire path never raises.
- Missing clips → the controller refuses to start and names them.
- Action model silent for 30 s → scores fade to zero, the health flag goes false, the wall shows "?", the log and the ledger say so; it recovers by itself.
- The bus binds only to this machine; recording only happens with an explicit `--record`.
