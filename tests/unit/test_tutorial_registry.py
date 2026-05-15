import pytest
from lib import tutorial_registry as TR


def test_load_index_returns_all_known_tutorials():
    idx = TR.load_index()
    ids = {e["id"] for e in idx["entries"]}
    assert "Lysozyme_in_water" in ids
    assert "KALP15_in_DPPC" in ids
    assert "Protein_Ligand_Complex" in ids


def test_load_manifest_for_lysozyme():
    m = TR.load_manifest("Lysozyme_in_water")
    assert m["pipeline_variant"] == "protein_aqueous_standard"
    assert "step_1" in m["documents"]


def test_load_manifest_missing_returns_none():
    assert TR.load_manifest("Umbrella_Sampling") is None  # derived, no manifest


def test_get_entry_for_id():
    e = TR.get_entry("KALP15_in_DPPC")
    assert e["domain"] == "membrane_md"
    assert "membrane_composition" in e["required_inputs"]


def test_route_protein_only_picks_lysozyme():
    decision = TR.route(prompt="run a basic protein simulation in water",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "Lysozyme_in_water"
    assert decision.confidence in ("high", "medium")
    assert decision.missing_inputs == []


def test_route_membrane_requires_composition():
    decision = TR.route(prompt="membrane protein in DPPC",
                        pdb_hints={"has_protein": True, "has_membrane": True,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "KALP15_in_DPPC"
    assert "membrane_composition" in decision.missing_inputs


def test_route_membrane_ok_when_prereq_present():
    decision = TR.route(prompt="membrane protein in DPPC",
                        pdb_hints={"has_protein": True, "has_membrane": True,
                                   "has_ligand": False},
                        prerequisites={"membrane_composition": {"DPPC": 128}})
    assert decision.missing_inputs == []
    assert decision.unsupported_reason is None


def test_route_protein_ligand_requires_ligand_inputs():
    decision = TR.route(prompt="protein-ligand binding",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": True},
                        prerequisites={})
    assert decision.tutorial_id == "Protein_Ligand_Complex"
    assert "ligand_structure" in decision.missing_inputs or \
           "ligand_itp" in decision.missing_inputs


def test_route_unknown_falls_back_to_lysozyme():
    decision = TR.route(prompt="something obscure",
                        pdb_hints={"has_protein": True, "has_membrane": False,
                                   "has_ligand": False},
                        prerequisites={})
    assert decision.tutorial_id == "Lysozyme_in_water"
    assert decision.confidence == "low"
