import json
from pathlib import Path
import pytest
from lib import state


def test_initial_state_has_required_top_level_keys(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    assert s["schema_version"] == state.SCHEMA_VERSION
    assert s["workspace_dir"] == str(tmp_workspace)
    assert s["current_step"] == 0
    assert s["last_completed_stage"] is None
    assert s["step_outputs"] == {}
    assert s["retry_history"] == []
    assert s["pending_warnings"] == []
    assert s["topology_backups"] == []


def test_write_then_read_round_trip(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    s["current_step"] = 3
    state.write(tmp_workspace, s)
    loaded = state.read(tmp_workspace)
    assert loaded == s


def test_write_is_atomic(tmp_workspace: Path):
    s = state.initial(workspace_dir=tmp_workspace)
    state.write(tmp_workspace, s)
    # Atomic write should not leave temp file behind
    assert not list(tmp_workspace.glob("state.json.tmp*"))
    assert (tmp_workspace / "state.json").exists()


def test_require_keys_passes_when_keys_present(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    s["step_outputs"]["step_1"] = {"forcefield": "charmm36"}
    state.require_step_keys(s, ["step_1"])  # should not raise


def test_require_keys_fails_when_missing(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    with pytest.raises(state.StateContractError) as exc:
        state.require_step_keys(s, ["step_1"])
    assert "step_1" in str(exc.value)


def test_require_stage_passes_when_match(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.require_last_stage(s, "env")


def test_require_stage_fails_when_mismatch(tmp_workspace: Path):
    s = state.initial(tmp_workspace)
    with pytest.raises(state.StateContractError):
        state.require_last_stage(s, "env")
