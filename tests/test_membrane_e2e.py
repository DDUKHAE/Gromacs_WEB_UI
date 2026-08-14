"""The whole membrane pipeline, run for real, checked against the tutorial's numbers.

Marked `integration`: needs gmx and takes about a minute. It starts from a bare
workspace, an unprocessed PDB and a System Builder submission, and calls
`env_builder.build_environment` -- the same entry point `web/runner.py` calls.
Nothing between the submission and the finished, ionised, indexed system is
written by hand: the tutorial choice, the parameter resolution, pdb2gmx's
terminus answers, the lipid topology and the whole InflateGRO assembly are all
production code. That is the point of the file. Three defects (pdb2gmx's
missing `-ter`, the path-prefixed force-field include, the missing DPPC row in
`[ molecules ]`) survived every other test in this repo because their fixtures
did those steps by hand.

Run with:
  PATH="/tmp/gmxonly:$PATH" python3 -m pytest tests/test_membrane_e2e.py -m integration -v
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from lib import gmx_wrapper as GW
from lib import gro_file, state
from lib.mdp_templates import base as MDP
from skills.env_builder import env_builder as EB
from skills.env_builder import membrane_assembly as MA
from skills.md_runner import md_runner as MD

TUT = Path(__file__).resolve().parent.parent / "tutorial_data" / "KALP15_in_DPPC"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("gmx") is None, reason="gmx not on PATH"),
    pytest.mark.skipif(not (TUT / "dppc128.pdb").is_file(),
                       reason="needs tutorial_data/KALP15_in_DPPC"),
]

#: A membrane submission as the System Builder would write it. `membrane` is
#: what routes the run to KALP15_in_DPPC and satisfies its membrane_composition
#: requirement; everything else (force field, water model, box) comes from the
#: tutorial manifest through RPARAM.resolve, and is asserted below rather than
#: repeated here.
SUBMISSION = {"build_type": "membrane",
              "membrane": {"lipid_type": "DPPC"},
              "simulation": {"ion_concentration_M": 0.15}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One full run of the production environment build. Everything asserts on it."""
    ws = tmp_path_factory.mktemp("kalp") / "kalp15_e2e"
    EB.init_workspace(ws)
    for name in ("dppc128.pdb", "dppc.itp", "lipid.itp",
                 "inflategro.pl", "water_deletor.pl"):
        shutil.copy2(TUT / name, ws / "inputs" / name)
    (ws / "system_config.json").write_text(json.dumps(SUBMISSION))

    # GW.get_gmxlib() cannot derive GMXLIB from a bare `gmx` symlink, which is
    # the documented way to put gmx on PATH here, so supply the environment the
    # production code would have found on a normal install. Environment, not a
    # stand-in for a pipeline step.
    resolved = Path(shutil.which("gmx")).resolve().parent.parent / "share" / "gromacs" / "top"
    if not (resolved / "gromos53a6.ff").is_dir():
        pytest.skip("needs gromos53a6.ff in GMXLIB")
    mp = pytest.MonkeyPatch()
    mp.setenv("GMXLIB", str(resolved))
    try:
        EB.build_environment(pdb_path=TUT / "KALP-15_princ.pdb", prompt="",
                             workspace_dir=ws, interactive=False)
    finally:
        mp.undo()
    return ws, state.read(ws)["step_outputs"]["step_2"]["membrane_assembly"]


def test_the_submission_routed_itself_to_the_membrane_tutorial(built):
    """state["tutorial"] is what md_runner reads to pick the phase sequence and
    the membrane mdp overrides, and only build_environment writes it."""
    ws, _ = built
    s = state.read(ws)
    assert s["tutorial"]["id"] == "KALP15_in_DPPC"
    assert s["tutorial"]["variant"] == "membrane_md_standard"
    assert s["tutorial"]["has_protein"] is True
    # Resolved from the manifest, not from a dict this test wrote.
    resolved = s["step_outputs"]["step_0"]["resolved_parameters"]["values"]
    assert resolved["forcefield"] == "gromos53a6"
    assert resolved["water_model"] == "spc"
    assert s["step_outputs"]["step_1"]["forcefield"] == "gromos53a6_lipid"


