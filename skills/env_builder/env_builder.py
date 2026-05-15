"""env-builder skill — Step 0–5 of the GROMACS pipeline."""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lib import state


def init_workspace(workspace_dir: Path) -> None:
    workspace_dir = Path(workspace_dir)
    for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
        (workspace_dir / sub).mkdir(parents=True, exist_ok=True)
    if not state.path(workspace_dir).exists():
        state.write(workspace_dir, state.initial(workspace_dir))


def _detect_gpu_ids() -> list[int]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            text=True, timeout=10,
        )
        return [int(x.strip()) for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def collect_hardware(workspace_dir: Path) -> None:
    cpu = os.cpu_count() or 1
    gpus = _detect_gpu_ids()
    ntomp = max(1, cpu // max(1, len(gpus) or 1))
    s = state.read(workspace_dir)
    s["hardware"] = {"cpu_count": cpu, "gpu_ids": gpus, "ntomp": ntomp}
    state.write(workspace_dir, s)
