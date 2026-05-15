import shutil
from pathlib import Path
import pytest

GMX = shutil.which("gmx")


def test_md_runner_accepts_externally_prepared_env(tmp_workspace: Path):
    """User provides stage1_env/ artifacts + minimal state.json,
       md-runner must accept and proceed (or skip gracefully if no gmx).
    """
    from lib import state
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 2, "gpu_ids": [], "ntomp": 2}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_1"] = {
        "forcefield": "charmm36", "water_model": "tip3p",
        "top_file": "stage1_env/topol.top",
        "gro_file": "stage1_env/processed.gro",
    }
    s["step_outputs"]["step_2"] = {"box_type": "cubic", "box_distance": 1.0,
                                    "box_gro": "stage1_env/box.gro"}
    s["step_outputs"]["step_3"] = {"solv_gro": "stage1_env/solv.gro",
                                    "n_solvent_molecules": 0}
    s["step_outputs"]["step_5"] = {"ion_gro": "stage1_env/ions.gro",
                                    "n_na": 0, "n_cl": 0, "net_charge": 0.0}
    state.write(tmp_workspace, s)
    for f in ("processed.gro", "topol.top", "ions.gro"):
        (tmp_workspace / "stage1_env" / f).write_text("placeholder")
    from skills.md_runner.md_runner import assert_ready
    assert_ready(tmp_workspace)  # no exception


def test_illustrator_accepts_externally_prepared_md(tmp_workspace: Path):
    from lib import state
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_7"] = {
        "production_gro": "stage2_md/production.gro",
    }
    state.write(tmp_workspace, s)
    for f in ("production.tpr", "production.xtc", "production.edr"):
        (tmp_workspace / "stage2_md" / f).write_text("placeholder")
    from skills.illustrator.illustrator import assert_ready
    assert_ready(tmp_workspace)


@pytest.mark.skipif(GMX is None, reason="gmx not on PATH")
def test_full_pipeline_progresses_last_completed_stage(tmp_workspace: Path,
                                                       ubq_pdb_path: Path):
    from skills.env_builder import build_environment
    from skills.md_runner import run_simulation
    from skills.illustrator import illustrate
    from lib import state
    shutil.copy(ubq_pdb_path, tmp_workspace / "inputs" / "input.pdb")
    build_environment(
        pdb_path=tmp_workspace / "inputs" / "input.pdb",
        prompt="protein in water",
        workspace_dir=tmp_workspace,
        prerequisites={},
        interactive=False,
    )
    assert state.read(tmp_workspace)["last_completed_stage"] == "env"
    run_simulation(workspace_dir=tmp_workspace,
                   phase_overrides={p: {"nsteps": 100, "dt": 0.001}
                                     for p in ("em","nvt","npt","production")},
                   interactive=False)
    assert state.read(tmp_workspace)["last_completed_stage"] == "md"
    illustrate(workspace_dir=tmp_workspace, animation={"enabled": False})
    assert state.read(tmp_workspace)["last_completed_stage"] == "viz"
