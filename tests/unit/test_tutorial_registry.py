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
