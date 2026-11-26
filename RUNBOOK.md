# Runbook

How to run Cockaigne's sensing and control, what failures look like, and what to do. Written for the operator, not the programmer.

## What runs where

Everything runs on one computer, the render PC, which also runs Resolume. The four cameras sit on their own wired network with the PoE switch and talk to nobody but this machine. Nothing here touches the internet.

Three of our processes run in the gallery, each in its own terminal:

1. **The sensing chain** — `python -m cockaigne_sensing.run`. One command: cameras in, people list and crowd state out, published on the bus it opens itself at `ws://127.0.0.1:8765`. The camera password is the first line of `camera_password.txt` in the repo folder, a file git ignores so it never leaves this machine (without that file, the environment variable `COCKAIGNE_RTSP_PASSWORD` is used). It refuses to start if a configured camera has no calibration file, naming the camera; a camera that is down at start is retried every ten seconds while the rest run. (`python -m cockaigne_sensing.bus.run <recording>` still serves recordings for desk work.)
2. **The controller** — `python -m cockaigne_controller.run`. Reads the crowd state from the bus, fires one clip a minute in Resolume, publishes each decision.
3. **Resolume** — started like any other day; it must be open with the Cockaigne composition loaded before the controller starts, because the controller reads the clip list from it and refuses to start if clips are missing (it prints which ones).

The data wall is an HTML page, `datawall/index.html`: open it in Chrome while the sensing chain runs, F11 for full screen. It opens one connection to `ws://127.0.0.1:8765` and shows whatever arrives. Its camera panel reads each camera's latest frame from `http://127.0.0.1:8766` — served from memory, to this machine only, never written to disk. Because of that rule the page must run on this PC: give the wall its own screen on a spare output of the graphics card, extend the Windows desktop onto it, keep Resolume's output on the video screens, and drag Chrome to the wall's screen before pressing F11. Two switches go on the end of the address: `?spot=x,y` draws the viewing spot, and `?blind=bluff` makes the wall keep its last Tech adoption figure instead of showing "?" when the action sense cannot see.

A fourth process joins these once a model has been chosen and `actions.live` is set to true: **Ollama**, the local server for the model that reads phones, drinks and food. Start it before the sensing chain. Without it the chain still runs and the action sense reports itself blind.

Stopping anything: Ctrl-C in its terminal. Starting order barely matters — the controller retries Resolume's clip list at start-up and the bus every five seconds — but the comfortable order is Resolume, then sensing, then the controller.

## Desk rehearsal, no cameras and no Resolume

```
python -m cockaigne_sensing.tools.fake_room --scenario day --out day.jsonl
python -m cockaigne_sensing.features.run day.jsonl --out full.jsonl
python -m cockaigne_sensing.bus.run full.jsonl            (terminal 1)
python -m cockaigne_controller.fake_resolume              (terminal 2)
python -m cockaigne_controller.run --layout pool.json     (terminal 3)
```

The live launcher can also rehearse from footage: give a camera entry `file:`
with a recorded clip instead of `ip:` and it plays as a camera, looped.
Terminal 1 then becomes `python -m cockaigne_sensing.run`. In any rehearsal,
`python -m cockaigne_sensing.tools.watch_bus` in its own terminal prints the
room's state once a second — headcount, ring, Coherence Index, reservoir,
moods, camera health — which is how to see the system working before the
data wall exists.

## The studio shed, one real camera

`config/studio.yaml` is the shed: a 3.5 x 7.0 m floor, the viewing spot on
the centre line 3.5 m in, cam1 on its sub-stream facing into the room.

```
python -m cockaigne_sensing.tools.frame_grid rtsp://... --out grid.png   (read the far wall's floor line off the grid)
python -m cockaigne_sensing.tools.bench_detect CLIP --out bench/shed     (a clip of someone walking about)
python -m cockaigne_sensing.tools.calibrate_auto bench/shed/tracks.jsonl --camera cam1        --facing into_u --far-wall-centre U V --config config/studio.yaml
python -m cockaigne_sensing.run --config config/studio.yaml              (the live chain)
python -m cockaigne_sensing.tools.watch_bus                              (watch it work)
```

### The studio shed, one double-click

The desktop shortcut **Cockaigne START** runs `start_studio.ps1` in the repo folder. It does the whole start in the comfortable order and says what it is doing:

