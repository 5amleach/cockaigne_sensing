"""Shared helpers for the controller tests: a made-up clip pool that
satisfies the start-up validator, and small drivers for the decision loop."""
from cockaigne_controller.clipmap import ClipMap
from cockaigne_controller.config import load
from cockaigne_controller.loop import Controller

ARMS = {"a": "architecture", "u": "furniture", "s": "storm", "r": "rivers",
        "f": "feast", "h": "herd", "m": "machinery", "c": "cargo"}


def full_pool():
    """Barren in and out of every arm, ring chains up and down, same-ring
    laterals both ways around, collapses, Ring 4 loops, a Barren loop."""
    names = ["b_b"]
    letters = list(ARMS)
    for i, a in enumerate(letters):
        names += [f"b_{a}1", f"{a}1b", f"{a}4{a}4", f"{a}2b", f"{a}3b"]
        for r in (1, 2, 3):
            names += [f"{a}{r}{a}{r + 1}", f"{a}{r + 1}{a}{r}"]
        nxt = letters[(i + 1) % len(letters)]
        for r in (1, 2, 3, 4):
            names += [f"{a}{r}{nxt}{r}", f"{nxt}{r}{a}{r}"]
    return names


def pool_288():
    """The real clip pool, built from the naming rule and nothing else:
    Barren coded `b1`, eight Barren ascents, same-arm ascents, a descent to
    Barren from every ring, and same-ring laterals between every pair of
    arms. 288 names, no loop clips."""
    names = []
    for x in ARMS:
        names.append(f"b1{x}1")
        for r in (1, 2, 3):
            names.append(f"{x}{r}{x}{r + 1}")
        for r in (1, 2, 3, 4):
            names.append(f"{x}{r}b1")
            names += [f"{x}{r}{y}{r}" for y in ARMS if y != x]
    return names


def make_controller(pool=None, no_repeat_minutes=0, **cfg_over):
    """The no-repeat rule is off unless a test asks for it, so the older
    tests keep testing the moves they were written for."""
    cfg = load()
    cfg["controller"] = dict(cfg["controller"], **{"arm_chooser": "fixed", **cfg_over})
    cfg["no_repeat"] = {"minutes": no_repeat_minutes}
    names = pool if pool is not None else full_pool()
    layout = {n: (1, i) for i, n in enumerate(names, start=1)}
    cmap = ClipMap(names, ARMS)
    assert cmap.missing() == []
    return Controller(cfg, cmap, layout)


def crowd(t, ring, n=3, cohesion=0.5):
    return {"stream": "crowd", "t": t, "ring_target": ring, "n": n,
            "n_smooth": n, "cohesion_smooth": cohesion}


def step(c, t):
    """Decide and confirm the fire, as run.py does on a healthy Resolume."""
    d, li = c.decide(t)
    c.confirm_fired(d, t)
    return d


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
