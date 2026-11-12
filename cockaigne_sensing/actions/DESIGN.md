# Actions design

Written 12 November 2026 by Claude (Fable) and accepted by Sam the same day, with his decisions recorded at the end and in DECISIONS.md. The module is built to this design except for the choice of model.

The actions module answers one question per person, every few seconds: is this person on a phone, drinking, eating, or none of these. Everything after it already existed: `features` counts the scores and computes `action_rates`, the bus writes `action` ledger lines, and the controller leans on the rates. So the module has one output, the per-person `actions` scores in the people list (Contract 1), plus a health flag beside them.

## The shape

```
people list ──► who is due ──► close-up crops ──► model ──► votes ──► scores
 (Contract 1)                   from capture      one word   per person   written back into
                                                                          the people list
```

A worker thread runs this loop beside the launcher's main loop. The main loop never waits for it. Ten times a second the main loop hands the worker the newest people list and copies the worker's current scores into the message before `features` sees it. If the worker is slow, stuck or dead, the people list still goes out on time, and the scores fade to zero.

## Where the picture comes from

Detection runs on the 640 × 360 sub-stream. A far person is under 100 pixels tall there, which is too small to see a phone. The September bench found a phone plain to a human eye in a crop from the 3840 × 2160 picture.

Reading four 4K video streams continuously means decoding about 100 large frames a second in order to use about one. So the module asks each camera for a single full-size still picture instead, only when someone seen by that camera is due. Reolink cameras serve one over HTTP (`/cgi-bin/api.cgi?cmd=Snap`), once HTTP is switched on in the camera. One still serves every person that camera can see, so the cost grows with the number of cameras, not the number of people.

How long the camera takes to answer is not yet measured. `tools.script_session` times ten stills at the start of every run and prints the result. If the answer is slow (more than about half a second), the fallback is the main stream with a reader that keeps only the newest frame. That fallback is not built. It would sit behind the same function, so nothing else would change.

That function is the privacy boundary. `capture.Closeups.crops` fetches the picture, cuts out the rectangles, and returns only the rectangles. The whole picture never leaves `capture`.

The rectangle is the person's box from the newest people list, read after the still arrives so the two are as close in time as possible. It is scaled from the sub-stream's size to the still's size and widened by `crop_pad` (0.25) to forgive the moment between them. The crop is then shrunk so its longer side is at most `crop_max_px` (448). Smaller crops are answered faster, and the right size is a bench question.

The data wall's camera panel is not affected. It shows the sub-stream, as before.

## Who is asked, and when

The render PC's one graphics card also plays the video wall. The module must never take more of it than agreed, however full the room is. So the limit is a ceiling of questions per second for the whole room (`max_asks_per_s`, starting at 3), with one question in flight at a time.

- A person is due when they have not been asked for `interval_s` (3 seconds).
- Among people who are due, the one asked longest ago goes first.
- A person is skipped while coasting (no camera saw them this step) and until they have been in the room `min_age_s`.
- A person whose newest answer differs from the one before is due again after `recheck_s` (1 second). A first "phone" is checked almost at once, and so is the first "none" after a run of "phone".

| Room | Each person asked | Questions in total |
|---|---|---|
| 1 to 9 people | every 3 seconds | up to 180 a minute |
| 20 people | about every 7 seconds | 180 a minute |

With nobody to ask about, the worker puts a blank question every `heartbeat_s`. That proves the model is alive in an empty room and keeps it loaded, so the first visitor does not wait for a cold start.

## The model

A vision-language model is a program that takes a picture and a question and answers in words. It runs locally through Ollama on `127.0.0.1:11434`. The module refuses in code to talk to any other address, the same rule as the bus.

The question is fixed. The answer is forced to be one of the enabled words or "none" by Ollama's structured output (a shape the reply must fit), so there is nothing to parse. Temperature is zero, so the same crop gives the same answer. The model is kept loaded between questions.

A question that fails or takes longer than `request_timeout_s` produces no answer. It is never counted as "none".

A fake model that answers from a script stands in for tests and for desks without a graphics card (`model: fake`, or `fake:phone,none`).

## From answers to scores

Each person keeps their last `history_readings` answers (4), each with its time.

- Two answers in a row that name the same action start it (`agree_readings`).
- It then holds until two answers in a row agree on something else. One stray answer neither starts an action nor ends one.
- While it holds, the score is the share of the kept answers that name it. Two of two is 1.0. Three of four is 0.75.
- An answer older than `reading_stale_s` is forgotten, so a person who can no longer be asked fades to zero.
- A person who leaves the room takes their answers with them.

A consequence worth stating: the machine reports sustained actions, not glances. In a quiet room a phone is reported within about 5 seconds of first showing. In a full room, within about 10. Both figures assume the model answers in under a second, which the bench must confirm. A shorter look at a phone is never reported. The data wall's figure is therefore a count of people settled into their phones.

## When the sense cannot see

Every people message carries `actions_health`: whether the model has answered within `fail_warn_s`, and how long ago. When it has not, the launcher logs it and writes a ledger note, and the scores fade to zero.

Sam's decision for the data wall: it shows "?" for Tech adoption, or it bluffs. "?" is the default. `?blind=bluff` on the wall's address keeps the last figure and says nothing. The bluff lives on the wall only. The controller, the log and the ledger always get the truth.

## What it will get wrong

- A person facing away from the camera that sees them hides the phone with their body. The people list names only the one camera with the best view of the person, not the one facing them. This version asks that camera and accepts the miss.
- Drinking and eating are brief. A sip lasts a second or two and will usually fall between questions.
- Nobody knows yet how well any small model reads infrared crops from a camera mounted high on a wall. That is the main risk in this module, and only pictures from that height can answer it.

## Choosing the model

`tools.script_session` fills the screen with one instruction at a time and a countdown, and saves full-size stills of the performer labelled with the instruction. The right answer comes from the script, so nothing is labelled by hand. `tools.bench_actions` then puts those stills to each candidate model and reports how often each was right, split by action, facing, mark and posture, and how long an answer took.

Models to bench, in this order: `qwen3-vl:4b-instruct`, `gemma4:e2b`, `gemma3:4b`, `qwen2.5vl:3b`, `moondream`. Some current models reason aloud before answering unless told not to; `no_think: true` turns that off.

## Order of work from here

1. Shed. Switch on HTTP at the camera (the overlays and the clock are still to be fixed there from 16 October). Run the scripted session; it times the stills first.
2. Render PC. Pull the models in Ollama and run the bench. Pick one. Set `model`, `crop_max_px` and `max_asks_per_s` from the timings, and `live: true`.
3. Render PC with the real Resolume composition playing. Run the chain with the action sense on and watch the wall for dropped frames. Lower `max_asks_per_s` until there are none.
4. Delete `script_session` and `bench_actions` once the model is chosen. They exist for that one decision.

## Decided, 12 November 2026

1. **Stills instead of the main stream.** Sam: fine, as long as the data wall still shows the camera stream. It does.
2. **A ceiling of questions per second instead of a fixed interval per person.** Built as designed.
3. **A blind sense shows "?" or bluffs.** Sam: it is art rather than accuracy, but people must feel the monitoring is functional, which may matter more than the decision. Contract 1 gained `actions_health`.
4. **Labels come from a scripted session** that Sam performs to instructions on screen. No hand labelling and no hosted model.
