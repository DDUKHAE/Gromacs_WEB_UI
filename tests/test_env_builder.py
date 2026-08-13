import shutil
from pathlib import Path

import pytest

from lib import state
from lib import gmx_wrapper as GW
from skills.env_builder import env_builder as EB


def _init(ws):
    ws.mkdir(exist_ok=True)
    (ws / "stage1_env").mkdir(exist_ok=True)
    state.write(ws, state.initial(ws))


def _fake_gw_run(responses):
    """responses: dict keyed by first arg (command name) -> GmxResult kwargs."""
    def _run(args, cwd, interactive_inputs=None, **kwargs):
        cmd = args[0]
        resp = responses[cmd]
        return GW.GmxResult(command=list(args), returncode=resp.get("returncode", 0),
                             stdout=resp.get("stdout", ""), stderr=resp.get("stderr", ""),
                             classification=resp.get("classification", "success"))
    return _run


def test_step4_parses_nonzero_charge_warning(tmp_path, monkeypatch):
    _init(tmp_path)
    grompp_stderr = (
        "WARNING 1 [file topol.top, line 10]:\n"
        "  System has non-zero total charge: -3.000000\n"
    )
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "grompp": {"stderr": grompp_stderr},  # returncode 0: within -maxwarn budget
    }))
    EB.run_step4_ions_prep(tmp_path)
    s = state.read(tmp_path)
    assert s["step_outputs"]["step_4"]["initial_net_charge"] == -3.0


def test_step4_defaults_to_zero_charge_when_no_warning(tmp_path, monkeypatch):
    _init(tmp_path)
    monkeypatch.setattr(GW, "run", _fake_gw_run({"grompp": {}}))
    EB.run_step4_ions_prep(tmp_path)
    s = state.read(tmp_path)
    assert s["step_outputs"]["step_4"]["initial_net_charge"] == 0.0


def _seed_step4(ws, initial_net_charge):
    s = state.read(ws)
    s["step_outputs"]["step_4"] = {"initial_net_charge": initial_net_charge}
    (ws / "stage1_env" / "topol.top").write_text("; fake topology\n")
    state.write(ws, s)


def test_step5_computes_real_net_charge_not_hardcoded_zero(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-3.0)
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 3 NA ions and 0 CL ions.\n"},
    }))
    EB.run_step5_genion(tmp_path)
    s = state.read(tmp_path)
    step5 = s["step_outputs"]["step_5"]
    # -3.0 + 3 NA (+1 each) - 0 CL == 0.0, properly neutralized
    assert step5["net_charge"] == 0.0
    assert step5["neutrality_tier"] == "pass"


def test_step5_fatal_charge_raises_and_blocks_pipeline(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-3.0)
    # genion only adds 1 NA -> residual net charge -2.0 -> fatal (> 0.5 tol)
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 1 NA ions and 0 CL ions.\n"},
    }))
    with pytest.raises(RuntimeError, match="neutralization gate FATAL"):
        EB.run_step5_genion(tmp_path)
    s = state.read(tmp_path)
    # current_step must NOT have advanced past the gate on fatal charge
    assert s["current_step"] != 5 or s["last_completed_stage"] != "env"


def test_step5_never_hardcodes_net_charge_to_zero_source(tmp_path):
    import inspect
    src = inspect.getsource(EB.run_step5_genion)
    assert '"net_charge": 0.0' not in src


def test_select_tutorial_records_has_protein_false_for_ethanol(tmp_path):
    _init(tmp_path)
    pdb = tmp_path / "input.pdb"
    pdb.write_text("HETATM    1  C1  ETH A   1       0.000   0.000   0.000\n")
    EB.select_tutorial(
        tmp_path, pdb, prompt="ethanol solvation",
        prerequisites={"solute_topology": "eth.itp",
                        "coulomb_vdw_lambda_schedule": "0 0.5 1"})
    s = state.read(tmp_path)
    assert s["tutorial"]["has_protein"] is False


