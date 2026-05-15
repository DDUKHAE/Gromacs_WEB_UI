import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_step1_pdb2gmx_produces_topology(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import (
        init_workspace, collect_hardware, select_tutorial, run_step1_topology,
    )
    from lib import state
    init_workspace(tmp_workspace)
    collect_hardware(tmp_workspace)
    select_tutorial(tmp_workspace, ubq_pdb_path,
                    "protein in water", prerequisites={})
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    run_step1_topology(tmp_workspace, forcefield="charmm36", water="tip3p")
    s = state.read(tmp_workspace)
    assert (tmp_workspace / "stage1_env" / "processed.gro").exists()
    assert (tmp_workspace / "stage1_env" / "topol.top").exists()
    assert s["step_outputs"]["step_1"]["forcefield"] == "charmm36"
