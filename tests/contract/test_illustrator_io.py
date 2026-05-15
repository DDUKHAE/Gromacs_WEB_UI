from pathlib import Path
import pytest
from lib import state


def _seed_md_stage(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    s["step_outputs"]["step_7"] = {
        "em_gro": "stage2_md/em.gro", "nvt_gro": "stage2_md/nvt.gro",
        "npt_gro": "stage2_md/npt.gro",
        "production_gro": "stage2_md/production.gro",
    }
    state.write(ws, s)
    for fname in ("production.tpr", "production.xtc", "production.edr"):
        (ws / "stage2_md" / fname).write_text("placeholder")


def test_entry_gate_passes_when_md_complete(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    _seed_md_stage(tmp_workspace)
    assert_ready(tmp_workspace)


def test_entry_gate_fails_when_stage_marker_wrong(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    from lib.state import StateContractError
    _seed_md_stage(tmp_workspace)
    s = state.read(tmp_workspace)
    s["last_completed_stage"] = "env"
    state.write(tmp_workspace, s)
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)


def test_entry_gate_fails_when_trajectory_missing(tmp_workspace: Path):
    from skills.illustrator.illustrator import assert_ready
    from lib.state import StateContractError
    _seed_md_stage(tmp_workspace)
    (tmp_workspace / "stage2_md" / "production.xtc").unlink()
    with pytest.raises(StateContractError):
        assert_ready(tmp_workspace)
