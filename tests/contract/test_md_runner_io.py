# tests/contract/test_md_runner_io.py
from pathlib import Path
import pytest
from lib import state


def _populate_env_stage(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"}
    s["step_outputs"]["step_1"] = {"forcefield": "charmm36",
                                    "water_model": "tip3p",
                                    "top_file": "stage1_env/topol.top",
                                    "gro_file": "stage1_env/processed.gro"}
    s["step_outputs"]["step_2"] = {"box_type": "cubic", "box_distance": 1.0,
                                    "box_gro": "stage1_env/box.gro"}
    s["step_outputs"]["step_3"] = {"solv_gro": "stage1_env/solv.gro",
                                    "n_solvent_molecules": 1000}
    s["step_outputs"]["step_5"] = {"ion_gro": "stage1_env/ions.gro",
                                    "n_na": 0, "n_cl": 0, "net_charge": 0.0}
    state.write(ws, s)
    for fname in ("processed.gro", "topol.top", "ions.gro", "index.ndx"):
        (ws / "stage1_env" / fname).write_text("placeholder")


def test_entry_gate_passes_when_stage1_complete(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    _populate_env_stage(tmp_workspace)
    assert_ready(tmp_workspace)


def test_entry_gate_fails_when_state_missing_keys(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    s = state.initial(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_stage_marker_wrong(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    _populate_env_stage(tmp_workspace)
    s = state.read(tmp_workspace)
    s["last_completed_stage"] = None
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_files_missing(tmp_workspace: Path):
    from skills.md_runner.md_runner import assert_ready
    from lib.state import StateContractError
    _populate_env_stage(tmp_workspace)
    (tmp_workspace / "stage1_env" / "processed.gro").unlink()
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)
