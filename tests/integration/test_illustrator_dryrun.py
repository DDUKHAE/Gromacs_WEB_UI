import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")
pytestmark = pytest.mark.skipif(GMX is None, reason="gmx not on PATH")


def test_core_analyses_produce_xvg(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import run_core_analyses
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_simulation(
        workspace_dir=tmp_workspace,
        phase_overrides={"em": {"nsteps": 50},
                          "nvt": {"nsteps": 50, "dt": 0.001},
                          "npt": {"nsteps": 50, "dt": 0.001},
                          "production": {"nsteps": 100, "dt": 0.001}},
        interactive=False,
    )
    summaries = run_core_analyses(tmp_workspace)
    for key in ("rmsd", "rmsf", "gyrate", "energy_potential",
                "energy_temperature", "energy_density"):
        assert key in summaries
        assert "mean" in summaries[key] or summaries[key]["count"] == 0
    viz = tmp_workspace / "stage3_viz"
    for fname in ("rmsd.xvg", "rmsf.xvg", "gyrate.xvg"):
        assert (viz / fname).exists()


def test_advanced_analyses_run(tmp_workspace: Path, ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import run_advanced_analyses
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    run_simulation(workspace_dir=tmp_workspace,
                   phase_overrides={p: {"nsteps": 100, "dt": 0.001}
                                     for p in ("em","nvt","npt","production")},
                   interactive=False)
    out = run_advanced_analyses(tmp_workspace)
    assert "hbond" in out
    assert "dssp" in out
    assert "pca" in out
