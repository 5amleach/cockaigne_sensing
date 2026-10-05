# Contracts

The JSON messages that pass between modules. These are fixed. Any change is agreed first and logged in `DECISIONS.md`, and every module that reads or writes the message is updated in the same commit.

All times are seconds as a float. Live, `t` is `time.monotonic()` on the sensing machine. From a file, `t` is the frame's time within the file; under replay the controller still runs on its own clock, so a mixed recording does not share one timeline. A decision's `t` is when it was planned, at the audio lead, about five seconds before it fires. All positions are in metres on a floor plan. The origin is the corner where the data wall meets the left arm of the U. `x` runs along the data wall. `y` is 0 at the data wall and increases toward the closed end of the U. Confidences run 0 to 1.

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

- `id` is stable across the whole room and all cameras, as best a plain tracker can: a crossing, a long occlusion or a calibration error can retire or swap an id.
- `x`, `y` in metres; `vx`, `vy` in metres per second, smoothed.
- `age` is seconds since this person was first seen.
- `box_ratio` is the rectangle's width divided by its height in the best camera view. `box_h` is that rectangle's height in pixels, used to judge slump against the person's own standing height.
- `posture`, `actions`, `arousal`, `valence` are filled in by `features` and `actions`. `floor` emits them as `"standing"`, all zeros, `0.5`, `0.0` and later stages overwrite. A reader must not assume they are meaningful until the message has passed through `features`.

## Contract 2 — crowd state

`features` → `bus` → controller and data wall. About once a second.

```json
{"t": 12.40, "n": 9, "n_smooth": 8.3,
 "clustering": 0.71, "synchrony": 0.44, "stillness": 0.33, "coordination": 0.62,
 "cohesion_relational": 0.66, "cohesion_raw": 0.66, "cohesion_smooth": 0.52,
 "accumulator": 0.63, "ring_target": 2,
 "moods": {"happy": 3, "sad": 1, "bored": 4, "annoyed": 1},
 "actions": {"phone": 2, "drink": 0, "eat": 0, "sitting": 1},
 "action_rates": {"phone": 1.4, "drink": 0.0, "eat": 0.0}}
```

- `n` is the headcount. `n_smooth` is the headcount smoothed over about ten seconds; it is computed here and nowhere else, and the controller reads it for its occupancy bands.
- The signal values run 0 to 1. `coordination` is stillness and synchrony folded into one: `stillness + (1 - stillness) * synchrony`. `cohesion_relational` is the geometric mean of clustering and coordination (1.0 for one person, 0.0 for an empty room); it is the number the data wall displays as the Coherence Index. `cohesion_raw` is the blend of the proxy score and `cohesion_relational`, and it is what drives the ring. `cohesion_smooth` is its ten-second weighted average. `accumulator` is the reservoir level, 0 to 1. `ring_target` is 0 (Barren) to 4.
- `moods` and `actions` are counts of people. `action_rates` are each action's current rate divided by its running baseline, so 1.0 means normal and 3.0 means three times the usual amount. The controller uses `action_rates`, not counts, to bias the arm choice.

## Contract 3 — clip decision

Controller → bus → data wall. Owned by the controller package (`cockaigne_controller/BRIEF.md`); updated 5 October 2026 to match what is published.

```json
{"stream": "decision", "t": 12.4, "from": "b", "to": "m1", "clip": "b_m1",
 "resolume_index": 47, "arm": "machinery", "reason": "action_bias",
 "context": "small", "personality": "Operator", "ring_target": 1,
 "confirmed": true}
```

- `from` and `to` are nodes: `b` (Barren) or an arm letter plus a ring number.
- `context` is the occupancy band: `solo`, `small`, `medium` or `large`.
- `reason` is one of `ring`, `bandit`, `action_bias`, `path` (an intermediate step), `loop`, `probe`, `lateral` (holding a ring by moving sideways to another arm).
- `confirmed` says whether Resolume confirmed the clip connected; when false, the wall's position was held and the move is retried next cycle.

## Ledger entries

`bus` appends one line per event to `ledger.jsonl`. Never wiped.

```json
{"t_wall": "2026-09-19T14:02:11+09:30", "kind": "action", "person": 4, "action": "phone", "conf": 0.81}
{"t_wall": "2026-09-19T14:02:40+09:30", "kind": "decision", "arm": "machinery", "ring": 2, "n": 9}
{"t_wall": "2026-09-19T14:03:40+09:30", "kind": "outcome", "arm": "machinery", "delta_cohesion": 0.07}
```

`kind` is one of `action`, `decision`, `outcome`, `ring_change`, `day_start`, `note`. Extra fields depend on kind.

## Recording format

Every message above, one per line, in a `.jsonl` file, with an extra top-level field `"stream"` naming the contract: `"tracks"`, `"people"`, `"crowd"`, `"decision"`. The replayer reads the file and re-emits each line when its `t` comes due. The bus's `--record` captures the stream it is replaying; messages clients send back (decisions) are rebroadcast but not recorded there — the controller records its own decisions with its `--record`.

## Transport

WebSocket on `ws://127.0.0.1:8765`. Each frame of the socket is one JSON message with the `stream` field. A client that wants only crowd state ignores the rest. Nothing binds to an external interface.
