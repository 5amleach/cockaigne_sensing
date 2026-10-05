# Architecture

One program, one computer, no internet. The computer is the render PC (Windows, RTX 5070 Ti 16GB). The cameras sit on a closed network with a PoE switch and nothing else.

## The chain

```
cameras ──► capture ──► detect ──► floor ──► features ──► bus ──► controller
                                     │                      ▲       └──► data wall
                                     └──► actions ──────────┘
```

Each arrow is a JSON message defined in `CONTRACTS.md`. Each module can be run on its own, reading its input from a recorded file instead of from the module above it. That is what makes the system testable at a desk.

## Modules

### capture

Opens one source per camera and hands out frames with a timestamp. A source is either an RTSP camera stream or a video file. Both produce the same thing, so nothing downstream knows or cares which one it is.

The Reolink cameras give two streams. The sub-stream is small and cheap and is what detection normally runs on. The main stream is 3840×2160 and is only read when a module needs a close look at one person.

### detect

Finds people in a frame and gives each one a number that stays the same from frame to frame. Uses a pretrained YOLO detector (person class only) and the ByteTrack tracker built into the Ultralytics library. Output is one message per camera per frame: a list of rectangles with track ids and confidences. Pixel coordinates only. Knows nothing about the floor.

### floor

Turns pixel positions into floor positions in metres and merges the four cameras into one list of people.

Calibration is done once per camera by hand: four marked points on the floor, measured in metres, matched to where they appear in the picture. From those four pairs OpenCV computes a homography, which is a fixed conversion from picture to floor. It is saved in `config/`.

For each detected person, the bottom centre of the rectangle is roughly where the feet are. That point goes through the conversion. Positions from different cameras within about half a metre of each other are the same person. A short tracker on the merged floor positions keeps a stable id per person across the whole room, predicts where each person will be next, and drops anyone unseen for a few seconds.

Output is the **people list** (Contract 1): one entry per person with position, velocity, time in room, and the rectangle's shape. Nothing downstream ever sees a picture.

### features

Pure arithmetic on the people list. No models.

Crowd: clustering (mean nearest-neighbour distance compared with what random placement would give for the same headcount and floor), synchrony (how aligned everyone's movement vectors are), stillness (fraction standing still at once). These combine by geometric mean, so a low score on any one pulls the whole down. The combined score is smoothed over ten seconds, then feeds a reservoir that fills while the score is high and drains slowly when it is low. The reservoir level picks the ring. Going up needs a higher level than coming down, so the wall does not flicker at a boundary.

Per person: posture (sitting, standing, walking) from the rectangle's width-to-height ratio and whether the person has stopped. Arousal from speed, acceleration and vertical bounce. Valence from slump relative to the person's own standing height and from smoothness of movement. Path straightness (straight-line distance divided by distance walked) for boredom. These four numbers map to Happy, Sad, Bored, Annoyed with a dwell timer so labels do not flicker.

Output is the **crowd state** (Contract 2).

Every threshold lives in `config/sensing.yaml`. Expect to change them on site for a week.

### actions

Every few seconds, for each tracked person, cuts the person's rectangle out of the main-stream frame and asks a local vision-language model one multiple-choice question: phone, drinking, eating, or none of these. Requires two agreeing answers in a row before reporting an action. Runs through Ollama on the GPU. Results are merged into the people list as per-person action scores.

There is no cheap shortcut for phones. A lit screen was expected to show as a bright rectangle in infrared, but on venue footage the screen faces the holder and the brightest things in the crop are hands and forearms. The model answers for all three actions.

### bus

Publishes the people list and the crowd state over a WebSocket on the local machine. The controller and the data wall each open a connection and receive every message. Also holds the recorder (writes every message to a `.jsonl` file, development only), the replayer (reads a `.jsonl` file back at the original speed), and the ledger (an append-only record of events that the data wall reads and that is never wiped).

### tools

Command-line helpers. `bench_detect` runs detection over a video file and reports. `calibrate` helps produce a camera's homography from four clicked points. `fake_room` generates a made-up people list with scripted behaviour, so features, the controller and the data wall can be built before any camera exists. `replay` plays a recorded file into the bus.

## The controller

The controller is the second package in this repo, `cockaigne_controller`, decided 5 October 2026 so one session can test the whole chain. It reads the crowd state (Contract 2) from the bus, decides the next clip with a bandit over the eight arms, fires it in Resolume over OSC, and publishes its decision (Contract 3) back through the bus for the data wall. Its full brief, including the clip naming rule, the clock, the daily personalities and the build order, is `cockaigne_controller/BRIEF.md`. Everything adjustable lives in `config/controller.yaml`.

## What is not in this repo

The data wall (HTML page) is a separate project. It consumes Contracts 1, 2 and 3 over one WebSocket and produces nothing this repo needs. Keeping it apart means it can be rebuilt without touching sensing or the controller.

## Privacy rules built into the code

- Recording is off unless `--record` is passed explicitly. The gallery configuration never passes it.
- No module below `capture` receives a frame except `actions`, which receives only a cropped rectangle and discards it after the model answers.
- Nothing leaves the machine. The bus binds to localhost.
