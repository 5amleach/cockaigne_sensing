"""Bandit, action bias and personality tests, build steps 4 and 5. No network."""
import datetime
import random

import pytest

from cockaigne_controller.bandit import ActionBias, Bandit, Beta, reward_from_delta
from cockaigne_controller.personality import personality_for, priors

ARMS = ["architecture", "furniture", "storm", "rivers",
        "feast", "herd", "machinery", "cargo"]
CONTEXTS = ["solo", "small", "medium", "large"]


def crowd(t, n=4, sitting=0, **rates):
    base = {"phone": 1.0, "drink": 1.0, "eat": 1.0}
    base.update(rates)
    return {"t": t, "n": n, "action_rates": base, "actions": {"sitting": sitting}}


def test_reward_maps_cohesion_change_around_a_half():
    assert reward_from_delta(0.0, 0.15) == 0.5
    assert reward_from_delta(0.15, 0.15) == 1.0
    assert reward_from_delta(-0.15, 0.15) == 0.0
    assert reward_from_delta(9.9, 0.15) == 1.0  # clamped


def test_beta_takes_fractional_bernoulli_updates():
    b = Beta(1, 1)
    b.update(0.75)
    assert b.a == pytest.approx(1.75) and b.b == pytest.approx(1.25)


def test_bandit_learns_which_arm_pays():
    bandit = Bandit(ARMS, CONTEXTS, rng=random.Random(7))
    for _ in range(40):
        bandit.update("small", "feast", 1.0)
        bandit.update("small", "machinery", 0.0)
    picks = [bandit.choose("small", {})[0] for _ in range(50)]
    assert picks.count("feast") > 35
    assert "machinery" not in picks


def test_bias_leans_on_close_calls_but_cannot_overturn_conviction():
    # Flat beliefs: a decisive lean wins and is named as the reason.
    bandit = Bandit(ARMS, CONTEXTS, rng=random.Random(3))
    arm, reason = bandit.choose("small", {"machinery": 5.0})
    assert (arm, reason) == ("machinery", "action_bias")
    # A sharp belief in feast out-draws a realistic lean on machinery.
    bandit.reset({arm: ((60.0, 2.0) if arm == "feast" else (1.0, 9.0)) for arm in ARMS})
    realistic_lean = 0.25 * 1.0 / 3  # weight x full excess / small-band size
    picks = [bandit.choose("small", {"machinery": realistic_lean})[0] for _ in range(50)]
    assert picks.count("feast") > 45


def test_action_bias_decays_with_a_90_second_half_life():
    bias = ActionBias({"half_life_s": 90, "targets": {"phone": "machinery"},
                       "weights": {"phone": 0.25}, "sitting_baseline_s": 600,
                       "sitting_baseline_floor": 0.02},
                      {"small": 3})
    bias.observe(crowd(0.0, phone=3.0))     # excess 2.0
    assert bias.bias("small")["machinery"] == pytest.approx(0.25 * 2.0 / 3)
    bias.observe(crowd(90.0))               # back to normal, one half-life later
    assert bias.bias("small")["machinery"] == pytest.approx(0.25 * 1.0 / 3)


def test_sitting_rate_is_derived_against_its_own_baseline():
    cfg = {"half_life_s": 90, "targets": {"sitting": "furniture"},
           "weights": {"sitting": 0.25}, "sitting_baseline_s": 600,
           "sitting_baseline_floor": 0.02}
    bias = ActionBias(cfg, {"small": 3})
    for i in range(60):                     # a minute of nobody sitting
        bias.observe(crowd(float(i)))
    assert bias.bias("small").get("furniture", 0.0) == 0.0
    bias.observe(crowd(60.0, n=4, sitting=2))  # half the room sits down
    assert bias.bias("small")["furniture"] > 0.5


