from cockaigne_controller.overlays import Overlays

CFG = {
    "chairs": {"clip": "Chairs_A", "action": "sitting", "rest_s": 300, "says": "PERSON SITTING: RELEASING CHAIRS"},
    "pig": {"clip": "pig_b", "action": "phone", "rest_s": 600, "says": "PHONE USE: RELEASING PIG"},
}
LAYOUT = {"chairs_a": (4, 1), "pig_b": (5, 1)}


def names(items):
    return [i["name"] for i in items]


def test_fires_on_the_action_then_rests():
    o = Overlays(CFG, LAYOUT)
    assert names(o.due({"actions": {"sitting": 0, "phone": 0}}, 0)) == []
    assert names(o.due({"actions": {"sitting": 1}}, 10)) == ["chairs"]
    assert names(o.due({"actions": {"sitting": 2}}, 200)) == []        # resting
    assert names(o.due({"actions": {"sitting": 1, "phone": 1}}, 311)) == ["chairs", "pig"]
    assert names(o.due({"actions": {"phone": 1}}, 900)) == []          # pig rests 600 s
    assert names(o.due({"actions": {"phone": 1}}, 911)) == ["pig"]


def test_a_missing_clip_switches_that_overlay_off():
    o = Overlays(CFG, {"pig_b": (5, 1)})
    assert names(o.items) == ["pig"] and len(o.missing) == 1
    assert Overlays(None, LAYOUT).items == []
