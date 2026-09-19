# Contracts

The JSON messages that pass between modules. These are fixed. Any change is agreed first and logged in `DECISIONS.md`, and every module that reads or writes the message is updated in the same commit.

All times are seconds as a float. Live, `t` is `time.monotonic()` on the sensing machine. From a file, `t` is the frame's time within the file. All positions in metres use a floor plan with the origin at one corner, `x` across the room and `y` along it. Confidences run 0 to 1.

## Contract 0 — camera tracks

`detect` → `floor`. One message per camera per processed frame.

```json
{"t": 12.40, "camera": "cam1", "w": 640, "h": 360,
 "tracks": [
   {"id": 3, "box": [412, 118, 470, 310], "conf": 0.91}
 ]}
```

`box` is `[x1, y1, x2, y2]` in pixels of the frame the detector saw (`w` × `h`). `id` is stable for one camera only; a person seen by two cameras has two different ids here. Missing people are simply absent from the list.

## Contract 1 — people list

`floor` → `features`, `actions`, `bus`. About ten times a second.

```json
{"t": 12.40,
 "floor": {"w": 12.0, "h": 9.0},
 "people": [
   {"id": 7, "x": 2.1, "y": 4.8, "vx": 0.3, "vy": -0.1, "age": 12.4,
    "box_ratio": 0.94, "box_h": 192,
    "posture": "sitting",
    "actions": {"phone": 0.81, "drink": 0.0, "eat": 0.0},
    "arousal": 0.62, "valence": -0.15}
 ]}
```

- `id` is stable across the whole room and all cameras.
- `x`, `y` in metres; `vx`, `vy` in metres per second, smoothed.
- `age` is seconds since this person was first seen.
- `box_ratio` is the rectangle's width divided by its height in the best camera view. `box_h` is that rectangle's height in pixels, used to judge slump against the person's own standing height.
- `posture`, `actions`, `arousal`, `valence` are filled in by `features` and `actions`. `floor` emits them as `"standing"`, all zeros, `0.5`, `0.0` and later stages overwrite. A reader must not assume they are meaningful until the message has passed through `features`.

## Contract 2 — crowd state

`features` → `bus` → controller and data wall. About once a second.

```json
{"t": 12.40, "n": 9,
 "clustering": 0.71, "synchrony": 0.44, "stillness": 0.33,
 "cohesion_raw": 0.56, "cohesion_smooth": 0.52,
 "accumulator": 0.63, "ring_target": 2,
 "moods": {"happy": 3, "sad": 1, "bored": 4, "annoyed": 1},
 "actions": {"phone": 2, "drink": 0, "eat": 0, "sitting": 1},
 "action_rates": {"phone": 1.4, "drink": 0.0, "eat": 0.0}}
```

- `n` is the headcount.
- The three signals and `cohesion_raw` run 0 to 1. `cohesion_smooth` is the ten-second weighted average. `accumulator` is the reservoir level, 0 to 1. `ring_target` is 0 (Barren) to 4.
- `moods` and `actions` are counts of people. `action_rates` are each action's current rate divided by its running baseline, so 1.0 means normal and 3.0 means three times the usual amount. The controller uses `action_rates`, not counts, to bias the arm choice.

## Contract 3 — clip decision

Controller → Resolume bridge and data wall. Owned by the controller repo, reproduced here so the data wall has one place to look.

```json
{"t": 12.40, "from": "barren", "to": "m1",
 "clip": "b_m1", "resolume_index": 47, "arm": "machinery",
 "reason": "action_bias", "context": "occ_6_15"}
```

## Ledger entries

`bus` appends one line per event to `ledger.jsonl`. Never wiped.

```json
{"t_wall": "2026-09-19T14:02:11+09:30", "kind": "action", "person": 4, "action": "phone", "conf": 0.81}
{"t_wall": "2026-09-19T14:02:40+09:30", "kind": "decision", "arm": "machinery", "ring": 2, "n": 9}
{"t_wall": "2026-09-19T14:03:40+09:30", "kind": "outcome", "arm": "machinery", "delta_cohesion": 0.07}
```

`kind` is one of `action`, `decision`, `outcome`, `ring_change`, `day_start`, `note`. Extra fields depend on kind.

## Recording format

Every message above, one per line, in a `.jsonl` file, with an extra top-level field `"stream"` naming the contract: `"tracks"`, `"people"`, `"crowd"`, `"decision"`. The replayer reads the file and re-emits each line when its `t` comes due.

## Transport

WebSocket on `ws://127.0.0.1:8765`. Each frame of the socket is one JSON message with the `stream` field. A client that wants only crowd state ignores the rest. Nothing binds to an external interface.
