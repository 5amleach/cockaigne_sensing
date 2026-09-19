"""The recorder and replayer round-trip messages exactly. Runs without a GPU or network."""
from cockaigne_sensing.bus import Recorder, replay
from cockaigne_sensing.detect.tracker import Track, tracks_message


def test_round_trip(tmp_path):
    path = tmp_path / "tracks.jsonl"
    rec = Recorder(path)
    msgs = [
        tracks_message(0.0, "cam1", 640, 360, [Track(1, (10, 20, 50, 120), 0.9, 0.0)]),
        tracks_message(0.2, "cam1", 640, 360, []),
    ]
    for m in msgs:
        rec.write(m)
    rec.close()

    back = list(replay(path))
    assert back == msgs
    assert back[0]["stream"] == "tracks"
    assert back[0]["tracks"][0]["box"] == [10, 20, 50, 120]
    assert list(replay(path, stream="people")) == []
