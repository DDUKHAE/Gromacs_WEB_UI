import json

import pytest

from lib import protocol_contract as pc
from lib import run_plan as rp


PDB = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n"


def test_user_settings_are_locked_while_tutorial_difference_is_warning(tmp_path):
    pdb = tmp_path / "input.pdb"
    pdb.write_text(PDB)
    (tmp_path / "system_config.json").write_text(json.dumps({
        "forcefield": {"name": "charmm36", "water_model": "tip3p"},
        "box": {"type": "dodecahedron", "edge_distance_nm": 1.1},
        "ions": {"concentration_M": 0.2, "neutralize": True},
        "membrane": {"lipids_upper": [{"name": "DPPC", "fraction": 1.0}]},
    }))

    plan = rp.materialize(tmp_path, pdb, "KALP15_in_DPPC")

    assert plan["user_locked_settings"]["forcefield"] == "charmm36"
    assert plan["compatibility"]["status"] == "warning"
    assert any(item["field"] == "forcefield" for item in plan["compatibility"]["items"])
    assert rp.assert_valid(tmp_path)["plan_sha256"] == plan["plan_sha256"]


def test_auto_plan_is_materialized_before_contract_and_bound_to_it(tmp_path):
    pdb = tmp_path / "input.pdb"
    pdb.write_text(PDB)
    plan = rp.materialize(tmp_path, pdb)
    contract = pc.materialize(tmp_path, plan["tutorial"]["id"])

    assert plan["tutorial"]["mode"] == "auto"
    assert contract["run_plan"]["sha256"] == plan["plan_sha256"]
    assert pc.assert_valid(tmp_path)["tutorial_id"] == plan["tutorial"]["id"]


def test_plan_checksum_tampering_is_detected(tmp_path):
    pdb = tmp_path / "input.pdb"
    pdb.write_text(PDB)
    rp.materialize(tmp_path, pdb)
    plan_path = tmp_path / rp.FILENAME
    payload = json.loads(plan_path.read_text())
    payload["user_locked_settings"]["forcefield"] = "oplsaa"
    plan_path.write_text(json.dumps(payload))

    with pytest.raises(rp.RunPlanError, match="checksum mismatch"):
        rp.assert_valid(tmp_path)
