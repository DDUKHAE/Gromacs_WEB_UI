import hashlib
import json
import os
import platform
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
        "provenance": {
            "gmx_version": None,
            "platform": None,
            "force_field": None,
            "mdp_hashes": {},
            "seed": {},
        },
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


class StateContractError(Exception):
    """Raised when state.json violates a skill's entry contract."""


def require_step_keys(state_data: dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in state_data.get("step_outputs", {})]
    if missing:
        raise StateContractError(f"missing required step keys: {missing}")


def require_last_stage(state_data: dict[str, Any], expected: str) -> None:
    actual = state_data.get("last_completed_stage")
    if actual != expected:
        raise StateContractError(
            f"last_completed_stage must be {expected!r}, got {actual!r}"
        )


def _provenance_block(state_data: dict[str, Any]) -> dict[str, Any]:
    prov = state_data.setdefault("provenance", {})
    prov.setdefault("gmx_version", None)
    prov.setdefault("platform", None)
    prov.setdefault("force_field", None)
    prov.setdefault("mdp_hashes", {})
    prov.setdefault("seed", {})
    return prov


def capture_provenance(workspace_dir: Path) -> dict[str, Any]:
    """Capture `gmx --version` and OS platform into `state.provenance`.

    Safe to call repeatedly (idempotent) and safe to call when `gmx` is not
    installed: the gmx_version field is simply left as None instead of
    raising, so a missing GROMACS binary never crashes a run."""
    from lib import gmx_wrapper as GW

    s = read(workspace_dir)
    prov = _provenance_block(s)
    try:
        prov["gmx_version"] = GW.get_version()
    except Exception:
        prov["gmx_version"] = None
    prov["platform"] = platform.platform()
    write(workspace_dir, s)
    return prov


def record_force_field(workspace_dir: Path, forcefield: str) -> None:
    s = read(workspace_dir)
    prov = _provenance_block(s)
    prov["force_field"] = forcefield
    write(workspace_dir, s)


def record_mdp_hash(workspace_dir: Path, phase: str, mdp_path: Path) -> str:
    """sha256 the rendered mdp file for `phase` and store it in
    provenance.mdp_hashes, keyed by phase. Returns the hex digest."""
    digest = hashlib.sha256(Path(mdp_path).read_bytes()).hexdigest()
    s = read(workspace_dir)
    prov = _provenance_block(s)
    prov["mdp_hashes"][phase] = digest
    write(workspace_dir, s)
    return digest


def record_seed(workspace_dir: Path, phase: str, seed: int) -> None:
    s = read(workspace_dir)
    prov = _provenance_block(s)
    prov["seed"][phase] = seed
    write(workspace_dir, s)
