import json
from pathlib import Path
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
