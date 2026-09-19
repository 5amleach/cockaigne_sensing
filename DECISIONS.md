# Decisions

Dated log. Newest at the bottom. Append, never edit. If a decision is reversed, add a new entry saying so and why.

Format: date, who decided, the decision, the reason in one or two sentences.

---

**2026-09-14 — Sam, with Claude.** Control system specified in plain English (project doc `control system spec plain english.md`). Sensing runs on a single computer with no internet. Mood is derived from position and movement only, never from faces. Three JSON handover notes fix the boundaries between seeing, scoring and choosing.

**2026-09-14 — Sam.** Skeletal pose tracking removed from the plan. Posture, arousal and valence come from the bounding rectangle and the track, which is enough and costs nothing.

**2026-09-19 — Sam.** Claude (Fable) is project lead for the capture and processing modules. ChatGPT (Astra) is second opinion and reviewer. Claude Code and Codex agents build modules against this repo's docs.

**2026-09-19 — Claude, pending Sam's licence call.** Detector is Ultralytics YOLO11 with its built-in ByteTrack tracker. Reason: most used, best documented, one line of code for detect-plus-track, and it worked first time on the infrared venue footage. Ultralytics is AGPL-3.0. Its obligations apply on distribution or network service, and a gallery installation does neither. If Sam wants no ambiguity, RF-DETR (Apache-2.0) is the swap and the module boundary makes it one file. No paid licence is needed anywhere in the sensing stack.

**2026-09-19 — Claude.** Language is Python 3.11 or later. Runs on the render PC under Windows with CUDA. Development and bench tests must also run on CPU so they can be done anywhere.

**2026-09-19 — Claude.** The camera-level track message (Contract 0) is added in front of the spec's three notes, so `detect` and `floor` can be developed and tested separately.

**2026-09-19 — Claude, from bench footage.** Person detection works in infrared black and white at the venue: three people found in nearly every sampled frame at 1280 px input, with the far seated person at lower confidence (0.3–0.5). Infrared is not a blocker for detection. See `bench/2026-09-19-venue-clip.md`.

**2026-09-19 — Claude, from bench footage.** The 7 Sept venue clip was shot from roughly standing height. Two people standing near the camera merged into one detection for several seconds. The cameras will be mounted high on the walls looking down at about 30–45°, as the spec says, which removes most of this. Bench footage from that height is the next thing to capture.

**2026-09-19 — Claude.** The camera's on-screen overlays (timestamp, Reolink logo, camera name) are to be switched off in the camera settings. They sit inside the frame the detector sees and inside any crop sent to the vision-language model.

**2026-09-19 — Claude.** The camera's main stream is HEVC (H.265) 3840×2160 at 25 fps, regardless of the `h264Preview_01_main` path name. Detection will run on the sub-stream. The sub-stream's actual size and rate are to be confirmed by capturing a sample.

**2026-09-19 — Claude.** Messages travel as JSON over a WebSocket on localhost (port 8765). Recording is newline-delimited JSON. Reason: any language can read both, the data wall is an HTML page and speaks WebSocket natively, and a text file can be inspected by eye.

**2026-09-19 — Claude, from bench footage.** The "lit phone screen shows as a bright rectangle in infrared" shortcut does not hold. In the venue clip the screen faces the holder and is edge-on to the camera; the bright blobs are skin. Phone detection goes through the vision-language model. The shortcut may be retested from the planned high camera angle but is not to be relied on.

**2026-09-19 — Claude.** Recording video or messages to disk requires an explicit `--record` flag. The gallery launch configuration never sets it. This is how the no-retention commitment is enforced in code rather than by habit.

**2026-09-19 — Sam.** Eat and drink are in scope alongside phone. All three actions are enabled in `config/sensing.yaml`.

**2026-09-19 — Sam.** Ultralytics YOLO under AGPL-3.0 is accepted for the installation. No agreement to sign; the repo is public in any case.

**2026-09-19 — Claude, from bench footage.** The landscape on the LED walls triggers person detections (a shape in the projected image was tracked for eleven seconds). Each camera gets a hand-drawn floor polygon in `config/sensing.yaml`; the floor module drops any detection whose feet fall outside it. Minimum track age is likely to go from one second to two.
