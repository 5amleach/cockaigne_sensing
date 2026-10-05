# Controller brief

Written 5 October 2026 by Claude (Fable). The controller decides which clip plays next and tells Resolume. It lives in this repository as a second package, `cockaigne_controller`, beside `cockaigne_sensing`. It reads Contract 2 from the bus and writes Contract 3 back to it. It never sees a picture or a person; it sees one crowd-state message a second.

## What it holds

**The map.** 33 nodes: Barren (`b`) plus eight arms at four rings. Arms and letters, confirmed by Sam: a Architecture, u Furniture, s Storm, r Rivers, f Feast, h Herd, m Machinery, c Cargo (c to be confirmed against the clip files). A node is an arm letter plus a ring number (`m1` is Machinery ring 1). The letter table lives in `config/controller.yaml`.

**The clip table.** Clips are named by the move they carry, from-node then to-node, as in `a1m1` (Architecture 1 to Machinery 1) and `b_m1` or `bm1` (Barren to Machinery 1). The pool also holds loop clips for the eight Ring 4 nodes and for Barren, and direct collapse clips from Rings 2 and 3 to Barren. The table is built at start-up from two sources and nowhere else: the clip names Resolume reports over its REST API (`GET /api/v1/composition`, port 8080), and the naming rule. The controller refuses to start if any clip the map needs is missing, and prints which. No clip index is ever typed by hand.

**The clock.** Clips are 60 seconds. The controller fires each clip itself, so it knows exactly when the current one started and fires the next at 60.0 seconds on its own clock. It never asks Resolume where the playhead is. Audio stems for the next arm are fired 5 seconds before the video.

**The ring rule.** The ring comes from `ring_target` in the crowd state and nothing else.

**The bandit.** One belief per arm per context. Context is the occupancy band from smoothed headcount: solo (1), small (2 to 5), medium (6 to 15), large (16+). Beliefs are Beta distributions. At decision time draw one sample per arm, add the action bias, and take the highest. Reward for the clip just played is the change in `cohesion_smooth` from 10 seconds after the clip started to its end, scaled to 0 to 1 by a clamp around zero, and applied as a Bernoulli update to that arm's Beta. The reward window and the scaling live in config.

**The action bias.** For each action in `action_rates`, the excess above normal is `max(0, rate - 1)`. Sitting leans on Furniture, phone on Machinery, drinking on Rivers, eating on Feast, each with a weight in config. The lean is added to that arm's draw, scaled by one over the occupancy band's size, and decays with a 90-second half-life from the last time the excess was seen. It leans; it never selects.

**The destination.** Ring plus arm names the target node. If a clip exists from the current node to the target, use it. If not, move one step along the shortest path through the clips that do exist. Staying on a node plays its loop clip if one exists; Barren without a loop probes to a Ring 1 node and returns.

**Daily personality.** A named parameter set chosen by the date at day start: prior strength (how fast it commits), Storm prior (risk appetite), reward scaling, and patience (the reward window). Four presets in config: Courtier, Operator, Accountant, Naif. At day start the Beta beliefs reset to the day's priors. The ledger is never reset.

**Resolume.** `resolume.py` sends `/composition/layers/{layer}/clips/{index}/connect 1` over OSC (UDP port 7000, library python-osc) and sets `/composition/layers/{layer}/audio/volume` for the stem layers. It reads the composition over REST (library requests) at start-up. `fake_resolume.py` is a tiny UDP listener that prints every message it receives, so the controller can be run and tested with Resolume closed.

**Audio.** Four stems per arm on four audio layers, in two banks of four so an arm change can crossfade: the outgoing bank ramps down and the incoming ramps up over the 5-second lead. Stem volumes within a bank follow the ring. Stub this behind one function first; the ramp logic can come later.

**The bus.** The controller connects to `ws://127.0.0.1:8765` as a client. It reads crowd messages and sends each decision message back into the socket; the bus rebroadcasts it (already built). The data wall needs one socket for everything.

**The ledger.** Append `decision` and `outcome` entries to the same `ledger.jsonl` the sensing bus writes, and a `day_start` entry naming the personality.

## Contract 3, as published

```json
{"stream": "decision", "t": 12.4, "from": "b", "to": "m1", "clip": "b_m1",
 "resolume_index": 47, "arm": "machinery", "reason": "action_bias",
 "context": "small", "personality": "Operator", "ring_target": 1}
```

`reason` is one of `ring`, `bandit`, `action_bias`, `path` (an intermediate step), `loop`, `probe`.

## Build order

1. `clipmap.py`: nodes, arm letters, naming rule, shortest path. Tested with a made-up clip list.
2. `resolume.py` and `fake_resolume.py`: read a layout, fire a clip, ramp a volume. Tested against the fake.
3. `clock.py` and `loop.py`: the 60-second cycle, reading the bus, writing decisions, ring only (arm fixed). First end-to-end run: fake room, bus, controller, fake Resolume.
4. `bandit.py`: Beta beliefs per arm per context, Thompson draw, reward from the cohesion delta, action bias with decay.
5. `personality.py` and the daily reset, the ledger entries.
6. `audio.py` stub.

Every number in `config/controller.yaml`. Tests without network except one loopback test. Record every decision message with `--record` for replay. Report after step 3 and again after step 5.
