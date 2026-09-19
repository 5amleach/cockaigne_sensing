"""actions: phone, drinking, eating, per person, from a local vision-language model.

NOT YET WRITTEN. Brief for whoever builds it.

A vision-language model takes a picture and answers a question about it in
words. We run one locally through Ollama (https://ollama.com), which serves
models over http://127.0.0.1:11434 with no internet involved.

Loop, every interval_s per tracked person:
1. Get the person's box in the main-stream frame. (Detection ran on the
   sub-stream; scale the box by main_w/sub_w and main_h/sub_h.) Pad the box
   by 20% and crop.
2. Send the crop to the model with a fixed multiple-choice prompt:
   "This is an infrared security camera image of one person. Answer with
   exactly one word: phone, drinking, eating, or none." Parse the one
   word. Anything unparseable is "none". (A bright-blob shortcut for
   phone screens was tested on venue footage and does not work: skin is
   brighter than the screen and the screen faces the holder. See
   DECISIONS.md, 2026-09-19.)
3. (Reserved. Numbering kept so the steps below match earlier notes.)
4. Keep the last agree_readings answers per person. Report an action only
   when they all agree. Confidence = fraction of the last few readings
   that agreed.
5. Keep a running baseline rate per action over baseline_window_s and emit
   action_rates = current rate / baseline (see Contract 2).
6. Drop the crop immediately. Never write it to disk.

Models to test on bench footage, in this order: qwen2.5vl:3b, gemma3:4b,
moondream. Judge them against labels produced by a strong hosted model on
the same crops (development footage only; see spec Part four).

Only actions listed in config actions.enabled are asked about.
"""
