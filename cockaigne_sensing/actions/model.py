"""One question to a local vision-language model, one word back.

A vision-language model takes a picture and a question and answers in words.
Ours runs on this machine through Ollama (https://ollama.com). The question
never changes and the answer is forced to be one of a few words, so there is
nothing to interpret: the model's whole reply is "phone", "drink", "eat" or
"none". A question that fails or times out gives None, which means "no
answer". It is never counted as "none".

The crop is turned into a JPEG in memory, sent to 127.0.0.1, and dropped.
Nothing here touches the disk, and the code refuses any model server that is
not on this machine.
"""
from __future__ import annotations

import base64
import json
from urllib.parse import urlparse

import cv2
import numpy as np
import requests

QUESTION = ("This is an infrared camera image of one person. "
            "What is the person doing? Answer with exactly one of: {words}.")


def local_only(url: str) -> str:
    """The model server's address, refused unless it is this machine. The
    same rule as the bus: no picture of a visitor leaves the computer."""
    if urlparse(url).hostname not in ("127.0.0.1", "localhost"):
        raise ValueError(f"the model server must be on this machine, not {url!r}; "
                         "see the privacy rules in ARCHITECTURE.md")
    return url.rstrip("/")


class OllamaModel:
    """Asks the configured Ollama model about one crop at a time."""

    def __init__(self, cfg: dict):
        self.url = local_only(cfg["ollama_url"]) + "/api/chat"
        self.words = list(cfg["enabled"]) + ["none"]
        self.timeout_s = cfg["request_timeout_s"]
        self.body = {
            "model": cfg["model"], "stream": False,
            "keep_alive": -1,   # stay loaded, so there is no cold start between questions
            # The reply must fit this shape, so it cannot be anything but one of the words.
            "format": {"type": "object", "required": ["answer"],
                       "properties": {"answer": {"type": "string", "enum": self.words}}},
            "options": {"temperature": 0, "num_predict": cfg["num_predict"]},
        }
        if cfg["no_think"]:
            self.body["think"] = False   # some models reason aloud first unless told not to
        self.question = QUESTION.format(words=", ".join(self.words))

    def ask(self, crop: np.ndarray) -> str | None:
        """The model's one-word answer for this crop, or None for no answer."""
        ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            return None
        message = {"role": "user", "content": self.question,
                   "images": [base64.b64encode(jpeg.tobytes()).decode("ascii")]}
        try:
            reply = requests.post(self.url, json=dict(self.body, messages=[message]),
                                  timeout=self.timeout_s)
            reply.raise_for_status()
            word = json.loads(reply.json()["message"]["content"])["answer"]
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None
        return word if word in self.words else None


class FakeModel:
    """Answers from a script without looking, for tests and for desks with no
    graphics card. The words are given back in order, round and round."""

    def __init__(self, words: list[str | None]):
        self.words = words or ["none"]
        self.asked = 0

    def ask(self, crop: np.ndarray) -> str | None:
        word = self.words[self.asked % len(self.words)]
        self.asked += 1
        return word


def make_model(cfg: dict):
    """The model named in config. "fake" always answers none; "fake:phone,none"
    answers those words in turn. Anything else is an Ollama model tag."""
    name = cfg["model"]
    if name == "fake" or name.startswith("fake:"):
        return FakeModel([w.strip() for w in name[5:].split(",") if w.strip()])
    return OllamaModel(cfg)
