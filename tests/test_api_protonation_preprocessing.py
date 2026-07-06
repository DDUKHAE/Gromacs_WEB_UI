import json
from pathlib import Path
from fastapi.testclient import TestClient
from web.server import create_app

HIS_PDB = (
    "ATOM      1  ND1 HIS A  42       1.000   2.000   3.000  1.00  0.00           N  \n"
)
RUN_ID = "prot_20260101_120000"


def test_create_run_preprocesses_his_states(tmp_path):
    pdb_bytes = HIS_PDB.encode()
    system_config = json.dumps({
        "protonation": {"ph": 7.0, "his_states": {"A:42": "HSD"}}
    })

    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"llm": "", "system_config": system_config},
        files={"pdb_file": ("test.pdb", pdb_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    pdb_path = tmp_path / "runs" / run_id / "inputs" / "input.pdb"
    content = pdb_path.read_text()
    assert "HSD" in content
    assert "HIS" not in content


def test_create_run_without_protonation_leaves_pdb_unchanged(tmp_path):
    pdb_bytes = HIS_PDB.encode()

    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"llm": ""},
        files={"pdb_file": ("test.pdb", pdb_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    pdb_path = tmp_path / "runs" / run_id / "inputs" / "input.pdb"
    content = pdb_path.read_text()
    assert "HIS" in content
