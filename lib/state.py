import json
import os
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
STATE_FILENAME = "state.json"


def initial(workspace_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_dir": str(workspace_dir),
        "current_step": 0,
        "last_completed_stage": None,
        "tutorial": None,
        "hardware": None,
        "step_outputs": {},
        "retry_history": [],
        "pending_warnings": [],
        "topology_backups": [],
    }


def path(workspace_dir: Path) -> Path:
    return Path(workspace_dir) / STATE_FILENAME


def read(workspace_dir: Path) -> dict[str, Any]:
    with open(path(workspace_dir)) as f:
        return json.load(f)


def write(workspace_dir: Path, data: dict[str, Any]) -> None:
    target = path(workspace_dir)
    fd, tmp = tempfile.mkstemp(prefix=STATE_FILENAME + ".tmp", dir=workspace_dir)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
