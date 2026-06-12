from pathlib import Path
import pytest
from lib.pdb_analyzer import PDBAnalyzer

LYSOZYME_PDB = Path(__file__).parent.parent / "tutorial_data" / "Lysozyme_in_water" / "1AKI.pdb"


def test_analyze_chains():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert result["chains"] == ["A"]


def test_analyze_residue_count():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert result["residue_count"] == 129


def test_analyze_atom_count():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert result["atom_count"] == 1001


def test_analyze_net_charge():
    # 1AKI: ARG×11 + LYS×6 - ASP×7 - GLU×2 = +8
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert result["net_charge"] == 8


def test_disulfide_detection():
    # 1AKI has 4 disulfide bridges: C6-C127, C30-C115, C64-C80, C76-C94
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert len(result["disulfide_candidates"]) == 4


def test_disulfide_fields():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    bridge = result["disulfide_candidates"][0]
    assert "cys1" in bridge
    assert "cys2" in bridge
    assert "distance_angstrom" in bridge
    assert bridge["distance_angstrom"] <= 2.5


def test_hetatm_excludes_water():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    names = [h["resname"] for h in result["hetatm"]]
    assert "HOH" not in names


def test_missing_residues_empty_for_complete_structure():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    assert result["missing_residues"] == []


def test_result_schema():
    result = PDBAnalyzer(LYSOZYME_PDB).analyze()
    for key in ("chains", "residue_count", "atom_count", "net_charge",
                "hetatm", "missing_residues", "disulfide_candidates", "altloc_residues"):
        assert key in result, f"Missing key: {key}"
