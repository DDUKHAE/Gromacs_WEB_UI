from lib import tutorial_registry as tr

EIGHT = {"Lysozyme_in_water", "KALP15_in_DPPC", "Protein_Ligand_Complex",
         "Umbrella_Sampling", "Building_Biphasic_Systems",
         "Free_Energy_Calculations_Methane_in_Water",
         "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol", "Virtual_Sites"}


def test_index_loads():
    idx = tr.load_index()
    assert isinstance(idx, dict) and "entries" in idx and idx["entries"]


def test_every_tutorial_resolvable():
    for tid in EIGHT:
        assert tr.get_entry(tid) is not None, f"missing registry entry: {tid}"


def test_unknown_tutorial_returns_none():
    assert tr.get_entry("Not_A_Real_Tutorial") is None
