import json
from pathlib import Path

from fastapi.testclient import TestClient

from web.server import create_app

PDB = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"

# The Ethanol free-energy tutorial's required_inputs (solute_topology,
# coulomb_vdw_lambda_schedule) are only satisfied once advanced_workflow.
# free_energy is populated (lib/run_plan.py:_provided_inputs); this is
# pre-existing, unrelated to the axis-resolution logic under test here.
_FREE_ENERGY_CONFIG = json.dumps({
    "advanced_workflow": {
        "free_energy": {
            "coordinate": "solute.gro",
            "topology": "solute.itp",
            "couple_moltype": "ETH",
            "lambda_schedule": [
                {"id": "0", "init_lambda_state": 0, "coul_lambdas": [0.0], "vdw_lambdas": [0.0]},
            ],
        }
    }
})


def test_create_run_resolves_tutorial_id_from_axes(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"system_type": "aqueous_protein", "protocol": "standard_md"},
        files={"pdb_file": ("test.pdb", PDB, "text/plain")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    plan_path = tmp_path / "runs" / run_id / "resolved_run_plan.json"
    assert plan_path.exists()
    assert '"id": "Lysozyme_in_water"' in plan_path.read_text()


def test_create_run_honors_tutorial_id_hint_within_cell(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={
            "system_type": "small_molecule_solution",
            "protocol": "alchemical_fe",
            "tutorial_id": "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
            "system_config": _FREE_ENERGY_CONFIG,
        },
        files=[
            ("pdb_file", ("test.pdb", PDB, "text/plain")),
            ("workflow_files", ("solute.gro", b"coordinates\n0\n   1 1 1\n", "text/plain")),
            ("workflow_files", ("solute.itp", b"[ moleculetype ]\n", "text/plain")),
        ],
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    plan_path = tmp_path / "runs" / run_id / "resolved_run_plan.json"
    assert "Ethanol" in plan_path.read_text()


def test_create_run_rejects_unsupported_combination(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"system_type": "protein_ligand_complex", "protocol": "umbrella_sampling"},
        files={"pdb_file": ("test.pdb", PDB, "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "unsupported_combination"
    assert not (tmp_path / "runs").exists()


def test_create_run_without_axes_still_works(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={},
        files={"pdb_file": ("test.pdb", PDB, "text/plain")},
    )
    assert resp.status_code == 201
