import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_harness(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    from web.server import create_app
    app = create_app(harness_dir=tmp_harness)
    return TestClient(app)


_SAMPLE_CONFIG = {
    "version": "1.0",
    "builder_type": "solution",
    "forcefield": {"name": "charmm36-jul2022", "water_model": "tip3p"},
    "box": {"type": "dodecahedron", "edge_distance_nm": 1.0},
}


def test_list_presets_empty(client):
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_save_preset_returns_201(client):
    resp = client.post("/api/presets", json={"name": "Test Preset", "config": _SAMPLE_CONFIG})
    assert resp.status_code == 201


def test_saved_preset_appears_in_list(client):
    client.post("/api/presets", json={"name": "MyPreset", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "MyPreset" in names


def test_saved_preset_config_is_stored(client):
    client.post("/api/presets", json={"name": "ConfigTest", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    preset = next(p for p in resp.json() if p["name"] == "ConfigTest")
    assert preset["config"]["builder_type"] == "solution"


def test_delete_preset_returns_200(client):
    client.post("/api/presets", json={"name": "ToDelete", "config": _SAMPLE_CONFIG})
    resp = client.delete("/api/presets/ToDelete")
    assert resp.status_code == 200


def test_deleted_preset_absent_from_list(client):
    client.post("/api/presets", json={"name": "Gone", "config": _SAMPLE_CONFIG})
    client.delete("/api/presets/Gone")
    resp = client.get("/api/presets")
    names = [p["name"] for p in resp.json()]
    assert "Gone" not in names


def test_delete_nonexistent_preset_returns_404(client):
    resp = client.delete("/api/presets/doesnotexist")
    assert resp.status_code == 404


def test_save_preset_without_name_returns_400(client):
    resp = client.post("/api/presets", json={"name": "", "config": _SAMPLE_CONFIG})
    assert resp.status_code == 400


def test_save_preset_without_config_returns_400(client):
    resp = client.post("/api/presets", json={"name": "NoConfig"})
    assert resp.status_code == 400


def test_preset_name_sanitized(client):
    client.post("/api/presets", json={"name": "My Preset!!!", "config": _SAMPLE_CONFIG})
    resp = client.get("/api/presets")
    # Special chars replaced with underscores
    names = [p["name"] for p in resp.json()]
    assert any("My_Preset" in n for n in names)


# ── POST /api/runs with system_config ────────────────────────────────────────

def test_create_run_with_system_config_saves_file(tmp_harness, client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    config_json = json.dumps(_SAMPLE_CONFIG)
    resp = client.post(
        "/api/runs",
        data={"system_config": config_json},
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    config_path = tmp_harness / "runs" / run_id / "system_config.json"
    assert config_path.exists()
    saved = json.loads(config_path.read_text())
    assert saved["builder_type"] == "solution"


def test_create_run_with_invalid_system_config_returns_400(client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    resp = client.post(
        "/api/runs",
        data={"system_config": '{"box": {"type": "hexagonal"}}'},
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 400


def test_create_run_without_system_config_succeeds(tmp_harness, client):
    pdb_content = b"ATOM      1  CA  ALA A   1       1.000   1.000   1.000\nEND\n"
    resp = client.post(
        "/api/runs",
        files={"pdb_file": ("test.pdb", pdb_content, "chemical/x-pdb")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    # No system_config.json created when field is absent
    config_path = tmp_harness / "runs" / run_id / "system_config.json"
    assert not config_path.exists()
