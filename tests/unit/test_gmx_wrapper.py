from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from lib import gmx_wrapper as GW


def test_run_success_returns_zero_exit(tmp_path: Path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = GW.run(["pdb2gmx", "-f", "in.pdb"], cwd=tmp_path)
    assert result.returncode == 0
    assert result.classification == "success"


def test_run_grompp_warning_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr="WARNING 1 [...] use -maxwarn to override")
        result = GW.run(["grompp"], cwd=Path("."))
    assert result.classification == "grompp_warning"


def test_run_oom_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="",
                                          stderr="Out of memory")
        result = GW.run(["mdrun"], cwd=Path("."))
    assert result.classification == "command_error"


def test_run_topology_mismatch_classified():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="",
            stderr="Number of coordinates in coordinate file does not match topology")
        result = GW.run(["grompp"], cwd=Path("."))
    assert result.classification == "topology_mismatch"


def test_run_passes_gmx_bin_env_override(monkeypatch):
    monkeypatch.setenv("GMX_BIN", "/tmp/fake-gmx")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        GW.run(["hardware"], cwd=Path("."))
        args, _ = mock_run.call_args
    assert args[0][0] == "/tmp/fake-gmx"
