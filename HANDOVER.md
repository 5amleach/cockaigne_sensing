# Handover, 12 November 2026

Written by Claude (Fable) at the end of a working session with Sam, so that any agent or person starting cold can pick up. Everything built is on the `actions-design` branch and pushed. This file lists what is still open. Delete an item when it is done, and delete the file when it is empty.

## Where things stand

- The actions module is built and tested, and switched off (`actions.live: false`) until a model is chosen. Its design and the day's decisions are in `cockaigne_sensing/actions/DESIGN.md` and `DECISIONS.md`.
- The data wall shows "?" for Tech adoption while the action sense is off or blind.
- cam1 is done (Claude Code, 12 November). It serves 4K stills over HTTP, in 0.66 to 0.81 seconds each. Its overlays are off and its clock is set to Sydney time from the PC. The camera was factory reset to get there, because its password was lost. What was set, why, and how to redo it after another reset are in `DECISIONS.md` (12 November, "The shed camera cam1 now serves…") and `bench/2026-11-12-camera-stills.md`.
- On the render PC, the camera password is in the environment variable `COCKAIGNE_RTSP_PASSWORD`. It is letters and digits only, so the old risk from an `@` is gone. `camera_password.txt` would override the variable, and it does not exist there. Don't create one unless it holds the current password.
- A live test in a local gallery is planned for late November. The video plays on two monitors; the data wall needs a third screen on the same PC.

## Open, in order

1. **The scripted session (Sam, in the shed, lights off so the camera is in infrared).**
   `python -m cockaigne_sensing.tools.script_session --out bench/sessions/shed1 --config config/studio.yaml --speak`
   The full-screen window has not been run on a real display yet. If it fails, add `--no-window`. If the Reolink app can record the live view, record the performance too, so that models needing video clips can be tested later.
2. **Add a YOLO object check to `tools.bench_actions` before running it.** The detector already knows "cell phone", "cup" and "bottle". Run on the close-up crop it may spot what is in the hand, far more cheaply than a language model. It should be scored against the same stills as the language models.
3. **Run the bench (render PC, needs Ollama and the models pulled).** The command is in `RUNBOOK.md`. Pick a model, set `actions.model`, `crop_max_px`, `max_asks_per_s`, and `live: true`. Stills take about 0.73 seconds, which is over the half second `actions/DESIGN.md` allows before considering the main-stream fallback. Judge the fallback from the still and the model's answer together.
4. **Local `main` on the render PC is four commits ahead of GitHub.** `actions-design` was built from the GitHub copy and lacks them. Show Sam the commits (`git log origin/main..main --oneline`), push `main` if he agrees, then merge it into `actions-design`.
5. **Before the gallery test:** calibration for that room (`tools.calibrate` from floor markers is still unwritten; `calibrate_auto` exists), a run with Resolume on all three screens watching for dropped frames, and merging `actions-design` into `main`.
6. **An idea Sam has not decided on.** He said the monitoring may matter more than the decision. The wall could show each inspection as it happens: the person's box pulses on the camera panel and the verdict appears beside it.
