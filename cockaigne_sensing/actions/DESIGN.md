# Actions design

Written 12 November 2026 by Claude (Fable), for Sam to accept or change before anything is built. The actions module answers one question per person, every few seconds: is this person on a phone, drinking, eating, or none of these. It is the only unbuilt module in the sensing chain. Everything after it already exists: `features` counts the scores and computes `action_rates`, the bus writes `action` ledger lines, and the controller leans on the rates. So this module has exactly one output, the per-person `actions` scores in the people list (Contract 1), and that message does not change.

This document replaces the brief in `actions/__init__.py` where the two disagree. The disagreements are listed at the end as decisions for Sam.

## The shape

```
people list ──► scheduler ──► close-up crops ──► model ──► votes ──► scores
 (Contract 1)   who is due     from capture      one word   per person   merged back into
                                                                         the people list
```

A worker thread runs this loop beside the launcher's main loop. The main loop never waits for it. Ten times a second the main loop hands the worker the newest people list and copies the worker's current scores into the message before `features` sees it. If the worker is slow, stuck or dead, the people list still goes out on time with the last scores, which fade to zero.

## Where the picture comes from

Detection runs on the 640 × 360 sub-stream. A far person is under 100 pixels tall there, which is too small to see a phone. The September bench found a phone plain to a human eye in a crop from the 3840 × 2160 picture.

The brief said to read the main stream. Reading four 4K video streams continuously means decoding 100 large frames a second in order to use about one a second. This design asks each camera for a single full-size still picture instead, only when someone seen by that camera is due. Reolink cameras serve one over HTTP (`/cgi-bin/api.cgi?cmd=Snap`). One still serves every person that camera can see, so the cost grows with the number of cameras, not the number of people.

Two things about the still are unknown until measured in the shed. The first is how long the camera takes to answer. The second is how far the still lags the live picture. If the answer is slow (more than about half a second), the fallback is the main stream with a reader thread that keeps only the newest frame. The module does not care which is used, because both sit behind one function in `capture`.

That function is the privacy boundary. `capture.closeups(camera, boxes)` fetches the picture, cuts out the rectangles, and returns only the rectangles. The whole picture never leaves `capture`. This is the rule in ARCHITECTURE.md, enforced by where the code sits.

The rectangle is the person's box from the newest people list, scaled from the sub-stream's size to the still's size and padded by a margin (`crop_pad`, starting at 0.25) to forgive the lag. The crop is then shrunk so its longer side is at most `crop_max_px`. Smaller crops are answered faster, and the right size is a bench question.

## Who is asked, and when

The render PC's one graphics card also plays the video wall. The module must never take more of it than agreed, however full the room is. So the limit is a budget of questions per second (`max_asks_per_s`), not an interval per person.

- A person is due when they have not been asked for `interval_s` seconds.
- Among people who are due, the one asked longest ago goes first.
- Only one question is in flight at any moment.
- A person is skipped while coasting (no camera saw them this step) and until they have been in the room `min_age_s` seconds.
- A person whose newest answer differs from the one before is due again at once. A first "phone" is checked within a second or two, and so is the first "none" after a run of "phone". The budget is spent where something is changing.

In a quiet room everyone is asked every `interval_s`. In a full room the interval stretches by itself. With a budget of 3 a second and 20 people, each person is asked about every 7 seconds.

## The model

A vision-language model is a program that takes a picture and a question and answers in words. It runs locally through Ollama on `127.0.0.1:11434`. The module refuses in code to talk to any other address, the same rule as the bus.

The question is fixed: "This is an infrared camera image of one person. Is the person using a phone, drinking, eating, or none of these?" The answer is forced to be one of the enabled words by Ollama's structured output (a schema the model's reply must fit), so there is nothing to parse and no unparseable reply. Temperature is zero, so the same crop gives the same answer. The model is kept loaded so there is no cold start between questions.

A question that fails or takes longer than `request_timeout_s` produces no reading. It is not counted as "none". After `fail_warn_s` without a successful answer the module logs a warning, at most every `warn_every_s`.

The model sits behind one function, `ask(crop) -> word or None`. A fake model that answers from a script stands in for tests and for desks without a graphics card.

## From answers to scores

Each person keeps their last `history_readings` answers (starting at 4), each with its time.

- A person's score for an action is zero unless their newest `agree_readings` answers (2) all name that action.
- When they do, the score is the share of the kept answers that name it. Two of two is 1.0. Three of four is 0.75.
- An answer older than `reading_stale_s` is forgotten, so a person who stops being asked fades to zero.
- A person who leaves the room takes their answers with them.

