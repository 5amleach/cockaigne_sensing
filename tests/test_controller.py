"""Controller tests, the map, the fake Resolume, the decision loop. One OSC
loopback test; everything else stays off the network."""
import pytest

from cockaigne_controller.clipmap import BARREN, ClipMap, node_ring, parse_clip_name
from cockaigne_controller.clock import ClipClock
from cockaigne_controller.loop import Controller
from cockaigne_controller.resolume import layout_from_composition
from tests.helpers import ARMS, climb_to, crowd, full_pool, make_controller, step


def test_clip_names_parse_by_the_rule():
    assert parse_clip_name("a1m1", ARMS, 4) == ("a1", "m1")
    assert parse_clip_name("b_m1", ARMS, 4) == ("b", "m1")
    assert parse_clip_name("bm1", ARMS, 4) == ("b", "m1")
    assert parse_clip_name("M4M4", ARMS, 4) == ("m4", "m4")   # a loop, case ignored
    assert parse_clip_name("s3b", ARMS, 4) == ("s3", "b")     # a collapse
    assert parse_clip_name("ident_logo", ARMS, 4) is None     # not a move clip
    assert parse_clip_name("a5a1", ARMS, 4) is None           # no ring 5


def test_map_reports_what_is_missing():
    pool = [n for n in full_pool() if n not in ("m4m4", "f2b")]
    problems = ClipMap(pool, ARMS).missing()
    assert any("loop clip for m4" in p for p in problems)
    assert any("f2 to b" in p for p in problems)
    # A node nothing leads into shows up as unroutable.
    pool = [n for n in full_pool()
            if (parse_clip_name(n, ARMS, 4) or ("", ""))[1] != "c1"]
    problems = ClipMap(pool, ARMS).missing()
    assert any("no route" in p and "c1" in p for p in problems)
    # The pool that once crashed a Barren probe is now refused at start-up.
    pool = [n for n in full_pool() if n not in ("b_b", "b_m1")]
    problems = ClipMap(pool, ARMS).missing()
    assert any("b to m1" in p and "probe" in p for p in problems)
    # An arm cut off from its ring neighbours is a ring-preserving gap.
    pool = [n for n in full_pool()
            if not (parse_clip_name(n, ARMS, 4)
                    and {parse_clip_name(n, ARMS, 4)[0][1:], parse_clip_name(n, ARMS, 4)[1][1:]} == {"2"}
                    and "s2" in (parse_clip_name(n, ARMS, 4)))]
    problems = ClipMap(pool, ARMS).missing()
    assert any("ring-preserving" in p and "s2" in p for p in problems)


def test_shortest_path_steps_through_existing_clips():
    cmap = ClipMap(full_pool(), ARMS)
    assert cmap.next_step("b", "m3") == "m1"      # b -> m1 -> m2 -> m3
    assert cmap.next_step("m1", "m2") == "m2"     # direct
    assert cmap.next_step("m3", "a2") == "b"      # collapse, then out the other arm
    assert cmap.clip_for("m4", "m4") == "m4m4"


def test_ring_only_loop_climbs_and_collapses():
    c = make_controller(default_arm="machinery")
    c.observe(crowd(59.0, 1))
    d = step(c, 60.0)
    assert (d["from"], d["to"], d["reason"]) == ("b", "m1", "ring")
    c.observe(crowd(119.0, 3))
    d = step(c, 120.0)
    assert (d["to"], d["reason"]) == ("m2", "path")   # no m1 -> m3 clip: step
    c.observe(crowd(179.0, 3))
    d = step(c, 180.0)
    assert (d["to"], d["reason"]) == ("m3", "ring")
    c.observe(crowd(239.0, 0))
    d = step(c, 240.0)
    assert (d["to"], d["clip"], d["arm"]) == ("b", "m3b", "barren")  # direct collapse


def climb_to(c, ring, t0=60.0):
    """Walk the controller to machinery at this ring, fresh crowd and a
    confirmed fire each cycle. Returns at the moment of arrival."""
    goal = "b" if ring == 0 else f"m{ring}"
    t = t0
    for _ in range(12):
        c.observe(crowd(t - 1.0, ring))
        d = step(c, t)
        t += 60.0
        if d["to"] == goal:
            return d, t
    raise AssertionError(f"never reached {goal}")


