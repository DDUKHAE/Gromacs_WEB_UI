"""The membrane assembly's ordered steps.

Unit tests stub GW.run so the ordering, arguments and topology bookkeeping can
be checked without GROMACS. The integration tests at the bottom let real gmx be
the oracle for the files this module writes. The end-to-end run lives in Task 10.
"""
import re
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


def test_both_minimisations_use_the_tutorials_packing_electrostatics(workspace):
    """minim_inflategro.mdp uses a plain 1.2 nm cut-off, not PME: the unsolvated
    system carries KALP-15's +4 e, and Ewald with a net charge is a warning that
    must stay fatal after genion rather than be waved through with -maxwarn 3."""
    gro = workspace / "stage1_env" / "system_inflated.gro"
    gro.write_text(WHOLE_GRO)
    with mock.patch.object(MA.GW, "run", side_effect=_fake_run([])):
        MA.prepare_bilayer(workspace)
        first = (workspace / "stage1_env" / "em.mdp").read_text()
        MA.minimise(workspace, gro, "system_inflated_em")
        second = (workspace / "stage1_env" / "em.mdp").read_text()

    for text in (first, second):
        assert "coulombtype              = cutoff" in text
        assert "rcoulomb                 = 1.2" in text
        assert "rvdw                     = 1.2" in text
    assert "define                   = -DSTRONG_POSRES" in second


def test_a_caller_supplied_env_keeps_the_backup_setting(workspace):
    """Task 6 runs the same commands 40 times in one directory; losing
    GMX_MAXBACKUP there buries stage1_env under #file.N# backups."""
    seen = {}

    def fake(args, cwd, **kw):
        seen.update(kw.get("env") or {})
        return FakeResult()

    with mock.patch.object(MA.GW, "run", side_effect=fake):
        MA._run(workspace, ["editconf"], env={"OMP_NUM_THREADS": "1"})
    assert seen == {"GMX_MAXBACKUP": "-1", "OMP_NUM_THREADS": "1"}


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


# --------------------------------------------------------------------------
# integration: real gmx as the oracle for the files written above
# --------------------------------------------------------------------------

pytestmark_needs_data = pytest.mark.skipif(
    not (TUT / "dppc128.pdb").is_file(), reason="needs tutorial_data/KALP15_in_DPPC")


def _real_workspace(ws):
    """A workspace with the force field built and the bilayer made whole.

    Each fixture gets its own: the two chains below both write processed.gro,
    from editconf and from pdb2gmx respectively, so sharing one directory would
    make them order-dependent. Rebuilding costs ~0.1 s.
    """
    if shutil.which("gmx") is None:
        pytest.skip("needs gmx on PATH")
    for sub in ("inputs", "stage1_env"):
        (ws / sub).mkdir(parents=True)
    state.write(ws, state.initial(ws))
    for name in ("dppc128.pdb", "KALP-15_princ.pdb", "inflategro.pl"):
        shutil.copy2(TUT / name, ws / "inputs" / name)
    shutil.copy2(TUT / "dppc.itp", ws / "stage1_env" / "dppc.itp")
    # GW.get_gmxlib() derives GMXLIB from the gmx path without resolving
    # symlinks, so a `ln -s .../gmx /tmp/gmxonly/gmx` on PATH yields nothing.
    resolved = Path(shutil.which("gmx")).resolve().parent.parent / "share" / "gromacs" / "top"
    gmxlib = next((Path(c) for c in (GW.get_gmxlib(), resolved)
                   if c and (Path(c) / "gromos53a6.ff").is_dir()), None)
    if gmxlib is None:
        pytest.skip("needs gromos53a6.ff in GMXLIB")
    BFF.build(TUT / "lipid.itp", gmxlib, ws / "stage1_env")
    return ws, MA.prepare_bilayer(ws)


@pytest.fixture(scope="module")
def real_bilayer(tmp_path_factory):
    return _real_workspace(tmp_path_factory.mktemp("kalp_bilayer"))


