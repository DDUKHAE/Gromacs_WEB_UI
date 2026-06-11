import json
import pytest
from pathlib import Path
from lib.tutorial_auditor import audit_run, AuditReport, AuditItem


@pytest.fixture
def workspace(tmp_path):
    state = {
        "schema_version": "1.0",
        "workspace_dir": str(tmp_path),
        "current_step": 9,
        "last_completed_stage": "viz",
        "tutorial": {
            "id": "Lysozyme_in_water",
            "variant": "protein_aqueous_standard",
            "routing_confidence": "high",
        },
        "hardware": {"ntomp": 4},
        "step_outputs": {
            "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron", "box_distance": 1.0},
            "step_7": {"phase_sequence": ["em", "nvt", "npt", "production"]},
        },
        "retry_history": [],
        "pending_warnings": [],
        "topology_backups": [],
    }
    (tmp_path / "state.json").write_text(json.dumps(state))
    meta = {"tutorial_id": "Lysozyme_in_water"}
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    return tmp_path


def test_audit_returns_report(workspace):
    report = audit_run(workspace)
    assert isinstance(report, AuditReport)


def test_audit_pass_on_matching_config(workspace):
    report = audit_run(workspace)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "pass"


def test_audit_fail_on_wrong_forcefield(workspace):
    state = json.loads((workspace / "state.json").read_text())
    state["step_outputs"]["step_1"]["forcefield"] = "amber99sb"
    (workspace / "state.json").write_text(json.dumps(state))
    report = audit_run(workspace)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "fail"
    assert "charmm36" in ff_item.expected
    assert "amber99sb" in ff_item.actual


def test_audit_fail_on_wrong_phase_sequence(workspace):
    state = json.loads((workspace / "state.json").read_text())
    state["step_outputs"]["step_7"]["phase_sequence"] = ["em", "production"]  # skipped NVT/NPT
    (workspace / "state.json").write_text(json.dumps(state))
    report = audit_run(workspace)
    seq_item = next(i for i in report.items if i.key == "phase_sequence")
    assert seq_item.status == "fail"


def test_audit_no_tutorial_returns_na(tmp_path):
    state = {
        "schema_version": "1.0", "workspace_dir": str(tmp_path),
        "current_step": 9, "last_completed_stage": "viz",
        "tutorial": None, "hardware": {"ntomp": 4},
        "step_outputs": {}, "retry_history": [], "pending_warnings": [],
        "topology_backups": [],
    }
    (tmp_path / "state.json").write_text(json.dumps(state))
    (tmp_path / "meta.json").write_text("{}")
    report = audit_run(tmp_path)
    assert report.tutorial_id is None
    assert all(i.status == "n/a" for i in report.items)


from unittest.mock import patch, MagicMock
from lib import state as state_lib
from skills.md_runner import md_runner as MD


def test_run_phase_records_phase_to_state(tmp_path):
    """run_phase() must append the phase name to step_7.phase_sequence in state.json."""
    ws = tmp_path
    s = state_lib.initial(ws)
    s["hardware"] = {"ntomp": 1}
    state_lib.write(ws, s)

    stage2 = ws / "stage2_md"
    stage2.mkdir()
    (ws / "stage1_env").mkdir()
    (ws / "stage1_env" / "ions.gro").write_text("fake")
    (ws / "stage1_env" / "topol.top").write_text("fake")

    fake_result = MagicMock()
    fake_result.ok = True

    with patch("skills.md_runner.md_runner.MDP.render", return_value=stage2 / "em.mdp") as _m, \
         patch("skills.md_runner.md_runner.GW.run", return_value=fake_result) as _g:
        MD.run_phase(ws, "em")

    updated = state_lib.read(ws)
    seq = updated.get("step_outputs", {}).get("step_7", {}).get("phase_sequence", [])
    assert "em" in seq
