"""Bus tests: ledger, event derivation, the localhost-only rule, and one
loopback round trip. No GPU; nothing leaves the machine."""
import asyncio
import json

from cockaigne_sensing.bus.ledger import Ledger, LedgerEvents
from cockaigne_sensing.bus.publish import Publisher


def crowd(t, ring, n=2):
    return {"stream": "crowd", "t": t, "ring_target": ring, "n": n}


def people(t, *entries):
    return {"stream": "people", "t": t, "people": list(entries)}


def pers(pid, phone=0.0):
    return {"id": pid, "actions": {"phone": phone, "drink": 0.0, "eat": 0.0}}


def test_ledger_appends_and_reopening_does_not_truncate(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger(path)
    led.append("day_start", note="first")
    led.close()
    led = Ledger(path)
    led.append("note", text="second")
    led.close()
    lines = [json.loads(l) for l in open(path)]
    assert [e["kind"] for e in lines] == ["day_start", "note"]
    assert all("t_wall" in e for e in lines)


def test_ring_changes_are_logged_once_each(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl")
    ev = LedgerEvents(led, count_min=0.5)
    for m in [crowd(1, 0), crowd(2, 0), crowd(3, 1), crowd(4, 1), crowd(5, 2), crowd(6, 1)]:
        ev.observe(m)
    led.close()
    entries = [json.loads(l) for l in open(led.path)]
    assert [(e["kind"], e["ring"]) for e in entries] == [
        ("ring_change", 1), ("ring_change", 2), ("ring_change", 1)]


def test_an_action_is_logged_once_per_stretch(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl")
    ev = LedgerEvents(led, count_min=0.5)
    ev.observe(people(1, pers(7, phone=0.8)))   # starts: logged
    ev.observe(people(2, pers(7, phone=0.9)))   # continues: not logged again
    ev.observe(people(3, pers(7, phone=0.1)))   # stops
    ev.observe(people(4, pers(7, phone=0.7)))   # starts again: logged
    led.close()
    entries = [json.loads(l) for l in open(led.path)]
    assert [(e["person"], e["action"]) for e in entries] == [(7, "phone"), (7, "phone")]


def test_bus_refuses_to_bind_beyond_the_local_machine():
    import pytest
    with pytest.raises(ValueError):
        Publisher("0.0.0.0", 8765)


def test_client_messages_are_rebroadcast_to_the_others():
    # The controller sends its clip decision to the bus; the data wall, on its
    # one socket, receives it. The sender does not get its own echo.
    from websockets.asyncio.client import connect

    async def round_trip():
        pub = Publisher("127.0.0.1", 0)
        port = await pub.start()
        decision = {"stream": "decision", "t": 9.0, "clip": "b_m1", "arm": "machinery"}
        async with connect(f"ws://127.0.0.1:{port}") as controller, \
                   connect(f"ws://127.0.0.1:{port}") as wall:
            await asyncio.sleep(0.05)
            await controller.send(json.dumps(decision))
            received = json.loads(await asyncio.wait_for(wall.recv(), timeout=2))
            try:
                await asyncio.wait_for(controller.recv(), timeout=0.2)
                echoed = True
            except asyncio.TimeoutError:
                echoed = False
        await pub.close()
        return received, echoed

    received, echoed = asyncio.run(round_trip())
    assert received["stream"] == "decision" and received["clip"] == "b_m1"
    assert not echoed


def test_loopback_round_trip():
    # One message over a real socket on the local machine, port chosen by the
    # system. Loopback only; nothing leaves the computer.
    from websockets.asyncio.client import connect

    async def round_trip():
        pub = Publisher("127.0.0.1", 0)
        port = await pub.start()
        async with connect(f"ws://127.0.0.1:{port}") as client:
            await asyncio.sleep(0.05)  # let the server register the client
            await pub.publish({"stream": "crowd", "t": 1.0, "ring_target": 2})
            received = json.loads(await asyncio.wait_for(client.recv(), timeout=2))
        await pub.close()
        return received

    msg = asyncio.run(round_trip())
    assert msg == {"stream": "crowd", "t": 1.0, "ring_target": 2}
