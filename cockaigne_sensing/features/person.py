"""Per-person posture, arousal, valence and a mood label, from the track alone.

Everything here is arithmetic on one person's position, velocity and rectangle
shape. No pictures and no models. The one exception is the mood label, which
also reads the action sense's answer for folded arms or hands on hips. The thresholds live in config/sensing.yaml
under mood: and are starting guesses; they are to be tuned on site against
footage from the final camera height, and the labels are provisional until
then (DECISIONS.md, 2026-10-05).

Terms used below. Arousal is how energetic the movement is, 0 to 1. Valence is
how positive the person's bearing reads, -1 to 1. Slump is how far the
person's rectangle has shrunk below their own standing height, which is the
only height reference available without a model. Straightness is how directly
they have walked: straight-line distance divided by distance actually walked.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _spread(values: list) -> float:
    """Standard deviation: how far the values typically sit from their average."""
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


@dataclass
class _PersonState:
    """What the scorer remembers about one person between messages."""
    path: list = field(default_factory=list)    # (t, x, y) over the straightness window
    accels: list = field(default_factory=list)  # (t, acceleration) over the roughness window
    body: list = field(default_factory=list)    # (t, box height, box width) over the body window
    v_prev: tuple | None = None                 # (t, vx, vy) from the previous message
    ref_h: float = 0.0                          # standing-height reference in pixels, a decaying maximum
    stopped_since: float | None = None          # when the person last came to a stop
    feet_cut: bool = False                      # the last rectangle ran off the bottom of the picture
    label: str | None = None                    # current mood label
    label_since: float = 0.0                    # when the label was adopted
    last_seen: float = 0.0


class PersonScorer:
    """Keeps a little state per person id and fills in the per-person fields.

    Call update() with each people message. It rewrites posture, arousal and
    valence in place (the floor module emits placeholders) and returns the
    mood label per person id for the crowd message's counts.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg["mood"]
        self.still = cfg["cohesion"]["still_speed_mps"]
        self.count_min = cfg["actions"]["count_min"]
        # Forget a person a while after the floor tracker itself would have
        # dropped them; derived, not a separate tunable.
        self.forget_after_s = 2.0 * cfg["floor_tracker"]["drop_after_s"] + 10.0
        self.states: dict[int, _PersonState] = {}

    def update(self, msg: dict) -> dict[int, str]:
        t = msg["t"]
        labels: dict[int, str] = {}
        for p in msg["people"]:
            st = self.states.setdefault(p["id"], _PersonState())
            self._track(st, t, p)
            p["posture"] = self._posture(st, t, p)
            p["arousal"] = round(self._arousal(st, p), 2)
            p["valence"] = round(self._valence(st, p), 2)
            labels[p["id"]] = p["mood"] = self._mood(st, t, p)
        for pid in [pid for pid, st in self.states.items()
                    if t - st.last_seen > self.forget_after_s]:
            del self.states[pid]
        return labels

    def _track(self, st: _PersonState, t: float, p: dict) -> None:
        """Bring this person's remembered history up to date."""
        dt = max(0.0, t - st.last_seen) if st.last_seen else 0.0
        st.last_seen = t
        # Positions for straightness are sampled sparsely. At the full message
        # rate, centimetre jitter summed to metres of phantom walking and a
        # person standing still read as bored.
        if not st.path or t - st.path[-1][0] >= self.cfg["straightness_sample_s"]:
            st.path.append((t, p["x"], p["y"]))
        st.path = [h for h in st.path if t - h[0] <= self.cfg["straightness_window_s"]]
        if st.v_prev is not None:
            t0, vx0, vy0 = st.v_prev
            if t - t0 > 1e-3:
                accel = math.hypot(p["vx"] - vx0, p["vy"] - vy0) / (t - t0)
                st.accels.append((t, accel))
        st.v_prev = (t, p["vx"], p["vy"])
        st.accels = [a for a in st.accels if t - a[0] <= self.cfg["accel_window_s"]]
        # The rectangle's size, only when the person was actually seen this
        # step: a coasting person keeps an old rectangle that says nothing.
        if p.get("view"):
            st.body.append((t, float(p["box_h"]), p["box_ratio"] * p["box_h"]))
            v = p["view"]
            if v.get("box") and v.get("h"):
                st.feet_cut = v["box"][3] >= v["h"] - self.cfg["sitting_edge_px"]
        st.body = [b for b in st.body if t - b[0] <= self.cfg["body_window_s"]]
        # The standing-height reference: a maximum that decays toward the
        # current height, so a walk toward or away from the camera washes out
        # rather than reading as a permanent slump or stretch.
        if st.ref_h <= 0:
            st.ref_h = p["box_h"]
        else:
            a = 1.0 - math.exp(-dt / self.cfg["valence_ref_s"]) if dt > 0 else 0.0
            st.ref_h = max(float(p["box_h"]), st.ref_h - a * (st.ref_h - p["box_h"]))
        if math.hypot(p["vx"], p["vy"]) < self.still:
            if st.stopped_since is None:
                st.stopped_since = t
        else:
            st.stopped_since = None

    def _posture(self, st: _PersonState, t: float, p: dict) -> str:
        if math.hypot(p["vx"], p["vy"]) >= self.still:
            return "walking"
        stopped_long_enough = (st.stopped_since is not None
                               and t - st.stopped_since >= self.cfg["sitting_still_s"])
        # A visitor close to the camera has their legs cut off by the bottom of
        # the picture, which leaves a short, wide rectangle that looks like a
        # sitter. Their shape says nothing about sitting, so it is not read.
        if stopped_long_enough and not st.feet_cut and p["box_ratio"] > self.cfg["sitting_ratio"]:
            return "sitting"
        return "standing"

    def _arousal(self, st: _PersonState, p: dict) -> float:
        """The larger of two energies: walking speed, and body movement on the spot.

        Body movement is how much the person's rectangle grows and shrinks over
        the last few seconds. Bouncing changes its height; waving arms changes
        its width. Someone dancing in one place is energetic, not calm.
        """
        speed = math.hypot(p["vx"], p["vy"])
        walking = speed / self.cfg["arousal_speed_full_mps"]
        return _clamp(max(walking, self._body_motion(st) / self.cfg["arousal_body_full"]), 0.0, 1.0)

    def _body_motion(self, st: _PersonState) -> float:
        """Spread of the rectangle's height and width, as a fraction of its height."""
        if len(st.body) < 5:
            return 0.0
        hs = [b[1] for b in st.body]
        ws = [b[2] for b in st.body]
        mean_h = sum(hs) / len(hs)
        if mean_h <= 0:
            return 0.0
        return (_spread(hs) + _spread(ws)) / mean_h

    def _valence(self, st: _PersonState, p: dict) -> float:
        """Slumped and jerky reads negative; upright and smooth reads positive."""
        slump = _clamp(1.0 - p["box_h"] / st.ref_h, 0.0, 1.0) if st.ref_h > 0 else 0.0
        roughness = (sum(a for _, a in st.accels) / len(st.accels)) if st.accels else 0.0
        c = self.cfg
        v = ((c["valence_slump_neutral"] - slump) / c["valence_slump_scale"]
             - roughness / c["valence_jerk_scale"])
        return _clamp(v, -1.0, 1.0)

    def _straightness(self, st: _PersonState) -> float:
        """Straight-line distance over distance walked, in the recent window.

        Someone who has barely moved is not judged: too little path reads 1.0.
        """
        pts = st.path
        if len(pts) < 2:
            return 1.0
        walked = sum(math.hypot(x1 - x0, y1 - y0)
                     for (_, x0, y0), (_, x1, y1) in zip(pts, pts[1:]))
        if walked < self.cfg["straightness_min_path_m"]:
            return 1.0
        # Someone who has stayed within a small circle has not wandered, however
        # much their position wobbled: bouncing or swaying on the spot is not
        # aimless drifting.
        cx = sum(x for _, x, _ in pts) / len(pts)
        cy = sum(y for _, _, y in pts) / len(pts)
        if max(math.hypot(x - cx, y - cy) for _, x, y in pts) < self.cfg["wander_min_radius_m"]:
            return 1.0
        direct = math.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2])
        return min(1.0, direct / walked)

    def _mood(self, st: _PersonState, t: float, p: dict) -> str:
        """Happy, sad, bored or annoyed, held for label_dwell_s so it cannot flicker."""
        c = self.cfg
        straightness = self._straightness(st)
        # A pose the action sense reads (arms folded, hands on hips) outranks
        # the arithmetic: each pose reads as the mood config gives it.
        posed = [mood for pose, mood in c["pose_moods"].items()
                 if p.get("actions", {}).get(pose, 0.0) >= self.count_min]
        if posed:
            candidate = posed[0]
        elif p["valence"] <= c["sad_valence"]:
            candidate = "annoyed" if p["arousal"] >= c["annoyed_arousal"] else "sad"
        elif straightness < c["bored_straightness"] and p["arousal"] < c["bored_arousal_max"]:
            candidate = "bored"
        elif p["valence"] >= c["happy_valence"]:
            candidate = "happy"
        else:
            # The neutral middle: keep whatever the label already is.
            candidate = st.label or ("happy" if p["valence"] >= 0 else "sad")
        if st.label is None:
            st.label, st.label_since = candidate, t
        elif candidate != st.label and t - st.label_since >= c["label_dwell_s"]:
            st.label, st.label_since = candidate, t
        return st.label
