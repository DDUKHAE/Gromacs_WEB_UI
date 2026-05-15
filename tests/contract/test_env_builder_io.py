from pathlib import Path
from unittest.mock import patch
from skills.env_builder.env_builder import init_workspace, collect_hardware
from lib import state


def test_init_workspace_creates_dirs_and_state(tmp_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    assert (ws / "inputs").is_dir()
    assert (ws / "stage1_env").is_dir()
    assert (ws / "stage2_md").is_dir()
    assert (ws / "stage3_viz").is_dir()
    s = state.read(ws)
    assert s["current_step"] == 0
    assert s["last_completed_stage"] is None


def test_collect_hardware_populates_state(tmp_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    with patch("os.cpu_count", return_value=16):
        collect_hardware(ws)
    s = state.read(ws)
    assert s["hardware"]["cpu_count"] == 16
    assert "ntomp" in s["hardware"]
    assert isinstance(s["hardware"]["gpu_ids"], list)
