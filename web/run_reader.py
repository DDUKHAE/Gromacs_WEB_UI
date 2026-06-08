import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class RunInfo:
    run_id: str
    workspace: Path
    status: str
    protein: str
    created_at: str
    last_completed_stage: str | None
    current_step: int
    pending_warnings: list = field(default_factory=list)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def derive_status(workspace: Path) -> str:
    pid_file = workspace / "runner.pid"
    exit_file = workspace / "runner.exit"
    state_file = workspace / "state.json"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            return "pending"
        if _process_alive(pid):
            return "running"
        if not exit_file.exists():
            return "aborted"

    if not exit_file.exists():
        return "pending"

    try:
        code = int(exit_file.read_text().strip())
    except ValueError:
        return "failed"
    if code != 0:
        return "failed"

    if state_file.exists():
        try:
            s = json.loads(state_file.read_text())
            if s.get("last_completed_stage") == "viz":
                return "completed"
            return "paused"
        except Exception:
            pass
    return "completed"


def read_run(run_id: str, runs_dir: Path) -> RunInfo | None:
    workspace = runs_dir / run_id
    if not workspace.is_dir():
        return None

    parts = run_id.rsplit("_", 2)
    protein = parts[0] if len(parts) == 3 else run_id
    try:
        created_at = datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S").isoformat()
    except (ValueError, IndexError):
        created_at = ""

    last_stage: str | None = None
    current_step = 0
    pending_warnings: list = []
    state_file = workspace / "state.json"
    if state_file.exists():
        try:
            s = json.loads(state_file.read_text())
            last_stage = s.get("last_completed_stage")
            current_step = s.get("current_step", 0)
            pending_warnings = s.get("pending_warnings", [])
        except Exception:
            pass

    return RunInfo(
        run_id=run_id,
        workspace=workspace,
        status=derive_status(workspace),
        protein=protein,
        created_at=created_at,
        last_completed_stage=last_stage,
        current_step=current_step,
        pending_warnings=pending_warnings,
    )


def list_runs(runs_dir: Path) -> list[RunInfo]:
    if not runs_dir.exists():
        return []
    items = []
    for d in sorted(runs_dir.iterdir(), reverse=True):
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("_"):
            info = read_run(d.name, runs_dir)
            if info:
                items.append(info)
    return items
