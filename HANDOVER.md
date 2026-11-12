# Handover, 12 November 2026

Written by Claude (Fable) at the end of a working session with Sam, so that any agent or person starting cold can pick up. Everything built is on the `actions-design` branch and pushed. This file lists what is still open. Delete an item when it is done, and delete the file when it is empty.

## Where things stand

- The actions module is built and tested, and switched off (`actions.live: false`) until a model is chosen. Its design and the day's decisions are in `cockaigne_sensing/actions/DESIGN.md` and `DECISIONS.md`.
- The data wall shows "?" for Tech adoption while the action sense is off or blind.
- Sam switched HTTP on at cam1 through the Reolink app. The camera password goes on the first line of `camera_password.txt` in the repo folder, which git ignores.
- A live test in a local gallery is planned for late November. The video plays on two monitors; the data wall needs a third screen on the same PC.

## Open, in order

1. **Camera chores on cam1 (a local agent on the render PC).** Check that stills arrive:
   `python -c "from cockaigne_sensing.config import load; from cockaigne_sensing.capture import fetch_still; f = fetch_still(load('config/studio.yaml')['cameras'][0], 5); print(None if f is None else f.shape)"`
   It should print a shape such as (2160, 3840, 3). Then, through the camera's HTTP API at `/cgi-bin/api.cgi`: turn off the on-screen overlays (camera name, date and time, watermark; `GetOsd` then `SetOsd`) and set the clock from the PC (`GetTime` then `SetTime`). Read every setting before writing it and change only those fields. Do not touch the address, password, RTSP, ONVIF, resolution, bitrate or firmware, and do not reboot the camera without asking Sam. Never print or log the password or an address that contains it. Time ten stills and write the result to `bench/<date>-camera-stills.md`.
2. **A known risk with stills.** The camera password contains an `@`. The video stream copes with that. The still request is untested with it. If video works and stills return nothing, suspect the `@` first; the cure is a password of letters and digits only.
3. **The scripted session (Sam, in the shed, lights off so the camera is in infrared).**
   `python -m cockaigne_sensing.tools.script_session --out bench/sessions/shed1 --config config/studio.yaml --speak`
   The full-screen window has not been run on a real display yet. If it fails, add `--no-window`. If the Reolink app can record the live view, record the performance too, so that models needing video clips can be tested later.
4. **Add a YOLO object check to `tools.bench_actions` before running it.** The detector already knows "cell phone", "cup" and "bottle". Run on the close-up crop it may spot what is in the hand, far more cheaply than a language model. It should be scored against the same stills as the language models.
5. **Run the bench (render PC, needs Ollama and the models pulled).** The command is in `RUNBOOK.md`. Pick a model, set `actions.model`, `crop_max_px`, `max_asks_per_s`, and `live: true`.
6. **Local `main` on the render PC is four commits ahead of GitHub.** `actions-design` was built from the GitHub copy and lacks them. Show Sam the commits (`git log origin/main..main --oneline`), push `main` if he agrees, then merge it into `actions-design`.
7. **Before the gallery test:** calibration for that room (`tools.calibrate` from floor markers is still unwritten; `calibrate_auto` exists), a run with Resolume on all three screens watching for dropped frames, and merging `actions-design` into `main`.
8. **An idea Sam has not decided on.** He said the monitoring may matter more than the decision. The wall could show each inspection as it happens: the person's box pulses on the camera panel and the verdict appears beside it.
