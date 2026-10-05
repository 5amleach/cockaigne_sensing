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
    merged = tr.merge([Sighting(2.0, 2.0, 0.4, 500, 0.9), Sighting(2.2, 2.3, 0.4, 300, 0.8),
                       Sighting(5.0, 5.0, 0.4, 400, 0.9)])
    assert len(merged) == 2
    lead = next(m for m in merged if m.x < 3)
    assert lead.box_h == 500 and abs(lead.x - 2.1) < 1e-9


def test_tracker_drops_the_unseen():
    tr = FloorTracker(drop_after_s=1.0)
    tr.update(0.0, [Sighting(1, 1, 0.4, 500, 0.9)])
    assert len(tr.update(0.5, [])) == 0 and len(tr.people) == 1
    tr.update(2.0, [])
    assert len(tr.people) == 0


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
