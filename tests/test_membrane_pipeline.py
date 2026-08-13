"""The membrane variant's integration with env_builder and md_runner."""
import inspect
import re
from pathlib import Path
from unittest import mock

import pytest

from lib import state
from lib.mdp_templates import base as MDP
from skills.env_builder import env_builder as EB
from skills.md_runner import md_runner as MD


def _workspace(tmp_path, name):
    ws = tmp_path / name
    for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
        (ws / sub).mkdir(parents=True)
    state.write(ws, state.initial(ws))
    return ws


# --- routing --------------------------------------------------------------


def test_membrane_variant_routes_to_the_assembly(tmp_path):
    """A membrane run must not go through the aqueous box/solvate/ions path."""
    ws = _workspace(tmp_path, "kalp_20260807_120000")

    with mock.patch.object(EB, "membrane_assembly") as ma, \
         mock.patch.object(EB, "run_step2_box") as box:
        EB.dispatch_environment_build(ws, {"forcefield": "gromos53a6"},
                                      variant="membrane_md_standard")
    ma.assemble.assert_called_once()
    box.assert_not_called()


def test_aqueous_variant_still_uses_the_standard_steps(tmp_path):
    ws = _workspace(tmp_path, "aki_20260807_120000")

    params = {"box_type": "cubic", "box_distance_nm": 1.0,
              "ion_concentration_M": 0.15, "forcefield": "charmm36"}
    with mock.patch.object(EB, "membrane_assembly") as ma, \
         mock.patch.object(EB, "run_step2_box") as box, \
         mock.patch.object(EB, "run_step3_solvate"), \
         mock.patch.object(EB, "run_step4_ions_prep"), \
         mock.patch.object(EB, "run_step5_genion"):
        EB.dispatch_environment_build(ws, params,
                                      variant="protein_aqueous_standard")
    box.assert_called_once()
    ma.assemble.assert_not_called()


def test_build_environment_routes_through_the_dispatcher():
    """The dispatcher is only wired in if build_environment actually calls it.

    A structural check because build_environment's own path (pdb2gmx, the run
    plan and the protocol contract) needs gmx and a full submission; Task 10's
    end-to-end run is the behavioural oracle.
    """
    src = inspect.getsource(EB.build_environment)
    assert "dispatch_environment_build(workspace_dir, params.values" in src
    assert "run_step2_box" not in src, (
        "build_environment still calls run_step2_box directly, so a membrane "
        "run would build an aqueous box before reaching the assembly"
    )


def test_the_assembly_is_not_swallowed_by_a_broad_except():
    """MembraneAssemblyError subclasses Exception, not RuntimeError, so that a
    fatal packing or topology failure cannot be demoted into a retryable
    judgment. A try/except around the call here would undo that."""
    body = inspect.getsource(EB.dispatch_environment_build).split('"""')[-1]
    assert "except" not in body
    assert not issubclass(
        EB.membrane_assembly.MembraneAssemblyError, RuntimeError)


# --- the index file -------------------------------------------------------


def test_membrane_phases_pass_the_index_file():
    """grompp needs -n index.ndx to resolve tc_grps=Protein_DPPC."""
    args = MD.build_grompp_args(
        phase="npt", variant="membrane_md_standard",
        mdp_name="npt.mdp", input_gro="nvt.gro", top="topol.top",
        tpr="npt.tpr", index="index.ndx", input_cpt=None, maxwarn=1,
    )
    assert "-n" in args
    assert args[args.index("-n") + 1] == "index.ndx"


def test_aqueous_phases_do_not_pass_an_index_file():
    args = MD.build_grompp_args(
        phase="npt", variant="protein_aqueous_standard",
        mdp_name="npt.mdp", input_gro="nvt.gro", top="topol.top",
        tpr="npt.tpr", index=None, input_cpt=None, maxwarn=1,
    )
    assert "-n" not in args