def test_step1_topology_survives_the_capped_termini(built):
    """The production pdb2gmx call, not a hand-written one.

    Without `-ter` and "None" for both termini, pdb2gmx builds an NH3+ start
    terminus and dies with "atom N not found in buiding block 1ACE" (its own
    typo) -- the ACE cap has no N. 138 atoms is the united-atom KALP-15.
    """
    ws, _ = built
    processed = ws / "stage1_env" / "processed.gro"
    assert gro_file.count(processed) == 138
    topol = (ws / "stage1_env" / "topol.top").read_text()
    assert '#include "gromos53a6_lipid.ff/forcefield.itp"' in topol
    assert '#include "dppc.itp"' in topol


def test_bilayer_box_matches_the_tutorial(built):
    """The tutorial hardcodes -box 6.41840 6.44350 6.59650; here it is read off
    the pre-equilibrated bilayer instead, and has to agree."""
    ws, _ = built
    box = gro_file.box_vectors(
        gro_file.read(ws / "stage1_env" / "dppc128_whole.gro"))
    assert box == pytest.approx((6.41840, 6.44350, 6.59650), abs=1e-4)
    assert box == gro_file.box_vectors(
        gro_file.read(ws / "stage1_env" / "KALP_newbox.gro"))


def test_the_overlapping_lipids_were_deleted(built):
    """Two lipids overlap KALP-15 at the P-CA cutoff of 14 A on this system.

    Both leaflet counts are asserted, not just the total: inflategro.pl prints
    a per-leaflet count and does not total them, so a wrong leaflet attribution
    would still add up to 2.
    """
    _, summary = built
    assert summary["lipids_removed"] == 2
    assert (summary["lipids_removed_upper"], summary["lipids_removed_lower"]) == (1, 1)


def test_shrink_converged_one_iteration_past_the_reference_script(built):
    """run_inflategro.sh hardcodes 26, which lands at 0.6976 nm^2 -- still above
    TARGET_APL. 27 is the first iteration at or below it."""
    _, summary = built
    assert summary["shrink_iterations"] == 27
    assert summary["apl_target"] == MA.TARGET_APL
    assert summary["apl_final"] <= summary["apl_target"]
    assert summary["apl_history"][-2] > summary["apl_target"]
    history = summary["apl_history"]
    assert history == sorted(history, reverse=True), history


def test_the_finished_system_reconciles_atom_for_atom(built):
    """grompp rejects any [molecules]/coordinate mismatch, so these counts are
    not bookkeeping: 138 protein + 126x50 lipid + 3653x3 water + 4 Cl = 17401."""
    ws, _ = built
    ions = ws / "stage1_env" / "ions.gro"
    counts = MA.residue_counts(ions)
    assert counts["DPPC"] == 126 and counts["SOL"] == 3653 and counts["CL"] == 4
    assert "NA" not in counts
    assert gro_file.count(ions) == 138 + 126 * 50 + 3653 * 3 + 4 == 17401
    topol = (ws / "stage1_env" / "topol.top").read_text()
    assert re.search(r"^DPPC 126$", topol, re.M)
    assert re.search(r"^SOL\s+3653$", topol, re.M)


def test_the_index_groups_the_mdp_files_couple_to(built):
    _, summary = built
    groups = summary["index_groups"]
    assert groups["Protein_DPPC"] == groups["Protein"] + groups["DPPC"] == 6438
    assert groups["Water_and_ions"] == 10963
    assert groups["Protein_DPPC"] + groups["Water_and_ions"] == 17401


