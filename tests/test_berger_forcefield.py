"""Building gromos53a6_lipid.ff from lipid.itp.

The KALP-15/DPPC tutorial has the user hand-edit a copy of gromos53a6.ff. Three
details in the real files defeat a naive transcription of those instructions,
and each has a test here:

* at.num cannot come from rounding the mass (united-atom CH2 = 14.0270 vs
  nitrogen = 14.0067)
* lipid.itp misspells the marker as "paramaters for lipid-GROMOS interactions"
* most HW rows sit in the SPC block the tutorial says to keep, so removing the
  lipid-GROMOS block does not remove them
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import berger_forcefield as BFF

# A miniature stand-in for $GMXLIB/gromos53a6.ff, with the sections the
# merge targets and one native row each so we can prove nothing is clobbered.
GROMOS_NONBONDED = """\
[ atomtypes ]
;name  at.num   mass      charge  ptype       c6           c12
    O    8 	0.000      0.000     A  0.0022619536       1e-06

[ nonbond_params ]
; i    j func          c6           c12
      OM        O  1  0.0022619536   8.611e-07

[ pairtypes ]
; i    j func          c6           c12
       O        O  1  0.0022619536  7.4149321e-07
"""

GROMOS_BONDED = """\
[ bondtypes ]
  C    O     2   0.123    1.6600e+07

[ dihedraltypes ]
S      S      1   gd_21
"""

# Mirrors the real lipid.itp: no at.num, the misspelled marker, HW rows both
# inside the lipid-GROMOS block and inside the kept SPC block.
LIPID_ITP = """\
;; Berger/GROMOS mixture

[ defaults ]
1       1

[ atomtypes ]
;name     mass     charge ptype  c6           c12
   LO    15.9994    0.000  A 2.36400e-03 1.59000e-06 carbonyl O, OPLS
  LNL    14.0067    0.000  A 3.35300e-03 3.95100e-06 Nitrogen, OPLS
  LP2    14.0270    0.000  A 5.94100e-03 1.55300e-05 CH2, Berger
   LP    30.9738    0.000  A 9.13600e-03 2.51900e-05 Phosphorus, OPLS

[ nonbond_params ]
  ; i    j    func    c6           c12
   LO    LO     1 2.36400e-03  1.59000e-06
  ;; paramaters for lipid-GROMOS interactions
   LO     O     1 1.00000e-03  1.00000e-06
  LP2    HW     1 0.000000e+00 0.000000e+00
  ;; lipid-SPC/SPCE interactions
   LO    OW     1 3.12800e-04  2.58400e-07
  LNL    HW     1 0.000000e+00 0.000000e+00

[ pairtypes ]
  ; i    j    func   cs6          cs12
   LO    LO     1 2.95200e-04  1.98700e-07
   LO    HW     1 0.00000e+00  0.00000e+00

[ dihedraltypes ]
  LP2 LP2  3   9.2789   12.156  -13.120 -3.0597 26.240 -31.495
