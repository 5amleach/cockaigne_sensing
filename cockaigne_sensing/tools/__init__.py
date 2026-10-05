"""tools: command-line helpers, none of which run in the gallery.

bench_detect    run detection over a video file and report what it found
calibrate_auto  approximate a camera's homography from the people in a recording
calibrate       (not yet written) click four measured floor markers instead
fake_room       emit a made-up people list with scripted behaviour
plan_view       draw a people recording as paths on the floor plan

Replaying a recording into the bus is `python -m cockaigne_sensing.bus.run`.
"""
