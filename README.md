# Cockaigne sensing

The part of *Cockaigne* that watches the room.

Four infrared cameras look at the gallery floor. This code finds the people in the pictures, works out where each person is standing in metres, follows them from moment to moment, and turns that into two things: a measure of how much the crowd is acting as a group, and a list of what individual people are doing. It publishes those results as small JSON messages. Two other programs read them: the controller, which chooses the next video clip, and the data wall, which displays the machine's claims about the room.

No pictures are ever written to disk in the gallery. Recording exists only for development, and only when switched on explicitly.

## Read these first

Every person and every coding agent working on this repo reads these four files before touching anything:

1. `ARCHITECTURE.md` — the modules, what each one does, and how data flows between them.
2. `CONTRACTS.md` — the exact JSON messages that pass between modules. These are fixed. Change them only by agreement, logged in `DECISIONS.md`.
3. `DECISIONS.md` — a dated log of every decision made so far. Append to it. Never edit old entries.
4. `AGENTS.md` — the working rules for coding agents.

For a plain-language description of every module there is `GUIDE.md`, and for running the installation and handling failures, `RUNBOOK.md`.

## Layout

```
cockaigne_sensing/      the Python package, one folder per module
  capture/              opens a camera stream or a video file and hands out frames
  detect/               finds people in a frame and follows them between frames
  floor/                converts picture positions to floor positions and merges cameras
  features/             crowd cohesion and per-person mood, computed from positions and movement
  actions/              asks a local vision-language model whether a person is on a phone, drinking or eating
  bus/                  publishes messages, records them for replay, keeps the ledger
  tools/                command-line helpers: bench tests, calibration, fake room, replay
config/                 every threshold and camera setting lives here, nowhere else
bench/                  results from tests on footage (numbers and notes, never video)
tests/                  small tests that run without a GPU
```

## Running a bench test on footage

```
pip install -e .
python -m cockaigne_sensing.tools.bench_detect path/to/clip.mkv --out bench/run1
python -m cockaigne_sensing.floor.run bench/run1/tracks.jsonl --out bench/run1/people.jsonl --config config/venue_bench.yaml
python -m cockaigne_sensing.tools.plan_view bench/run1/people.jsonl --out bench/run1/plan.png
```

That prints how many people were found each second, saves a few annotated frames to look at, and writes the per-camera track messages to a `.jsonl` file that the later modules can replay.

## Status

5 Oct 2026. Capture, detect, floor, features, the fake room and the bus exist; the chain runs end to end on venue footage and on scripted rooms (see `bench/`). The controller (`cockaigne_controller`) exists through build step 5 — clip map, clock, bandit, action lean, daily personality, ledger — with audio stems stubbed, and has run against the fake day, the bus and the fake Resolume. Actions is described but not yet written, as it needs the render PC's GPU.
