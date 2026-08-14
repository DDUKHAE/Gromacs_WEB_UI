"""`.gro` reading, writing and concatenation.

Format, verified against a real file produced by gmx editconf:
  line 1      title
  line 2      atom count, right-aligned
  lines 3..   one line per atom, fixed columns
  last line   three box vectors

The tutorial's merge step is `cat` plus hand-editing: "remove unnecessary lines
(the box vectors from the KALP structure, the header information from the DPPC
structure) and update the second line of the coordinate file (total number of
atoms) accordingly."
"""
import pytest

from lib import gro_file


PEPTIDE = """\
KALP-15
    3
    1LYS      N    1   1.000   2.000   3.000
    1LYS     CA    2   1.100   2.100   3.100
    2ALA      N    3   1.200   2.200   3.200
   1.00000   2.00000   3.00000
"""

BILAYER = """\
Pure DPPC bilayer
    2
    1DPPC     C1    1   1.577   5.265   0.920
    1DPPC     C2    2   1.600   5.300   1.000
   6.41840   6.44350   6.59650
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_read_splits_title_atoms_and_box(tmp_path):
    g = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    assert g.title == "KALP-15"
    assert len(g.atoms) == 3
    assert g.box.split() == ["1.00000", "2.00000", "3.00000"]


def test_read_rejects_a_declared_count_that_disagrees(tmp_path):
    bad = PEPTIDE.replace("    3\n", "    9\n", 1)
    with pytest.raises(gro_file.GroFileError, match="declares 9"):
        gro_file.read(_write(tmp_path, "bad.gro", bad))


def test_count_reads_line_two(tmp_path):
    assert gro_file.count(_write(tmp_path, "p.gro", PEPTIDE)) == 3


def test_concat_sums_the_atom_counts(tmp_path):
    a = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    b = gro_file.read(_write(tmp_path, "b.gro", BILAYER))
    merged = gro_file.concat(a, b, "system")
    assert len(merged.atoms) == 5


def test_concat_keeps_the_bilayer_box_and_drops_the_peptide_one(tmp_path):
    """The combined system must adopt the bilayer's unit cell."""
    a = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    b = gro_file.read(_write(tmp_path, "b.gro", BILAYER))
    merged = gro_file.concat(a, b, "system")
    assert merged.box.split() == ["6.41840", "6.44350", "6.59650"]


def test_concat_puts_the_peptide_first(tmp_path):
    a = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    b = gro_file.read(_write(tmp_path, "b.gro", BILAYER))
    merged = gro_file.concat(a, b, "system")
    assert "LYS" in merged.atoms[0]
    assert "DPPC" in merged.atoms[-1]


def test_written_file_declares_the_real_atom_count(tmp_path):
    a = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    b = gro_file.read(_write(tmp_path, "b.gro", BILAYER))
    out = tmp_path / "system.gro"
    gro_file.write(out, gro_file.concat(a, b, "system"))
    assert gro_file.count(out) == 5
    assert gro_file.read(out).title == "system"


def test_atom_lines_are_copied_verbatim(tmp_path):
    """Residue and atom numbers are 5-character fields that wrap at 100000.
    Re-emitting them from parsed integers would corrupt large systems, so
    nothing here parses them."""
    a = gro_file.read(_write(tmp_path, "p.gro", PEPTIDE))
    original = list(a.atoms)
    out = tmp_path / "again.gro"
    gro_file.write(out, a)
    assert gro_file.read(out).atoms == original


def test_wrapped_atom_numbers_survive_a_round_trip(tmp_path):
    """A system at the wrap boundary: atom number 100000 is written as 00000."""
    text = (
        "wrapped\n    2\n"
        "99999SOL     OW99999   1.000   1.000   1.000\n"
        "100000SOL    HW1    0   1.100   1.100   1.100\n"
        "   5.00000   5.00000   5.00000\n"
    )
    g = gro_file.read(_write(tmp_path, "w.gro", text))
    out = tmp_path / "w2.gro"
    gro_file.write(out, g)
    assert out.read_text() == text


def test_box_vectors_are_parsed_as_floats(tmp_path):
    b = gro_file.read(_write(tmp_path, "b.gro", BILAYER))
    assert gro_file.box_vectors(b) == pytest.approx((6.41840, 6.44350, 6.59650))


def test_read_rejects_a_file_too_short_to_be_gro(tmp_path):
    with pytest.raises(gro_file.GroFileError):
        gro_file.read(_write(tmp_path, "t.gro", "title\n0\n"))


@pytest.mark.integration
def test_gmx_accepts_a_concat_built_from_real_tutorial_structures(tmp_path):
    """The real oracle: build peptide + bilayer .gro from tracked PDBs via
    `gmx editconf`, concat them with this module, and have `gmx editconf`
    read the merged file back. A structural assertion alone would not catch
    a format this module silently corrupts but GROMACS still complains about.
    """
    import os
    import shutil
    import subprocess

    from pathlib import Path as _Path

    gmx = shutil.which("gmx")
    if gmx is None:
        pytest.skip("gmx not on PATH")
    peptide_pdb = _Path("tutorial_data/KALP15_in_DPPC/KALP-15_princ.pdb")
    bilayer_pdb = _Path("tutorial_data/KALP15_in_DPPC/dppc128.pdb")
    if not (peptide_pdb.is_file() and bilayer_pdb.is_file()):
        pytest.skip("needs tutorial_data/KALP15_in_DPPC/*.pdb")

    env = {**os.environ, "GMX_MAXBACKUP": "-1"}
    shutil.copy(peptide_pdb, tmp_path / "peptide.pdb")
    shutil.copy(bilayer_pdb, tmp_path / "bilayer.pdb")

    def editconf(pdb_name, gro_name):
        r = subprocess.run(
            ["gmx", "editconf", "-f", pdb_name, "-o", gro_name],
            cwd=tmp_path, capture_output=True, input="0\n", text=True, env=env,
        )
        assert r.returncode == 0, r.stderr[-2000:]

    editconf("peptide.pdb", "peptide.gro")
    editconf("bilayer.pdb", "bilayer.gro")

    a = gro_file.read(tmp_path / "peptide.gro")
    b = gro_file.read(tmp_path / "bilayer.gro")
    merged = gro_file.concat(a, b, "system")
    gro_file.write(tmp_path / "system.gro", merged)

    assert gro_file.count(tmp_path / "system.gro") == len(a.atoms) + len(b.atoms)

    result = subprocess.run(
        ["gmx", "editconf", "-f", "system.gro", "-o", "system_check.pdb"],
        cwd=tmp_path, capture_output=True, input="0\n", text=True, env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert (tmp_path / "system_check.pdb").is_file()