1. Starts Resolume (Avenue when installed, otherwise Arena) with the `cockaigne_e29` composition, the one with the sounds loaded, unless Resolume is already open, and waits until layer 1 holds its clips (about half a minute from cold).
2. Closes any earlier sensing chain and controller, so a second double-click is a clean restart.
3. Starts the sensing chain with `config/studio.yaml` in a window titled "Cockaigne sensing", and waits for its bus.
4. Starts the controller in a window titled "Cockaigne controller". It fires its first clip at once and one a minute after that.
5. Opens the data wall in Edge, with the viewing spot drawn, full screen on the data screen (the projector): the screen that is not the widest, since the widest is the landscape. Nothing needs dragging and there is no F11 to press. To leave it by hand, press Alt+F4 on it. With only one screen it opens as an ordinary window; press F11 in it for full screen.

If a step cannot be done, the start window stays open and says why in red. The two program windows also stay open if their program stops, so the last lines can be read. **Cockaigne STOP**, or Ctrl+Alt+S from anywhere while the show runs, closes the sensing chain, the controller and Resolume, which also takes a full-screen picture off the monitors. (`start_studio.ps1 -Stop` without `-All` leaves Resolume open.) The key is held by `stop_hotkey.ps1`, a hidden program that START opens first and STOP closes. It is not on the shortcut any more: on 27 Nov 2026 Windows ignored the shortcut's key while the show filled the screens. If the key does nothing, `stop_hotkey.log` says why. Both close the data wall too. The wall runs in its own Edge, with its own profile in the git-ignored folder `.edge-wall`, so Sam's own Edge windows are never closed and can stay open while the wall starts. That Edge is started signed out of any account, with no extensions, no sync and no session restore, so nothing but the wall page can appear on the data screen. Resolume remembers its full-screen output, so once Output > Fullscreen has been chosen on a set of screens, every later start comes up full size. The shortcut icons are in `desktop/`. The paths to Resolume, the composition and Edge are at the top of `start_studio.ps1`.

## Experiment 29 install: one camera, set up in the room

START uses `config/studio.yaml` and camera cam1 (192.168.1.101). The phone sense is on (`actions.live: true`). It needs Ollama, which starts with Windows. Do these steps once the camera is mounted and the screens are in place. They take about half an hour.

1. **Mount the camera so it faces the visitors.** Put it high, at the screen end of the room, looking out over the floor. A phone is only seen from the front, so a camera behind the visitors can't spot phones. Tilt it down until the floor right up to the far wall is in the picture.
2. **Measure the floor the camera covers.** Measure it as a rectangle: x runs across the room, and y runs away from the camera, with y = 0 under the camera. Put the two numbers in `floor:` in `config/studio.yaml`. Put the spot where visitors stand to watch in `cohesion: proxy_spot_x_m` and `proxy_spot_y_m`, and the same two numbers in `$wallSpot` near the top of `start_studio.ps1`.
3. **Take a gridded still:** `python -m cockaigne_sensing.tools.frame_grid rtsp://admin:PASSWORD@192.168.1.101:554/h264Preview_01_sub --out grid.png --step 50`. Read two things off it, in pixels of the 640 x 360 picture:
    - the point where the far wall meets the floor, in the middle of the picture;
    - the corners of the floor where visitors can stand. Leave the monitors and the projector screen outside these corners.
4. **Walk about for two minutes** while the camera records boxes: `python -m cockaigne_sensing.tools.bench_detect rtsp://admin:PASSWORD@192.168.1.101:554/h264Preview_01_sub --camera cam1 --out bench/e29 --seconds 120`. Cover the whole floor, standing still now and then.
5. **Calibrate:** copy `config/homography_cam1.json` somewhere safe first, then run `python -m cockaigne_sensing.tools.calibrate_auto bench/e29/tracks.jsonl --camera cam1 --facing into_u --far-wall-centre U V --config config/studio.yaml`, with U V from step 3.
6. **Leave the screens out:** put the floor corners from step 3 in `floor_polygon:` under cam1 in `config/studio.yaml`, for example `[[40, 350], [600, 350], [520, 140], [120, 140]]`. Feet outside that outline are ignored, so figures on the monitors and projector are never counted.
7. **Check it:** double-click START, then run `python -m cockaigne_sensing.tools.watch_bus` in a terminal. With the screens playing and nobody in the room, it should read n=0. One person walking in should read n=1, and two should read n=2. Hold a phone up facing the camera for a few seconds, and Tech adoption on the data wall should rise above 0.
8. **Delete `bench/e29`.** `bench_detect` saved snapshots of whoever walked about.