def test_no_index_file_means_no_index_flag_even_for_a_membrane_run():
    """A membrane workspace resumed before build_index ran has no index.ndx;
    passing -n for a file that does not exist is a fatal grompp error."""
    args = MD.build_grompp_args(
        phase="npt", variant="membrane_md_standard",
        mdp_name="npt.mdp", input_gro="nvt.gro", top="topol.top",
        tpr="npt.tpr", index=None, input_cpt=None, maxwarn=1,
    )
    assert "-n" not in args


def test_build_grompp_args_keeps_the_restraint_and_checkpoint_options():
    args = MD.build_grompp_args(
        phase="npt", variant="membrane_md_standard", mdp_name="npt.mdp",
        input_gro="nvt.gro", top="topol.top", tpr="npt.tpr",
        index="index.ndx", input_cpt="nvt.cpt", maxwarn=3,
        restraint="nvt.gro",
    )
    assert args == ["grompp", "-f", "npt.mdp", "-c", "nvt.gro",
                    "-r", "nvt.gro", "-t", "nvt.cpt",
                    "-p", "topol.top", "-o", "npt.tpr",
                    "-n", "index.ndx", "-maxwarn", "3"]


def test_run_phase_finds_the_index_file_in_stage1_env(run_phase_grompp_args):
    """build_grompp_args is only useful if run_phase hands it the real path
    the assembly wrote index.ndx to."""
    ws, args = run_phase_grompp_args("kalp", "em", index=True,
                                     variant="membrane_md_standard")
    assert args[args.index("-n") + 1] == str(ws / "stage1_env" / "index.ndx")


def test_run_phase_omits_the_index_for_an_aqueous_run(run_phase_grompp_args):
    """The aqueous sequence never builds an index file."""
    _, args = run_phase_grompp_args("aki", "em", index=False,
                                    variant="protein_aqueous_standard")
    assert "-n" not in args


def test_a_stray_index_file_does_not_reach_an_aqueous_grompp(run_phase_grompp_args):
    """The variant decides, not the presence of the file: an aqueous run's
    mdp couples to Protein/Non-Protein, and a leftover index.ndx (an imported
    or umbrella workspace) must not silently redefine those groups."""
    _, args = run_phase_grompp_args("aki_with_index", "em", index=True,
                                    variant="protein_aqueous_standard")
    assert "-n" not in args


# --- expert-mode overrides on a membrane run (Task 8 review, Fix 1) -------


def test_run_simulation_survives_a_membrane_run_with_a_locked_contract(tmp_path, monkeypatch):
    """Task 8 review, Fix 1, end to end: an expert-mode membrane run used to
    die at npt with a StateContractError -- not retryable, since
    StateContractError subclasses Exception, not RuntimeError -- because
    lib.protocol_contract.phase_overrides forced pcoupl="Berendsen"
    regardless of variant, colliding with md_runner's own
    pcoupl="Parrinello-Rahman" override. Drives the real run_simulation, with
    a materialized, non-empty protocol contract (temperature_K + pressure_bar
    locked) for the membrane tutorial -- that combination was previously
    untested, which is how this shipped.
    """
    import json
    from lib import gmx_wrapper as GW
    from lib import protocol_contract as PC

    ws = _workspace(tmp_path, "kalp_locked")
    (ws / "stage1_env" / "processed.gro").write_text("gro")
    (ws / "stage1_env" / "topol.top").write_text("top")
    (ws / "stage1_env" / "ions.gro").write_text("gro")
    s = state.read(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 1, "gpu_ids": [], "ntomp": 1}
    s["tutorial"] = {"id": "KALP15_in_DPPC", "variant": "membrane_md_standard"}
    for key in ("step_1", "step_2", "step_3", "step_5"):
        s["step_outputs"][key] = {"ok": True}
    state.write(ws, s)
    (ws / "system_config.json").write_text(json.dumps({
        "simulation": {"_expert_mode": True, "temperature_K": 310.0,
                       "pressure_bar": 2.0},
    }))
    PC.materialize(ws, "KALP15_in_DPPC")

    def fake_run(args, cwd, **kwargs):
        if args[0] == "grompp":
            Path(cwd, args[args.index("-o") + 1]).write_text("tpr")
        if args[0] == "mdrun":
            Path(cwd, f"{args[args.index('-deffnm') + 1]}.gro").write_text("gro")
        return GW.GmxResult(command=list(args), returncode=0, stdout="",
                            stderr="", classification="success")

    monkeypatch.setattr(GW, "run", fake_run)
    MD.run_simulation(ws)  # must not raise StateContractError at npt

    rendered = (ws / "stage2_md" / "npt.mdp").read_text()
    assert "pcoupl                   = Parrinello-Rahman" in rendered
    assert "ref_p                    = 2.0 2.0" in rendered