def test_select_tutorial_records_has_protein_true_for_lysozyme(tmp_path):
    _init(tmp_path)
    pdb = tmp_path / "input.pdb"
    pdb.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
    )
    EB.select_tutorial(tmp_path, pdb, prompt="lysozyme in water", prerequisites={})
    s = state.read(tmp_path)
    assert s["tutorial"]["has_protein"] is True


from lib import llm_assist


def test_review_pdb_flags_skips_llm_when_no_flags(tmp_path, monkeypatch):
    pdb = tmp_path / "clean.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    called = []
    monkeypatch.setattr(llm_assist, "review_pdb", lambda *a, **k: called.append(1))
    EB._review_pdb_flags(pdb)
    assert called == []


def test_review_pdb_flags_calls_llm_and_rejects(tmp_path, monkeypatch):
    pdb = tmp_path / "altloc.pdb"
    # altloc 'A' on the CA atom (column 17) triggers altloc_residues
    pdb.write_text(
        "ATOM      1  CA AALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    monkeypatch.setattr(
        llm_assist, "review_pdb",
        lambda flags, summary: llm_assist.CheckpointVerdict(
            proceed=False, diagnosis="unresolved altloc conflict"))
    with pytest.raises(RuntimeError, match="unresolved altloc conflict"):
        EB._review_pdb_flags(pdb)


def test_review_pdb_flags_calls_llm_and_proceeds(tmp_path, monkeypatch):
    pdb = tmp_path / "altloc.pdb"
    pdb.write_text(
        "ATOM      1  CA AALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    monkeypatch.setattr(
        llm_assist, "review_pdb",
        lambda flags, summary: llm_assist.CheckpointVerdict(proceed=True, diagnosis="fine"))
    EB._review_pdb_flags(pdb)  # must not raise


def test_review_pdb_flags_never_raises_on_malformed_pdb(tmp_path):
    pdb = tmp_path / "truncated.pdb"
    pdb.write_text("ATOM      1  CA  ALA A\n")  # truncated — indexes past end of line
    EB._review_pdb_flags(pdb)  # must not raise


def test_gro_checkpoint_skipped_on_pass(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=0.0)
    called = []
    monkeypatch.setattr(llm_assist, "review_gro", lambda judgment: called.append(judgment) or llm_assist.CheckpointVerdict(proceed=True, diagnosis=""))
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 0 NA ions and 0 CL ions.\n"},
    }))
    EB.run_step5_genion(tmp_path)
    assert called == []


def test_gro_checkpoint_called_on_warning_and_rejects(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-2.95)
    monkeypatch.setattr(
        llm_assist, "review_gro",
        lambda judgment: llm_assist.CheckpointVerdict(
            proceed=False, diagnosis="residual charge too high for this ligand"))
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 3 NA ions and 0 CL ions.\n"},
    }))
    with pytest.raises(RuntimeError, match="residual charge too high for this ligand"):
        EB.run_step5_genion(tmp_path)


def test_gro_checkpoint_called_on_warning_and_accepts(tmp_path, monkeypatch):
    _init(tmp_path)
    _seed_step4(tmp_path, initial_net_charge=-2.95)
    monkeypatch.setattr(
        llm_assist, "review_gro",
        lambda judgment: llm_assist.CheckpointVerdict(proceed=True, diagnosis="fine"))
    monkeypatch.setattr(GW, "run", _fake_gw_run({
        "genion": {"stdout": "Will try to add 3 NA ions and 0 CL ions.\n"},
    }))
    EB.run_step5_genion(tmp_path)
    s = state.read(tmp_path)
    assert s["step_outputs"]["step_5"]["neutrality_tier"] == "warning"


# ---------------------------------------------------------------------------
# pdb2gmx terminus selection (capped N-/C-termini)
# ---------------------------------------------------------------------------

TUTORIAL_DATA = Path(__file__).resolve().parent.parent / "tutorial_data"


