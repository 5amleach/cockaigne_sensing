"""Floor module tests. No GPU, no network, no video: synthetic data and the committed fixtures."""
import json
from pathlib import Path

import numpy as np

from cockaigne_sensing.config import load
from cockaigne_sensing.floor.camera import Camera, focal_from_hfov, homography_from_camera
from cockaigne_sensing.floor.homography import pixel_to_floor
from cockaigne_sensing.floor.run import FloorStage
from cockaigne_sensing.floor.tracker import FloorTracker, Sighting

REPO = Path(__file__).resolve().parent.parent
W, L = 6.1, 7.4


def test_homography_round_trip():
    cam = Camera(3.05, 0.0, 3.0, 35.0, 0.0, "into_u", focal_from_hfov(3840, 87), 1920, 1080)
    H = homography_from_camera(cam, W, L)
    for x, y in [(1.0, 2.0), (3.05, 3.5), (5.5, 7.0), (0.5, 6.5)]:
        u, v = cam.project(np.array([[x, y]]))[0]
        fx, fy = pixel_to_floor(H, u, v)
        assert abs(fx - x) < 0.01 and abs(fy - y) < 0.01


def test_tracker_keeps_one_id_for_a_walker():
    tr = FloorTracker(merge_distance_m=0.5, drop_after_s=3.0, velocity_window_s=1.0)
    ids = set()
    for i in range(50):  # 10 seconds at 5 Hz, walking 0.5 m/s along y
        t = i * 0.2
        people = tr.update(t, [Sighting(3.0, 1.0 + 0.5 * t, 0.4, 600, 0.9)])
        assert len(people) == 1
        ids.add(people[0].id)
    assert ids == {1}
    assert abs(people[0].vy - 0.5) < 0.1 and abs(people[0].vx) < 0.05
    assert abs(people[0].first_seen) < 1e-9


def test_merge_collapses_two_cameras_views_of_one_person():
    tr = FloorTracker(merge_distance_m=0.5)
    merged = tr.merge([Sighting(2.0, 2.0, 0.4, 500, 0.9, camera="c1"),
                       Sighting(2.2, 2.3, 0.4, 300, 0.8, camera="c2"),
                       Sighting(5.0, 5.0, 0.4, 400, 0.9, camera="c1")])
    assert len(merged) == 2
    lead = next(m for m in merged if m.x < 3)
    assert lead.box_h == 500 and abs(lead.x - 2.1) < 1e-9


def test_two_people_close_together_in_one_camera_stay_two():
    # The audit's case: 20 cm apart, one camera, boxes side by side.
    tr = FloorTracker(merge_distance_m=0.5)
    merged = tr.merge([Sighting(2.0, 2.0, 0.4, 500, 0.9, camera="c1", box=(100, 50, 200, 550)),
                       Sighting(2.2, 2.0, 0.4, 490, 0.9, camera="c1", box=(210, 55, 310, 545))])
    assert len(merged) == 2
    # A duplicate detection of one person, heavily overlapping, still merges.
    merged = tr.merge([Sighting(2.0, 2.0, 0.4, 500, 0.9, camera="c1", box=(100, 50, 200, 550)),
                       Sighting(2.05, 2.0, 0.4, 480, 0.9, camera="c1", box=(105, 60, 205, 540))])
    assert len(merged) == 1


def test_a_long_absent_id_is_not_revived():
    # The audit's case: seen at t=0, nothing for an hour, same spot again.
    tr = FloorTracker(drop_after_s=3.0)
    tr.update(0.0, [Sighting(1.0, 1.0, 0.4, 500, 0.9)])
    people = tr.update(3600.0, [Sighting(1.0, 1.0, 0.4, 500, 0.9)])
    assert len(people) == 1
    assert people[0].id == 2                 # a new person, not the ghost
    assert people[0].first_seen == 3600.0    # with a new age


def test_tracker_coasts_then_goes_quiet_then_drops():
    tr = FloorTracker(drop_after_s=2.0, coast_s=1.0)
    tr.update(0.0, [Sighting(1, 1, 0.4, 500, 0.9)])
    assert len(tr.update(0.5, [])) == 1    # within coast_s: still reported
    assert len(tr.update(1.6, [])) == 0    # past coast_s: quiet, but remembered
    assert len(tr.people) == 1
    tr.update(3.0, [])
    assert len(tr.people) == 0             # past drop_after_s: forgotten


