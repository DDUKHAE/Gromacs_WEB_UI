import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "presets"
TUTORIAL_IDS = {
    "Lysozyme_in_water",
    "KALP15_in_DPPC",
    "Protein_Ligand_Complex",
    "Umbrella_Sampling",
    "Building_Biphasic_Systems",
    "Free_Energy_Calculations_Methane_in_Water",
    "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    "Virtual_Sites",
}


def test_each_bundled_tutorial_has_a_loadable_preset():
    preset_paths = sorted(PRESETS.glob("tutorial-*.json"))
    preset_ids = {path.stem.removeprefix("tutorial-") for path in preset_paths}

    assert preset_ids == TUTORIAL_IDS
    for path in preset_paths:
        config = json.loads(path.read_text())
        assert config["forcefield"]["name"]
        assert config["forcefield"]["water_model"]
        assert config["box"]["type"]
        assert "edge_distance_nm" in config["box"]
        assert config["ions"]["salt_type"]
        assert "concentration_M" in config["ions"]
        assert config["simulation"]["_expert_mode"] is True
        assert config["notes"]["tutorial_id"] in TUTORIAL_IDS
        assert config["notes"]["required_files"]