#: The menus pdb2gmx really prints, verified against gmx 2026 for each force
#: field. "None" is last, and its index differs -- answering 2 on oplsaa picks
#: NH2 and reproduces the exact ACE failure this machinery exists to prevent.
MENUS = {
    "gromos53a6": (["NH3+", "NH2", "None"], ["COO-", "COOH", "None"]),
    "oplsaa": (["NH3+", "ZWITTERION_NH3+", "NH2", "None"],
               ["COO-", "ZWITTERION_COO-", "COOH", "None"]),
    "charmm36": (["NH3+", "NH2", "HYD1", "MET1", "5TER", "5MET", "5PHO", "5POM", "None"],
                 ["COO-", "COOH", "CT2", "CT1", "HYD2", "MET2", "3TER", "None"]),
}


def _menu(kind, residue, resid, ff):
    options = MENUS[ff][0 if kind == "start" else 1]
    return "".join([f"Select {kind} terminus type for {residue}-{resid}\n"]
                   + [f" {i}: {name}\n" for i, name in enumerate(options)])


def _fake_pdb2gmx(chains, ff="gromos53a6"):
    """A pdb2gmx that prints one chain's menus per successful answer pair.

    Mirrors the real thing: it asks two menus per chain, in chain order, and
    stops at the first chain whose answers it cannot use -- so a caller that
    supplies too few answers sees the next chain's prompt, not an error.
    """
    calls = []

    def _run(args, cwd, interactive_inputs=None, timeout=None, **kwargs):
        calls.append({"args": list(args), "inputs": interactive_inputs,
                      "timeout": timeout})
        answers = list(interactive_inputs or [])
        out, ok = "", True
        if "-ter" not in args:
            # No -ter, no menus, no prompt: pdb2gmx just builds the default
            # charged termini.
            return GW.GmxResult(command=list(args), returncode=0, stdout="",
                                stderr="", classification="success")
        for index, (residue, resid) in enumerate(chains):
            out += _menu("start", residue[0], resid[0], ff)
            out += _menu("end", residue[1], resid[1], ff)
            wanted = [MENUS[ff][0].index("None") if residue[0] in EB._TERMINUS_CAPS else 0,
                      MENUS[ff][1].index("None") if residue[1] in EB._TERMINUS_CAPS else 0]
            if answers[2 * index:2 * index + 2] != [str(x) for x in wanted]:
                ok = False  # this chain's terminus cannot be built: stop here
                break
        return GW.GmxResult(command=list(args), returncode=0 if ok else 1,
                            stdout=out, stderr="" if ok else "Fatal error: atom N not found",
                            classification="success" if ok else "command_error")

    return _run, calls


def _run_step1(ws, monkeypatch, pdb_source, runner, ff="gromos53a6_lipid"):
    _init(ws)
    (ws / "inputs").mkdir(exist_ok=True)
    if isinstance(pdb_source, str):
        (ws / "inputs" / "input.pdb").write_text(pdb_source)
    else:
        shutil.copy2(pdb_source, ws / "inputs" / "input.pdb")
    monkeypatch.setattr(GW, "run", runner)
    EB.run_step1_topology(ws, ff, "spc")


KALP = TUTORIAL_DATA / "KALP15_in_DPPC" / "KALP-15_princ.pdb"
LYSOZYME = TUTORIAL_DATA / "Lysozyme_in_water" / "1AKI.pdb"
CAPPED_CHAIN = (("ACE", "NH2"), (1, 17))
BARE_CHAIN = (("LYS", "LEU"), (1, 129))


def test_capped_termini_get_ter_and_the_none_answers(tmp_path, monkeypatch):
    """KALP-15 is ACE/NH2-capped. Answering 0 builds an NH3+ start terminus and
    dies with "atom N not found in buiding block 1ACE" -- the cap has no N."""
    runner, calls = _fake_pdb2gmx([CAPPED_CHAIN])
    _run_step1(tmp_path, monkeypatch, KALP, runner)
    assert "-ter" in calls[0]["args"]
    assert calls[-1]["inputs"][:2] == ["2", "2"]


@pytest.mark.parametrize("ff,expected", [("gromos53a6", ["2", "2"]),
                                         ("oplsaa", ["3", "3"]),
                                         ("charmm36", ["8", "7"])])