This is the brief's rule with the window written down. It has a consequence worth stating. The machine reports sustained actions, not glances. In a quiet room a phone is reported within about 5 seconds of first showing. In a full room, within about 10. Both figures assume the model answers in under a second, which the bench must confirm. A look at a phone shorter than that is never reported. The data wall's phone count is therefore a count of people settled into their phones.

## What it will get wrong

- A person facing away from every camera that sees them hides the phone with their body. The people list names only the one camera with the best view of the person, not the one facing them. This version asks that camera and accepts the miss.
- Drinking and eating are brief. A sip lasts a second or two and will usually fall between questions. Expect `drink` to fire for people holding a cup near the face, and rarely otherwise.
- Nobody knows yet how well any small model reads infrared crops from a camera mounted high on a wall. That is the main risk in this module, and only footage from that height can answer it.

## Trying it without the gallery

- `python -m cockaigne_sensing.actions.run people.jsonl --video cam1=clip.mkv --out people_actions.jsonl` replays a recording, cuts crops from the matching video, asks the model, and writes the people list with scores filled in. `--model fake` needs no graphics card.
- `python -m cockaigne_sensing.tools.bench_actions crops/ --models a,b,c` runs each candidate model over a folder of labelled crops and prints, per model, how often it was right for each action, what it confused with what, and how long it took.
- `--save-crops DIR` on the live launcher writes crops to disk for building that labelled set. It is the same kind of switch as `--record`: development only, never in the gallery configuration, and it logs a loud line when it is on.

Models to bench, in this order: `qwen3-vl:4b-instruct`, `gemma4:e2b`, `gemma3:4b`, `qwen2.5vl:3b`, `moondream`. The first two are newer than the brief's list. Some current models think aloud before answering unless told not to; the module turns that off, and the bench confirms it per model.

## Files and size

| File | Job | Lines, about |
|---|---|---|
| `capture/closeup.py` | fetch a still or newest main frame, cut rectangles, return only those | 90 |
| `actions/crops.py` | scale a box between frame sizes, pad, clamp, shrink | 40 |
| `actions/model.py` | one question to Ollama, one word back; the fake model | 70 |
| `actions/votes.py` | answers in, scores out | 70 |
| `actions/worker.py` | the scheduler and the thread | 130 |
| `actions/run.py` | the replay entry point | 80 |
| `tools/bench_actions.py` | model comparison on labelled crops | 90 |

About 570 lines. The two packages stand at about 3,100 lines of code today, so the total stays under 3,700 against the 5,000 budget. The launcher gains about 15 lines. No new dependency: `requests` is already logged for the controller.

New config under `actions:`: `live`, `source` (`snap` or `main`), `max_asks_per_s`, `min_age_s`, `crop_pad`, `crop_max_px`, `history_readings`, `reading_stale_s`, `request_timeout_s`, `fail_warn_s`, `ollama_url`. The existing keys keep their meaning.

## Order of work

1. Shed, half an hour. Turn on HTTP in the camera's web interface (the overlays and the clock are still to be fixed there from 16 October). Time twenty still requests and note the picture size. This settles `snap` against `main`.
2. Build everything that needs no graphics card: crops, votes, scheduler, worker, fake model, replay entry, tests. This can start now.
3. Shed, an hour, two people. A staged session at the final camera height: phone, drink, eat, none; near, middle, far; standing and sitting; facing the camera, side-on, facing away. Saved with `--save-crops`, then labelled by hand from contact sheets. Two to three hundred crops.
4. Bench the models on the render PC. Pick one. Set `crop_max_px` and the budget from the timings.
5. Render PC with the real Resolume composition playing. Run actions at the chosen budget and watch for dropped frames on the wall. Lower the budget until there are none.

## Decisions for Sam

1. **Stills instead of the main stream.** Departs from the brief and from ARCHITECTURE.md's wording. Needs HTTP switched on at each camera, on the closed network. The camera password travels in the request address, as it already does for RTSP, and is masked in every log line.
2. **A budget of questions per second instead of a fixed interval per person.** Refines the brief. `interval_s` remains as the fastest any one person is asked.
3. **Should the wall be able to say the sense is offline?** Today a dead actions module and a room with no phones look the same: zeros. Audit item 13 names this. Option A changes no contract: the module writes a ledger `note` when it loses and regains the model, and the wall shows zeros. Option B adds a health entry to the people list beside `cameras`, so the wall can show the action counts as unavailable. B is a contract change and touches the data wall. Recommended: B, because the wall displays the machine's claims and "nobody is on a phone" is a claim it cannot support while blind.
4. **The model shortlist** gains two newer models ahead of the brief's three.
5. **Development crops on disk** behind `--save-crops`, never in the gallery. The brief also proposed labelling crops with a hosted model. This design labels by hand instead, so no development footage leaves the machine. Say if the hosted route is still wanted.
