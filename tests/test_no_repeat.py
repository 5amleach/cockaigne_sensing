"""The no-repeat rule: the wall does not go back to a node it showed in the
last few minutes, unless the crowd's ring leaves it no other way."""
from cockaigne_controller.clipmap import node_ring
from cockaigne_controller.recent import Recent
from tests.helpers import climb_to, crowd, full_pool, make_controller, pool_288, step


def test_recent_window_and_exemptions():
    r = Recent(8)
    r.arrive("m3", 100.0)
    r.arrive("b", 100.0)
    assert r.is_recent("m3", 100.0 + 7 * 60)
    assert not r.is_recent("m3", 100.0 + 8 * 60)
    assert not r.is_recent("b", 101.0)        # Barren is never blocked
    assert not r.is_recent("a3", 101.0)       # never shown
    off = Recent(0)
    off.arrive("m3", 100.0)
    assert not off.is_recent("m3", 101.0)


def test_fixed_arm_home_is_avoided_and_said_so():
    c = make_controller(pool_288(), no_repeat_minutes=8)
    _, t = climb_to(c, 3)
    c.observe(crowd(t - 1.0, 3))
    d = step(c, t)                            # holding Ring 3: sideways off m3
    assert d["from"] == "m3" and d["reason"] == "lateral"
    c.observe(crowd(t + 59.0, 3))
    d = step(c, t + 60.0)                     # the fixed arm wants m3 again
    assert d["to"] != "m3" and node_ring(d["to"]) == 3
    assert d["avoided"] == "m3" and d["reason"] == "lateral"


def test_a_held_ring_tours_every_axis_without_quick_returns():
    c = make_controller(pool_288(), no_repeat_minutes=8)
    _, t = climb_to(c, 3)
    arrivals = {}
    for _ in range(20):
        c.observe(crowd(t - 1.0, 3))
        d = step(c, t)
        assert node_ring(d["to"]) == 3        # the crowd's ring is kept
        if d["to"] in arrivals:
            assert t - arrivals[d["to"]] >= 8 * 60
        arrivals[d["to"]] = t
        t += 60.0
    assert len(arrivals) == 8                 # all eight axes came round


def test_the_crowds_ring_wins_over_the_rule():
    c = make_controller(full_pool(), no_repeat_minutes=8)
    _, t = climb_to(c, 3)                     # came up through m2 a minute ago
    c.observe(crowd(t - 1.0, 2))
    d = step(c, t)
    assert d["to"] == "m2" and "avoided" not in d
