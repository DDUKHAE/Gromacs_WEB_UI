# skills/md_runner/md_runner.py
from pathlib import Path
from typing import Any
from lib import state
from lib.state import StateContractError


REQUIRED_KEYS = ["step_1", "step_2", "step_3", "step_5"]
REQUIRED_FILES = ["processed.gro", "topol.top", "ions.gro"]


def assert_ready(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    state.require_last_stage(s, "env")
    state.require_step_keys(s, REQUIRED_KEYS)
    if not s.get("hardware"):
        raise StateContractError("hardware profile missing")
    ws = Path(workspace_dir)
    for fname in REQUIRED_FILES:
        if not (ws / "stage1_env" / fname).exists():
            raise StateContractError(f"missing stage1 file: {fname}")
    return s