### Test footage on tuning days

`record_cam.ps1` in PowerShell saves cam1's main and sub streams to `D:\cockaigne recordings\<date>` in 10-minute `.mkv` files; `record_cam.ps1 -Stop` stops it. It copies the stream without decoding, so it runs beside the live show. Main is about 3.3 GB an hour, so a 7-hour day is about 25 GB. It is for tuning days only: the exhibition records nothing, and the files stay on this PC.

## Choosing the actions model: the scripted session

Before the first run, switch on HTTP in the camera's port settings, put tape on the floor at three marks, and have a phone, a cup and something to eat within reach.

```
python -m cockaigne_sensing.tools.script_session --out bench/sessions/shed1 --config config/studio.yaml --speak
python -m cockaigne_sensing.tools.bench_actions bench/sessions/shed1 --config config/studio.yaml --no-think --models objects,qwen3-vl:4b-instruct,gemma4:e2b,gemma3:4b,qwen2.5vl:3b,moondream --out bench/actions-shed1.md
```

The first command times ten stills from the camera and prints how long they took, then fills the screen with one instruction at a time and a countdown: amber means get ready, white in a green frame means hold it. A low beep is a new instruction and a high beep is hold. It takes about eighteen minutes and saves about 275 full-size stills of the performer, each labelled with the instruction. Esc stops it. The steps and timings are in `config/session_script.yaml`. The second command needs Ollama running with each model pulled; it prints, per model, how often it was right and how long an answer took. These two tools write pictures to disk and are for the shed only.