"""


@pytest.fixture
def gmxlib(tmp_path):
    ff = tmp_path / "gmxlib" / f"{BFF.FF_SOURCE}.ff"
    ff.mkdir(parents=True)
    (ff / "ffnonbonded.itp").write_text(GROMOS_NONBONDED)
    (ff / "ffbonded.itp").write_text(GROMOS_BONDED)
    (ff / "forcefield.doc").write_text("GROMOS96 53A6 force field\n")
    (ff / "forcefield.itp").write_text('#include "ffnonbonded.itp"\n')
    return ff.parent


@pytest.fixture
def lipid_itp(tmp_path):
    p = tmp_path / "lipid.itp"
    p.write_text(LIPID_ITP)
    return p


@pytest.fixture
def built(tmp_path, gmxlib, lipid_itp):
    dest = tmp_path / "stage1_env"
    summary = BFF.build(lipid_itp, gmxlib, dest)
    ff = dest / f"{BFF.FF_TARGET}.ff"
    return summary, ff, (ff / "ffnonbonded.itp").read_text(), (ff / "ffbonded.itp").read_text()


def _rows(text: str, section: str) -> list[str]:
    body = re.search(rf"^\[\s*{section}\s*\](.*?)(?=^\[|\Z)", text, re.S | re.M).group(1)
    return [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith(";")]


def test_creates_the_target_forcefield_directory(built):
    summary, ff, _, _ = built
    assert ff.is_dir()
    assert summary["forcefield"] == BFF.FF_TARGET == "gromos53a6_lipid"
    # Files not involved in the merge must be carried over verbatim.
    assert (ff / "forcefield.itp").is_file()


def test_atom_number_column_is_added(built):
    """lipid.itp has 6 columns; the gromos table needs 7 with at.num second."""
    _, _, nb, _ = built
    rows = _rows(nb, "atomtypes")
    for row in rows:
        assert len(row.split(";")[0].split()) == 7, row


@pytest.mark.parametrize("atom_type,expected_z", [
    ("LO", 8),    # oxygen
    ("LNL", 7),   # nitrogen, mass 14.0067
    ("LP2", 6),   # united-atom CH2, mass 14.0270 -- also rounds to 14
    ("LP", 15),   # phosphorus
])
def test_atomic_numbers_are_not_derived_by_rounding_the_mass(built, atom_type, expected_z):
    """CH2 (14.0270) and N (14.0067) both round to 14 but differ in element."""
    _, _, nb, _ = built
    row = next(r for r in _rows(nb, "atomtypes") if r.split()[0] == atom_type)
    assert int(row.split()[1]) == expected_z


def test_unknown_mass_is_refused_rather_than_guessed(tmp_path, gmxlib):
    p = tmp_path / "lipid.itp"
    p.write_text(LIPID_ITP.replace("15.9994", "99.9999"))
    with pytest.raises(BFF.BergerForceFieldError, match="atomic number"):
        BFF.build(p, gmxlib, tmp_path / "out")


def test_lipid_gromos_block_is_removed(built):
    """Protein-lipid interactions must fall back to GROMOS combination rules."""
    _, _, nb, _ = built
    rows = _rows(nb, "nonbond_params")
    assert not any(r.split()[:2] == ["LO", "O"] for r in rows), rows
    assert "lipid-GROMOS" not in nb


def test_misspelled_marker_in_the_real_file_is_matched(built):
    """lipid.itp says "paramaters"; matching the tutorial's spelling finds nothing."""
    _, _, nb, _ = built
    assert "paramaters" not in nb


def test_deleted_marker_with_the_rows_still_present_is_rejected(tmp_path, gmxlib):
    """A missing marker must not be read as "already prepared".

    Prepared files have the lipid-GROMOS *rows* removed. If only the comment
    was lost, accepting the file would silently merge parameters the tutorial
    says to delete, so detection is by row content, not by marker presence.
    """
    p = tmp_path / "lipid.itp"
    p.write_text(LIPID_ITP.replace(";; paramaters for lipid-GROMOS interactions", "; unrelated"))
    with pytest.raises(BFF.BergerForceFieldError, match="still pairs lipid types"):
        BFF.build(p, gmxlib, tmp_path / "out")


def test_spc_block_is_preserved(built):
    _, _, nb, _ = built
    rows = _rows(nb, "nonbond_params")
    assert any(r.split()[:2] == ["LO", "OW"] for r in rows), rows


def test_hw_rows_are_dropped_including_those_in_the_kept_spc_block(built):
    """Removing the lipid-GROMOS block does not remove the SPC block's HW rows."""
    _, _, nb, _ = built
    rows = _rows(nb, "nonbond_params")
    assert not any(re.search(r"\bHW\b", r) for r in rows), rows


def test_native_gromos_parameters_are_not_clobbered(built):
    _, _, nb, bonded = built
    assert any(r.split()[0] == "O" for r in _rows(nb, "atomtypes"))
    assert any(r.split()[:2] == ["OM", "O"] for r in _rows(nb, "nonbond_params"))
    assert any("gd_21" in r for r in _rows(bonded, "dihedraltypes"))
    assert any(r.split()[0] == "C" for r in _rows(bonded, "bondtypes"))


def test_ryckaert_bellemans_dihedrals_are_appended(built):
    _, _, _, bonded = built
    rb = [r for r in _rows(bonded, "dihedraltypes") if len(r.split()) > 2 and r.split()[2] == "3"]
    assert rb, _rows(bonded, "dihedraltypes")


def test_pairtypes_are_merged(built):
    _, _, nb, _ = built
    assert any(r.split()[:2] == ["LO", "LO"] for r in _rows(nb, "pairtypes"))


def test_forcefield_doc_is_updated(built):
    _, ff, _, _ = built
    assert "Berger lipid parameters" in (ff / "forcefield.doc").read_text()


def test_summary_counts_what_was_merged(built):
    summary, _, _, _ = built
    assert summary["merged"] == {
        "atomtypes": 4, "nonbond_params": 2, "pairtypes": 1, "dihedraltypes": 1,
    }


