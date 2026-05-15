from unittest.mock import patch
from pathlib import Path
from lib import state


def _seed(ws: Path, variant: str):
    s = state.initial(ws)
    s["last_completed_stage"] = "md"
    s["tutorial"] = {"id": "X", "variant": variant, "manifest_path": ""}
    s["step_outputs"]["step_7"] = {"production_gro": "stage2_md/production.gro"}
    state.write(ws, s)
    for fn in ("production.tpr", "production.xtc", "production.edr"):
        (ws / "stage2_md" / fn).write_text("x")


def test_umbrella_dispatch_calls_wham(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "umbrella_sampling")
    with patch("skills.illustrator.illustrator._run_wham") as m:
        m.return_value = {"pmf_xvg": "pmf.xvg"}
        out = run_variant_analyses(tmp_workspace)
    assert m.called
    assert out["pmf_xvg"] == "pmf.xvg"


def test_free_energy_dispatch_calls_bar(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "free_energy_alchemical")
    with patch("skills.illustrator.illustrator._run_bar") as m:
        m.return_value = {"dG_kJ_per_mol": -12.3}
        out = run_variant_analyses(tmp_workspace)
    assert m.called
    assert out["dG_kJ_per_mol"] == -12.3


def test_standard_variant_returns_empty(tmp_workspace: Path):
    from skills.illustrator import run_variant_analyses
    _seed(tmp_workspace, "protein_aqueous_standard")
    assert run_variant_analyses(tmp_workspace) == {}
