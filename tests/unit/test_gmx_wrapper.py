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


def test_backup_topology_creates_bak(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("[ molecules ]\nProtein 1\n")
    bak = GW.backup_topology(top)
    assert bak.exists()
    assert bak.suffix == ".bak"
    assert bak.read_text() == top.read_text()


def test_restore_topology(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("original")
    bak = GW.backup_topology(top)
    top.write_text("mutated")
    GW.restore_topology(top)
    assert top.read_text() == "original"


def test_restore_without_backup_raises(tmp_path: Path):
    top = tmp_path / "topol.top"
    top.write_text("x")
    with pytest.raises(FileNotFoundError):
        GW.restore_topology(top)