def test_coasted_person_moves_along_their_velocity():
    tr = FloorTracker(coast_s=1.0, bounds=(6.1, 7.4))
    for i in range(10):  # walking 0.5 m/s along y, last seen at t=1.8, y=1.9
        tr.update(i * 0.2, [Sighting(3.0, 1.0 + 0.1 * i, 0.4, 600, 0.9)])
    out = tr.update(2.4, [])  # missed, 0.6 s later
    assert len(out) == 1
    assert abs(out[0].x - 3.0) < 0.05 and abs(out[0].y - 2.2) < 0.15
    assert out[0].first_seen == 0.0  # age keeps counting from the real first sighting


def test_stage_drops_feet_that_map_off_the_floor(tmp_path):
    cam = Camera(3.05, 0.0, 3.0, 35.0, 0.0, "into_u", focal_from_hfov(3840, 87), 1920, 1080)
    H = homography_from_camera(cam, W, L)
    hpath = tmp_path / "h.json"
    hpath.write_text(json.dumps({"H": H.tolist()}))
    cfg = load()
    cfg["floor"] = {"width_m": W, "length_m": L}
    cfg["cameras"] = [{"name": "c", "homography": str(hpath), "floor_polygon": []}]
    stage = FloorStage(cfg)
    on_floor = cam.project(np.array([[3.0, 4.0]]))[0]          # a real person's feet
    on_wall = cam.project(np.array([[3.0, 9.5]]))[0]           # "feet" of a figure painted on the far wall
    msg = {"t": 1.0, "camera": "c", "w": 3840, "h": 2160, "tracks": [
        {"id": 1, "box": [on_floor[0] - 50, on_floor[1] - 300, on_floor[0] + 50, on_floor[1]], "conf": 0.9},
        {"id": 2, "box": [on_wall[0] - 30, on_wall[1] - 150, on_wall[0] + 30, on_wall[1]], "conf": 0.5},
    ]}
    sightings = stage.sightings(msg)
    assert len(sightings) == 1 and abs(sightings[0].y - 4.0) < 0.05


def test_calibration_scales_to_the_messages_frame_size(tmp_path):
    # A 4K calibration used on a sub-stream: pixels are scaled by the ratio.
    cam = Camera(3.05, 0.0, 3.0, 35.0, 0.0, "into_u", focal_from_hfov(3840, 87), 1920, 1080)
    H = homography_from_camera(cam, W, L)
    hpath = tmp_path / "h.json"
    hpath.write_text(json.dumps({"H": H.tolist(), "image_size": [3840, 2160]}))
    cfg = load()
    cfg["floor"] = {"width_m": W, "length_m": L}
    cfg["cameras"] = [{"name": "c", "homography": str(hpath), "floor_polygon": []}]
    stage = FloorStage(cfg)
    u, v = cam.project(np.array([[3.0, 6.0]]))[0]   # a real floor point, in 4K pixels
    u, v = u * 640 / 3840, v * 360 / 2160           # ...seen in a 640x360 frame
    msg = {"t": 1.0, "camera": "c", "w": 640, "h": 360,
           "tracks": [{"id": 1, "box": [u - 10, v - 60, u + 10, v], "conf": 0.9}]}
    sightings = stage.sightings(msg)
    assert len(sightings) == 1
    assert abs(sightings[0].x - 3.0) < 0.05 and abs(sightings[0].y - 6.0) < 0.05
    # A different aspect means the wrong calibration: that camera is skipped.
    msg["w"], msg["h"] = 640, 480
    assert stage.sightings(msg) == []


def test_venue_fixture_runs_through_the_stage():
    cfg = load(REPO / "config" / "venue_bench.yaml")
    stage = FloorStage(cfg)
    from cockaigne_sensing.bus import replay
    n_msgs, n_with_people, worst = 0, 0, 0.0
    for msg in replay(REPO / "bench" / "fixtures" / "venue_A_from_data_wall_tracks.jsonl", stream="tracks"):
        out = stage.push(msg)
        if out:
            n_msgs += 1
            n_with_people += bool(out["people"])
            for p in out["people"]:
                worst = max(worst, -p["x"], p["x"] - W, -p["y"], p["y"] - L)
    assert n_msgs > 900 and n_with_people > 500
    assert worst <= 0.31  # nothing beyond the floor plus the allowed margin
