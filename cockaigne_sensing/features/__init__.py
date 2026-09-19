"""features: crowd cohesion and per-person mood, from the people list alone.

NOT YET WRITTEN. Brief for whoever builds it. Every formula below is in the
control system spec (Part two and Part three). No models, only arithmetic.

Crowd, once a second:
- clustering: mean nearest-neighbour distance, divided by the expected
  mean nearest-neighbour distance for n points placed at random on a floor
  of this size (about 0.5 * sqrt(area / n)). Map so that closer than random
  gives a score near 1 and further than random near 0. Clamp to [0, 1].
- synchrony: length of the sum of all velocity vectors, divided by the sum
  of all speeds. People slower than still_speed_mps are left out of this.
- stillness: fraction of people slower than still_speed_mps.
- relational cohesion C: geometric mean of the signals that are switched
  on. Leave two placeholder signals returning 1.0 so more can be added.
- proxy score A: what the estimator falls back on when there is nobody
  to be relational with. Built from dwell (time in room), stillness and
  proximity to the wall, each scaled 0 to 1, averaged, and then capped at
  proxy_ceiling (0.75). The cap is what keeps Ring 4 out of reach for a
  lone visitor: Ring 4 needs a score above 0.8 and only relational
  evidence can supply it. There is no rule that mentions population.
- effective occupancy n_eff: the headcount smoothed over about ten
  seconds, so someone stepping through the door does not flip the room
  in one frame.
- blend weight w from n_eff: about 0 at one person, about 0.5 at two,
  about 0.9 at three, 1.0 from four. Piecewise linear from config.
- cohesion_raw = (1 - w) * A + w * C. This is the one score the rest of
  the system sees. The machine is always "measuring cohesion"; it just
  has worse and worse evidence as the room empties.
- cohesion_smooth: exponentially weighted average over smooth_window_s.
- accumulator (the reservoir): chases cohesion_smooth. If the score is
  above the level, the level rises toward it at rise_rate_per_s; if
  below, it falls toward it at fall_rate_per_s (slower). It never jumps
  and is never reset when people arrive or leave. Clamp to [0, 1].
- ring_target: from accumulator via ring_up and ring_down thresholds,
  with the current ring remembered so up and down differ (hysteresis).
- With n == 0: A and C are 0, the reservoir drains at fall_rate.
- With n == 1: clustering and synchrony are reported as 1.0 (a set of one
  contains no disagreement) and C is 1.0, but w is about 0 so C barely
  counts. The data wall shows the 100% and Population 1 side by side; that
  is deliberate.

  Reasoning for all of this is in the project doc "single viewer brief
  for discussion" and DECISIONS.md, 2026-09-19.

Per person, on every people-list message:
- posture: "sitting" if box_ratio > sitting_ratio and speed below
  still_speed_mps for two seconds; "walking" if speed above it; else "standing".
- arousal: normalised combination of speed, absolute acceleration and the
  bounce of the box top. Start with speed alone and add the rest once a
  recording exists to tune against.
- valence: from slump (box_h relative to this person's own running maximum
  box_h while standing) and from movement smoothness (variance of
  acceleration). Slumped and jerky is negative.
- path straightness over the last 30 s: straight-line displacement divided
  by path length. Low straightness and low speed reads as bored.
- mood label from arousal, valence and straightness: happy, sad, bored,
  annoyed. Hold each label for label_dwell_s before it may change.

Output is Contract 2 plus the per-person fields written back into
Contract 1. Test from a recording of people-list messages, and from
tools.fake_room.
"""