def test_the_none_index_comes_from_the_force_fields_own_menu(tmp_path, monkeypatch,
                                                             ff, expected):
    """"None" is last, but not at the same index in every force field: 2 on
    oplsaa is NH2 and 2 on charmm36 is HYD1, either of which reproduces the
    original ACE failure. The index is read off the printed menu."""
    runner, calls = _fake_pdb2gmx([CAPPED_CHAIN], ff=ff)
    _run_step1(tmp_path, monkeypatch, KALP, runner, ff=ff)
    assert calls[-1]["inputs"][:2] == expected
    assert calls[-1]["args"].count("-ter") == 1


def test_a_capped_multi_chain_pdb_answers_every_chain(tmp_path, monkeypatch):
    """pdb2gmx asks two menus *per chain*. Answering only the first chain's
    pair leaves it blocked on chain B's prompt forever, which is worse than the
    loud failure it replaces."""
    runner, calls = _fake_pdb2gmx([CAPPED_CHAIN, CAPPED_CHAIN, CAPPED_CHAIN])
    _run_step1(tmp_path, monkeypatch, KALP, runner)
    assert calls[-1]["inputs"][:6] == ["2"] * 6
    # Every call carries far more answers than menus, so an unpredicted prompt
    # is answered rather than waited on.
    assert all(len(call["inputs"]) > 6 for call in calls)
    assert all(call["timeout"] == EB.PDB2GMX_TIMEOUT_S for call in calls)


def test_uncapped_chains_in_a_capped_file_keep_the_default(tmp_path, monkeypatch):
    runner, calls = _fake_pdb2gmx([CAPPED_CHAIN, BARE_CHAIN])
    _run_step1(tmp_path, monkeypatch, KALP, runner)
    assert calls[-1]["inputs"][:4] == ["2", "2", "0", "0"]


def test_surrounding_hetatm_water_does_not_hide_the_cap(tmp_path, monkeypatch):
    """Most PDB-bank files carry crystallographic waters or a ligand around the
    protein, so a first/last-residue scan loses the cap and lands back on
    "atom C not found in buiding block 17NH2". Which residue is capped is
    pdb2gmx's own answer here (it names the residue in every prompt); the file
    is only asked whether a cap is present at all.
    """
    water = "HETATM  200  O   HOH A 900       0.0   0.0   0.0  1.00  0.00           O\n"
    pdb = water + KALP.read_text().rstrip("\n") + "\n" + water
    runner, calls = _fake_pdb2gmx([CAPPED_CHAIN])
    _run_step1(tmp_path, monkeypatch, pdb, runner)
    assert "-ter" in calls[0]["args"]
    assert calls[-1]["inputs"][:2] == ["2", "2"]


def test_ordinary_termini_leave_pdb2gmx_non_interactive(tmp_path, monkeypatch):
    """Lysozyme has charged termini: the aqueous call must stay exactly as it
    was, because -ter would block on stdin for answers nobody supplies."""
    runner, calls = _fake_pdb2gmx([BARE_CHAIN])
    _run_step1(tmp_path, monkeypatch, LYSOZYME, runner)
    assert len(calls) == 1
    assert calls[0]["inputs"] is None
    assert calls[0]["args"] == ["pdb2gmx", "-f", str(tmp_path / "inputs" / "input.pdb"),
                                "-o", "processed.gro", "-p", "topol.top",
                                "-water", "spc", "-ff", "gromos53a6_lipid", "-ignh"]


def test_a_pdb2gmx_that_never_prints_a_menu_is_reported_not_retried(tmp_path, monkeypatch):
    """A failure before the first prompt (a bad force field, say) must surface
    its own message instead of looping the probe."""
    calls = []

    def _run(args, cwd, interactive_inputs=None, timeout=None, **kwargs):
        calls.append(list(args))
        return GW.GmxResult(command=list(args), returncode=1, stdout="",
                            stderr="Fatal error: could not find force field",
                            classification="command_error")

    with pytest.raises(RuntimeError, match="could not find force field"):
        _run_step1(tmp_path, monkeypatch, KALP, _run)
    assert len(calls) == 1
