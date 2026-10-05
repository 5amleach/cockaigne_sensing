"""Controller tests, build steps 1 to 3: the map, the fake Resolume, the
ring-only loop. One OSC loopback test; everything else stays off the network."""
import pytest

from cockaigne_controller.clipmap import BARREN, ClipMap, parse_clip_name
from cockaigne_controller.clock import ClipClock
from cockaigne_controller.config import load
from cockaigne_controller.loop import Controller
from cockaigne_controller.resolume import layout_from_composition

ARMS = {"a": "architecture", "u": "furniture", "s": "storm", "r": "rivers",
        "f": "feast", "h": "herd", "m": "machinery", "c": "cargo"}


def full_pool():
    """A made-up clip pool that satisfies the map: Barren in and out of every
    arm, ring chains up and down, collapses, Ring 4 loops, a Barren loop."""
    names = ["b_b"]
    for a in ARMS:
        names += [f"b_{a}1", f"{a}1b", f"{a}4{a}4", f"{a}2b", f"{a}3b"]
        for r in (1, 2, 3):
            names += [f"{a}{r}{a}{r + 1}", f"{a}{r + 1}{a}{r}"]
    return names


def make_controller(pool=None, **cfg_over):
    cfg = load()
    cfg["controller"] = dict(cfg["controller"], arm_chooser="fixed", **cfg_over)
    names = pool if pool is not None else full_pool()
    layout = {n: (1, i) for i, n in enumerate(names, start=1)}
    cmap = ClipMap(names, ARMS)
    assert cmap.missing() == []
    return Controller(cfg, cmap, layout)


def crowd(t, ring, n=3, cohesion=0.5):
    return {"stream": "crowd", "t": t, "ring_target": ring, "n": n,
            "cohesion_smooth": cohesion}


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
    # An arm with no way in at all shows up as unroutable.
    pool = [n for n in full_pool() if not n.startswith("b_c") and n != "cb"]
    pool.remove("c1b")
    problems = ClipMap(pool, ARMS).missing()
    assert any("no route" in p and "c1" in p for p in problems)


def test_shortest_path_steps_through_existing_clips():
    cmap = ClipMap(full_pool(), ARMS)
    assert cmap.next_step("b", "m3") == "m1"      # b -> m1 -> m2 -> m3
    assert cmap.next_step("m1", "m2") == "m2"     # direct
    assert cmap.next_step("m3", "a2") == "b"      # collapse, then out the other arm
    assert cmap.clip_for("m4", "m4") == "m4m4"


def test_ring_only_loop_climbs_and_collapses():
    c = make_controller(default_arm="machinery")
    c.observe(crowd(1.0, 1))
    d, _ = c.decide(60.0)
    assert (d["from"], d["to"], d["reason"]) == ("b", "m1", "ring")
    c.observe(crowd(61.0, 3))
    d, _ = c.decide(120.0)
    assert (d["to"], d["reason"]) == ("m2", "path")   # no m1 -> m3 clip: step
    d, _ = c.decide(180.0)
    assert (d["to"], d["reason"]) == ("m3", "ring")
    c.observe(crowd(181.0, 0))
    d, _ = c.decide(240.0)
    assert (d["to"], d["clip"], d["arm"]) == ("b", "m3b", "barren")  # direct collapse


def test_staying_put_loops_or_probes():
    c = make_controller()
    c.observe(crowd(1.0, 0))
    d, _ = c.decide(60.0)
    assert (d["to"], d["reason"], d["clip"]) == ("b", "loop", "b_b")
    # Without a Barren loop clip, Barren probes out to Ring 1 and returns.
    c = make_controller(pool=[n for n in full_pool() if n != "b_b"])
    c.observe(crowd(1.0, 0))
    d, _ = c.decide(60.0)
    assert (d["to"], d["reason"]) == ("m1", "probe")
    d, _ = c.decide(120.0)
    assert (d["to"], d["reason"]) == ("b", "ring")
    # A mid-ring node with no loop bounces to its downward neighbour.
    c = make_controller()
    c.observe(crowd(1.0, 3))
    for t in (60.0, 120.0, 180.0):
        c.decide(t)                       # b -> m1 -> m2 -> m3
    d, _ = c.decide(240.0)
    assert (d["from"], d["to"], d["reason"]) == ("m3", "m2", "probe")
    d, _ = c.decide(300.0)
    assert (d["to"], d["reason"]) == ("m3", "ring")
    # Ring 4 has a loop and uses it.
    c = make_controller()
    c.observe(crowd(1.0, 4))
    for t in (60.0, 120.0, 180.0, 240.0, 300.0):
        d, _ = c.decide(t)
    assert (d["from"], d["to"], d["reason"]) == ("m4", "m4", "loop")


def test_clock_fires_audio_lead_then_clip():
    clock = ClipClock(clip_s=60.0, audio_lead_s=5.0)
    clock.start(100.0)
    assert not clock.audio_due(154.9) and not clock.clip_due(159.9)
    assert clock.audio_due(155.0)
    clock.mark_audio()
    assert not clock.audio_due(156.0)   # once per clip
    assert clock.clip_due(160.0)


def test_occupancy_context_bands():
    c = make_controller()
    assert c.context() == "solo"
    for i in range(300):
        c.observe(crowd(i * 1.0, 2, n=8))
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


def test_controller_refuses_a_holey_pool():
    from cockaigne_controller.clipmap import ClipMap
    pool = [n for n in full_pool() if n != "m4m4"]
    assert ClipMap(pool, ARMS).missing() != []
