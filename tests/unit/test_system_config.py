from lib.system_config import validate_advanced_workflow


def test_free_energy_requires_a_nonempty_lambda_schedule():
    errors = validate_advanced_workflow(
        {"advanced_workflow": {"free_energy": {"coordinate": "inputs/met.gro", "topology": "inputs/topol.top", "couple_moltype": "MET"}}},
        "Free_Energy_Calculations_Methane_in_Water",
    )

    assert errors == ["advanced_workflow.free_energy.lambda_schedule is required"]


def test_umbrella_rejects_an_absolute_window_path():
    errors = validate_advanced_workflow(
        {"advanced_workflow": {"umbrella": {
            "group1": "Chain_A", "group2": "Chain_B", "index": "inputs/index.ndx",
            "windows": [{"id": "000", "coordinate": "/tmp/window.gro"}],
        }}},
        "Umbrella_Sampling",
    )

    assert errors == ["advanced_workflow.umbrella.windows[0].coordinate must be a relative path"]


def test_free_energy_rejects_an_absolute_topology_include():
    errors = validate_advanced_workflow(
        {"advanced_workflow": {"free_energy": {
            "coordinate": "inputs/met.gro", "topology": "inputs/topol.top", "couple_moltype": "MET",
            "lambda_schedule": [{"id": "00", "init_lambda_state": 0, "coul_lambdas": [0.0], "vdw_lambdas": [0.0]}],
            "topology_includes": ["/tmp/met.itp"],
        }}},
        "Free_Energy_Calculations_Methane_in_Water",
    )

    assert errors == ["advanced_workflow.free_energy.topology_includes[0] must be a relative path"]