def test_run_simulation_sets_membrane_pressure_and_coupling_overrides(tmp_path):
    """The override dict run_simulation builds for npt/npt_pr/production is
    never exercised by the integration grompp tests -- those hardcode their
    own copy of the same values. Pin the construction itself, or a typo here
    (e.g. "pcoupl" -> "fcoupl") would only surface via a full gmx run."""
    from lib import validators as V

    ws = _workspace(tmp_path, "kalp_20260807_130000")
    (ws / "stage1_env" / "processed.gro").write_text("gro")
    (ws / "stage1_env" / "topol.top").write_text("top")
    (ws / "stage1_env" / "ions.gro").write_text("gro")
    s = state.read(ws)
    s["last_completed_stage"] = "env"
    s["hardware"] = {"cpu_count": 1, "gpu_ids": [], "ntomp": 1}
    s["tutorial"] = {"id": "t", "variant": "membrane_md_standard"}
    for key in ("step_1", "step_2", "step_3", "step_5"):
        s["step_outputs"][key] = {"ok": True}
    state.write(ws, s)

    calls = []

    def fake_run_phase_with_recovery(workspace_dir, phase, phase_runner=None, overrides=None):
        calls.append((phase, dict(overrides or {})))
        return V.Judgment(tier="pass", metric="stub")

    with mock.patch.object(MD, "run_phase_with_recovery", side_effect=fake_run_phase_with_recovery):
        MD.run_simulation(ws)

    by_phase = dict(calls)
    for phase in ("npt", "npt_pr", "production"):
        overrides = by_phase[phase]
        assert overrides["pcoupltype"] == "semiisotropic"
        assert overrides["pcoupl"] == "Parrinello-Rahman"
        assert overrides["ref_p_list"] == "1.0 1.0"
        assert overrides["compressibility_list"] == "4.5e-5 4.5e-5"
        assert overrides["tc_grps"] == "Protein_DPPC Water_and_ions"
    # em/nvt are unaffected -- the override block is scoped to the
    # pressure-coupled phases only.
    assert "pcoupl" not in by_phase["em"]
    assert "pcoupl" not in by_phase["nvt"]


def test_lipid_collapse_has_documented_remediations():
    """The troubleshooting page's two remedies, in escalating order."""
    steps = MD.MUTATION_BY_CAUSE["lipid_collapse"]
    assert len(steps) == 2
    assert "-DPOSRES_LIPID" in steps[0]["define"]
    assert steps[1].get("mdp_template") == "anneal_npt"


def test_run_phase_honours_the_mdp_template_mutation(run_phase_grompp_args):
    """The second remedy is inert unless run_phase actually swaps templates:
    "mdp_template" would otherwise reach str.format as an unused key and be
    dropped in silence, leaving the collapsing npt phase unchanged."""
    ws, args = run_phase_grompp_args(
        "kalp_anneal", "npt", MD.MUTATION_BY_CAUSE["lipid_collapse"][1],
        variant="membrane_md_standard", index=True, stage2_files=["nvt.gro"])

    assert args[args.index("-f") + 1] == "anneal_npt.mdp"
    # The phase's own bookkeeping is untouched by the template swap.
    assert args[args.index("-o") + 1] == "npt.tpr"
    rendered = (ws / "stage2_md" / "anneal_npt.mdp").read_text()
    assert "define" in rendered and "-DPOSRES_LIPID" in rendered


