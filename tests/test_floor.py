"""Floor module tests. No GPU, no network, no video: synthetic data and the committed fixtures."""
import json
from pathlib import Path

import numpy as np

from cockaigne_sensing.config import load
from cockaigne_sensing.floor.camera import Camera, focal_from_hfov, homography_from_camera
from cockaigne_sensing.floor.homography import pixel_to_floor
from cockaigne_sensing.floor.run import FloorStage
from cockaigne_sensing.floor.tracker import FloorTracker, Sighting, people_message

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


def test_same_camera_track_keeps_its_number_through_a_floor_jump():
    # Legs hidden for a moment: the feet point leaps 2 m, but the camera's
    # tracker kept its id, so the person keeps theirs.
    tr = FloorTracker(gate_m=1.2)
    a = tr.update(0.0, [Sighting(2.0, 4.0, 0.4, 300, 0.9, camera="cam1", det_id=5, box=(1, 1, 2, 2))])
    b = tr.update(0.2, [Sighting(2.0, 6.0, 0.4, 150, 0.9, camera="cam1", det_id=5, box=(1, 1, 2, 2))])
    assert a[0].id == b[0].id == 1


def test_a_visitor_lost_for_half_a_minute_gets_their_number_back():
    tr = FloorTracker(drop_after_s=60.0, coast_s=1.0, gate_m=1.2)
    for i in range(10):   # walking, then out of view at y=3.0
        tr.update(i * 0.2, [Sighting(2.0, 2.1 + 0.1 * i, 0.4, 300, 0.9, camera="c", det_id=1)])
    assert tr.update(10.0, []) == []    # quiet while unseen: not counted
    # Back 30 s later, half a metre from where they were lost, with a new camera track.
    people = tr.update(30.0, [Sighting(2.3, 3.4, 0.4, 300, 0.9, camera="c", det_id=9)])
    assert [p.id for p in people] == [1]
    assert people[0].vx == 0.0 and people[0].vy == 0.0   # the old heading is not kept
    # Someone appearing far from anywhere a visitor was lost is a new number.
    people = tr.update(30.2, [Sighting(2.3, 3.4, 0.4, 300, 0.9, camera="c", det_id=9),
                              Sighting(0.5, 6.5, 0.4, 300, 0.9, camera="c", det_id=10)])
    assert sorted(p.id for p in people) == [1, 2]


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


def test_seen_person_carries_view_and_a_coasting_person_does_not():
    tr = FloorTracker(coast_s=1.0)
    seen = tr.update(0.0, [Sighting(2.0, 3.0, 0.4, 500, 0.88, camera="cam1", det_id=7,
                                    box=(412, 118, 470, 310), w=640, h=360)])
    msg = people_message(0.0, W, L, seen)
    assert msg["people"][0]["view"] == {"camera": "cam1", "track": 7,
                                       "box": [412, 118, 470, 310],
                                       "w": 640, "h": 360, "conf": 0.88}
    coasting = tr.update(0.5, [])   # missed this step: still reported, but unseen
    msg = people_message(0.5, W, L, coasting)
    assert len(msg["people"]) == 1 and msg["people"][0]["view"] is None


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


def _bent_camera_file(tmp_path):
    """A calibration that records a lens bend and the camera's place, like the
    23 Nov Light Room fit: 3.3 m up at the closed end, looking back at 19 degrees."""
    import cv2
    from cockaigne_sensing.floor.lens import picture_height, straighten
    lens, pose, size = {"f": 436.0, "k1": 0.8}, [3.6, 8.7, 3.3, 180.0, 19.0, 0.0], (640, 360)

    def to_pixel(x, y):
        # The column: project with the bend, using the same steps lens.py uses.
        from cockaigne_sensing.floor.lens import _axes
        cam = (np.array([x, y, 0.0]) - np.array(pose[:3])) @ _axes(*pose[3:]).T
        xu, yu = cam[0] / cam[2], cam[1] / cam[2]
        xd, yd = xu, yu
        for _ in range(8):
            s = 1 + lens["k1"] * (xd * xd + yd * yd)
            xd, yd = xu / s, yu / s
        return size[0] / 2 + lens["f"] * xd, size[1] / 2 + lens["f"] * yd

    floor = np.array([[1.0, 1.0], [6.2, 1.0], [6.2, 5.0], [1.0, 5.0]], np.float32)
    px = np.array([straighten(*to_pixel(x, y), lens, size) for x, y in floor], np.float32)
    H = cv2.getPerspectiveTransform(px, floor)
    path = tmp_path / "bent.json"
    path.write_text(json.dumps({"H": H.tolist(), "image_size": list(size), "lens": lens, "pose": pose}))
    return path, to_pixel, lambda x, y, z: picture_height(pose, lens, size, x, y, z)


def test_lens_bend_is_straightened_and_wall_figures_fail_the_height_check(tmp_path):
    path, to_pixel, row_at = _bent_camera_file(tmp_path)
    cfg = load()
    cfg["floor"] = {"width_m": 7.2, "length_m": 9.6}
    cfg["cameras"] = [{"name": "c", "homography": str(path), "floor_polygon": []}]
    stage = FloorStage(cfg)

    def box_for(x, y, tall_m):
        u, v = to_pixel(x, y)
        return [u - 15, row_at(x, y, tall_m), u + 15, v]

    msg = {"t": 1.0, "camera": "c", "w": 640, "h": 360, "tracks": [
        {"id": 1, "box": box_for(1.2, 2.0, 1.7), "conf": 0.9},   # a visitor near the picture's edge
        {"id": 2, "box": box_for(6.8, 3.5, 5.0), "conf": 0.5},   # a figure on the wall, far too tall
        {"id": 3, "box": box_for(3.6, 3.0, 0.3), "conf": 0.5},   # far too short to be anyone
    ]}
    sightings = stage.sightings(msg)
    assert [s.det_id for s in sightings] == [1]
    # The bend is undone, so the edge-of-picture visitor lands where they stand.
    assert abs(sightings[0].x - 1.2) < 0.05 and abs(sightings[0].y - 2.0) < 0.05
    # A box whose bottom is on the picture's lower edge has its feet out of view.
    msg["tracks"] = [{"id": 4, "box": [300, 150, 340, 359], "conf": 0.9}]
    assert stage.sightings(msg) == []
    # With the check switched off in config, the wall figure is kept again.
    cfg["floor_tracker"] = dict(cfg["floor_tracker"], height_check=dict(cfg["floor_tracker"]["height_check"], enabled=False))
    msg["tracks"] = [{"id": 2, "box": box_for(6.8, 3.5, 5.0), "conf": 0.5}]
    assert len(FloorStage(cfg).sightings(msg)) == 1
