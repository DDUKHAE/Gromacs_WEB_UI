from lib.pdb_preprocessor import apply_his_states


# Minimal 80-col PDB ATOM line for chain A, resseq 42, residue HIS
_HIS_ATOM = (
    "ATOM      1  ND1 HIS A  42       1.000   2.000   3.000  1.00  0.00           N  \n"
)
_ALA_ATOM = (
    "ATOM      2  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C  \n"
)


def test_renames_his_to_hsd():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSD"})
    assert "HSD" in result
    assert "HIS" not in result


def test_renames_his_to_hse():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSE"})
    assert "HSE" in result
    assert "HIS" not in result


def test_renames_his_to_hsp():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSP"})
    assert "HSP" in result
    assert "HIS" not in result


def test_leaves_non_his_unchanged():
    result = apply_his_states(_ALA_ATOM, {"A:1": "HSD"})
    assert "ALA" in result
    assert "HSD" not in result


def test_leaves_unmapped_his_unchanged():
    result = apply_his_states(_HIS_ATOM, {"B:42": "HSD"})  # different chain
    assert "HIS" in result


def test_multiple_his_residues():
    pdb = (
        "ATOM      1  ND1 HIS A  10       0.0   0.0   0.0  1.00  0.00           N  \n"
        "ATOM      2  ND1 HIS A  20       0.0   0.0   0.0  1.00  0.00           N  \n"
        "ATOM      3  CA  ALA A  30       0.0   0.0   0.0  1.00  0.00           C  \n"
    )
    result = apply_his_states(pdb, {"A:10": "HSD", "A:20": "HSP"})
    lines = result.splitlines()
    assert lines[0][17:20] == "HSD"
    assert lines[1][17:20] == "HSP"
    assert lines[2][17:20] == "ALA"


def test_empty_his_states_is_noop():
    result = apply_his_states(_HIS_ATOM, {})
    assert result == _HIS_ATOM


def test_non_atom_records_untouched():
    pdb = "REMARK  HIS references are not renamed in REMARK lines\n" + _HIS_ATOM
    result = apply_his_states(pdb, {"A:42": "HSD"})
    assert result.startswith("REMARK  HIS")
