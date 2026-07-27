from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app


PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


def test_run_action_rejects_unknown_action(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/runs/protein_20260710_120000/action",
        json={"action": "pause"},
    )
    assert response.status_code == 400


def test_run_id_path_traversal_is_rejected(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/runs/../state.json")
    assert response.status_code in (400, 404)
