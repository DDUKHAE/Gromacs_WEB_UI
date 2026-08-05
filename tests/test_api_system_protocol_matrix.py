from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app


def test_matrix_endpoint_shape(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/system-protocol-matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert {s["id"] for s in data["system_types"]} == {
        "aqueous_protein", "protein_ligand_complex", "small_molecule_solution"}
    assert {p["id"] for p in data["protocols"]} == {
        "standard_md", "umbrella_sampling", "alchemical_fe", "virtual_sites"}
    assert len(data["combos"]) == 6


def test_matrix_endpoint_excludes_membrane(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    data = client.get("/api/system-protocol-matrix").json()
    system_type_ids = {s["id"] for s in data["system_types"]}
    assert "membrane" not in system_type_ids
    assert all(c["system_type"] != "membrane" for c in data["combos"])
