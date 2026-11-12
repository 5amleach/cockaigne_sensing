"""actions: phone, drinking, eating, per person, from a local vision-language model.

Built 12 November 2026, except for the choice of model, which waits on a
bench of real crops (see DESIGN.md in this folder and DECISIONS.md).

A worker thread (worker.py) asks about each person every few seconds, under
a ceiling on questions per second so the graphics card that plays the wall
is never crowded. For each question, capture cuts the person's rectangle
from one full-size still and hands over only the rectangle. The model
(model.py, through Ollama on this machine only) answers with one word:
phone, drink, eat or none. A person's answers are kept for a short while
(votes.py); two that agree start an action and two that agree end it. The
scores go into the people list (Contract 1) before features sees it, with
`actions_health` beside them saying whether the model is answering at all.

Nothing here writes a picture to disk. The crop lives in memory for the
length of one question.

Run it from a recording:
    python -m cockaigne_sensing.actions.run people.jsonl --video cam1=clip.mkv --out out.jsonl
"""
from .model import FakeModel, OllamaModel, make_model
from .votes import Votes
from .worker import ActionsWorker, due_people

__all__ = ["ActionsWorker", "due_people", "Votes", "make_model", "OllamaModel", "FakeModel"]
