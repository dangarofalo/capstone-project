"""Small JSON file that remembers where each collector stopped reading."""
import json
from pathlib import Path


def load_state(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, state: dict) -> None:
    # Write to a temp file first so a crash mid-write cannot corrupt the checkpoint.
    target = Path(path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(target)
