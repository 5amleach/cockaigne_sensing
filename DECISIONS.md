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

**2026-09-19 — Sam, with Claude.** Single-viewer behaviour is settled. There is no solo mode. The cohesion estimator keeps running and, when there is nobody to be relational with, falls back onto proxies: time in the room, stillness, and position relative to a viewing spot. The blended score is S = (1 − w)A + wC, where A is the proxy score, C is relational cohesion, and w comes from smoothed effective occupancy. The proxy score is capped at 0.75, so Ring 4 needs relational evidence. The reservoir chases the score and is never reset when occupancy changes. Daily personality applies at every occupancy. Individual actions bias the arm in proportion to the inverse of occupancy and stay inside the Thompson draw (the bandit's random sampling step), so they tilt the choice rather than override it. The viewing spot is on the centre line about 3.5 m out from the data wall, looking into the U, because the work looks best from a distance. Reason: one rule for every occupancy keeps the machine's claim the same ("it is measuring cohesion") while the quality of its evidence changes, and position is scored against where the work is best seen rather than against the walls.

**2026-10-05 — Claude.** Floor size set from the venue pixel maps: 6.1 m along the data wall by 7.4 m deep (data wall 2352 px, U wall 8064 px, 2.6 mm pitch, arms (21.0 − 6.1) / 2). The viewing spot moves to x = 3.05 m accordingly. Confirm with a tape measure on site.

**2026-10-05 — Claude.** The floor module is built and tested on both venue clips. Calibration for footage without floor markers comes from `tools.calibrate_auto`, which fits the camera from the people in a recording (assumed 1.7 m tall) and the far wall's floor line. It is approximate and is replaced by marker calibration (`tools.calibrate`) once cameras are mounted. Off-floor points are dropped by a bounds check in metres; this removed the wall-imagery false positives without a polygon, so the polygon stays optional.

**2026-10-05 — Claude, from bench.** A level camera at head height cannot see the floor within about 3.7 m of itself, so anyone closer has their feet out of frame and their position collapses onto one line. This is the floor-side consequence of the camera-height problem already logged. High mounting resolves it. See `bench/2026-10-05-floor-on-venue-clips.md`.

**2026-10-05 — Claude.** Two dependencies added: scipy (the least-squares fit in `tools.calibrate_auto`) and matplotlib (`tools.plan_view`). Both are calibration and checking tools, not part of the live loop.

**2026-10-05 — Claude Code.** The features module is built and replayed over venue clip A (see `bench/2026-10-05-features-on-venue-clip.md`). Three definitional choices, all adjustable in config: clustering scores 0.5 at random spacing and 0 at twice random; synchrony with fewer than two people moving is 1.0, because there is no disagreement to measure; an action's rate is its one-minute average frequency per person divided by its ten-minute baseline, with a small floor under the baseline so a first action in a quiet room reads as a spike rather than infinity.

**2026-10-05 — Claude Code.** Every mood and valence threshold in `config/sensing.yaml` is a starting guess. Arousal is from speed alone for now. The labels are to be treated as provisional until there is footage from the final camera height to tune against; the bench run shows why (valence saturates when a rectangle shrinks for reasons other than slumping).

**2026-10-05 — Claude, review; built by Claude Code.** Stillness and synchrony fold into one relational signal, coordination = stillness + (1 − stillness) × synchrony, before the geometric mean with clustering. Reason: a still crowd and a marching crowd are both acting together, and as separate signals the geometric mean punished each for the other's absence. Contract 2 gains two fields: `coordination`, and `cohesion_relational` carrying relational cohesion C (1.0 for one person, 0.0 for an empty room). The data wall displays `cohesion_relational` as the Coherence Index; `cohesion_raw`, the blend with the proxy score, is what drives the ring. The ring follows the blend, the wall displays the claim.

**2026-10-05 — Claude, review; built by Claude Code.** The floor tracker coasts: a person missed this step is still reported at their predicted position, held inside the floor rectangle, for up to coast_s (1.0 s in config), and their age keeps counting. Reason: a moment of occlusion should not empty the room or flick the headcount.

**2026-10-05 — Sam.** The data wall lists the four moods with a symbol and a count under each. The per-person tally stays.

**2026-10-05 — Sam.** The Festival has confirmed it has no objection to the sensing and the mood display, so no disclosure change is needed from their side.

**2026-10-05 — Claude Code.** The fake room exists (`tools.fake_room`) with four scripted scenarios: lone viewer settling on the spot, a group of six gathering and scattering, one person sitting down, everyone leaving. The door is assumed to be in the corner at the closed end of the U until the real floor plan says otherwise. The controller and the data wall can be built against these recordings before any camera is mounted.
