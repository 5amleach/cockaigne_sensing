# Guide

What each part of the system does, for a reader who is not a programmer. One section per module. The exact message formats are in `CONTRACTS.md`; the adjustable numbers are in `config/sensing.yaml` and `config/controller.yaml`, each with a one-line comment beside it.

## capture

Opens the four infrared cameras and hands out pictures, each stamped with the time it was taken. It can open a video file instead of a camera, and everything downstream behaves identically, which is how the system is tested at a desk. Each camera offers two picture streams: a small cheap one that detection runs on, and a full-size one used only when a close look at one person is needed.

In: camera streams or a video file. Out: timestamped frames, handed to `detect` and nowhere else — this is the only module that ever holds a picture of the room. Config that matters: the camera addresses and which stream each uses. If it stops: everything downstream starves, the controller goes blind (see the controller section) and the wall settles to Barren.

## detect

Finds the people in each picture and gives each one a number that stays the same from moment to moment, using a pretrained person detector and tracker (Ultralytics YOLO with ByteTrack). It reports each person as a rectangle in pixel coordinates with a confidence. It knows nothing about the floor, metres, or the other cameras.

In: frames. Out: one "camera tracks" message per camera per frame (Contract 0). Config that matters: `detector.imgsz` (bigger finds distant people, costs more computer), `detector.conf` (the confidence bar), `min_track_age_s` (ignores one-frame flickers). If it stops: same as capture stopping — the room goes quiet and the wall drains.

## floor

Turns pixel positions into metres on the floor plan and merges the four cameras into one list of people. Each camera has a calibration, a fixed conversion from picture to floor, produced from measured floor markers (or, until the cameras are mounted, approximated from the people in a recording). The bottom centre of each rectangle is taken as the feet. Anything whose feet land off the floor — figures in the wall imagery, mostly — is dropped. A simple tracker keeps one id per person across the whole room, and a person missed for a moment is still reported at their predicted position for up to a second (`coast_s`), so brief occlusion does not empty the room.

In: camera tracks. Out: the people list (Contract 1), about ten a second. Config that matters: the floor size (6.1 × 7.4 m, to be tape-measured), `merge_distance_m` (when two cameras see the same person), `drop_after_s`, `coast_s`. If it stops: same as above, the chain is broken.

## features

Pure arithmetic on the people list; this is where the machine's claims come from. For the crowd: clustering, synchrony and stillness combine into relational cohesion; a proxy score (time in the room, stillness, distance from the viewing spot) stands in when the room is nearly empty; the two blend by the smoothed headcount, under a ceiling that keeps the top ring collective. The blended score feeds a reservoir — a level that rises slowly and drains more slowly, never resets, and picks the ring with a gap between going up and coming down so the wall does not flicker. For each person: posture, arousal, valence and a mood label (happy, sad, bored, annoyed) held long enough not to flicker.

In: the people list. Out: the crowd state (Contract 2), once a second, plus the per-person fields written back into the people list. Config that matters: almost everything under `cohesion:` and `mood:`; the mood thresholds are starting guesses to be tuned on site. If it stops: no crowd state arrives, and after thirty seconds the controller goes blind and walks the wall down to Barren.

## actions

Not yet built. Every few seconds it will cut each person's rectangle out of the full-size picture and ask a small local vision-language model one multiple-choice question: phone, drinking, eating, or none. Two agreeing answers in a row are required before an action is reported. The crop is discarded immediately after the answer. It needs the render PC's graphics card.

In: the people list plus crops from capture. Out: per-person action scores merged into the people list. If it stops: actions read as zero everywhere; the wall and the bandit simply lose that signal, and nothing else changes.

## bus

The post office. It publishes every message over one local WebSocket; the controller and the data wall each open one connection and receive everything, and anything a client sends back (the controller's clip decisions) is passed on to the other clients. It refuses, in code, to bind anywhere but the local machine. It also holds the recorder (writes messages to a file, development only, never in the gallery), the replayer (plays a recording back at its original pace), and the ledger — an append-only file of events (`day_start`, `ring_change`, `action`, `decision`, `outcome`) that is never wiped.

In: messages from the chain. Out: the same messages, to every listener, plus ledger lines. Config that matters: `bus.host` and `bus.port` (fixed), `ledger_path`. If it stops: the controller keeps firing clips on its own clock and reconnects every five seconds; the data wall goes stale until the bus is back.

## tools

Command-line helpers, none of which run in the gallery: `bench_detect` (run detection over a clip and report), `calibrate_auto` (approximate camera calibration from the people in a recording), `plan_view` (draw a recording as paths on the floor plan), `fake_room` (a scripted, made-up room for building without cameras), and, still to come, `calibrate` from measured floor markers.

## controller

The second package, `cockaigne_controller`. Once every sixty seconds it decides where the wall goes next and tells Resolume (the video player) which clip to play, choosing the ring from the crowd state alone and the arm with a bandit — a set of running beliefs, one per arm per crowd size, that are sampled each time, rewarded when cohesion rose after a clip, and gently leaned on by what individuals are doing (sitting leans Furniture, phones lean Machinery, and so on). Holding a ring moves sideways to another arm at the same ring; Ring 4 and Barren have loop clips. Each day starts as one of four personalities, which sets how fast it commits and how it treats risk. Audio stems for the next arm start five seconds before the video.

In: the crowd state, and Resolume's clip list at start-up. Out: OSC messages to Resolume, a decision message (Contract 3) through the bus, ledger entries. Config that matters: everything in `config/controller.yaml`. If it stops: the wall freezes on the last clip — this is the one process whose death is immediately visible — so restart it; it rebuilds its clip table, starts at Barren, and refuses to start at all if clips are missing, printing which.
