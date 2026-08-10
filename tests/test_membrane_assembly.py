"""The membrane assembly's ordered steps.

Unit tests stub GW.run so the ordering, arguments and topology bookkeeping can
be checked without GROMACS. The integration tests at the bottom let real gmx be
the oracle for the files this module writes. The end-to-end run lives in Task 10.
"""
import shutil
from pathlib import Path
from unittest import mock

import pytest

from lib import berger_forcefield as BFF
from lib import gmx_wrapper as GW
from lib import gro_file
from lib import state
from skills.env_builder import membrane_assembly as MA

TUT = Path(__file__).resolve().parent.parent / "tutorial_data" / "KALP15_in_DPPC"

#: A bilayer PDB must actually hold lipids. Two DPP residues plus one water is
#: the smallest file that is a bilayer as far as this module is concerned; the
#: residue name is DPP because PDB allows only three characters.
STUB_BILAYER_PDB = (
    "HEADER    stub\n"
    "CRYST1   64.184   64.435   65.965  90.00  90.00  90.00 P 1           1\n"
    "ATOM      1  C1  DPP A   1      15.771  52.651   9.201  1.00  0.00\n"
    "ATOM      2  C2  DPP A   1      16.771  52.651   9.201  1.00  0.00\n"
    "ATOM      3  C1  DPP A   2      15.771  53.651   9.201  1.00  0.00\n"
    "ATOM      4  OW  SOL     3      28.423  59.953   2.090  1.00  0.00\n"
    "END\n"
)

WHOLE_GRO = (
    "w\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
    "   6.41840   6.44350   6.59650\n"
)


class FakeResult:
    ok = True
    returncode = 0
    stdout = ""
    stderr = ""
    classification = "ok"


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "kalp_20260807_120000"
    for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
        (ws / sub).mkdir(parents=True)
    state.write(ws, state.initial(ws))
    (ws / "inputs" / "dppc128.pdb").write_text(STUB_BILAYER_PDB)
    return ws


def _fake_run(calls):
    """A GW.run stub that records calls and produces trjconv/mdrun output."""
    def fake(args, cwd, **kw):
        calls.append((list(args), kw))
        if args[0] in ("trjconv", "editconf"):
            (Path(cwd) / args[args.index("-o") + 1]).write_text(WHOLE_GRO)
        if args[0] == "mdrun":
            (Path(cwd) / f"{args[args.index('-deffnm') + 1]}.gro").write_text(WHOLE_GRO)
        return FakeResult()
    return fake


# --------------------------------------------------------------------------
# residue counting and the throwaway DPPC topology
# --------------------------------------------------------------------------

def test_write_dppc_topology_counts_residues_from_the_bilayer(workspace, tmp_path):
    """Upstream's copy hardcodes DPPC 128 / SOL 3655; we count instead."""
    bilayer = tmp_path / "b.gro"
    atoms = (
        [f"    1DPPC     C{i}{i:5d}   1.000   1.000   1.000" for i in range(1, 3)]
        + [f"    2DPPC     C{i}{i:5d}   1.000   1.000   1.000" for i in range(3, 5)]
        + [f"    3SOL      OW{i:5d}   1.000   1.000   1.000" for i in range(5, 6)]
    )
    bilayer.write_text("b\n" + f"{len(atoms):5d}\n" + "\n".join(atoms)
                       + "\n   6.0   6.0   6.0\n")
    out = workspace / "stage1_env" / "topol_dppc.top"
    counts = MA.write_dppc_topology(workspace, bilayer, out)
    assert counts == {"DPPC": 2, "SOL": 1}
    text = out.read_text()
    assert "DPPC 2" in text.replace("  ", " ")
    assert '#include "gromos53a6_lipid.ff/forcefield.itp"' in text


def test_write_dppc_topology_counts_the_pdb_bilayer_as_dpp(workspace):
    """The distributed bilayer is a PDB whose residue name is DPP, not DPPC."""
    out = workspace / "stage1_env" / "topol_dppc.top"
    assert MA.write_dppc_topology(
        workspace, workspace / "inputs" / "dppc128.pdb", out
    ) == {"DPPC": 2, "SOL": 1}


