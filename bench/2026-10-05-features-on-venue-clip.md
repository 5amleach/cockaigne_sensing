# Bench: features module on venue clip A, 5 October 2026

The features module (built today) replayed over the clip A fixture, through the floor module:

```
python -m cockaigne_sensing.floor.run bench/fixtures/venue_A_from_data_wall_tracks.jsonl --out people.jsonl --config config/venue_bench.yaml
python -m cockaigne_sensing.features.run people.jsonl --out full.jsonl --config config/venue_bench.yaml
```

1,000 people messages in, 1,000 augmented messages and 200 crowd messages out. No tuning was done; every number is the starting guess in `config/venue_bench.yaml`.

## What the crowd state did

| t (s) | n | clustering | stillness | cohesion_raw | reservoir | ring |
|---|---|---|---|---|---|---|
| 20 | 1 | 1.00 | 0.00 | 0.20 | 0.08 | 0 |
| 60 | 0 | 0.00 | 0.00 | 0.00 | 0.15 | 1 |
| 100 | 2 | 0.25 | 0.50 | 0.39 | 0.20 | 1 |
| 140 | 2 | 0.85 | 0.50 | 0.61 | 0.30 | 1 |
| 199 | 2 | 0.38 | 0.50 | 0.47 | 0.46 | 2 |

The shape is right. The lone visitor (15–55 s) scores through the proxies only and barely moves the reservoir because they keep walking. The empty half-minute drains gently rather than resetting. When the group arrives the relational signals take over, the reservoir climbs at its capped rate with no jumps, and the room ends on Ring 2. The clip is 200 s; higher rings are meant to take longer than that.

## What is crude, and why that is expected

- Headcount reads 2 at the end where 3 are present: the third person is the one nearest the camera, whose feet are out of frame (the known camera-height problem; see the floor bench note).
- Stillness sits at 0.50 while people near the camera slide along the collapsed-feet line: their positions move even when they do not. Same cause.
- Valence swings to -1 when a rectangle shrinks for reasons other than slumping (occlusion, the frame edge). Mood labels are provisional until footage from the mounted height exists; the dwell timer keeps them from flickering, not from being wrong.

None of these is a features bug to fix now; all trace to the level camera. The module to judge against the next capture is this one.