def test_staying_put_loops_probes_or_moves_sideways():
    # Barren with a loop clip loops.
    c = make_controller()
    c.observe(crowd(59.0, 0))
    d = step(c, 60.0)
    assert (d["to"], d["reason"], d["clip"]) == ("b", "loop", "b_b")
    # Without a Barren loop clip, Barren probes out to Ring 1 and returns.
    c = make_controller(pool=[n for n in full_pool() if n != "b_b"])
    c.observe(crowd(59.0, 0))
    d = step(c, 60.0)
    assert (d["to"], d["reason"]) == ("m1", "probe")
    c.observe(crowd(119.0, 0))
    d = step(c, 120.0)
    assert (d["to"], d["reason"]) == ("b", "ring")
    # Holding Ring 3 is a sideways move that never leaves the ring.
    c = make_controller()
    _, t = climb_to(c, 3)
    c.observe(crowd(t - 1.0, 3))
    d = step(c, t)
    assert d["reason"] == "lateral"
    assert d["from"] == "m3" and node_ring(d["to"]) == 3 and d["to"] != "m3"
    c.observe(crowd(t + 59.0, 3))
    d = step(c, t + 60.0)
    assert (d["to"], d["reason"]) == ("m3", "ring")   # the fixed arm pulls it home
    # Ring 4 has a loop and uses it.
    c = make_controller()
    _, t = climb_to(c, 4)
    c.observe(crowd(t - 1.0, 4))
    d = step(c, t)
    assert (d["from"], d["to"], d["reason"]) == ("m4", "m4", "loop")


def test_blind_controller_steps_down_to_barren():
    c = make_controller()
    _, t0 = climb_to(c, 3)
    walk = []
    for i in range(4):          # sensing has gone quiet; the clock keeps going
        t = t0 + 60.0 * (i + 1)
        assert c.is_blind(t)
        d = step(c, t)
        walk.append((d["to"], d["ring_target"]))
    assert walk == [("m2", 2), ("m1", 1), ("b", 0), ("b", 0)]


def test_blind_descent_starts_from_the_displayed_position():
    # The audit's reproduction: wall at m1, last request Ring 4, sensing dies.
    # The old code climbed to m2; the descent must follow the wall, not the wish.
    c = make_controller()
    c.observe(crowd(59.0, 4))
    d = step(c, 60.0)                 # first hop toward ring 4
    assert d["to"] == "m1"
    d = step(c, 120.0)                # silence since t=59: blind
    assert (d["to"], d["ring_target"]) == ("b", 0)


def test_stale_crowd_time_counts_as_blind():
    # The same message replayed with fresh receipt times is not freshness.
    c = make_controller()
    c.observe(crowd(10.0, 2), now=10.0)
    assert not c.is_blind(20.0)
    for receipt in (50.0, 80.0, 110.0):
        c.observe(crowd(10.0, 2), now=receipt)   # t never advances
    assert c.is_blind(110.0)


def test_unconfirmed_fire_keeps_the_displayed_position():
    c = make_controller()
    c.observe(crowd(59.0, 1))
    d1, _ = c.decide(60.0)            # fired, but Resolume never confirmed
    assert c.displayed == "b"
    c.observe(crowd(119.0, 1))
    d2, _ = c.decide(120.0)           # the retry plans from reality
    assert (d2["from"], d2["to"]) == (d1["from"], d1["to"])
    c.confirm_fired(d2, 120.0)
    assert c.displayed == "m1"


def test_clock_fires_audio_lead_then_clip():
    clock = ClipClock(clip_s=60.0, audio_lead_s=5.0)
    clock.start(100.0)
    assert not clock.audio_due(154.9) and not clock.clip_due(159.9)
    assert clock.audio_due(155.0)
    clock.mark_audio()
    assert not clock.audio_due(156.0)   # once per clip
    assert clock.clip_due(160.0)


def test_occupancy_context_comes_from_n_smooth():
    c = make_controller()
    assert c.context() == "solo"
    c.observe(crowd(1.0, 2, n=8))     # features did the smoothing already
    assert c.context() == "medium"


