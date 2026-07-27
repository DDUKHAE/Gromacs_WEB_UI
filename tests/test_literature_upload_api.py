from pathlib import Path

from fastapi.testclient import TestClient

from lib import protocol_contract as pc
from lib import run_plan as rp
from web.server import create_app


RUN_ID = "protein_20260720_120000"
PDB = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


def _prepared_workspace(root: Path) -> Path:
    workspace = root / "runs" / RUN_ID
    inputs = workspace / "inputs"
    inputs.mkdir(parents=True)
    pdb = inputs / "input.pdb"
    pdb.write_text(PDB)
    plan = rp.materialize(workspace, pdb)
    pc.materialize(workspace, plan["tutorial"]["id"])
    return workspace


def test_literature_upload_is_run_local_and_extension_limited(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    client = TestClient(create_app(tmp_path))

    response = client.post(
        f"/api/runs/{RUN_ID}/literature/upload",
        files={"literature_file": ("protocol.txt", b"local evidence", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["corpus_path"] == "literature"
    assert (workspace / "literature" / "protocol.txt").read_bytes() == b"local evidence"

    rejected = client.post(
        f"/api/runs/{RUN_ID}/literature/upload",
        files={"literature_file": ("payload.exe", b"no", "application/octet-stream")},
    )
    assert rejected.status_code == 400
