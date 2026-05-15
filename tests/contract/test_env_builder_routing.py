from pathlib import Path
from skills.env_builder.env_builder import select_tutorial, init_workspace
from lib import state


def test_select_tutorial_records_decision(tmp_path: Path, ubq_pdb_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    decision = select_tutorial(
        workspace_dir=ws,
        pdb_path=ubq_pdb_path,
        prompt="run a basic protein simulation in water",
        prerequisites={},
    )
    assert decision.tutorial_id == "Lysozyme_in_water"
    s = state.read(ws)
    assert s["tutorial"]["id"] == "Lysozyme_in_water"
    assert s["tutorial"]["variant"] == "protein_aqueous_standard"


def test_select_tutorial_blocks_missing_prereq(tmp_path: Path, ubq_pdb_path: Path):
    ws = tmp_path / "ws"
    init_workspace(ws)
    import pytest
    from skills.env_builder.env_builder import UnsupportedTutorialError
    with pytest.raises(UnsupportedTutorialError):
        select_tutorial(
            workspace_dir=ws,
            pdb_path=ubq_pdb_path,
            prompt="umbrella sampling pmf",
            prerequisites={},  # missing reaction_coordinate_definition
        )
