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


def test_resolve_tutorial_id_valid_combos():
    assert tr.resolve_tutorial_id("aqueous_protein", "standard_md") == "Lysozyme_in_water"
    assert tr.resolve_tutorial_id("protein_ligand_complex", "standard_md") == "Protein_Ligand_Complex"
    assert tr.resolve_tutorial_id("aqueous_protein", "umbrella_sampling") == "Umbrella_Sampling"
    assert tr.resolve_tutorial_id("small_molecule_solution", "standard_md") == "Building_Biphasic_Systems"
    assert tr.resolve_tutorial_id("small_molecule_solution", "virtual_sites") == "Virtual_Sites"


def test_resolve_tutorial_id_free_energy_cell_defaults_to_methane():
    assert tr.resolve_tutorial_id("small_molecule_solution", "alchemical_fe") == \
        "Free_Energy_Calculations_Methane_in_Water"


def test_resolve_tutorial_id_free_energy_cell_honors_hint():
    result = tr.resolve_tutorial_id(
        "small_molecule_solution", "alchemical_fe",
        tutorial_id_hint="Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol")
    assert result == "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol"


def test_resolve_tutorial_id_ignores_hint_outside_cell():
    result = tr.resolve_tutorial_id("aqueous_protein", "standard_md", tutorial_id_hint="Virtual_Sites")
    assert result == "Lysozyme_in_water"


def test_resolve_tutorial_id_unsupported_combo_returns_none():
    assert tr.resolve_tutorial_id("protein_ligand_complex", "umbrella_sampling") is None
    assert tr.resolve_tutorial_id("membrane", "standard_md") is None


def test_combo_matrix_response_shape():
    payload = tr.combo_matrix_response()
    assert {s["id"] for s in payload["system_types"]} == {
        "aqueous_protein", "protein_ligand_complex", "small_molecule_solution"}
    assert {p["id"] for p in payload["protocols"]} == {
        "standard_md", "umbrella_sampling", "alchemical_fe", "virtual_sites"}
    assert len(payload["combos"]) == 6
    fe_combo = next(c for c in payload["combos"] if c["protocol"] == "alchemical_fe")
    assert fe_combo["tutorial_ids"] == [
        "Free_Energy_Calculations_Methane_in_Water",
        "Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol",
    ]
