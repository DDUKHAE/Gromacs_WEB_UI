# tests/contract/test_md_runner_warning_flow.py
from pathlib import Path
from unittest.mock import patch
from lib import state, validators as V


def _seed_for_warning(ws: Path):
    s = state.initial(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 4, "gpu_ids": [], "ntomp": 4}
    s["tutorial"] = {"id": "Lysozyme_in_water",
                     "variant": "protein_aqueous_standard",
                     "manifest_path": ""}
    for k in ("step_1","step_2","step_3","step_5"):
        s["step_outputs"][k] = {}
    state.write(ws, s)


def _make_warning():
    return V.Judgment(
        tier="warning", metric="density", observed=985.0,
        expected_range=(995, 1005), cause="pressure_coupling",
        suggested_mutation={"target": "npt.mdp",
                            "changes": {"tau_p": "2.0 → 5.0"},
                            "rationale": "relax barostat"},
    )


def test_warning_returns_pending_decision(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    assert out["status"] == "warning_pending_decision"
    assert out["warning_id"]
    s = state.read(tmp_workspace)
    assert len(s["pending_warnings"]) == 1
    assert s["pending_warnings"][0]["warning_id"] == out["warning_id"]


def test_warning_auto_declined_when_noninteractive(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=False)
    assert out["status"] == "warning_declined"
    s = state.read(tmp_workspace)
    assert any(e["cause"] == "auto_decline_noninteractive"
               for e in s["retry_history"])


def test_accept_warning_applies_mutation(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result, accept_warning
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    wid = out["warning_id"]
    overrides = accept_warning(tmp_workspace, wid)
    assert "tau_p" in overrides
    s = state.read(tmp_workspace)
    assert all(p["warning_id"] != wid for p in s["pending_warnings"])
    assert any(e["tier"] == "warning" and e["warning_id"] == wid
               for e in s["retry_history"])


def test_decline_warning_records_and_clears(tmp_workspace: Path):
    from skills.md_runner.md_runner import handle_phase_result, decline_warning
    _seed_for_warning(tmp_workspace)
    out = handle_phase_result(tmp_workspace, phase="npt",
                              judgment=_make_warning(),
                              interactive=True)
    decline_warning(tmp_workspace, out["warning_id"])
    s = state.read(tmp_workspace)
    assert s["pending_warnings"] == []
    assert any(e["cause"] == "user_decline" for e in s["retry_history"])
