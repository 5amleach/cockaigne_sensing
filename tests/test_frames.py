"""Frame server tests: no GPU, no camera, nothing beyond this machine."""
import json
import urllib.error
import urllib.request

import cv2
import numpy as np

from cockaigne_sensing.frames import FrameServer, FrameStore


def _get(url):
    """(status, headers, body) for a GET, whether it succeeds or not."""
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_serves_the_latest_frame_with_the_right_headers():
    store = FrameStore(["cam1"])
    server = FrameServer(store, 0)   # port 0: any free port
    server.start()
    base = f"http://127.0.0.1:{server.port}"
    try:
        status, _, _ = _get(f"{base}/frame/cam1.jpg")
        assert status == 503   # the camera is known but has no frame yet

        ok, jpeg = cv2.imencode(".jpg", np.zeros((36, 64, 3), np.uint8))
        assert ok
        store.put("cam1", jpeg.tobytes())
        status, headers, body = _get(f"{base}/frame/cam1.jpg")
        assert status == 200
        assert headers["Content-Type"] == "image/jpeg"
        assert headers["Cache-Control"] == "no-store"
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert body == jpeg.tobytes()

        status, _, body = _get(f"{base}/cameras")
        assert status == 200 and json.loads(body) == ["cam1"]

        status, _, _ = _get(f"{base}/frame/nosuch.jpg")
        assert status == 404
    finally:
        server.stop()


def test_refuses_to_bind_anywhere_but_this_machine():
    try:
        FrameServer(FrameStore(), 0, host="0.0.0.0")
        raised = False
    except ValueError:
        raised = True
    assert raised
