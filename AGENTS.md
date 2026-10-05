# Working rules for coding agents

You are one of several assistants (Claude Code, Codex, and others) building this repo. None of you can see the others' conversations. The repo is the only shared memory. These rules keep the build from drifting.

## Before you start

1. Read `README.md`, `ARCHITECTURE.md`, `CONTRACTS.md` and `DECISIONS.md`. All of them, every session.
2. Read the module you are working on and the module either side of it in the chain.
3. If your task conflicts with a contract or a logged decision, stop and say so. Do not quietly work around it.

## How to write code here

- One module per folder. A module talks to its neighbours only through the messages in `CONTRACTS.md`. It never imports another module's internals.
- Every module has a `run` entry point that can read its input from a recorded `.jsonl` file or a video file, so it can be tested alone.
- Plain Python. Small functions with one job. A name says what the thing does. A docstring says why it exists, in a sentence a non-programmer could follow.
- No clever abstractions, no frameworks, no class hierarchies. If a plain function will do, use a plain function.
- Every number that might be adjusted on site (a threshold, a window length, a distance) lives in `config/sensing.yaml`, never in code.
- Use the proven library rather than writing your own: OpenCV for video and geometry, Ultralytics for detection and tracking, NumPy for arithmetic, `websockets` for the bus. Do not add a dependency without logging it in `DECISIONS.md`.
- Anything that must run on CPU as well as GPU takes a `device` argument and defaults to auto.
- Privacy is enforced in code: no frames leave `capture` except cropped rectangles into `actions`; nothing writes video to disk without `--record`; the bus binds to localhost only.

## When you finish

- Add or update a small test in `tests/` that runs without a GPU and without network.
- If you made a decision anyone else needs to know about, append it to `DECISIONS.md` with today's date and your name (for example "Claude Code" or "Codex").
- Update the `Status` line in `README.md` if a module changed state.
- Do not change `CONTRACTS.md` unless the task explicitly says so.

## Style of comments and docs

Full sentences. One idea per sentence. Explain a technical term the first time it appears. Assume an intelligent reader who is not a programmer.

## Size budget

The system stays small enough for one person to read in a sitting. No file over 300 lines. No module (one folder) over 1,000 lines. Both packages together stay under 5,000 lines of code, counting non-blank, non-comment lines and not counting `tests/` or documentation. A change that would break the budget is not made; it comes back as a question first, with what would have to be simplified or removed.
