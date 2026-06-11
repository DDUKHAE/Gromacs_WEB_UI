import json
import pytest
from pathlib import Path
from lib.system_config_validator import validate_run_against_config, ConfigAuditReport


@pytest.fixture
def workspace_with_config(tmp_path):
    config = {
        "version": "1.0",
        "builder_type": "solution",
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
    }
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    return tmp_path


@pytest.fixture
def workspace_with_state(workspace_with_config):
    state = {
        "schema_version": "1.0",
        "workspace_dir": str(workspace_with_config),
        "step_outputs": {
            "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        },
    }
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    return workspace_with_config


def test_returns_report_object(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    assert isinstance(report, ConfigAuditReport)


def test_has_config_true_when_file_present(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    assert report.has_config is True


def test_has_config_false_when_no_file(tmp_path):
    report = validate_run_against_config(tmp_path)
    assert report.has_config is False
    assert report.items == []


def test_pass_when_forcefield_matches(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "pass"


def test_fail_when_forcefield_mismatch(workspace_with_config):
    state = {
        "step_outputs": {
            "step_1": {"forcefield": "amber99sb", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        }
    }
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(workspace_with_config)
    ff_item = next(i for i in report.items if i.key == "forcefield")
    assert ff_item.status == "fail"


def test_pass_when_box_type_matches(workspace_with_state):
    report = validate_run_against_config(workspace_with_state)
    box_item = next(i for i in report.items if i.key == "box_type")
    assert box_item.status == "pass"


def test_na_when_state_not_yet_recorded(workspace_with_config):
    state = {"step_outputs": {}}
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(workspace_with_config)
    assert all(i.status == "n/a" for i in report.items)


def test_to_dict_has_expected_keys(workspace_with_state):
    d = validate_run_against_config(workspace_with_state).to_dict()
    assert "has_config" in d
    assert "passed" in d
    assert "failed" in d
    assert "items" in d


def test_na_when_state_has_no_step_outputs_key(workspace_with_config):
    """state.json exists but has no step_outputs key at all."""
    state = {"schema_version": "1.0"}  # no step_outputs
    (workspace_with_config / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(workspace_with_config)
    assert all(i.status == "n/a" for i in report.items)


def test_no_items_when_config_has_no_forcefield_or_box(tmp_path):
    """Config with only version/builder_type — no checkable fields."""
    config = {"version": "1.0", "builder_type": "solution"}
    (tmp_path / "system_config.json").write_text(json.dumps(config))
    state = {"step_outputs": {"step_1": {}, "step_2": {}}}
    (tmp_path / "state.json").write_text(json.dumps(state))
    report = validate_run_against_config(tmp_path)
    assert report.has_config is True
    assert report.items == []


# ── Audit endpoint integration ────────────────────────────────────────────────

def test_audit_endpoint_includes_config_audit(tmp_path):
    from web.server import create_app
    from fastapi.testclient import TestClient

    runs_dir = tmp_path / "runs"
    run_id = "protein_20260101_120000"
    ws = runs_dir / run_id
    ws.mkdir(parents=True)

    config = {
        "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
        "box": {"type": "dodecahedron"},
    }
    (ws / "system_config.json").write_text(json.dumps(config))
    state = {
        "step_outputs": {
            "step_1": {"forcefield": "charmm36", "water_model": "tip3p"},
            "step_2": {"box_type": "dodecahedron"},
        }
    }
    (ws / "state.json").write_text(json.dumps(state))
    (ws / "meta.json").write_text("{}")

    app = create_app(harness_dir=tmp_path)
    client = TestClient(app)

    resp = client.get(f"/api/runs/{run_id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "config_audit" in data
    assert data["config_audit"]["has_config"] is True
