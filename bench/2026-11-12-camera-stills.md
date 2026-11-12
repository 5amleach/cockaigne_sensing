# cam1 stills over HTTP, 12 November 2026

Measured by Claude Code on the render PC, after the camera was factory reset and set up again (see DECISIONS.md, 12 November).

The camera is a Reolink RLC-810A at 192.168.1.101. The stills come from `capture.fetch_still`, which asks the camera's `/cgi-bin/api.cgi?cmd=Snap` with a 5-second timeout. Every still came back at 3840 × 2160.

| Try | Seconds |
|---|---|
| 1 | 0.734 |
| 2 | 0.746 |
| 3 | 0.694 |
| 4 | 0.814 |
| 5 | 0.793 |
| 6 | 0.661 |
| 7 | 0.713 |
| 8 | 0.771 |
| 9 | 0.687 |
| 10 | 0.677 |

The fastest was 0.66 seconds, the median 0.73 and the slowest 0.81.

## What it means

- This is above the "about half a second" in `actions/DESIGN.md`, where the main-stream fallback is to be considered. The decision waits for the model bench, because what matters is the still and the model's answer together.
- With one question in flight at a time, the still alone caps questions at about 1.4 a second, below `max_asks_per_s: 3`.

## The picture

One still was saved and looked at, then deleted. It shows no camera name, no date and time, and no Reolink watermark. The camera was in black-and-white (infrared) mode at about 5 pm.
