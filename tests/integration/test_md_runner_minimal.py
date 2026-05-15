# tests/integration/test_md_runner_minimal.py
import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


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
