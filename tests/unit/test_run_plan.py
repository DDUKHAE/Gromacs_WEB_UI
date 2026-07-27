import json

from lib.run_plan import compile_plan


def test_free_energy_plan_blocks_when_lambda_schedule_is_missing(tmp_path):
    pdb = tmp_path / "input.pdb"
    pdb.write_text("ATOM      1  CA  ALA A   1       0.0   0.0   0.0\n")
    (tmp_path / "system_config.json").write_text(json.dumps({}))

    plan = compile_plan(tmp_path, pdb, "Free_Energy_Calculations_Methane_in_Water")

    assert plan["compatibility"]["status"] == "blocked"
    assert "lambda_schedule" in plan["missing_inputs"]
