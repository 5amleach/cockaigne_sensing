# Reading the actions bench on shed1, 15 November 2026

Claude Code ran this on the render PC, on an RTX 5070 Ti with nothing else using the graphics card. The tool's own report is `bench/actions-shed1.md`. It came from:

`python -m cockaigne_sensing.tools.bench_actions bench/sessions/shed1 --config config/studio.yaml --no-think --models objects,qwen3-vl:4b-instruct,gemma4:e2b,gemma3:4b,qwen2.5vl:3b,moondream --out bench/actions-shed1.md`

The stills are the 275 from Sam's scripted session on 12 November, at about 5 pm with the camera in infrared.

## Before the run

- The Ollama install was broken (its `lib` folder was empty) and was reinstalled as 0.40.16. The models were not affected.
- A model's first load took up to 35 seconds, far over the live 5-second answer timeout. The bench now gives the first question 300 seconds and unloads each model before the next.
- `gemma4:e2b` reasons aloud before answering unless told not to. Without `no_think` it never answered within 20 tokens. The bench gained `--no-think`. The other four models gave identical answers with it on or off.

## Result: qwen3-vl:4b-instruct is the clear choice

| Model | Right | none | phone | drink | eat | Median answer |
|---|---|---|---|---|---|---|
| qwen3-vl:4b-instruct | 69% | 97% | 74% | 69% | 10% | 0.36 s |
| gemma3:4b | 62% | 96% | 69% | 47% | 1% | 0.41 s |
| objects (YOLO) | 49% | 100% | 32% | 14% | 0% | 0.01 s |
| gemma4:e2b | 44% | 99% | 20% | 1% | 0% | 0.11 s |
| qwen2.5vl:3b | 31%* | 49% | 36% | 21% | 0% | 0.34 s |
| moondream | 30% | 0% | 85% | 67% | 0% | 0.14 s |

\* qwen2.5vl stopped answering after its 158th question, in two separate runs. Asked afresh, it answers the same crops. Something on this Ollama version breaks after a long run. That alone rules it out for a month unattended. The default `actions.model` in config is this model and should change.

Moondream calls almost everything a phone, and gemma4 calls almost everything nothing.

### qwen3-vl in detail

By facing, for each action:

| Facing | none | phone | drink | eat |
|---|---|---|---|---|
| facing the camera | 38/40 | 20/20 | 20/20 | 3/20 |
| side on | 40/40 | 20/20 | 17/20 | 3/20 |
| back to the camera | 29/30 | 1/15 | 1/15 | 0/15 |

- **Seen from the front or side, it is nearly perfect** on phone, drink and nothing in hand. It raised only 2 false alarms in 80 stills of nothing in hand.
- Scored by hold (the most common answer across the 5 stills of each 12-second hold), it got every phone, drink and nothing-in-hand hold right that was not back-turned.
- **Back-turned, it misses everything,** because the body hides the object. `actions/DESIGN.md` already accepts this miss.
- **Eating is not seen.** It got 6 of 55, and mistook eating for drinking or phone. No model or YOLO did better. Whatever Sam ate was small, or was held like a cup or a phone.

## Re-run without "eat", 16 November

The two best models were asked again with `enabled: [phone, drink]`, so the question offered only phone, drink or none. The same 275 stills were used, and the eat stills count as wrong whatever the answer.

| Model | none | phone | drink | eat stills called drink or phone |
|---|---|---|---|---|
| qwen3-vl, with eat | 107/110 | 41/55 | 38/55 | 21 |
| qwen3-vl, without eat | 108/110 | 41/55 | 36/55 | 17 |
| gemma3, with eat | 106/110 | 38/55 | 26/55 | 26 |
| gemma3, without eat | 105/110 | 40/55 | 23/55 | 29 |

Dropping eat does not sharpen phone or drink; the differences are a still or two either way. Eating is still mostly reported as drinking or phone, because the model now has no other word for it. So "eat" stays: it costs nothing in the other answers, and it lets the feast arm be driven now and then.

## Decided, 16 November

1. **Sam set `actions.model: qwen3-vl:4b-instruct`** in all three configs. `actions.no_think` stays false.
2. **"eat" stays in `enabled`**, from the re-run above.
3. **Speed:** 0.36 seconds an answer on a free card, plus about 0.73 seconds for the still. That is about one question a second, below the `max_asks_per_s: 3` ceiling. The load test with Resolume playing is still to come.
4. **Not tested:** a darker room, and more than one person in a crop.
