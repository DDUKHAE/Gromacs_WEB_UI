"""Wrapping inflategro.pl and water_deletor.pl.

Formats verified by running the real scripts:

  area.dat  one line, three whitespace-separated floats:
            total, upper leaflet, lower leaflet
            e.g. "10.3392401     10.3392401      10.3392401"

  stdout    "<n> will be removed from the upper leaflet..."
            "<n> will be removed from the lower leaflet..."
            These appear only when a protein is present, so absence means zero.
            Confirmed against KALP-15 + DPPC-128:
            "7 will be removed from the lower leaflet..." with 0 upper.

  water_deletor.pl reports "<n> water molecules have been deleted." on stdout
  and writes a shorter .gro; this module counts atoms via lib.gro_file.count
  rather than parsing that line, so the assertion below is on the atom delta.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import gro_file, inflate_gro

TUT = Path(__file__).resolve().parent.parent / "tutorial_data" / "KALP15_in_DPPC"


def test_parse_area_dat_reads_three_columns(tmp_path):
    p = tmp_path / "area.dat"
    p.write_text("10.3392401     10.3392401      10.3392401\n")
    assert inflate_gro.parse_area_dat(p) == pytest.approx(
        (10.3392401, 10.3392401, 10.3392401)
    )


def test_parse_area_dat_reads_differing_leaflets(tmp_path):
    p = tmp_path / "area.dat"
    p.write_text("0.640   0.631   0.649\n")
    total, upper, lower = inflate_gro.parse_area_dat(p)
    assert (total, upper, lower) == pytest.approx((0.640, 0.631, 0.649))


def test_parse_area_dat_rejects_a_short_line(tmp_path):
    p = tmp_path / "area.dat"
    p.write_text("0.640\n")
    with pytest.raises(inflate_gro.InflateGroError, match="3 values"):
        inflate_gro.parse_area_dat(p)


def test_parse_removed_reads_both_leaflets():
    out = (
        "Checking for overlap...\n"
        "6 will be removed from the upper leaflet...\n"
        "5 will be removed from the lower leaflet...\n"
        "\nCalculating Area per lipid...\n"
    )
    assert inflate_gro.parse_removed(out) == (6, 5)


def test_parse_removed_is_zero_when_nothing_was_removed():
    """With no protein there is no overlap, so the lines never appear."""
    assert inflate_gro.parse_removed("Calculating Area per lipid...\nDone!\n") == (0, 0)


@pytest.mark.integration
@pytest.mark.skipif(not (TUT / "inflategro.pl").is_file(),
                    reason="needs tutorial_data/KALP15_in_DPPC")
def test_inflate_runs_the_real_script(tmp_path):
    """Proves the parsers match live output rather than a transcribed sample.

    Runs on the bilayer alone, which needs no gmx: inflategro reads and writes
    .gro directly. The residue name in the PDB-derived file is DPP, not DPPC --
    the rename to DPPC happens only once the file has passed through a .tpr.
    """
    if shutil.which("gmx") is None:
        pytest.skip("gmx needed to convert the pdb to gro")
    shutil.copy(TUT / "dppc128.pdb", tmp_path / "dppc128.pdb")
    subprocess.run(
        [shutil.which("gmx"), "editconf", "-f", "dppc128.pdb", "-o", "bilayer.gro"],
        cwd=tmp_path, input="0\n", text=True, capture_output=True, check=True,
    )
    result = inflate_gro.inflate(
        script=TUT / "inflategro.pl",
        gro=tmp_path / "bilayer.gro",
        scale=4.0, resname="DPP", cutoff_a=14,
        out=tmp_path / "inflated.gro",
        gridsize=5, area_dat=tmp_path / "area.dat", cwd=tmp_path,
    )
    assert result.output.is_file()
    assert result.area_dat.is_file()
    assert result.apl_total > 0
    # Inflating by 4 multiplies the lateral area by 16.
    assert result.apl_total > 5.0
    assert result.removed_upper == 0 and result.removed_lower == 0


@pytest.mark.integration
@pytest.mark.skipif(not (TUT / "inflategro.pl").is_file(),
                    reason="needs tutorial_data/KALP15_in_DPPC")
def test_inflate_removes_lipids_that_overlap_the_real_protein(tmp_path):
    """With the real KALP-15 peptide present, inflategro.pl actually drops lipids.

    This is the load-bearing case for the shrink loop: it proves parse_removed
    reads counts off the real overlap-deletion path, not just the "nothing
    removed" path exercised above.
    """
    if shutil.which("gmx") is None:
        pytest.skip("gmx needed to convert the pdb to gro")
    gmx = shutil.which("gmx")
    shutil.copy(TUT / "dppc128.pdb", tmp_path / "dppc128.pdb")
    shutil.copy(TUT / "KALP-15_princ.pdb", tmp_path / "KALP-15_princ.pdb")
    subprocess.run(
        [gmx, "editconf", "-f", "dppc128.pdb", "-o", "bilayer.gro"],
        cwd=tmp_path, input="0\n", text=True, capture_output=True, check=True,
    )
    subprocess.run(
        [gmx, "editconf", "-f", "KALP-15_princ.pdb", "-o", "protein.gro"],
        cwd=tmp_path, input="0\n", text=True, capture_output=True, check=True,
    )
    combo = gro_file.concat(
        gro_file.read(tmp_path / "protein.gro"),
        gro_file.read(tmp_path / "bilayer.gro"),
        "protein + bilayer",
    )
    gro_file.write(tmp_path / "combo.gro", combo)

    result = inflate_gro.inflate(
        script=TUT / "inflategro.pl", gro=tmp_path / "combo.gro",
        scale=1.0, resname="DPP", cutoff_a=14,
        out=tmp_path / "inflated.gro", gridsize=5,
        area_dat=tmp_path / "area.dat", cwd=tmp_path,
    )
    assert result.removed > 0
    assert result.removed_upper + result.removed_lower == result.removed


@pytest.mark.integration
@pytest.mark.skipif(not (TUT / "water_deletor.pl").is_file(),
                    reason="needs tutorial_data/KALP15_in_DPPC")
def test_delete_trapped_water_runs_the_real_script(tmp_path):
    """The tracked dppc128.pdb already carries water inside the bilayer core."""
    if shutil.which("gmx") is None:
        pytest.skip("gmx needed to convert the pdb to gro")
    shutil.copy(TUT / "dppc128.pdb", tmp_path / "dppc128.pdb")
    subprocess.run(
        [shutil.which("gmx"), "editconf", "-f", "dppc128.pdb", "-o", "bilayer.gro"],
        cwd=tmp_path, input="0\n", text=True, capture_output=True, check=True,
    )
    removed = inflate_gro.delete_trapped_water(
        script=TUT / "water_deletor.pl",
        gro=tmp_path / "bilayer.gro",
        out=tmp_path / "bilayer_fix.gro",
        cwd=tmp_path,
    )
    # Observed on the real tracked input: 73 waters (219 atoms) removed.
    assert removed > 0
    assert removed % 3 == 0
    assert gro_file.count(tmp_path / "bilayer_fix.gro") == (
        gro_file.count(tmp_path / "bilayer.gro") - removed
    )


@pytest.mark.integration
@pytest.mark.skipif(not (TUT / "inflategro.pl").is_file(),
                    reason="needs tutorial_data/KALP15_in_DPPC")
def test_inflate_reports_a_missing_output_as_an_error(tmp_path):
    """A perl script that fails must not look like success."""
    (tmp_path / "empty.gro").write_text("t\n    0\n   1.0   1.0   1.0\n")
    with pytest.raises(inflate_gro.InflateGroError):
        inflate_gro.inflate(
            script=TUT / "inflategro.pl", gro=tmp_path / "empty.gro",
            scale=4.0, resname="DPP", cutoff_a=14,
            out=tmp_path / "nope.gro", gridsize=5,
            area_dat=tmp_path / "a.dat", cwd=tmp_path,
        )


@pytest.mark.integration
@pytest.mark.skipif(not (TUT / "inflategro.pl").is_file(),
                    reason="needs tutorial_data/KALP15_in_DPPC")
def test_inflate_does_not_treat_a_stale_output_as_success(tmp_path):
    """The script errors out on 0 lipids before ever opening its OUTPUT file.

    If a previous run's output happens to sit at `out` already, the
    is_file() check alone would not catch this failure -- only checking the
    process exit code does. This proves the returncode guard is load-bearing,
    not just the file-existence guard.
    """
    (tmp_path / "empty.gro").write_text("t\n    0\n   1.0   1.0   1.0\n")
    stale_out = tmp_path / "nope.gro"
    stale_out.write_text("stale leftover from a previous run\n")
    stale_area = tmp_path / "a.dat"
    stale_area.write_text("9.0 9.0 9.0\n")
    with pytest.raises(inflate_gro.InflateGroError):
        inflate_gro.inflate(
            script=TUT / "inflategro.pl", gro=tmp_path / "empty.gro",
            scale=4.0, resname="DPP", cutoff_a=14,
            out=stale_out, gridsize=5,
            area_dat=stale_area, cwd=tmp_path,
        )


def test_missing_script_is_reported(tmp_path):
    with pytest.raises(inflate_gro.InflateGroError, match="not found"):
        inflate_gro.inflate(
            script=tmp_path / "absent.pl", gro=tmp_path / "x.gro",
            scale=4.0, resname="DPPC", cutoff_a=14, out=tmp_path / "o.gro",
            gridsize=5, area_dat=tmp_path / "a.dat", cwd=tmp_path,
        )
