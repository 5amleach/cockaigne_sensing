"""floor: turns camera tracks (Contract 0) into the people list (Contract 1).

NOT YET WRITTEN. Brief for whoever builds it:

1. Calibration. For each camera, config/homography_<name>.json holds a 3x3
   matrix produced by tools.calibrate from four floor markers. Load it with
   numpy. cv2.perspectiveTransform applies it to a pixel point.

2. Feet. For each track, take the bottom centre of the box
   ((x1+x2)/2, y2) and convert it to metres.

2a. Wall content. The LED walls show a landscape with animals and
   figure-like shapes, and the detector sometimes fires on them (venue
   clip of 7 Sept, 40-48 s: a shape in the projected image was tracked as
   a person for eight seconds). Each camera has a floor polygon in
   config/sensing.yaml, in pixels of the detection frame, drawn by hand
   around the visible floor. A track whose feet point falls outside the
   polygon is dropped before conversion. cv2.pointPolygonTest does the
   test. The same test in metres (inside the floor rectangle) is a second
   guard after conversion.

3. Merge. Pool the floor points from all cameras for the same instant.
   Any two within merge_distance_m are one person; keep the one whose box
   was taller (closer to a camera, better view) as the "best view" for
   box_ratio and box_h.

4. Track on the floor. A simple constant-velocity tracker: predict each
   known person's position from their velocity, match predictions to the
   merged points nearest-first, keep ids for matches, start new ids for
   leftovers, drop anyone unseen for drop_after_s. Velocity is the average
   over velocity_window_s. Do not reach for a Kalman library; the floor is
   flat, people are slow, and the plain version is easier to read.

5. Emit Contract 1 at about ten messages a second with posture "standing",
   actions all zero, arousal 0.5, valence 0.0. features and actions fill
   those in later.

Test it from a recording: python -m cockaigne_sensing.floor.run tracks.jsonl
"""
