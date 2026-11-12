# Object check on the shed session, 12 November 2026

Run by Claude Code on the render PC with `tools.bench_actions bench/sessions/shed1 --config config/studio.yaml --models objects`. The check is the person detector (`yolo11s.pt`, trained on COCO) run on the same crops a language model would get. A phone, a cup, a bottle, a wine glass or a piece of food seen in the crop becomes the answer. The person was found in all 275 stills.

## At the detector's own threshold (conf 0.25)

Right 136 of 275 (49%). It answered in 0.02 seconds.

| Action | Right |
|---|---|
| none | 110 of 110 (100%) |
| phone | 18 of 55 (32%) |
| drink | 8 of 55 (14%) |
| eat | 0 of 55 (0%) |

By facing, it was right 58% facing the camera, 48% side on and 40% back to the camera. The three marks scored about the same, 46 to 51%.

It almost never names the wrong action. Its mistakes are misses: 54 eats, 46 drinks and 37 phones were called "none". There was one eat called drink and one drink called phone.

## Lower thresholds (a one-off run, not a setting in the tool)

| conf | right | none | phone | drink | eat |
|---|---|---|---|---|---|
| 0.25 | 49% | 100% | 32% | 14% | 0% |
| 0.10 | 52% | 91% | 50% | 25% | 0% |
| 0.05 | 51% | 79% | 61% | 38% | 0% |

Lowering the threshold trades false alarms for phones and drinks found. It never finds food: whatever Sam ate was not one of COCO's eight foods, or was too small in the crop.

## What it means

- **On its own, the check is not enough.** It misses most actions and cannot see eating.
- **When it does name an action, it is almost always right**, at 50 times the speed of a language model. That makes it worth considering as a fast first pass: its "phone" or "drink" taken as an answer, and a language model asked only when it says "none". That is a design question for after the language models are benched, not something built here.
- **The language models are the next run.** They need Ollama and the models pulled; the command is in RUNBOOK.md, with `objects` added to `--models` so all are in one report.