def test_anneal_template_define_is_a_real_placeholder(tmp_path):
    """`define` must be substitutable, or both remedies' -DPOSRES_LIPID is a
    no-op: str.format discards overrides a template has no placeholder for."""
    rendered = MDP.render("anneal_npt", {"define": "-DPOSRES"}, tmp_path).read_text()
    assert re.search(r"^define\s*=\s*-DPOSRES\s", rendered, re.M)
    assert "-DPOSRES_LIPID" not in rendered
    assert "{define}" not in rendered


def test_anneal_template_renders_from_its_defaults(tmp_path):
    rendered = MDP.render("anneal_npt", {}, tmp_path).read_text()
    assert re.search(r"^define\s*=\s*-DPOSRES -DPOSRES_LIPID", rendered, re.M)


def test_anneal_template_has_one_annealing_entry_per_coupling_group():
    """Upstream's file declares three for two groups and fails grompp."""
    text = (Path("lib/mdp_templates/anneal_npt.mdp")).read_text()

    def values(key):
        m = re.search(rf"^{key}\s*=\s*([^;\n]+)", text, re.M)
        return m.group(1).split() if m else []

    n_groups = len(values("tc_grps") or values("tc-grps"))
    assert n_groups == 2
    assert len(values("annealing")) == n_groups
    assert len(values("annealing_npoints")) == n_groups
    assert len(values("annealing_time")) == 2 * n_groups
    assert len(values("annealing_temp")) == 2 * n_groups
    assert len(values("ref_t")) == n_groups


@pytest.mark.integration
def test_grompp_accepts_the_corrected_annealing_template(tmp_path):
    """gmx is the only oracle for "one annealing entry per coupling group":
    the upstream file's three entries are a fatal grompp error, and no
    structural assertion proves the corrected one is accepted."""
    import os
    import shutil
    import subprocess

    gmx = shutil.which("gmx")
    if not gmx:
        pytest.skip("gmx not on PATH")

    # A two-group system: one SPC water is "Water_and_ions"; make_ndx cannot
    # invent a Protein_DPPC group here, so both coupling groups are supplied
    # by a hand-written index instead of a real membrane system.
    (tmp_path / "conf.gro").write_text(
        "two groups\n    6\n"
        "    1SOL     OW    1   0.500   0.500   0.500\n"
        "    1SOL    HW1    2   0.600   0.500   0.500\n"
        "    1SOL    HW2    3   0.400   0.500   0.500\n"
        "    2SOL     OW    4   1.500   1.500   1.500\n"
        "    2SOL    HW1    5   1.600   1.500   1.500\n"
        "    2SOL    HW2    6   1.400   1.500   1.500\n"
        "   3.00000   3.00000   3.00000\n")
    (tmp_path / "topol.top").write_text(
        '#include "oplsaa.ff/forcefield.itp"\n'
        '#include "oplsaa.ff/spce.itp"\n'
        "[ system ]\nt\n[ molecules ]\nSOL 2\n")
    (tmp_path / "index.ndx").write_text(
        "[ Protein_DPPC ]\n1 2 3\n[ Water_and_ions ]\n4 5 6\n")
    mdp = MDP.render("anneal_npt", {"define": ""}, tmp_path)

    done = subprocess.run(
        [gmx, "grompp", "-f", mdp.name, "-c", "conf.gro", "-p", "topol.top",
         "-n", "index.ndx", "-o", "anneal.tpr", "-maxwarn", "3"],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "GMX_MAXBACKUP": "-1"},
    )
    assert done.returncode == 0, done.stderr[-2000:]

    # And the upstream file's three-entry annealing block is genuinely fatal,
    # or correcting it proves nothing.
    upstream = Path("tutorial_data/KALP15_in_DPPC/mdp/anneal_npt.mdp")
    broken = tmp_path / "broken.mdp"
    broken.write_text(upstream.read_text().replace(
        "define\t\t= -DPOSRES -DPOSRES_LIPID", "define = "))
    failed = subprocess.run(
        [gmx, "grompp", "-f", broken.name, "-c", "conf.gro", "-p", "topol.top",
         "-n", "index.ndx", "-o", "broken.tpr", "-maxwarn", "3"],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "GMX_MAXBACKUP": "-1"},
    )
    assert failed.returncode != 0
    assert "annealing" in failed.stderr.lower()