def test_write_dppc_topology_is_fatal_without_lipids(workspace, tmp_path):
    """A coordinate file with no lipids cannot be the bilayer."""
    empty = tmp_path / "protein.gro"
    empty.write_text("p\n    1\n    1LYS      N    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    with pytest.raises(MA.MembraneAssemblyError, match="no DPPC"):
        MA.write_dppc_topology(workspace, empty, tmp_path / "out.top")


# --------------------------------------------------------------------------
# step 1: make the bilayer whole
# --------------------------------------------------------------------------

def test_prepare_bilayer_uses_maxwarn_two(workspace):
    """One warning is the GROMOS twin-range notice the tutorial's -maxwarn 1
    covers; the second is the intended OW-OW LJ-14 override that copying
    lipid.itp's [pairtypes] always produces."""
    calls = []
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        MA.prepare_bilayer(workspace)

    grompp = next(a for a, _ in calls if a[0] == "grompp")
    assert grompp[grompp.index("-maxwarn") + 1] == "2"


def test_prepare_bilayer_makes_molecules_whole_from_the_tpr(workspace):
    """trjconv must read the .tpr grompp just built, which is what renames DPP."""
    calls = []
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        MA.prepare_bilayer(workspace)

    order = [a[0] for a, _ in calls]
    assert order == ["grompp", "trjconv"]
    trjconv = calls[1][0]
    assert trjconv[trjconv.index("-s") + 1] == "dppc.tpr"
    assert trjconv[trjconv.index("-pbc") + 1] == "mol"


def test_every_trjconv_receives_its_output_group(workspace):
    """run_inflategro.sh omits this inside its loop and would block there."""
    calls = []
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        MA.prepare_bilayer(workspace)

    trjconvs = [(a, kw) for a, kw in calls if a[0] == "trjconv"]
    assert trjconvs
    for args, kw in trjconvs:
        assert kw.get("interactive_inputs") == ["0"], args


def test_assembly_disables_gmx_backups(workspace):
    calls = []
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        MA.prepare_bilayer(workspace)
    assert calls
    assert all((kw.get("env") or {}).get("GMX_MAXBACKUP") == "-1" for _, kw in calls), calls


def test_prepare_bilayer_is_fatal_when_gmx_fails(workspace):
    class Failed(FakeResult):
        ok = False
        classification = "command_error"
        stderr = "Fatal error: nope"

    with mock.patch.object(MA.GW, "run", return_value=Failed()):
        with pytest.raises(MA.MembraneAssemblyError, match="grompp"):
            MA.prepare_bilayer(workspace)


# --------------------------------------------------------------------------
# steps 2-3: place the peptide and merge
# --------------------------------------------------------------------------

def test_place_peptide_reads_the_box_from_the_bilayer(workspace, tmp_path):
    """The tutorial hardcodes -box 6.41840 6.44350 6.59650; we read it so a
    different bilayer works."""
    whole = workspace / "stage1_env" / "dppc128_whole.gro"
    whole.write_text(WHOLE_GRO)
    (workspace / "stage1_env" / "processed.gro").write_text(
        "p\n    1\n    1LYS      N    1   1.0   1.0   1.0\n   1.0   1.0   1.0\n"
    )
    calls = []
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        MA.place_peptide(workspace, whole)
    editconf = next(a for a, _ in calls if a[0] == "editconf")
    i = editconf.index("-box")
    assert editconf[i + 1:i + 4] == ["6.41840", "6.44350", "6.59650"]


def test_merge_system_atom_count_is_the_sum(workspace):
    pep = workspace / "stage1_env" / "KALP_newbox.gro"
    pep.write_text("p\n    2\n"
                   "    1LYS      N    1   1.0   1.0   1.0\n"
                   "    1LYS     CA    2   1.0   1.0   1.0\n"
                   "   6.0   6.0   6.0\n")
    bil = workspace / "stage1_env" / "dppc128_whole.gro"
    bil.write_text("b\n    3\n"
                   "    1DPPC     C1    1   1.0   1.0   1.0\n"
                   "    1DPPC     C2    2   1.0   1.0   1.0\n"
                   "    2SOL      OW    3   1.0   1.0   1.0\n"
                   "   6.41840   6.44350   6.59650\n")
    out = MA.merge_system(workspace, pep, bil)
    assert gro_file.count(out) == 5
    assert gro_file.read(out).box.split()[0] == "6.41840"
    # The peptide comes first: [ molecules ] lists Protein before DPPC.
    assert gro_file.read(out).atoms[0].endswith("N    1   1.0   1.0   1.0")


# --------------------------------------------------------------------------
# step 4: strong position restraints
# --------------------------------------------------------------------------

def test_install_strong_restraints_guards_the_include(workspace):
    topol = workspace / "stage1_env" / "topol.top"
    topol.write_text(
        "[ moleculetype ]\nProtein_chain_A 3\n\n"
        "#ifdef POSRES\n#include \"posre.itp\"\n#endif\n\n"
        "; Include water topology\n#include \"spc.itp\"\n\n"
        "[ system ]\nx\n\n[ molecules ]\nProtein_chain_A 1\n"
    )
    pep = workspace / "stage1_env" / "KALP_newbox.gro"
    pep.write_text(WHOLE_GRO)
    calls = []

    def fake(args, cwd, **kw):
        calls.append((list(args), kw))
        (Path(cwd) / args[args.index("-o") + 1]).write_text("; restraints\n")
        return FakeResult()

    with mock.patch.object(MA.GW, "run", side_effect=fake):
        MA.install_strong_restraints(workspace, pep)

    assert "#ifdef STRONG_POSRES" in topol.read_text()
    genrestr = calls[0][0]
    assert genrestr[0] == "genrestr"
    assert genrestr[genrestr.index("-f") + 1] == "KALP_newbox.gro"
    assert genrestr[genrestr.index("-fc") + 1:genrestr.index("-fc") + 4] == \
        ["100000", "100000", "100000"]


def test_install_strong_restraints_is_fatal_without_a_posres_block(workspace):
    """BFF refuses to place the guard outside a [moleculetype] scope."""
    (workspace / "stage1_env" / "topol.top").write_text("[ molecules ]\nDPPC 128\n")
    pep = workspace / "stage1_env" / "KALP_newbox.gro"
    pep.write_text(WHOLE_GRO)
    with mock.patch.object(MA.GW, "run", side_effect=AssertionError("must not run")):
        with pytest.raises(BFF.BergerForceFieldError):
            MA.install_strong_restraints(workspace, pep)


# --------------------------------------------------------------------------
# steps 5-6: inflate and correct [ molecules ]
# --------------------------------------------------------------------------

def _fake_inflate(workspace, removed_upper=6, removed_lower=5):
    result = MA.inflate_gro.InflateResult(
        apl_total=10.3, apl_upper=10.3, apl_lower=10.3,
        removed_upper=removed_upper, removed_lower=removed_lower,
        output=workspace / "stage1_env" / "system_inflated.gro",
        area_dat=workspace / "stage1_env" / "area.dat",
    )
    result.output.write_text(WHOLE_GRO)
    return result


def test_inflate_once_updates_the_molecules_count(workspace):
    """Skipping this makes the next grompp fail on an atom-count mismatch."""
    topol = workspace / "stage1_env" / "topol.top"
    topol.write_text("[ molecules ]\nProtein_chain_A 1\nDPPC 128\n")
    system = workspace / "stage1_env" / "system.gro"
    system.write_text(WHOLE_GRO)
    (workspace / "inputs" / "inflategro.pl").write_text("#!/usr/bin/perl\n")

    with mock.patch.object(MA.inflate_gro, "inflate",
                           return_value=_fake_inflate(workspace)) as inflate:
        result = MA.inflate_once(workspace, system)

    assert result.removed == 11
    assert "DPPC 117" in topol.read_text()
    # Inflation is by 4 with the 14 A P-CA cutoff that drops overlapping lipids.
    assert inflate.call_args.kwargs["scale"] == 4.0
    assert inflate.call_args.kwargs["cutoff_a"] == 14
    assert inflate.call_args.kwargs["resname"] == "DPPC"


def test_inflate_once_leaves_the_count_alone_when_nothing_was_removed(workspace):
    topol = workspace / "stage1_env" / "topol.top"
    topol.write_text("[ molecules ]\nProtein_chain_A 1\nDPPC 128\n")
    system = workspace / "stage1_env" / "system.gro"
    system.write_text(WHOLE_GRO)
    (workspace / "inputs" / "inflategro.pl").write_text("#!/usr/bin/perl\n")

    with mock.patch.object(MA.inflate_gro, "inflate",
                           return_value=_fake_inflate(workspace, 0, 0)):
        MA.inflate_once(workspace, system)
    assert "DPPC 128" in topol.read_text()


def test_inflate_once_is_fatal_when_the_count_cannot_be_updated(workspace):
    topol = workspace / "stage1_env" / "topol.top"
    topol.write_text("[ molecules ]\nProtein_chain_A 1\n")   # no DPPC row
    system = workspace / "stage1_env" / "system.gro"
    system.write_text(WHOLE_GRO)
    (workspace / "inputs" / "inflategro.pl").write_text("#!/usr/bin/perl\n")

    with mock.patch.object(MA.inflate_gro, "inflate",
                           return_value=_fake_inflate(workspace)):
        with pytest.raises(MA.MembraneAssemblyError, match="no DPPC row"):
            MA.inflate_once(workspace, system)


def test_inflate_once_is_fatal_when_molecules_stays_unmodified(workspace):
    """The count is read back, not assumed: an unmodified [molecules] is fatal."""
    topol = workspace / "stage1_env" / "topol.top"
    topol.write_text("[ molecules ]\nProtein_chain_A 1\nDPPC 128\n")
    system = workspace / "stage1_env" / "system.gro"
    system.write_text(WHOLE_GRO)
    (workspace / "inputs" / "inflategro.pl").write_text("#!/usr/bin/perl\n")

    with mock.patch.object(MA.inflate_gro, "inflate",
                           return_value=_fake_inflate(workspace)), \
         mock.patch.object(MA.BFF, "set_molecule_count", return_value=128):
        with pytest.raises(MA.MembraneAssemblyError, match="expected 117"):
            MA.inflate_once(workspace, system)


def test_inflate_once_is_fatal_without_the_perl_script(workspace):
    system = workspace / "stage1_env" / "system.gro"
    system.write_text(WHOLE_GRO)
    with pytest.raises(MA.MembraneAssemblyError, match="inflategro.pl"):
        MA.inflate_once(workspace, system)


# --------------------------------------------------------------------------
# step 7: the first minimisation
# --------------------------------------------------------------------------

def _minimise(workspace, gro, tag="system_inflated_em"):
    rendered = {}
    calls = []

    def fake_render(phase, overrides, output_dir):
        rendered.update(overrides)
        out = Path(output_dir) / f"{phase}.mdp"
        out.write_text("; stub\n")
        return out

    with mock.patch.object(MA.MDP, "render", side_effect=fake_render), \
         mock.patch.object(MA.GW, "run", side_effect=_fake_run(calls)):
        out = MA.minimise(workspace, gro, tag)
    return rendered, calls, out


def test_minimise_renders_strong_posres(workspace):
    gro = workspace / "stage1_env" / "system_inflated.gro"
    gro.write_text(WHOLE_GRO)
    rendered, _, _ = _minimise(workspace, gro)
    assert rendered.get("define") == "-DSTRONG_POSRES"


def test_minimise_passes_its_own_restraint_reference(workspace):
    """md_runner's automatic -r only triggers on -DPOSRES, so we must pass it.

    Without it grompp aborts with "Cannot find position restraint file".
    """
    gro = workspace / "stage1_env" / "system_inflated.gro"
    gro.write_text(WHOLE_GRO)
    _, calls, _ = _minimise(workspace, gro)
    grompp = next(a for a, _ in calls if a[0] == "grompp")
    assert grompp[grompp.index("-r") + 1] == "system_inflated.gro"
    assert grompp[grompp.index("-c") + 1] == "system_inflated.gro"
    assert grompp[grompp.index("-maxwarn") + 1] == "2"
    assert grompp[grompp.index("-o") + 1] == "system_inflated_em.tpr"


def test_minimise_unwraps_the_minimised_coordinates_in_place(workspace):
    """The reference script's `mv tmp.gro system_inflated_em.gro`."""
    gro = workspace / "stage1_env" / "system_inflated.gro"
    gro.write_text(WHOLE_GRO)
    _, calls, out = _minimise(workspace, gro)
    assert [a[0] for a, _ in calls] == ["grompp", "mdrun", "trjconv"]
    assert out.name == "system_inflated_em.gro"
    assert not (workspace / "stage1_env" / "tmp.gro").exists()
    trjconv = calls[2][0]
    assert trjconv[trjconv.index("-f") + 1] == "system_inflated_em.gro"
    assert trjconv[trjconv.index("-o") + 1] == "tmp.gro"
