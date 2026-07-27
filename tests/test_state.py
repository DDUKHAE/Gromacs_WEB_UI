import pytest
from lib import state


def test_initial_schema(tmp_path):
    s = state.initial(tmp_path)
    assert s["current_step"] == 0
    assert s["last_completed_stage"] is None
    assert s["retry_history"] == []


def test_write_read_roundtrip_atomic(tmp_path):
    s = state.initial(tmp_path)
    s["current_step"] = 7
    state.write(tmp_path, s)
    assert state.read(tmp_path)["current_step"] == 7
    assert not list(tmp_path.glob("state.json.tmp*"))


def test_require_last_stage_raises_on_mismatch(tmp_path):
    s = state.initial(tmp_path)
    s["last_completed_stage"] = "md"
    with pytest.raises(Exception):
        state.require_last_stage(s, "viz")


def test_require_last_stage_passes_on_match(tmp_path):
    s = state.initial(tmp_path)
    s["last_completed_stage"] = "viz"
    state.require_last_stage(s, "viz")  # should not raise


def test_require_step_keys_raises_on_missing(tmp_path):
    s = state.initial(tmp_path)
    s["step_outputs"] = {"env": {}}
    with pytest.raises(state.StateContractError):
        state.require_step_keys(s, ["env", "md"])
