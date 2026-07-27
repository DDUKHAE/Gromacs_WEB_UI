import pytest
from pathlib import Path
from lib.pdb_analyzer import PDBAnalyzer

INPUTS = [
    "tutorial_data/Lysozyme_in_water/1AKI.pdb",
    "tutorial_data/KALP15_in_DPPC/KALP-15_princ.pdb",
    "tutorial_data/Protein_Ligand_Complex/3HTB.pdb",
    "tutorial_data/Umbrella_Sampling/2BEG.pdb",
    "tutorial_data/Virtual_Sites/co2.pdb",
    "tutorial_data/Free_Energy_Ethanol/etoh.pdb",
]


@pytest.mark.parametrize("path", INPUTS)
def test_input_pdbs_parse_without_error(path):
    p = Path(path)
    if not p.exists():
        pytest.skip(f"input missing: {path}")
    result = PDBAnalyzer(p).analyze()
    assert result is not None
    assert isinstance(result, dict)
