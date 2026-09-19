# Bench: venue clip, 7 September 2026

Footage: `clip_20260907_110923.mkv`, 68 seconds, Reolink main stream, HEVC 3840×2160 at 25 fps, infrared black and white. Shot in the Light Room Studio with the LED walls lit. Three people: two standing near the camera, one seated on the floor at the far end near the equipment. Camera at roughly standing height, looking down the length of the U. Three shorter clips from 3–4 September are studio ceiling and bench shots with nobody in them and were not used.

Run on a two-core CPU with no GPU, YOLO11s, 1280 px input, ByteTrack, 5 frames per second.

## Detection

Three people found in almost every sampled frame. The two near people at 0.75–0.94 confidence. The far seated person at 0.3–0.5, with box height about 130 px in a 720 px view; a 640 px input would probably lose them. Occasional fourth detection at 0.25–0.37, short-lived, filtered by the one-second minimum track age.

Speed: 0.78 s per frame on CPU at 1280 px. On the render PC's GPU expect well under 0.05 s, so four cameras at 5–10 fps each are comfortable.

## Tracking

Eight distinct ids across 68 seconds for three people, using the repo's `bench_detect` tool with a one-second minimum track age. One near person kept a single id for 63 seconds. The other two each changed id two or three times. Causes seen in the snapshots: the two near people overlapped when one walked in front of the other (36–46 s), merging into one box; the far seated person dropped below the confidence threshold for a few frames (14–17 s) and came back with a new id.

Both are camera-height problems. From high on the wall looking down, people rarely overlap fully and the floor tracker merges views from other cameras. The next bench clip should be shot from the planned height and angle.

From 39 s the far person often carried two boxes at once, one tight and one loose that included the bench they were kneeling at (ids 20 and 35). The floor module's half-metre merge rule collapses these into one person. If it becomes a nuisance, lower the detector's overlap threshold (`iou`) from the default 0.7 to about 0.5.

## Infrared

Not a problem for detection. Dark clothing against the dark back wall still detected. The LED walls blow out to white in infrared and drag the camera's exposure down, which darkens the floor; detection coped. Skin is the brightest thing in the frame.

## Phone

At 60 s one person holds a phone and looks at it. The lit screen faces the holder and is seen edge-on by the camera, so it is not a bright patch. The bright blobs in the crop were the forearm, the fingers and a lanyard clip. The "phone screen as bright rectangle" shortcut in the spec does not hold from this angle. A crop of that person from the 4K main stream is about 700×950 px and the phone is plainly visible to a human, so the vision-language model route is the one to build. Whether a high camera sees screens more often is unknown; check on the next clip.

## Overlays

The camera burns a timestamp, the Reolink logo and the camera name into the picture. Switch these off in the camera's OSD settings before the next capture.

## Not yet measured

Sub-stream size and rate (no sub-stream capture exists). Vision-language model accuracy on infrared crops (needs the GPU). Detection from the planned mounting height.

---

# Second clip, same day: from the data-screen end

Footage: `clip_20260907_105939.mkv`, 200 seconds (the recording was cut off, so the file has no duration header; ffmpeg reads it fine). Camera at the data-screen end looking into the U, slightly above head height. The landscape is playing on all three walls, so every person is a dark silhouette against a bright wall. One person for the first 70 seconds, then three.

## Detection

All three people at 0.8–0.93 confidence once they are separated, and the long tracks prove it: the three people who arrive at 71 s, 91 s and 128 s keep ids 29, 34 and 81 to the end of the clip (627, 461 and 353 frames at 5 fps). Silhouette against a lit wall is an easier case for the detector than dark clothing against a dark wall.

## Wall imagery is detected as people

The landscape contains animals and figure-like shapes. At 40–52 s a dark shape near the projected arch was tracked as a person (id 16) for eleven seconds at 0.3–0.6 confidence. Something similar happened at 157–169 s (id 96). This will recur every time a clip with figures plays. Fix is in the floor module: each camera gets a hand-drawn floor polygon, and a detection whose feet fall outside it is dropped. Logged in DECISIONS.md.

## Short-lived ids

Eighteen ids in total, eleven of them under ten seconds. Most are flickers on wall content or people at the edge of frame while entering. The one-second minimum track age at 5 fps is loose; two seconds is probably right. The floor polygon removes most of the rest.

## Also

Both cameras were placed at or just above head height for these tests. The far wall of the U fills the top half of the frame. From the planned high mounting, the floor fills more of the frame and the walls less, which reduces wall false positives as well as occlusion. That capture is still the next step.
