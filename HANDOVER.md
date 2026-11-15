# Handover, 12 November 2026

Written by Claude (Fable) at the end of a working session with Sam, so that any agent or person starting cold can pick up. Everything built is on the `actions-design` branch and pushed. This file lists what is still open. Delete an item when it is done, and delete the file when it is empty.

## Where things stand

- The actions module is built and tested, and switched off (`actions.live: false`) until a model is chosen. Its design and the day's decisions are in `cockaigne_sensing/actions/DESIGN.md` and `DECISIONS.md`.
- The data wall shows "?" for Tech adoption while the action sense is off or blind.
- cam1 is done (Claude Code, 12 November). It serves 4K stills over HTTP, in 0.66 to 0.81 seconds each. Its overlays are off and its clock is set to Sydney time from the PC. The camera was factory reset to get there, because its password was lost. What was set, why, and how to redo it after another reset are in `DECISIONS.md` (12 November, "The shed camera cam1 now serves…") and `bench/2026-11-12-camera-stills.md`.
- On the render PC, the camera password is in the environment variable `COCKAIGNE_RTSP_PASSWORD`. It is letters and digits only, so the old risk from an `@` is gone. `camera_password.txt` would override the variable, and it does not exist there. Don't create one unless it holds the current password.
- A live test in a local gallery is planned for late November. The video plays on two monitors; the data wall needs a third screen on the same PC.

## Open, in order

1. **The scripted session is done (Sam, 12 November, about 5 pm, camera in infrared).** The full-screen window worked. It saved 275 stills, 5 for each of the 55 steps, with none missed. Each still took 0.75 seconds at the median and 0.89 at most. They are in `bench/sessions/shed1` with `session.jsonl` on the render PC only. Git ignores that folder, and it holds pictures of Sam, so it stays on this PC. A contact sheet checked by eye shows the labels match the poses at every mark, facing and posture. Two things for whoever scores the bench:
   - In "drink" and "eat" holds, about one still in three shows the hand lowered between sips or bites, with the cup or food held at chest height. The script's label still says drink or eat, so a model answering "none" on those stills is not plainly wrong. Consider scoring per hold (the majority of its 5 stills) as well as per still.
   - The "sitting" steps were done sitting on the rug, not on a chair.
   The performance was not recorded as video.
2. **The YOLO object check is built and run (Claude Code, 12 November).** `--models objects` in `tools.bench_actions` scores the detector's own object classes on the same crops. Results are in `bench/2026-11-12-objects-shed1.md`. It was right 49% of the time and answered in 0.02 seconds. It never raised a false alarm, but it found only 32% of phones and 14% of drinks, and no eating at all. It is not enough on its own. It might work as a fast first pass in front of a language model, which is to be decided after item 3.
3. **The bench has been run (Claude Code, 15 November). It is waiting on Sam's decisions.** See `bench/2026-11-15-actions-bench-notes.md`, and the raw report in `bench/actions-shed1.md`.
   - Ollama was reinstalled as 0.40.16 and all five models are pulled.
   - `qwen3-vl:4b-instruct` is the clear best. It was right 69% of the time, and seen from the front or side it got every phone and nearly every drink, with 2 false alarms in 80. It answers in 0.36 seconds.
   - qwen2.5vl, the current default in config, stops answering after about 158 questions. It is unfit to run unattended.
   - No model sees eating.
   - Waiting on Sam:
     - set `actions.model` to qwen3-vl;
     - keep or drop "eat";
     - then set `max_asks_per_s` from the load test with Resolume (item 5), and `live: true`.
   - With the still's 0.73 seconds, a question takes about 1.1 seconds in all. The main-stream fallback is not needed for now.
4. **Local `main` on the render PC is four commits ahead of GitHub.** `actions-design` was built from the GitHub copy and lacks them. Show Sam the commits (`git log origin/main..main --oneline`), push `main` if he agrees, then merge it into `actions-design`.
5. **Before the gallery test:** calibration for that room (`tools.calibrate` from floor markers is still unwritten; `calibrate_auto` exists), a run with Resolume on all three screens watching for dropped frames, and merging `actions-design` into `main`.
6. **An idea Sam has not decided on.** He said the monitoring may matter more than the decision. The wall could show each inspection as it happens: the person's box pulses on the camera panel and the verdict appears beside it.
