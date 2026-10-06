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

**2026-10-05 — Claude Code.** The bus publisher and ledger exist. The bus refuses in code to bind anywhere but the local machine. It writes three ledger kinds itself (day_start, ring_change, and action when a person's score crosses the reporting threshold, once per continuous stretch); decision and outcome entries are appended to the same file by the controller, which is safe because each entry is a single line. `bus.run` serves any recording at its original pace, so the controller and the data wall can be built against ws://127.0.0.1:8765 today.

**2026-10-05 — Claude, review; built by Claude Code.** Two single-viewer holes were found by replaying the fake day and are closed. First, in the blend, relational cohesion counts as 0.0 whenever fewer than two people are present, so a lone person arriving as a crowd leaves cannot inherit the crowd's lagging blend weight and ride a relational score of 1.0 to the top ring; the reported `cohesion_relational` still reads 1.0 for one person, because that is the displayed claim, not the driver. Second, the proxy-score cap of 19 September (proxy_ceiling 0.75) is replaced by `score_ceiling_by_n`, a ceiling on the blended score that follows the smoothed headcount (0.72 up to two people, 0.9 at three, none from four), and `ring_down` for Ring 4 rises to 0.74. Reason: a dyad standing close and still scores well on every signal, but a dyad is weak relational evidence, so the ceiling, not a population rule, keeps the top ring collective. The intent of the old cap — Ring 4 needs collective evidence — is kept and now covers pairs.

**2026-10-05 — Claude, review; built by Claude Code.** Path straightness samples positions once per second (`straightness_sample_s`), not at the full message rate. Reason: summed over thousands of messages, centimetre position jitter read as metres of walking, and a person standing still on the viewing spot was labelled bored.

**2026-10-05 — Sam, with Claude.** The controller lives in this repo as a second package, `cockaigne_controller`, rather than in a separate repo. Reason: one session can then build and test the whole chain, sensing through to clip decision, against the same fixtures and fake room.

**2026-10-05 — Sam, with Claude.** The bus rebroadcasts any message a client sends it to every other client. Reason: the controller publishes its clip decisions (Contract 3) back through the bus, so the data wall needs one socket for the whole installation.

**2026-10-05 — Sam, via the controller brief.** Arm letters: a Architecture, u Furniture, s Storm, r Rivers, f Feast, h Herd, m Machinery, c Cargo. The letter c is to be confirmed against the clip files. The full controller brief is saved as `cockaigne_controller/BRIEF.md`; ARCHITECTURE.md points to it.

**2026-10-05 — Claude Code.** Two dependencies added for the controller: python-osc (firing clips in Resolume over OSC) and requests (reading the composition over Resolume's REST API at start-up). Both touch only the local machine.

**2026-10-05 — Claude Code.** The controller is built through its brief's step 5, with audio stubbed behind one function (step 6). Definitional choices, all in `config/controller.yaml`: a cohesion change of zero scores reward 0.5 and the update is a fractional Bernoulli (reward r adds r to the Beta's successes and 1 − r to its failures); a decision's reason is `action_bias` only when the lean actually changed the winner of the Thompson draw; sitting has no rate in Contract 2, so the controller keeps its own baseline for the sitting fraction; `arm_chooser` can be set to `fixed` to pin one arm for tests or soaking. The brief does not say how the date picks the personality, so the rule is the day of the year modulo the preset order — an assumption, trivially replaced by a calendar in config.

**2026-10-05 — Claude Code.** The brief gives loop clips only to Ring 4 and Barren, but holding a ring is the room's common state. Until that is resolved, a node at Rings 1 to 3 asked to stay put bounces to its same-arm downward neighbour and back (upward at Ring 1, so the wall does not blink to Barren). Flagged in the build report: the real fix is loop clips for every node, or a defined look for staying still.

**2026-10-05 — Claude, review; built by Claude Code.** Holding a ring at Rings 1 to 3 is a sideways move, reason `lateral`: the next clip goes to the chooser's arm at the same ring, or its runner-up when it chose the arm the wall is already on. This replaces the up-and-down bounce of earlier today. Loops play only where loop clips exist (Ring 4 and Barren). Contract 2 gains `n_smooth` so the headcount is smoothed once, in features, and the controller's own smoothing is removed; Contract 3 in CONTRACTS.md is updated to match what the controller publishes (stream, personality, ring_target, the band names, and the reason list including `lateral`).

**2026-10-05 — Claude, review; built by Claude Code.** The controller's fail-safes: after every fire it confirms over REST within two seconds that the intended clip connected, and on a mismatch logs a warning and fires once more, never crashing; with no crowd state for thirty seconds it keeps cycling on its own clock and steps the ring down each cycle to Barren, logging that it is running blind; a dropped bus connection is retried every five seconds while the clock keeps firing. Log lines go to `controller.log` as well as the terminal. GUIDE.md and RUNBOOK.md at the repo root describe the system and its operation for a non-programmer.

**2026-10-05 — Sam, via Fable's review.** AGENTS.md gains a size budget: no file over 300 lines, no module over 1,000, both packages together under 5,000 lines of code; a change that would break it comes back as a question first.

**2026-10-05 — Sam, with Codex and Claude Code.** Codex audited the repository at commit b1e6546; the full audit is `AUDIT-2026-10.md` and the finding-by-finding response is `AUDIT-RESPONSE.md`. Every session reads both alongside the documents above. The headline accepted: the system is not ready for an unattended month — the live launcher, supervision and boot arrangement are the next build. Fixed the same day: the controller's displayed-versus-planned position with confirmed fires, the blind descent from the displayed node, message-clock freshness, a hardened bus reader, the full start-up validator with ring-preserving holds, the capped and warmed action lean, whole-clip rewards, camera-aware merging, ghost-revival expiry, calibration scaling by stored image size, the repaired fake day, dependency pins with a lock file, and the documentation corrected wherever it promised more than the code gives.

**2026-10-06 — Claude Code.** The live launcher exists: `python -m cockaigne_sensing.run` runs the whole sensing chain in one process — one reading-and-detecting thread per camera, floor, features and the bus in the main loop, the floor flushed on a timer so an empty room still reports itself. A camera entry may give `file:` instead of `ip:`, so recorded clips stand in for cameras at a desk, looped; frames are stamped with the machine clock either way. Contract 1 gains a `cameras` health field and the ledger gains `camera_lost` and `camera_back` kinds, both in CONTRACTS.md. Start-up refuses to run when a camera lacks its calibration file; a stream whose shape disagrees with its calibration is disabled by name. `--record DIR` writes the tracks, people and crowd recordings; without it only the ledger and `sensing.log` are written, and they contain no pictures. The launcher test drives two synthetic videos through the real chain with a stand-in detector, since the detector weights need the network; detection itself is covered by the bench runs.

**2026-10-06 — Claude Code.** Studio helpers for running the chain with one real camera before the venue exists: `config/studio.yaml` (the shed, 3.5 × 7.0 m, viewing spot at 1.75, 3.5), `tools.frame_grid` (a frame with a labelled pixel grid for reading the far wall's floor line, passwords hidden), `calibrate_auto --config` (so the fit uses the right floor), and `tools.watch_bus` (one plain line a second of headcount, ring, Coherence Index, reservoir, moods and camera health — the stand-in for the data wall). The RUNBOOK gains the shed procedure.