def test_personality_follows_the_date_and_sets_the_priors():
    cfg = {"personality_order": ["Courtier", "Operator", "Accountant", "Naif"],
           "personalities": {"Courtier": {"prior_strength": 2, "storm_prior": 0.3,
                                          "reward_scale": 0.1, "patience_s": 10},
                             "Operator": {"prior_strength": 6, "storm_prior": 0.5,
                                          "reward_scale": 0.15, "patience_s": 15},
                             "Accountant": {"prior_strength": 12, "storm_prior": 0.35,
                                            "reward_scale": 0.2, "patience_s": 20},
                             "Naif": {"prior_strength": 1, "storm_prior": 0.65,
                                      "reward_scale": 0.08, "patience_s": 8}}}
    day = datetime.date(2026, 1, 15)
    name, params = personality_for(day, cfg)
    assert name == cfg["personality_order"][15 % 4]
    assert personality_for(day, cfg) == personality_for(day, cfg)  # stable all day
    p = priors(params, ARMS)
    a, b = p["storm"]
    assert a / (a + b) == pytest.approx(params["storm_prior"])
    assert sum(p["feast"]) == pytest.approx(params["prior_strength"])


def test_day_start_resets_beliefs_and_notes_the_ledger(tmp_path):
    import json
    from cockaigne_sensing.bus import Ledger
    from tests.test_controller import full_pool, ARMS as ARM_LETTERS
    from cockaigne_controller.clipmap import ClipMap
    from cockaigne_controller.config import load
    from cockaigne_controller.loop import Controller

    cfg = load()
    cfg["ledger_path"] = str(tmp_path / "ledger.jsonl")
    names = full_pool()
    layout = {n: (1, i) for i, n in enumerate(names, start=1)}
    c = Controller(cfg, ClipMap(names, ARM_LETTERS), layout, rng=random.Random(1))
    ledger = Ledger(cfg["ledger_path"])
    c.ensure_day(datetime.date(2026, 1, 15), ledger)
    before = {k: (b.a, b.b) for k, b in c.bandit.beliefs.items()}
    c.bandit.update("small", "feast", 1.0)
    c.ensure_day(datetime.date(2026, 1, 15), ledger)   # same day: no reset
    assert c.bandit.beliefs[("small", "feast")].a != before[("small", "feast")][0]
    c.ensure_day(datetime.date(2026, 1, 16), ledger)   # new day: reset
    ledger.close()
    assert c.bandit.beliefs[("small", "feast")].a / sum(
        [c.bandit.beliefs[("small", "feast")].a, c.bandit.beliefs[("small", "feast")].b]
    ) == pytest.approx(0.5)
    entries = [json.loads(l) for l in open(cfg["ledger_path"])]
    assert [e["personality"] for e in entries if e["kind"] == "day_start"] \
        == [personality_for(datetime.date(2026, 1, 15),
                            {k: cfg[k] for k in ("personality_order", "personalities")})[0],
            personality_for(datetime.date(2026, 1, 16),
                            {k: cfg[k] for k in ("personality_order", "personalities")})[0]]


def test_reward_flows_from_cohesion_into_the_belief():
    import random as _r
    from tests.test_controller import full_pool, ARMS as ARM_LETTERS, crowd as crowd_msg
    from cockaigne_controller.clipmap import ClipMap
    from cockaigne_controller.config import load
    from cockaigne_controller.loop import Controller

    cfg = load()
    names = full_pool()
    layout = {n: (1, i) for i, n in enumerate(names, start=1)}
    c = Controller(cfg, ClipMap(names, ARM_LETTERS), layout, rng=_r.Random(5))
    c.ensure_day(datetime.date(2026, 1, 15))
    c.observe(crowd_msg(1.0, 2, cohesion=0.40))
    d, _ = c.decide(60.0)                 # the bandit picks some arm
    assert d["personality"] is not None
    c.fired(60.0)
    arm, context = d["arm"], d["context"]
    before = c.bandit.beliefs[(context, arm)].a
    c.observe(crowd_msg(60.0 + c.patience, 2, cohesion=0.40))   # window opens
    c.observe(crowd_msg(119.0, 2, cohesion=0.60))               # cohesion rose
    c.decide(120.0)                       # next decision settles the reward
    assert c.last_outcome["arm"] == arm
    assert c.last_outcome["reward"] == 1.0   # +0.2 >> reward scale
    assert c.bandit.beliefs[(context, arm)].a == pytest.approx(before + 1.0)
