"""Live launcher tests: the whole chain from moving pictures to bus messages.

The detector is the one component that cannot run here (no weights, no GPU,
no network), so a stand-in finds the bright rectangle these synthetic videos
contain. Everything else is real: camera threads pacing a file like a
camera, the floor with a 4K calibration scaled to the small frames, features,
the bus socket, health reporting and the ledger.
"""
import asyncio
import json

import cv2
import numpy as np
import pytest

from cockaigne_sensing.config import load
from cockaigne_sensing.floor.camera import Camera, focal_from_hfov, homography_from_camera

CAM = Camera(3.05, 0.0, 3.0, 35.0, 0.0, "into_u", focal_from_hfov(3840, 87), 1920, 1080)
SCALE = 12  # the videos are 320x180; the calibration is stored at 3840x2160


def write_video(path, n_frames, fps=10):
    """A person-shaped white rectangle walking across the floor at y = 4 m,
    drawn where the calibrated camera would see those feet."""
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"XVID"), fps, (320, 180))
    assert out.isOpened()
    for i in range(n_frames):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        x = 2.0 + 2.0 * i / n_frames                     # 2 m to 4 m along the wall
        u, v = CAM.project(np.array([[x, 4.0]]))[0] / SCALE
        cv2.rectangle(frame, (int(u) - 7, int(v) - 44), (int(u) + 7, int(v)),
                      (255, 255, 255), -1)
        out.write(frame)
    out.release()


class BrightBoxTracker:
    """Stands in for YOLO: the bright rectangle is the person."""

    def update(self, frame, t):
        from cockaigne_sensing.detect.tracker import Track
        mask = frame[:, :, 0] > 200
        if not mask.any():
            return []
        ys, xs = np.nonzero(mask)
        box = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
        return [Track(1, box, 0.9, t)]


def launcher_config(tmp_path, cameras):
    cfg = load()
    H = homography_from_camera(CAM, 6.1, 7.4)
    hpath = tmp_path / "h.json"
    hpath.write_text(json.dumps({"H": H.tolist(), "image_size": [3840, 2160]}))
    for cam in cameras:
        cam.setdefault("homography", str(hpath))
    cfg["cameras"] = cameras
    cfg["bus"] = {"host": "127.0.0.1", "port": 0,
                  "ledger_path": str(tmp_path / "ledger.jsonl")}
    cfg["launcher"] = {"detect_fps": 5, "camera_stale_s": 1.2,
                       "camera_retry_s": 5, "log_path": str(tmp_path / "sensing.log")}
    return cfg


def test_startup_refuses_a_camera_without_calibration(tmp_path):
    from cockaigne_sensing.run import calibration_sizes
    cfg = launcher_config(tmp_path, [{"name": "cam9", "file": "x.avi"}])
    cfg["cameras"][0]["homography"] = str(tmp_path / "absent.json")
    with pytest.raises(SystemExit):
        calibration_sizes(cfg)


def test_launcher_runs_end_to_end_and_reports_a_lost_camera(tmp_path):
    from websockets.asyncio.client import connect
    from cockaigne_sensing.run import Launcher

    write_video(tmp_path / "a.avi", 60)   # 6 s, loops: a healthy camera
    write_video(tmp_path / "b.avi", 25)   # 2.5 s, ends: a camera that dies
    cfg = launcher_config(tmp_path, [
        {"name": "c1", "file": str(tmp_path / "a.avi")},
        {"name": "c2", "file": str(tmp_path / "b.avi"), "loop": False},
    ])
    launcher = Launcher(cfg, tracker_factory=BrightBoxTracker)

    async def drive():
        task = asyncio.create_task(launcher.run())
        for _ in range(100):
            if launcher.port:
                break
            await asyncio.sleep(0.05)
        assert launcher.port, "the launcher never opened its bus"
        people, crowd, lost_seen = [], [], False
        async with connect(f"ws://127.0.0.1:{launcher.port}") as ws:
            end = asyncio.get_event_loop().time() + 7.5
            while asyncio.get_event_loop().time() < end:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                except asyncio.TimeoutError:
                    continue
                if msg["stream"] == "people":
                    people.append(msg)
                    if not msg["cameras"]["c2"]["alive"]:
                        lost_seen = True
                elif msg["stream"] == "crowd":
                    crowd.append(msg)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return people, crowd, lost_seen

    people, crowd, lost_seen = asyncio.run(drive())
    assert len(people) > 30 and len(crowd) >= 3
    assert all(set(p["cameras"]) == {"c1", "c2"} for p in people)
    seen = [p["people"][0] for p in people if p["people"]]
    assert seen, "the walking rectangle never became a person"
    assert all(abs(person["y"] - 4.0) < 0.5 for person in seen)
    assert any(2.0 <= person["x"] <= 4.2 for person in seen)
    assert lost_seen, "c2's death never reached the health field"
    entries = [json.loads(l) for l in open(cfg["bus"]["ledger_path"])]
    assert any(e["kind"] == "camera_lost" and e["camera"] == "c2" for e in entries)
    assert not any(e["kind"] == "camera_lost" and e["camera"] == "c1" for e in entries)
