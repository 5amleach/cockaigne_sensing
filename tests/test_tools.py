"""Small tests for the studio helpers: the grid tool, the bus watcher's line,
and the studio configuration itself."""
import json
import sys

import cv2
import numpy as np
import yaml

from cockaigne_sensing.tools.watch_bus import format_line


def test_studio_config_is_the_shed():
    cfg = yaml.safe_load(open("config/studio.yaml"))
    assert cfg["floor"] == {"width_m": 3.5, "length_m": 7.0}
    assert cfg["cohesion"]["proxy_spot_x_m"] == 1.75
    assert cfg["cohesion"]["proxy_spot_y_m"] == 3.5
    assert [c["name"] for c in cfg["cameras"]] == ["cam1"]
    assert cfg["cameras"][0]["stream"] == "sub"
    # The spot sits on the shed's centre line, inside the floor.
    assert 0 < cfg["cohesion"]["proxy_spot_y_m"] < cfg["floor"]["length_m"]


def test_frame_grid_writes_a_labelled_frame(tmp_path, monkeypatch, capsys):
    from cockaigne_sensing.tools import frame_grid
    vid = tmp_path / "clip.avi"
    out = cv2.VideoWriter(str(vid), cv2.VideoWriter_fourcc(*"XVID"), 10, (640, 360))
    for _ in range(20):
        out.write(np.full((360, 640, 3), 40, dtype=np.uint8))
    out.release()
    png = tmp_path / "grid.png"
    monkeypatch.setattr(sys, "argv", ["frame_grid", str(vid), "--at", "1.0",
                                      "--out", str(png), "--step", "200"])
    frame_grid.main()
    saved = cv2.imread(str(png))
    assert saved is not None and saved.shape == (360, 640, 3)
    # The grid line at x=200 is brighter than the plain background.
    assert saved[100, 200].max() > 150
    assert "640x360" in capsys.readouterr().out


def test_frame_grid_hides_the_password(tmp_path, monkeypatch, capsys):
    from cockaigne_sensing.tools import frame_grid
    monkeypatch.setattr(sys, "argv",
                        ["frame_grid", "rtsp://admin:secretword@10.0.0.9:554/x"])
    try:
        frame_grid.main()
    except SystemExit as e:
        text = str(e)
    assert "secretword" not in text and "admin:***@" in text


def test_watch_bus_line_reads_like_a_sentence():
    crowd = {"n": 2, "ring_target": 1, "cohesion_relational": 0.66,
             "cohesion_smooth": 0.52, "accumulator": 0.31,
             "moods": {"happy": 1, "bored": 1}}
    cameras = {"cam1": {"alive": True, "age_s": 0.2},
               "cam2": {"alive": False, "age_s": 12.0}}
    line = format_line(crowd, cameras)
    assert "n=2" in line and "ring=1" in line and "C=0.66" in line
    assert "reservoir=0.31" in line and "happy 1" in line and "annoyed 0" in line
    assert "cam1 ok 0.2s" in line and "cam2 LOST 12.0s" in line
    assert format_line(None, None).startswith("waiting")