@pytest.fixture(scope="module")
def real_protein_system(tmp_path_factory):
    """The whole assembly on the real inputs, up to the inflated system.

    Everything before `place_peptide` is env_builder's job, done here as
    scaffolding: pdb2gmx needs `-ter` with terminus "None" (menu index 2, not 0
    -- 0 is NH3+, which needs an N the ACE cap does not have) and `-ignh`
    (the PDB's ACE carries HA1/HA2/HA3, absent from the united-atom rtp entry).

    The topology gets a DPPC row but no SOL row: inflategro writes only the
    protein and the named lipid, so the bilayer's 3655 waters are gone from
    system_inflated.gro. The tutorial adds SOL at solvation, which is Task 7.
    """
    ws, whole = _real_workspace(tmp_path_factory.mktemp("kalp_protein"))
    stage = ws / "stage1_env"
    assert GW.run(["pdb2gmx", "-f", str(ws / "inputs" / "KALP-15_princ.pdb"),
                   "-o", "processed.gro", "-p", "topol.top",
                   "-ff", BFF.FF_TARGET, "-water", "spc", "-ter", "-ignh"],
                  cwd=stage, interactive_inputs=["2", "2"],
                  env=dict(MA.GMX_ENV)).ok
    BFF.add_include(stage / "topol.top", "dppc.itp")
    topol = stage / "topol.top"
    topol.write_text(topol.read_text().rstrip("\n") + "\nDPPC 128\n")

    peptide = MA.place_peptide(ws, whole)
    MA.install_strong_restraints(ws, peptide)
    system = MA.merge_system(ws, peptide, whole)
    return ws, MA.inflate_once(ws, system)


@pytest.mark.integration
@pytestmark_needs_data
def test_grompp_accepts_the_generated_dppc_topology(real_bilayer):
    """grompp checks [molecules] against the coordinates, so it validates the
    counts write_dppc_topology derived from the PDB: a wrong DPPC or SOL number
    aborts with "number of coordinates does not match topology"."""
    ws, whole = real_bilayer
    assert "DPPC 128" in (ws / "stage1_env" / "topol_dppc.top").read_text()
    assert "SOL 3655" in (ws / "stage1_env" / "topol_dppc.top").read_text()
    assert (ws / "stage1_env" / "dppc.tpr").is_file()
    # Passing through the .tpr renames DPP to DPPC, which inflategro relies on.
    assert MA.residue_counts(whole) == {"DPPC": 128, "SOL": 3655}
    assert gro_file.count(whole) == 17365


@pytest.mark.integration
@pytestmark_needs_data
def test_gmx_reads_the_merged_system(real_bilayer):
    """editconf on system.gro is the oracle for the merge arithmetic: a wrong
    atom count on line 2 makes gmx truncate or abort rather than agree."""
    ws, whole = real_bilayer
    stage = ws / "stage1_env"
    # pdb2gmx on KALP-15_princ.pdb currently fails on its ACE terminus, so the
    # peptide coordinates come straight from editconf. merge_system only needs
    # coordinates.
    assert GW.run(["editconf", "-f", str(ws / "inputs" / "KALP-15_princ.pdb"),
                   "-o", "processed.gro"], cwd=stage, env=dict(MA.GMX_ENV)).ok
    peptide = MA.place_peptide(ws, whole)
    assert gro_file.box_vectors(gro_file.read(peptide)) == \
        gro_file.box_vectors(gro_file.read(whole))
    system = MA.merge_system(ws, peptide, whole)
    assert gro_file.count(system) == gro_file.count(peptide) + gro_file.count(whole)

    check = GW.run(["editconf", "-f", "system.gro", "-o", "check.gro"],
                   cwd=stage, env=dict(MA.GMX_ENV))
    assert check.ok, check.stderr[-800:]
    assert gro_file.count(stage / "check.gro") == gro_file.count(system)


@pytest.mark.integration
@pytestmark_needs_data
def test_inflate_once_corrects_molecules_for_a_real_deletion(real_protein_system):
    """The [ molecules ] arithmetic fed by a real inflategro.pl run.

    grompp is the oracle: it compares [ molecules ] against the coordinates, so
    a wrong correction aborts with "number of coordinates ... does not match
    topology". 128 lipids x 50 atoms - 2 deleted + 138 protein atoms = 6438.
    """
    ws, result = real_protein_system
    stage = ws / "stage1_env"
    assert result.removed == 2, "the real overlap deletion on this system"
    assert re.search(r"^DPPC 126$", (stage / "topol.top").read_text(), re.M)
    assert gro_file.count(result.output) == 6438
    # Inflating by 4 multiplies the lateral area by 16, so this is far from
    # TARGET_APL -- that is what Task 6's shrink loop is for.
    assert result.apl_total > 10 * MA.TARGET_APL

    grompp = GW.run(["grompp", "-f", "em.mdp", "-c", result.output.name,
                     "-r", result.output.name, "-p", "topol.top",
                     "-o", "count_check.tpr", "-maxwarn", "3"],
                    cwd=stage, env=dict(MA.GMX_ENV))
    assert grompp.ok, grompp.stderr[-800:]

    # Seen to fail: uncorrected, the same grompp reports the mismatch.
    MA.BFF.set_molecule_count(stage / "topol.top", "DPPC", 128)
    try:
        stale = GW.run(["grompp", "-f", "em.mdp", "-c", result.output.name,
                        "-r", result.output.name, "-p", "topol.top",
                        "-o", "count_check.tpr", "-maxwarn", "3"],
                       cwd=stage, env=dict(MA.GMX_ENV))
        assert stale.classification == "topology_mismatch", stale.stderr[-800:]
    finally:
        MA.BFF.set_molecule_count(stage / "topol.top", "DPPC", 126)


