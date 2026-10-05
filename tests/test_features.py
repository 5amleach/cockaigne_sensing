"""Features tests: scripted rooms, no GPU, no network.

Each test builds people messages by hand and checks the properties the
installation depends on, not exact values: the proxy cap, the reservoir's
continuity, the ring hysteresis, and the dwell on mood labels.
"""
import math

from cockaigne_sensing.config import load
from cockaigne_sensing.features import FeatureStage
from cockaigne_sensing.features.crowd import (clustering_score, ring_from_level,
                                              synchrony_score)
from cockaigne_sensing.features.person import PersonScorer

W, L = 6.1, 7.4
SPOT = (3.05, 3.5)


def person(pid, x, y, vx=0.0, vy=0.0, age=10.0, box_ratio=0.4, box_h=600):
    return {"id": pid, "x": x, "y": y, "vx": vx, "vy": vy, "age": age,
            "box_ratio": box_ratio, "box_h": box_h, "posture": "standing",
            "actions": {"phone": 0.0, "drink": 0.0, "eat": 0.0},
            "arousal": 0.5, "valence": 0.0}


def msg(t, people):
    return {"stream": "people", "t": t, "floor": {"w": W, "h": L}, "people": people}


def run_room(stage, script, t0=0.0, t1=60.0, dt=0.5):
    """Feed messages from t0 to t1; script(t) returns the people list. Returns crowd messages."""
    out = []
    t = t0
    while t <= t1:
        _, crowd = stage.push(msg(round(t, 3), script(t)))
        if crowd:
            out.append(crowd)
        t += dt
    return out


def test_lone_viewer_is_capped_below_ring_4():
    # One person parked on the viewing spot, still, for ten minutes: the best
    # a lone visitor can possibly do. They reach Ring 3 and never Ring 4.
    stage = FeatureStage(load())
    crowds = run_room(stage, lambda t: [person(1, *SPOT, age=t)], t1=600.0)
    assert all(c["cohesion_raw"] <= 0.75 + 1e-9 for c in crowds)
    assert all(c["accumulator"] <= 0.75 + 1e-9 for c in crowds)
    assert all(c["ring_target"] <= 3 for c in crowds)
    assert crowds[-1]["ring_target"] == 3  # the proxies do carry them up


def test_group_can_reach_ring_4():
    # Four people gathered at the spot, still, long dwell: relational evidence.
    stage = FeatureStage(load())
    group = [person(i, SPOT[0] + 0.3 * math.cos(i), SPOT[1] + 0.3 * math.sin(i), age=300)
             for i in range(4)]
    crowds = run_room(stage, lambda t: group, t1=300.0)
    assert crowds[-1]["ring_target"] == 4


def test_reservoir_is_continuous_when_occupancy_changes():
    stage = FeatureStage(load())
    crowds = run_room(stage, lambda t: [person(1, *SPOT, age=t)], t1=300.0)
    level_before = crowds[-1]["accumulator"]
    assert level_before > 0.5
    # A second person walks in, far from the first. The score changes; the
    # reservoir moves at its rates and never jumps or resets.
    two = lambda t: [person(1, *SPOT, age=300 + t), person(2, 5.5, 6.8, age=t)]
    crowds2 = run_room(stage, two, t0=300.5, t1=360.0)
    levels = [level_before] + [c["accumulator"] for c in crowds2]
    steps = [abs(b - a) for a, b in zip(levels, levels[1:])]
    assert max(steps) <= 0.021 + 1e-9  # at most rise_rate per one-second emit
    assert min(levels) > 0.4           # no reset


def test_empty_room_drains_to_barren():
    stage = FeatureStage(load())
    group = [person(i, SPOT[0] + 0.3 * i, SPOT[1], age=300) for i in range(4)]
    run_room(stage, lambda t: group, t1=300.0)
    crowds = run_room(stage, lambda t: [], t0=300.5, t1=500.0)
    levels = [c["accumulator"] for c in crowds]
    assert all(b <= a + 1e-9 for a, b in zip(levels, levels[1:]))  # only drains
    assert levels[-1] < 0.1 and crowds[-1]["ring_target"] == 0
    assert crowds[-1]["cohesion_raw"] == 0.0


def test_ring_hysteresis_holds_between_thresholds():
    up, down = [0.2, 0.4, 0.6, 0.8], [0.1, 0.3, 0.5, 0.7]
    assert ring_from_level(0.45, 0, up, down) == 2
    assert ring_from_level(0.35, 2, up, down) == 2   # between down[1] and up[2]: holds
    assert ring_from_level(0.29, 2, up, down) == 1   # below down[1]: drops
    assert ring_from_level(0.95, 1, up, down) == 4
    assert ring_from_level(0.05, 4, up, down) == 0


def test_synchrony_reads_alignment():
    aligned = [person(1, 1, 1, vx=0.5, vy=0.0), person(2, 3, 3, vx=0.5, vy=0.0)]
    opposed = [person(1, 1, 1, vx=0.5, vy=0.0), person(2, 3, 3, vx=-0.5, vy=0.0)]
    assert synchrony_score(aligned, 0.15) == 1.0
    assert synchrony_score(opposed, 0.15) == 0.0
    # One mover: no disagreement to measure.
    assert synchrony_score([aligned[0], person(2, 3, 3)], 0.15) == 1.0


def test_clustering_reads_gathering():
    tight = [person(1, 3.0, 3.5), person(2, 3.4, 3.5)]
    spread = [person(1, 0.5, 0.5), person(2, 5.6, 6.9)]
    assert clustering_score(tight, W, L, 2.0) > 0.8
    assert clustering_score(spread, W, L, 2.0) < 0.2


def test_posture_sitting_needs_width_and_a_stop():
    scorer = PersonScorer(load())
    for i in range(10):  # 4.5 seconds stopped with a wide rectangle
        m = msg(i * 0.5, [person(1, 2, 2, box_ratio=0.9)])
        scorer.update(m)
    assert m["people"][0]["posture"] == "sitting"
    m = msg(5.0, [person(1, 2, 2, box_ratio=0.9, vx=0.6)])
    scorer.update(m)
    assert m["people"][0]["posture"] == "walking"


def test_mood_label_holds_for_the_dwell_time():
    cfg = load()
    scorer = PersonScorer(cfg)
    labels = {}
    t = 0.0
    while t <= 14.0:
        box_h = 600 if t < 6.0 else 390  # a sudden slump at t = 6
        labels[round(t, 1)] = scorer.update(msg(t, [person(1, 2, 2, box_h=box_h)]))[1]
        t += 0.5
    assert labels[0.0] == "happy"
    assert labels[7.5] == "happy"   # slumped, but the dwell holds the label
    assert labels[14.0] == "sad"    # dwell elapsed, label follows


def test_run_entry_point_writes_both_streams(tmp_path):
    import json
    import subprocess
    import sys
    src = tmp_path / "people.jsonl"
    with open(src, "w") as f:
        for i in range(30):
            f.write(json.dumps(msg(i * 0.1, [person(1, *SPOT, age=i * 0.1)])) + "\n")
    out = tmp_path / "out.jsonl"
    r = subprocess.run([sys.executable, "-m", "cockaigne_sensing.features.run",
                        str(src), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    streams = [json.loads(line)["stream"] for line in open(out)]
    assert streams.count("people") == 30
    assert 3 <= streams.count("crowd") <= 4  # 2.9 seconds at one per second