The fake Resolume prints every clip fire it receives. `--layout` is a saved clip list, used because there is no Resolume to ask; no `pool.json` is checked in, so generate one first (a JSON list of clip names covering the map — the tests' `full_pool()` in `tests/helpers.py` is the model).

## Sound

Each clip has one sound file, twelve seconds longer than the clip. The controller starts it six seconds before the picture, on layer 2 or layer 3 in turn, so two sounds overlap around every cut. The sounds live in the composition, in the same column as their clip on both layers. To put them there, once per composition, with Resolume open and the composition loaded:

```
python -m cockaigne_controller.load_sounds --dry-run     (lists clips without a sound, changes nothing)
python -m cockaigne_controller.load_sounds               (loads them; then save the composition in Resolume)
```

The folder it reads and the two sound layers are in `config/controller.yaml`. The picture layer must sit at zero transition, and the sound layers need nothing else set.

### Speakers

The sound goes out through a USB audio interface, an Arturia MiniFuse 1, to two Yamaha HS8 speakers. Windows names the interface "MiniFuse 1 Start". Resolume's own audio output is set to "Speakers (MiniFuse 1 Start)" in Preferences, Audio. This setting lives in Resolume's preferences on the render PC, not in the composition, so it survives opening any composition.

- Plug the interface in before double-clicking START. Resolume picks its audio device when it opens.
- Left speaker on the MiniFuse's left output, right speaker on its right output. The show is stereo.
- Windows "Mono audio" (Settings, Accessibility, Audio) must be off for the show. It is only for testing with one speaker.
- HS8s are loud. Turn the MiniFuse output knob and the speaker knobs down before the first sound, then bring them up.
- If the picture plays but nothing is heard, check Resolume Preferences, Audio, output device is the MiniFuse, then the composition's master volume.

## Full-size pictures

The show composition `cockaigne_e29` plays small copies of the clips. `cockaigne_e29_full` is the same composition with every slot pointed at its full-size master (8064 x 1176 ProRes, on two drives). It was made by opening a copy of the show composition in Resolume and running:

```
python -m cockaigne_controller.load_pictures --dry-run   (lists clips without a full-size file, changes nothing)
python -m cockaigne_controller.load_pictures             (loads them; then save the composition in Resolume)
```

Every picture clip must also be set to hold its last frame, or a clip that ends a moment before the next fire loops back and flashes its first frame. On a new or rebuilt composition, with Resolume open, run `python -m cockaigne_controller.hold_pictures` and save. `cockaigne_e29_full` was done on 27 November.

The folders it searches are in `config/controller.yaml` under `picture`. A clip with no full-size file keeps its small copy. START opens the composition named at the top of `start_studio.ps1` (`$compositionName`); START opens `cockaigne_e29_full`. To fall back to the small copies, run `start_studio.ps1 -Composition cockaigne_e29`, or change the name in the param line. The drive holding the level 2 masters (D:) must be plugged in.

## What failure looks like, and what to do

**The picture plays but there is no sound.** Look at layers 2 and 3 in Resolume: each should show a sound starting six seconds before every picture change. If the layers are empty, the composition was saved without its sounds; run `load_sounds` again. If sounds start but nothing is heard, check the layer volumes, the composition's master volume and the audio output in Resolume's preferences.

**The wall sits on one clip and the data screen shows no new decisions.** The controller has died; what the wall shows meanwhile is Resolume's own behaviour (typically the current clip looping or holding). Restart the controller. It starts at Barren and climbs again; beliefs learned earlier that day are lost, which is acceptable.

**The wall drains to Barren over a few minutes, one ring per minute, while people are clearly in the room.** The controller is running blind: the crowd state's own clock has not advanced for thirty seconds, so it steps the displayed position's ring down each cycle until Barren rather than guessing. The sensing process has died — restart `python -m cockaigne_sensing.run`. If sensing is up but a camera is down, the wall keeps running on the remaining cameras and `sensing.log` and the data screen's camera health say which one to fix. The log line reads `running blind, stepping the ring down each cycle`, and `crowd state is back` when it recovers.

**Tech adoption on the data screen shows "?".** The action sense cannot see: the model has not answered for half a minute. `sensing.log` says `action sense has gone blind` and the ledger has a note. Check that Ollama is running and that the model named in `actions.model` is pulled; the sense recovers by itself within seconds and logs `action sense is answering`. A "?" is also what the wall shows whenever `actions.live` is false. Nothing else is affected.

**The wall plays sensibly but the data screen is stale.** The bus has died (the controller will also be logging `bus unreachable; retrying in 5 s` while carrying on). Restart the bus; the controller reconnects within five seconds by itself, and the data wall page may need a reload.

**A clip fires but the wrong picture shows.** The controller checks, within two seconds of every fire, that Resolume actually connected the intended clip; on a mismatch it warns in the log, fires once more, and if still unconfirmed publishes the decision marked unconfirmed and keeps its position where the wall really is — the fire path itself cannot crash the controller. Repeated `layer shows clip X, wanted Y` warnings mean the composition in Resolume no longer matches what the controller read at start-up — probably someone edited it — so restart the controller.

**The controller refuses to start, printing `missing:` lines.** The clip pool in Resolume lacks clips the map needs (a loop, a collapse, a route). Fix the composition or hand the list to Sam; this is deliberate — better to not start than to dead-end mid-show.

**Everything runs but the numbers look mad.** The thresholds are in `config/sensing.yaml` and `config/controller.yaml`, every one with a comment. Change the number, restart the affected process. Nothing in the code carries its own copy of any number.

## Logs, and where to look afterwards

- **The ledger**, `ledger.jsonl` next to where the bus was started: one line per event — day start and personality, ring changes, detected actions, every clip decision, every outcome. Append-only, never wiped; this is the record of what the machine did and why.
- **The controller log**, `controller.log` (path in `config/controller.yaml`): everything the controller printed, including every fire, blind periods, bus reconnects and fire-confirmation warnings.
- **The sensing log**, `sensing.log` (path in `config/sensing.yaml`): the launcher's record — cameras lost and back, calibration complaints, start-up refusals.
- **The terminals** of the sensing chain and the bus show their own chatter; nothing sensing-side writes video or pictures to disk, ever, unless a developer passed `--record`, which the gallery configuration never does.

## The fail-safes, in one place

- Crowd clock stale for 30 s → the controller cycles on its own clock, stepping the displayed ring down to Barren, and logs it.
- Bus gone, or a malformed message on it → the reader logs and survives, retries every 5 s, and the clock keeps firing; unpublished decisions are logged.
- Fire not confirmed → one warning, one retry, the decision published marked unconfirmed, the wall's position held; the fire path never raises.
- Missing clips → the controller refuses to start and names them.
- Action model silent for 30 s → scores fade to zero, the health flag goes false, the wall shows "?", the log and the ledger say so; it recovers by itself.
- The bus binds only to this machine; recording only happens with an explicit `--record`.