@pytest.mark.integration
@pytestmark_needs_data
def test_minimise_runs_against_a_real_protein_topology(real_protein_system):
    """grompp + mdrun + trjconv on the inflated system, protein topology and all.

    Runs with the shipped GROMPP_MAXWARN. PACKING_MDP's plain cut-off is what
    keeps two warnings sufficient here: with PME, grompp adds "You are using
    Ewald electrostatics in a system with net charge" -- KALP-15's +4 e, with
    counter-ions not added until Task 7's genion -- and that is a warning which
    must stay fatal once the system is neutralised, so it is designed out rather
    than waved through with a higher cap.
    """
    ws, result = real_protein_system
    stage = ws / "stage1_env"

    out = MA.minimise(ws, result.output, "system_inflated_em")

    mdp = (stage / "em.mdp").read_text()
    assert "coulombtype              = cutoff" in mdp
    assert (stage / "system_inflated_em.tpr").is_file()
    assert out.name == "system_inflated_em.gro"
    assert gro_file.count(out) == gro_file.count(result.output)
    log = (stage / "system_inflated_em.log").read_text()
    assert "Steepest Descents converged" in log
    assert not (stage / "tmp.gro").exists(), "trjconv output moved onto the result"

    # The restraints reached mdrun: the energy term only appears when a
    # [ position_restraints ] block was actually compiled into the .tpr.
    assert "Position Rest." in log
    # And they held: at fc=100000 the peptide is pinned while the inflated
    # lipids relax by far more.
    before, after = gro_file.read(result.output).atoms, gro_file.read(out).atoms
    peptide = [(b, a) for b, a in zip(before, after) if "DPPC" not in b]
    assert len(peptide) == 138
    assert max(abs(float(b[20:28]) - float(a[20:28])) for b, a in peptide) < 0.05
    lipid = [(b, a) for b, a in zip(before, after) if "DPPC" in b]
    assert max(abs(float(b[20:28]) - float(a[20:28])) for b, a in lipid) > 0.1


@pytest.mark.integration
@pytestmark_needs_data
def test_shrink_to_target_converges_on_the_real_system(real_protein_system):
    """The real loop is the only oracle for the iteration count, the descent
    toward target, and the final atom count. Measured at ~6.5s for 27
    iterations (81 gmx invocations) on this system -- cheap enough to run
    every time, not a reason to fake this with stubs.

    26 iterations (the reference script's hardcoded count) lands at 0.698
    nm^2, still above TARGET_APL=0.64; 27 is the first at-or-below, which is
    why this loop is one iteration stricter than the reference script.
    """
    ws, result = real_protein_system
    stage = ws / "stage1_env"
    inflated_em = MA.minimise(ws, result.output, "system_inflated_em")

    shrink = MA.shrink_to_target(ws, inflated_em)

    assert shrink.iterations == 27
    assert shrink.apl_total <= MA.TARGET_APL
    assert len(shrink.apl_history) == 27
    # Iteration 26 is the reference script's stopping point, and it is not
    # yet at target -- confirms the loop isn't stopping early by accident.
    assert shrink.apl_history[-2] > MA.TARGET_APL
    # Descends overall from the post-inflation APL to the converged one.
    assert shrink.apl_history[0] > shrink.apl_history[-1]
    assert shrink.final_gro.name == "system_shrink27_em.gro"
    assert gro_file.count(shrink.final_gro) == 6438


# --- the shrink loop ----------------------------------------------------------
# The reference script hardcodes 26 iterations and asks the operator to inspect
# area_shrink*.dat afterwards. Terminating on the measured APL makes that check
# the loop's own condition; 26 becomes an expected value, not the control.


