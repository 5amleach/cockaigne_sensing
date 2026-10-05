"""Fake room tests: the scripted scenarios behave the way the room should."""
from cockaigne_sensing.config import load
from cockaigne_sensing.features import FeatureStage
from cockaigne_sensing.tools.fake_room import SCENARIOS, messages

W, L = 6.1, 7.4


def run_scenario(name):
    stage = FeatureStage(load())
    duration, actors = SCENARIOS[name]()
    crowds, last_people = [], None
    for msg in messages(duration, actors, W, L):
        people_msg, crowd = stage.push(msg)
        if people_msg["people"]:
            last_people = people_msg
        if crowd:
            crowds.append(crowd)
    return crowds, last_people


def test_positions_are_consistent_with_velocities():
    duration, actors = SCENARIOS["lone"]()
    prev = {}
    for msg in messages(duration, actors, W, L):
        for p in msg["people"]:
            if p["id"] in prev:
                t0, x0, y0, vx, vy = prev[p["id"]]
                dt = msg["t"] - t0
                # The movement must be explained by the velocity at one end of
                # the step (the person may turn at a waypoint mid-step), give
                # or take the two-centimetre jitter.
                assert min(abs(p["x"] - (x0 + vx * dt)),
                           abs(p["x"] - (x0 + p["vx"] * dt))) < 0.06
                assert min(abs(p["y"] - (y0 + vy * dt)),
                           abs(p["y"] - (y0 + p["vy"] * dt))) < 0.06
            prev[p["id"]] = (msg["t"], p["x"], p["y"], p["vx"], p["vy"])


def test_lone_viewer_scenario_climbs_but_stays_capped():
    crowds, _ = run_scenario("lone")
    assert all(c["ring_target"] <= 3 for c in crowds)
    assert all(c["accumulator"] <= 0.751 for c in crowds)
    assert crowds[-1]["ring_target"] >= 2  # settling on the spot does lift the room


def test_group_scenario_reaches_a_high_ring_then_empties():
    crowds, _ = run_scenario("group")
    assert max(c["ring_target"] for c in crowds) >= 3
    assert crowds[-1]["n"] == 0


def test_sitting_scenario_is_read_as_sitting():
    crowds, last_people = run_scenario("sitting")
    assert last_people["people"][0]["posture"] == "sitting"
    assert crowds[-1]["actions"]["sitting"] == 1


def test_leaving_scenario_drains():
    crowds, _ = run_scenario("leaving")
    assert crowds[-1]["n"] == 0
    levels = [c["accumulator"] for c in crowds if c["n"] == 0]
    assert levels[-1] <= levels[0] + 1e-9  # once empty, the reservoir only drains
