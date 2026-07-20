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
    display_name: str | None = None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _production_finished(workspace: Path) -> bool:
    """Return whether GROMACS wrote its normal production completion marker.

    A live LLM terminal is not evidence that MD is still running.  Read only
    the tail because production logs can become large.
    """
    log_path = workspace / "stage2_md" / "production.log"
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 65536))
            tail = handle.read().decode("utf-8", errors="replace")
        return "Finished mdrun on rank" in tail
    except OSError:
        return False


def derive_status(workspace: Path) -> str:
    pid_file = workspace / "runner.pid"
    exit_file = workspace / "runner.exit"
    state_file = workspace / "state.json"

    # Keep the MD state distinct from a still-open (or stalled) LLM terminal.
    # This prevents the UI from claiming "MD Running" after mdrun has ended.
    if _production_finished(workspace):
        try:
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
        except Exception:
            state = {}
        if state.get("last_completed_stage") != "viz":
            return "analysis_pending"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if pid <= 0:
                raise ValueError
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

    display_name: str | None = None
    meta_file = workspace / "meta.json"
    if meta_file.exists():
        try:
            m = json.loads(meta_file.read_text())
            display_name = m.get("display_name") or None
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
        display_name=display_name,
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
