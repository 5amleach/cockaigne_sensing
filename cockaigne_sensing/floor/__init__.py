"""floor: turns camera tracks (Contract 0) into the people list (Contract 1).

Built 5 October 2026 and tested on the two venue clips from 7 September.

How it works, in order:

1. Calibration. Each camera has a homography, a 3x3 conversion from picture
   pixels to floor metres, saved in config/homography_<name>.json. Until
   the cameras are mounted for real and calibrated from measured floor
   markers (tools.calibrate, not yet written), tools.calibrate_auto produces
   an approximate one from the people in a recording plus one known point
   on the far wall. See homography.py and camera.py.

2. Feet. For each rectangle, the bottom centre is taken as the feet and
   converted to metres.

3. Off-floor points are dropped. The LED walls show a landscape with
   animals and figure-like shapes, and the detector sometimes fires on
   them. Their "feet" convert to a point beyond the floor's edge, so a
   bounds check in metres removes them. A hand-drawn pixel polygon per
   camera (floor_polygon in config) can be added as a second guard.

4. Merge. Sightings from different cameras within merge_distance_m of each
   other are the same person. The tallest rectangle (closest camera) is
   kept as the best view for box_ratio and box_h.

5. Track. A plain constant-velocity tracker keeps one id per person across
   the whole room, predicts where each will be, matches nearest first,
   drops anyone unseen for drop_after_s. See tracker.py.

6. Emit Contract 1 with posture "standing", actions all zero, arousal 0.5
   and valence 0.0. features and actions overwrite those later.

Run it from a recording:
    python -m cockaigne_sensing.floor.run tracks.jsonl --out people.jsonl
"""
from .tracker import FloorTracker, Sighting, people_message

__all__ = ["FloorTracker", "Sighting", "people_message"]
