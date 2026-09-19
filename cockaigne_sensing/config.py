"""Loads config/sensing.yaml so every module reads its numbers from one place."""
from pathlib import Path
import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "sensing.yaml"


def load(path: str | Path | None = None) -> dict:
    """Return the settings as a plain dictionary."""
    with open(path or DEFAULT_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
