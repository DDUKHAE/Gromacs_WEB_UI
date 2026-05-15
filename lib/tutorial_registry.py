import json
from pathlib import Path
from typing import Any

INDEX_PATH = Path("docs/tutorial/tutorial_index.json")


def load_index(index_path: Path = INDEX_PATH) -> dict[str, Any]:
    with open(index_path) as f:
        return json.load(f)


def get_entry(tutorial_id: str, index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    idx = load_index(index_path)
    for entry in idx["entries"]:
        if entry["id"] == tutorial_id:
            return entry
    return None


def load_manifest(tutorial_id: str,
                  index_path: Path = INDEX_PATH) -> dict[str, Any] | None:
    entry = get_entry(tutorial_id, index_path)
    if not entry:
        return None
    mp = entry.get("manifest_path")
    if not mp:
        return None
    p = Path(mp)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)
