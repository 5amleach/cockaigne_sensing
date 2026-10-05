# Bench: floor module on the two venue clips, 5 October 2026

The floor module now runs end to end on the 7 September footage: camera tracks in, people list in metres out. Calibration is approximate (see below) and the camera height makes the positions crude. Both are fixed by the planned high mounting; the point of this run was to have the whole chain working on real data now.

Fixtures: `bench/fixtures/venue_A_from_data_wall_tracks.jsonl` (200 s, camera at the data-wall end looking into the U) and `venue_B_from_closed_end_tracks.jsonl` (68 s, camera at the closed end looking back). These are the detector's output, boxes only, no pictures. Config: `config/venue_bench.yaml` with homographies `config/homography_venueA.json` and `_venueB.json`.

## Floor size

From the venue pixel maps at 2.6 mm pitch: the data wall is 2352 px = 6.1 m, the U wall is 8064 px = 21.0 m, so each arm is (21.0 − 6.1) / 2 = 7.4 m. The floor is taken as 6.1 m wide by 7.4 m deep. Confirm with a tape on site. The LED corners are curved, which the model ignores.

## Calibration without markers

`tools.calibrate_auto` fits the camera's height, downward tilt and distance from its wall using the people in the recording (a standing person is about 1.7 m tall, so the height of their rectangle says how far away they are) plus one known point, the floor line at the middle of the far wall. Results:

- Camera A: 1.27 m in front of the data wall, 1.80 m high, tilted 3° up. Median box error 13 px over 1,661 boxes.
- Camera B: 1.8 m in front of the closed end, 2.15 m high, tilted 2° down. Median box error 37 px; the far-wall corners sit 50 px off, which is the lens's barrel distortion.

Reprojection of the far wall is within 20–50 px, so positions near the middle of the picture are good to a quarter of a metre or so.

## What the plan views show

`2026-10-05-plan-view-A.png` and `-B.png`.

Both cameras were at head height and roughly level. A level camera at 1.8 m cannot see the floor within about 3.7 m of itself: the bottom of the picture is already that far away. Anyone closer has their feet out of frame, the rectangle's bottom edge is the frame edge, and their position lands on one line (y ≈ 5.2 m in clip A, y ≈ 1.85 m in clip B). Most of the walking in both clips happened in that zone, so the plan views show people sliding along a line rather than crossing the floor. In clip A a round object on the floor near the camera hides feet as well, which produces the hump near x = 2.5 m.

This is the camera-height problem again, seen from the floor's side. From a high mount tilted 30–45° down, feet stay in frame across the whole floor and this artefact disappears.

## What works

- Wall imagery is removed. The figure in the projected landscape that the detector tracked for eleven seconds (clip A, 40–52 s) converts to a point beyond the far wall and is dropped by the bounds check. No hand-drawn polygon was needed for it.
- Ids. Clip A: the lone visitor kept one id for 36 s; after three people arrive, ids 8, 11 and 12 hold for 44, 70 and 37 s. Clip B: two of three people hold one id for most of the clip. Id changes come from occlusion near the camera, as before.
- Headcount per second matches what is visible, apart from the moments of occlusion.
- Test `test_venue_fixture_runs_through_the_stage` replays clip A through the stage on every test run.

## Not done

Hand-drawn floor polygons (not needed yet). Real calibration from floor markers (`tools.calibrate`, after mounting). Any use of the sub-stream (no sub-stream recording exists).
