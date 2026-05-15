# tests/integration/test_md_runner_minimal.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_run_simulation_end_to_end(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    result = run_simulation(
        workspace_dir=tmp_workspace,
        phase_overrides={"em": {"nsteps": 50},
                          "nvt": {"nsteps": 50, "dt": 0.001},
                          "npt": {"nsteps": 50, "dt": 0.001},
                          "production": {"nsteps": 50, "dt": 0.001}},
        interactive=False,
    )
    assert result["status"] in ("complete", "warning_declined")
    s = state.read(tmp_workspace)
    assert s["last_completed_stage"] == "md"
    assert (tmp_workspace / "stage2_md" / "production.gro").exists() or \
           (tmp_workspace / "stage2_md" / "md.gro").exists()


def test_em_phase_runs_to_completion(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_phase
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_phase(tmp_workspace, phase="em",
              overrides={"nsteps": 50})
    s = state.read(tmp_workspace)
    assert (tmp_workspace / "stage2_md" / "em.gro").exists()
    assert "em_gro" in s["step_outputs"].get("step_7", {})