def _apl_sequence(workspace, values):
    """Stub inflate/minimise so the loop sees a given APL trajectory."""
    stage = workspace / "stage1_env"
    calls = {"inflate": [], "minimise": []}

    def fake_inflate(script, gro, scale, resname, cutoff_a, out, gridsize,
                     area_dat, cwd):
        calls["inflate"].append((Path(gro).name, scale, cutoff_a, Path(out).name))
        Path(out).write_text("s\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                             "   6.0   6.0   6.0\n")
        Path(area_dat).write_text("0.0 0.0 0.0\n")
        apl = values[len(calls["inflate"]) - 1]
        return MA.inflate_gro.InflateResult(
            apl_total=apl, apl_upper=apl, apl_lower=apl,
            removed_upper=0, removed_lower=0,
            output=Path(out), area_dat=Path(area_dat),
        )

    def fake_minimise(ws, gro, tag):
        calls["minimise"].append(tag)
        out = stage / f"{tag}.gro"
        out.write_text("e\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                       "   6.0   6.0   6.0\n")
        return out

    return calls, fake_inflate, fake_minimise


def test_shrink_stops_when_the_target_apl_is_reached(workspace):
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [1.20, 0.90, 0.70, 0.63])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        result = MA.shrink_to_target(workspace, start)

    assert result.iterations == 4
    assert result.apl_total == pytest.approx(0.63)
    assert result.apl_history == pytest.approx([1.20, 0.90, 0.70, 0.63])


def test_shrink_scales_by_0_95_with_no_cutoff(workspace):
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [0.60])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        MA.shrink_to_target(workspace, start)
    _, scale, cutoff, _ = calls["inflate"][0]
    assert scale == 0.95
    assert cutoff == 0


def test_shrink_file_names_match_the_reference_script(workspace):
    """First iteration reads system_inflated_em.gro; later ones read the
    previous iteration's minimised output."""
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [1.0, 0.9, 0.60])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        MA.shrink_to_target(workspace, start)

    sources = [src for src, _, _, _ in calls["inflate"]]
    outputs = [out for _, _, _, out in calls["inflate"]]
    assert sources == ["system_inflated_em.gro",
                       "system_shrink1_em.gro",
                       "system_shrink2_em.gro"]
    assert outputs == ["system_shrink1.gro", "system_shrink2.gro",
                       "system_shrink3.gro"]
    assert calls["minimise"] == ["system_shrink1_em", "system_shrink2_em",
                                 "system_shrink3_em"]


def test_shrink_raises_when_the_cap_is_reached(workspace):
    """Fatal, not retryable: a system that never converged must not proceed."""
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [5.0] * 10)
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        with pytest.raises(MA.MembraneAssemblyError, match="did not reach"):
            MA.shrink_to_target(workspace, start, max_iterations=5)
    assert len(calls["inflate"]) == 5


def test_shrink_stops_on_exact_equality_with_the_target(workspace):
    """<= not <: an APL landing exactly on target must not be treated as
    still-above-target and trigger one more (unnecessary) iteration."""
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    # The third value must be strictly below target: an <=-to-< mutant never
    # stops at iteration 2 (0.64 < 0.64 is false), so it needs somewhere to
    # terminate on its own -- 5.0 would just run the stub dry (IndexError),
    # killing the mutant by accident rather than by a wrong-iteration assert.
    calls, fi, fm = _apl_sequence(workspace, [0.80, 0.64, 0.60])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        result = MA.shrink_to_target(workspace, start, target_apl=0.64)
    assert result.iterations == 2
    assert result.apl_total == pytest.approx(0.64)


def test_shrink_records_its_parameters_for_audit(workspace):
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [0.60])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        result = MA.shrink_to_target(workspace, start, target_apl=0.64)
    assert result.target_apl == 0.64


def test_shrink_target_apl_actually_controls_the_stopping_point(workspace):
    """Behavioural, not just recorded: a target above the first APL must stop
    immediately, not fall through to the module's TARGET_APL=0.64 default."""
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    # Padded past the value a target_apl->TARGET_APL(0.64) mutant would chase
    # (0.50 <= 0.64 at iteration 3), so that mutant terminates on a wrong
    # iteration instead of running the stub dry -- an IndexError would kill
    # the mutant by accident, not by observing the wrong result.
    calls, fi, fm = _apl_sequence(workspace, [1.20, 0.90, 0.50, 0.30])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        result = MA.shrink_to_target(workspace, start, target_apl=1.0)
    assert result.iterations == 2
    assert result.apl_total == pytest.approx(0.90)


def test_shrink_raises_membrane_assembly_error_when_max_iterations_is_zero(workspace):
    """A config-supplied 0 must hit the module's own error type, not an
    untyped IndexError from an empty history."""
    start = workspace / "stage1_env" / "system_inflated_em.gro"
    start.write_text("i\n    1\n    1DPPC     C1    1   1.0   1.0   1.0\n"
                     "   6.0   6.0   6.0\n")
    calls, fi, fm = _apl_sequence(workspace, [])
    with mock.patch.object(MA.inflate_gro, "inflate", side_effect=fi), \
         mock.patch.object(MA, "minimise", side_effect=fm), \
         mock.patch.object(MA, "_script", return_value=Path("inflategro.pl")):
        with pytest.raises(MA.MembraneAssemblyError, match="did not reach"):
            MA.shrink_to_target(workspace, start, max_iterations=0)
    assert calls["inflate"] == []