def test_layout_from_composition_reads_nested_names():
    data = {"layers": [
        {"clips": [{"name": {"value": "b_m1"}}, {"name": "m1m2"}, {}]},
        {"clips": [{"name": {"value": "stem_arch_1"}}]},
    ]}
    layout = layout_from_composition(data)
    assert layout["b_m1"] == (1, 1) and layout["m1m2"] == (1, 2)
    assert layout["stem_arch_1"] == (2, 1)


def test_osc_loopback_against_the_fake():
    # The one loopback test: a clip fire and a volume change arrive at the
    # fake Resolume exactly as Resolume would see them.
    import time
    from cockaigne_controller.fake_resolume import FakeResolume
    from cockaigne_controller.resolume import Resolume
    fake = FakeResolume(quiet=True)
    fake.start()
    try:
        res = Resolume("127.0.0.1", fake.port, rest_port=0)
        res.fire_clip(1, 47)
        res.set_volume(3, 0.8)
        deadline = time.time() + 2
        while len(fake.received) < 2 and time.time() < deadline:
            time.sleep(0.02)
    finally:
        fake.stop()
    assert ("/composition/layers/1/clips/47/connect", (1,)) in fake.received
    volume = next(args for addr, args in fake.received
                  if addr == "/composition/layers/3/audio/volume")
    assert volume[0] == pytest.approx(0.8)  # OSC carries 32-bit floats


def test_connected_clip_is_read_from_the_layer_json():
    from cockaigne_controller.resolume import connected_from_layer
    data = {"clips": [{"connected": {"value": "Disconnected"}},
                      {"connected": {"value": "Connected"}},
                      {"connected": False}]}
    assert connected_from_layer(data) == 2
    assert connected_from_layer({"clips": [{"connected": True}]}) == 1
    assert connected_from_layer({"clips": []}) is None


def test_fire_is_confirmed_retried_once_and_never_raises():
    import asyncio
    import logging
    from cockaigne_controller.run import fire_confirmed
    log = logging.getLogger("test_fire")

    class WrongUntilRefired:
        def __init__(self):
            self.fires = 0
        def fire_clip(self, layer, index):
            self.fires += 1
            return True
        def connected_clip(self, layer):
            return 3 if self.fires >= 2 else 5   # right only after the retry

    stub = WrongUntilRefired()
    assert asyncio.run(fire_confirmed(stub, 1, 3, log, confirm_s=0.1, poll_s=0.02))
    assert stub.fires == 2

    class NoRest(WrongUntilRefired):
        def connected_clip(self, layer):
            raise OSError("connection refused")

    dead = NoRest()
    assert asyncio.run(fire_confirmed(dead, 1, 3, log, confirm_s=0.1, poll_s=0.02))
    assert dead.fires == 1   # nothing to confirm against: counts as shown

    class AlwaysWrong(WrongUntilRefired):
        def connected_clip(self, layer):
            return 7

    wrong = AlwaysWrong()
    assert not asyncio.run(fire_confirmed(wrong, 1, 3, log, confirm_s=0.1, poll_s=0.02))
    assert wrong.fires == 2  # one retry, then the caller keeps displayed put

    class DeadSocket:
        def __init__(self):
            self.fires = 0
        def fire_clip(self, layer, index):
            self.fires += 1
            return False   # the OSC send itself failed

    sock = DeadSocket()
    assert not asyncio.run(fire_confirmed(sock, 1, 3, log, confirm_s=0.1, poll_s=0.02))
    assert sock.fires == 2   # one retry of the send, then give up, never raise


def test_fire_clip_itself_never_raises():
    from cockaigne_controller.resolume import Resolume
    res = Resolume("127.0.0.1", 7000, rest_port=0)

    def broken(*a, **k):
        raise OSError("network is down")
    res._osc.send_message = broken
    assert res.fire_clip(1, 3) is False
    assert res.set_volume(2, 0.5) is False


def test_controller_refuses_a_holey_pool():
    from cockaigne_controller.clipmap import ClipMap
    pool = [n for n in full_pool() if n != "m4m4"]
    assert ClipMap(pool, ARMS).missing() != []