def test_state_records_a_neutral_system_and_no_retries(built):
    """KALP-15 carries +4 e; genion is what has to have removed it. And a clean
    run provokes no md_runner retry -- five spurious command_error entries were
    a real defect here."""
    ws, _ = built
    s = state.read(ws)
    assert s["step_outputs"]["step_5"]["net_charge"] == 0.0
    assert s["step_outputs"]["step_5"]["n_cl"] == 4
    assert s["step_outputs"]["step_5"]["n_na"] == 0
    # step_3 records what solvate+water_deletor left, which is *before* genion
    # swapped 4 of those waters for the 4 Cl-, so it is 4 higher than the 3653
    # SOL the finished ions.gro holds. Both are asserted, and against each
    # other, because a step_3 that silently meant the post-genion count would
    # make the aqueous arm's own record mean something different.
    assert s["step_outputs"]["step_3"]["n_solvent_molecules"] == 3657
    assert (s["step_outputs"]["step_3"]["n_solvent_molecules"]
            - s["step_outputs"]["step_5"]["n_cl"]
            == MA.residue_counts(ws / "stage1_env" / "ions.gro")["SOL"] == 3653)
    assert s["step_outputs"]["step_3"]["water_atoms_removed"] > 0
    assert s["retry_history"] == []
    assert s["current_step"] == 5 and s["last_completed_stage"] == "env"


@pytest.mark.parametrize("phase", ["nvt", "npt", "production"])
def test_grompp_accepts_every_md_phase_with_exactly_two_warnings(built, phase):
    """The MD side, built by the production argv builder against the real
    system: tc_grps=Protein_DPPC and semiisotropic pressure coupling both have
    to resolve, at 323 K (DPPC's main transition is near 314 K, so the aqueous
    300 K would freeze the bilayer into the gel phase).

    The warning count is asserted, not just the exit code. Exactly two are
    expected -- the LJ-14 bondtype redefinition from merging lipid.itp, and the
    GROMOS twin-range notice -- which is what MEMBRANE_DEFAULT_MAXWARN=2 is
    sized for. A third warning is a real problem, so this fails rather than
    letting a higher cap hide it.
    """
    ws, summary = built
    stage = ws / "stage1_env"
    variant = state.read(ws)["tutorial"]["variant"]
    # Production's own choice of coupling groups, temperature and barostat --
    # not a dict written here, which would assert this test against itself.
    overrides = MD.apply_membrane_overrides(variant, phase, {})
    assert overrides["tc_grps"] == "Protein_DPPC Water_and_ions"
    assert overrides["ref_t"] == 323.0
    assert (phase == "nvt") or overrides["pcoupltype"] == "semiisotropic"
    mdp = MDP.render(phase, overrides, stage)
    assert "ref_t                    = 323" in mdp.read_text()
    args = MD.build_grompp_args(
        phase=phase, variant="membrane_md_standard", mdp_name=mdp.name,
        input_gro="ions.gro", top="topol.top", tpr=f"{phase}_e2e.tpr",
        index=summary["index_file"].split("/")[-1], input_cpt=None,
        maxwarn=MD.MEMBRANE_DEFAULT_MAXWARN,
        restraint="ions.gro" if phase != "production" else None,
    )
    check = GW.run(args, cwd=stage, env=dict(MA.GMX_ENV))
    assert check.ok, check.stderr[-2000:]
    assert (stage / f"{phase}_e2e.tpr").is_file()

    warnings = re.findall(r"^WARNING \d+ \[.*$", check.stderr, re.M)
    assert len(warnings) == 2, check.stderr[-2000:]
    assert "ffnonbonded.itp" in warnings[0] and "topol.top" in warnings[1]
    assert "Bondtype LJ-14 was defined previously" in check.stderr
    assert "twin-range" in check.stderr or "GROMOS" in check.stderr


def test_single_valued_pressure_coupling_is_still_fatal(built):
    """The negative half: semiisotropic on the aqueous single-valued
    ref_p/compressibility is a grompp ERROR that -maxwarn cannot suppress, so
    the two-valued overrides above are load-bearing, not decoration."""
    ws, _ = built
    stage = ws / "stage1_env"
    overrides = MD.apply_membrane_overrides("membrane_md_standard", "npt", {})
    del overrides["ref_p_list"], overrides["compressibility_list"]
    mdp = MDP.render("npt", overrides, stage)
    check = GW.run(["grompp", "-f", mdp.name, "-c", "ions.gro", "-r", "ions.gro",
                    "-p", "topol.top", "-n", "index.ndx", "-o", "reject.tpr",
                    "-maxwarn", str(MD.MEMBRANE_DEFAULT_MAXWARN)],
                   cwd=stage, env=dict(MA.GMX_ENV))
    assert not check.ok
    assert "I need exactly 2" in check.stderr
