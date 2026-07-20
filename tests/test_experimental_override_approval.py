import json
from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app


PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


def test_tutorial_difference_requires_explicit_web_approval(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    system_config = json.dumps({
        "forcefield": {"name": "charmm36", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.1},
        "membrane": {"lipids_upper": [{"name": "DPPC", "fraction": 1.0}]},
    })
    response = client.post(
        "/api/runs",
        data={"tutorial_id": "KALP15_in_DPPC", "system_config": system_config},
        files={"pdb_file": ("protein.pdb", PDB, "text/plain")},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "experimental_override_confirmation_required"
    assert detail["compatibility"]["status"] == "warning"
    assert any(item["policy"] == "experimental_override" for item in detail["compatibility"]["items"])