def test_rebuild_is_idempotent(tmp_path, gmxlib, lipid_itp):
    """A resumed run must not merge the parameters twice."""
    dest = tmp_path / "stage1_env"
    first = BFF.build(lipid_itp, gmxlib, dest)
    text_first = (dest / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()
    second = BFF.build(lipid_itp, gmxlib, dest)
    text_second = (dest / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()
    assert first["merged"] == second["merged"]
    assert text_first == text_second


def test_missing_source_forcefield_is_reported(tmp_path, lipid_itp):
    with pytest.raises(BFF.BergerForceFieldError, match=BFF.FF_SOURCE):
        BFF.build(lipid_itp, tmp_path / "empty", tmp_path / "out")


def test_missing_lipid_itp_is_reported(tmp_path, gmxlib):
    with pytest.raises(BFF.BergerForceFieldError, match="lipid.itp"):
        BFF.build(tmp_path / "nope.itp", gmxlib, tmp_path / "out")


# --- topol.top includes -------------------------------------------------------
# pdb2gmx writes the force-field include itself (it follows -ff), so the only
# topology edit the tutorial still needs is the lipid moleculetype include.

TOPOL = """\
; Include forcefield parameters
#include "gromos53a6_lipid.ff/forcefield.itp"

[ moleculetype ]
Protein     3

; Include Position restraint file
#ifdef POSRES
#include "posre.itp"
#endif

; Include water topology
#include "gromos53a6_lipid.ff/spc.itp"

[ system ]
KALP15 in DPPC

[ molecules ]
Protein     1
"""


def test_include_lands_after_posres_and_before_the_water_topology(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL)
    assert BFF.add_include(t, "dppc.itp") is True
    lines = t.read_text().splitlines()
    posres = max(i for i, l in enumerate(lines) if "posre.itp" in l)
    dppc = next(i for i, l in enumerate(lines) if "dppc.itp" in l)
    water = next(i for i, l in enumerate(lines) if "Include water topology" in l)
    mols = next(i for i, l in enumerate(lines) if l.strip().startswith("[ molecules ]"))
    assert posres < dppc < water < mols


def test_include_is_not_added_twice_on_a_resumed_run(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL)
    assert BFF.add_include(t, "dppc.itp") is True
    before = t.read_text()
    assert BFF.add_include(t, "dppc.itp") is False
    assert t.read_text() == before
    assert before.count('#include "dppc.itp"') == 1


def test_include_falls_back_to_system_when_there_is_no_water_topology(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL.replace('; Include water topology\n#include "gromos53a6_lipid.ff/spc.itp"\n', ""))
    assert BFF.add_include(t, "dppc.itp") is True
    lines = t.read_text().splitlines()
    dppc = next(i for i, l in enumerate(lines) if "dppc.itp" in l)
    system = next(i for i, l in enumerate(lines) if l.strip().startswith("[ system ]"))
    assert dppc < system


def test_include_without_an_insertion_point_is_an_error(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text("[ defaults ]\n1 1\n")
    with pytest.raises(BFF.BergerForceFieldError, match="insertion point"):
        BFF.add_include(t, "dppc.itp")


# --- accepting a hand-prepared lipid.itp --------------------------------------
# The tutorial's steps can equally be applied to lipid.itp before the merge.
# Both inputs must yield the same force field so it does not matter which a
# workspace happens to contain.

PREPARED_ITP = """\
;; Berger/GROMOS mixture, prepared by hand

[ defaults ]
1       1

[ atomtypes ]
;name  at.num   mass     charge ptype  c6           c12
   LO  8  15.9994    0.000  A 2.36400e-03 1.59000e-06 carbonyl O, OPLS
  LNL  7  14.0067    0.000  A 3.35300e-03 3.95100e-06 Nitrogen, OPLS
  LP2  6  14.0270    0.000  A 5.94100e-03 1.55300e-05 CH2, Berger
   LP  15  30.9738    0.000  A 9.13600e-03 2.51900e-05 Phosphorus, OPLS

[ nonbond_params ]
  ; i    j    func    c6           c12
   LO    LO     1 2.36400e-03  1.59000e-06
  ;; lipid-SPC/SPCE interactions
   LO    OW     1 3.12800e-04  2.58400e-07
  LNL     H     1 0.000000e+00 0.000000e+00

[ pairtypes ]
  ; i    j    func   cs6          cs12
   LO    LO     1 2.95200e-04  1.98700e-07
   LO    HW     1 0.00000e+00  0.00000e+00

[ dihedraltypes ]
  LP2 LP2  3   9.2789   12.156  -13.120 -3.0597 26.240 -31.495
"""


@pytest.fixture
def prepared_itp(tmp_path):
    p = tmp_path / "lipid.prepared.itp"
    p.write_text(PREPARED_ITP)
    return p


def test_prepared_lipid_itp_is_accepted(tmp_path, gmxlib, prepared_itp):
    """An at.num column that is already present must not be re-derived.

    Regression: the mass lookup saw at.num in column 2 and failed with
    "no atomic number known for atom type 'LO' of mass 8".
    """
    summary = BFF.build(prepared_itp, gmxlib, tmp_path / "out")
    assert summary["merged"]["atomtypes"] == 4


def test_prepared_input_keeps_correct_atomic_numbers(tmp_path, gmxlib, prepared_itp):
    BFF.build(prepared_itp, gmxlib, tmp_path / "out")
    nb = (tmp_path / "out" / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()
    got = {r.split()[0]: int(r.split()[1]) for r in _rows(nb, "atomtypes")
           if r.split()[0].startswith("L")}
    assert got == {"LO": 8, "LNL": 7, "LP2": 6, "LP": 15}


def test_raw_and_prepared_inputs_agree(tmp_path, gmxlib, lipid_itp, prepared_itp):
    """Same atom types and pair types either way; the only difference allowed
    is the HW->H rename the tutorial offers as an alternative to deletion."""
    raw = BFF.build(lipid_itp, gmxlib, tmp_path / "a")
    pre = BFF.build(prepared_itp, gmxlib, tmp_path / "b")
    nb_raw = (tmp_path / "a" / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()
    nb_pre = (tmp_path / "b" / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()

    key = lambda r: tuple(r.split()[:2])
    for section in ("atomtypes", "pairtypes"):
        assert {key(r) for r in _rows(nb_raw, section)} == {key(r) for r in _rows(nb_pre, section)}

    extra = {key(r) for r in _rows(nb_pre, "nonbond_params")} - {key(r) for r in _rows(nb_raw, "nonbond_params")}
    assert all(pair[1] == "H" for pair in extra), extra
    assert raw["merged"]["dihedraltypes"] == pre["merged"]["dihedraltypes"]


def test_h_renamed_rows_are_kept_not_stripped(tmp_path, gmxlib, prepared_itp):
    """HW rows are dropped, but rows already renamed to H are valid and stay."""
    BFF.build(prepared_itp, gmxlib, tmp_path / "out")
    nb = (tmp_path / "out" / f"{BFF.FF_TARGET}.ff" / "ffnonbonded.itp").read_text()
    rows = _rows(nb, "nonbond_params")
    assert any(r.split()[:2] == ["LNL", "H"] for r in rows), rows


def test_file_with_neither_marker_is_rejected(tmp_path, gmxlib):
    """A prepared file is recognised by its kept SPC block; without either
    marker we cannot tell prepared from corrupt, so refuse."""
    p = tmp_path / "lipid.itp"
    p.write_text(PREPARED_ITP.replace(";; lipid-SPC/SPCE interactions", "; nothing"))
    with pytest.raises(BFF.BergerForceFieldError, match="refusing to guess"):
        BFF.build(p, gmxlib, tmp_path / "out")


# --- the force-field include ---------------------------------------------------
# pdb2gmx writes this to match its -ff argument, so it is normally already
# correct. It is still verified: a topology that arrived another way would
# otherwise be simulated against gromos53a6 without the lipid parameters,
# producing wrong numbers instead of an error.

def test_correct_forcefield_include_is_left_alone(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL)
    assert BFF.ensure_forcefield_include(t) is False
    assert t.read_text() == TOPOL


def test_wrong_forcefield_include_is_redirected(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL.replace("gromos53a6_lipid.ff/forcefield.itp",
                               "gromos53a6.ff/forcefield.itp"))
    assert BFF.ensure_forcefield_include(t) is True
    text = t.read_text()
    assert '#include "gromos53a6_lipid.ff/forcefield.itp"' in text
    assert '#include "gromos53a6.ff/forcefield.itp"' not in text


def test_redirect_only_touches_the_forcefield_include(tmp_path):
    """Water and position-restraint includes must survive untouched."""
    t = tmp_path / "topol.top"
    t.write_text(TOPOL.replace("gromos53a6_lipid.ff/forcefield.itp",
                               "gromos53a6.ff/forcefield.itp"))
    BFF.ensure_forcefield_include(t)
    text = t.read_text()
    assert '#include "gromos53a6_lipid.ff/spc.itp"' in text
    assert '#include "posre.itp"' in text
    assert text.count("forcefield.itp") == 1


def test_redirect_is_idempotent(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text(TOPOL.replace("gromos53a6_lipid.ff/forcefield.itp",
                               "gromos53a6.ff/forcefield.itp"))
    assert BFF.ensure_forcefield_include(t) is True
    assert BFF.ensure_forcefield_include(t) is False


def test_topology_without_a_forcefield_include_is_reported(tmp_path):
    t = tmp_path / "topol.top"
    t.write_text("[ molecules ]\nProtein 1\n")
    with pytest.raises(BFF.BergerForceFieldError, match="no force-field include"):
        BFF.ensure_forcefield_include(t)


def test_hw_rows_are_dropped_from_pairtypes_too(built):
    """Regression: HW survived in [pairtypes] and grompp rejected the result.

    The tutorial's step 4 names only [nonbond_params], but the distributed
    lipid.itp carries 14 HW rows in [pairtypes] as well. HW is not an atom type
    in gromos53a6 (only OW is), so leaving them produces
    "ERROR: Unknown atomtype HW" from grompp -- a force field that builds
    cleanly and then cannot be used. Caught only by running grompp for real.
    """
    _, _, nb, _ = built
    rows = _rows(nb, "pairtypes")
    assert not any(re.search(r"\bHW\b", r) for r in rows), rows


def test_summary_counts_exclude_dropped_hw_pairtypes(built):
    """The fixture has 2 pairtypes rows, one of them HW."""
    summary, _, _, _ = built
    assert summary["merged"]["pairtypes"] == 1


# --- the real oracle ----------------------------------------------------------
# Structural assertions above all passed while the force field was still
# unusable: HW survived in [pairtypes] and grompp refused it. Only running
# grompp proves the merge produced something GROMACS accepts.

_TUT = Path(__file__).resolve().parent.parent / "tutorial_data" / "KALP15_in_DPPC"
_GMXLIB = Path(
    os.environ.get("GMXLIB")
    or "/opt/miniconda3/envs/gromacs_web/share/gromacs/top"
)

pytestmark_inputs = pytest.mark.skipif(
    not (_TUT / "lipid.itp").is_file() or not (_GMXLIB / "gromos53a6.ff").is_dir(),
    reason="needs tutorial_data/KALP15_in_DPPC and gromos53a6.ff in GMXLIB",
)


@pytest.mark.integration
@pytestmark_inputs
@pytest.mark.parametrize("lipid_name", ["lipid.itp", "lipid.prepared-manual.itp"])
def test_grompp_accepts_the_built_forcefield(tmp_path, lipid_name):
    """Both the upstream lipid.itp and a hand-prepared one must yield a force
    field grompp can read. Two warnings are expected and allowed:

    1. GROMOS twin-range cut-off -- inherent to the force field, the warning
       the tutorial's own `-maxwarn 1` is for.
    2. `Bondtype LJ-14 ... defined again` for OW-OW -- lipid.itp deliberately
       overrides gromos53a6's water 1-4 pair, so copying [pairtypes] as the
       tutorial instructs always produces it. Suppressing by de-duplicating
       would silently keep different parameters than the tutorial's.
    """
    gmx = shutil.which("gmx")
    if gmx is None:
        pytest.skip("gmx not on PATH")

    lipid = _TUT / lipid_name
    if not lipid.is_file():
        pytest.skip(f"{lipid_name} not present")

    BFF.build(lipid, _GMXLIB, tmp_path)
    for name in ("dppc.itp", "topol_dppc.top", "dppc128.pdb"):
        shutil.copy(_TUT / name, tmp_path / name)
    shutil.copy(_TUT / "mdp" / "minim.mdp", tmp_path / "minim.mdp")

    proc = subprocess.run(
        [gmx, "grompp", "-f", "minim.mdp", "-c", "dppc128.pdb",
         "-p", "topol_dppc.top", "-o", "dppc.tpr", "-maxwarn", "2"],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "GMX_MAXBACKUP": "-1"},
    )
    assert "Unknown atomtype" not in proc.stderr, proc.stderr[-2000:]
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert (tmp_path / "dppc.tpr").is_file()
