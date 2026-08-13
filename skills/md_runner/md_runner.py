# skills/md_runner/md_runner.py
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict
import re
from lib import state
from lib.state import StateContractError
from lib import gmx_wrapper as GW
from lib.mdp_templates import base as MDP
from lib import validators as V
from lib import xvg_parser
from lib import protocol_contract as PC
from lib.system_config import load_config
from lib import llm_assist


REQUIRED_KEYS = ["step_1", "step_2", "step_3", "step_5"]
REQUIRED_FILES = ["processed.gro", "topol.top", "ions.gro"]


def assert_ready(workspace_dir: Path) -> dict[str, Any]:
    s = state.read(workspace_dir)
    state.require_last_stage(s, "env")
    state.require_step_keys(s, REQUIRED_KEYS)
    if not s.get("hardware"):
        raise StateContractError("hardware profile missing")
    ws = Path(workspace_dir)
    for fname in REQUIRED_FILES:
        if not (ws / "stage1_env" / fname).exists():
            raise StateContractError(f"missing stage1 file: {fname}")
    # Idempotent: also covers workspaces entered directly at md_runner
    # (independent_entry_guide.md) where env_builder never ran Step 0.
    state.capture_provenance(ws)
    return s


def phase_sequence_for_variant(variant: str | None) -> list[str]:
    return PC.PHASE_SEQUENCE_BY_VARIANT.get(variant or "", ["em", "nvt", "npt", "npt_pr", "production"])


PHASE_INPUT_GRO = {
    "em":         ("stage1_env", "ions.gro"),
    "nvt":        ("stage2_md", "em.gro"),
    "npt":        ("stage2_md", "nvt.gro"),
    "npt_pr":     ("stage2_md", "npt.gro"),
    "production": ("stage2_md", "npt_pr.gro"),
    "umbrella":   ("stage2_md", "npt_pr.gro"),
    "free_energy":("stage2_md", "npt_pr.gro"),
}


def phase_input_for(variant: str | None, phase: str) -> tuple[str, str]:
    """Return the coordinate handoff for a phase in a tutorial variant."""
    if variant == "virtual_sites_topology" and phase == "production":
        return ("stage2_md", "em.gro")
    return PHASE_INPUT_GRO[phase]

# Preserve the extended-system state (thermostat/barostat variables) across
# equilibration stages when GROMACS produced a checkpoint. The coordinate file
# remains the mandatory fallback for an imported or older partial workspace.
PHASE_INPUT_CPT = {
    "npt": "nvt.cpt",
    "npt_pr": "npt.cpt",
    "production": "npt_pr.cpt",
    "umbrella": "npt_pr.cpt",
    "free_energy": "npt_pr.cpt",
}

PHASE_TO_STATE_KEY = {
    "em": "em_gro", "nvt": "nvt_gro", "npt": "npt_berendsen_gro",
    "npt_pr": "npt_gro",
    "production": "production_gro",
    "umbrella": "production_gro", "free_energy": "production_gro",
}


_GROMPP_WARNING_RE = re.compile(r"^WARNING\s+\d+\s+\[.*", re.MULTILINE)
_GEN_SEED_RE = re.compile(r"gen_seed\s*=\s*(-?\d+)")

_DEFINE_RE = re.compile(r"^define\s*=([^;\n]*)", re.MULTILINE)



def _record_grompp_warnings(ws: Path, phase: str, combined_output: str) -> None:
    """Log any grompp WARNING blocks into state so suppressed (-maxwarn)
    warnings remain auditable in the run record instead of silently vanishing."""
    warnings = [m.group(0).strip() for m in _GROMPP_WARNING_RE.finditer(combined_output)]
    if not warnings:
        return
    s = state.read(ws)
    step7 = s["step_outputs"].setdefault("step_7", {})
    log = step7.setdefault("grompp_warnings", {})
    log[phase] = warnings
    state.write(ws, s)



def _mdp_defines_restraints(mdp_path: Path) -> bool:
    """Whether a rendered mdp switches on any position restraints."""
    match = _DEFINE_RE.search(mdp_path.read_text())
    return bool(match) and "-DPOSRES" in match.group(1)


MEMBRANE_VARIANTS = frozenset({"membrane_md_standard"})


def build_grompp_args(phase: str, variant: str | None, mdp_name: str,
                      input_gro: str, top: str, tpr: str,
                      index: str | None, input_cpt: str | None,
                      maxwarn: int, restraint: str | None = None) -> list[str]:
    """Assemble a grompp command line.

    Membrane phases couple to the Protein_DPPC index group, which only exists
    in index.ndx, so they must pass -n or grompp fails on an unknown group.
    The aqueous sequence has no index file and must not be given -n.

    `restraint` is the -r reference structure, which position restraints have
    required since GROMACS 2018.
    """
    args = ["grompp", "-f", mdp_name, "-c", input_gro]
    if restraint:
        args.extend(["-r", restraint])
    if input_cpt:
        args.extend(["-t", input_cpt])
    args.extend(["-p", top, "-o", tpr])
    if variant in MEMBRANE_VARIANTS and index:
        args.extend(["-n", index])
    args.extend(["-maxwarn", str(maxwarn)])
    return args


def run_phase(workspace_dir: Path, phase: str,
              overrides: dict[str, Any] | None = None) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage2_md"
    render_overrides = dict(overrides or {})
    grompp_maxwarn = int(render_overrides.pop("grompp_maxwarn", 1))
    if "has_protein" not in render_overrides and "tc_grps" not in render_overrides:
        s_for_render = state.read(ws)
        render_overrides["has_protein"] = (
            s_for_render.get("tutorial") or {}
        ).get("has_protein", True)
    # A remediation may swap the template (see MUTATION_BY_CAUSE
    # "lipid_collapse") without renaming the phase: the .tpr, the state key and
    # the coordinate handoff all stay on the phase's own names.
    template = render_overrides.pop("mdp_template", phase)
    mdp_path = MDP.render(template, render_overrides, output_dir=out_dir)
    contract_errors = PC.validate_rendered_mdp(ws, mdp_path, phase)
    if contract_errors:
        raise StateContractError("; ".join(contract_errors))
    state.record_mdp_hash(ws, phase, mdp_path)
    if phase == "nvt":
        seed_match = _GEN_SEED_RE.search(mdp_path.read_text())
        if seed_match:
            state.record_seed(ws, phase, int(seed_match.group(1)))
    variant = (state.read(ws).get("tutorial") or {}).get("variant")
    in_dir_rel, in_gro = phase_input_for(variant, phase)
    in_gro_path = ws / in_dir_rel / in_gro
    top_path = ws / "stage1_env" / "topol.top"
    tpr_path = out_dir / f"{phase}.tpr"
    input_cpt = PHASE_INPUT_CPT.get(phase)
    index_path = ws / "stage1_env" / "index.ndx"
    grompp_args = build_grompp_args(
        phase=phase, variant=variant, mdp_name=mdp_path.name,
        input_gro=str(in_gro_path), top=str(top_path), tpr=tpr_path.name,
        index=str(index_path) if index_path.is_file() else None,
        input_cpt=input_cpt if input_cpt and (out_dir / input_cpt).is_file() else None,
        maxwarn=grompp_maxwarn,
        # Position restraints need an explicit reference structure since
        # GROMACS 2018; without it grompp fails with "Cannot find position
        # restraint file restraint.gro (option -r)". Both tutorials pass the
        # phase's own input coordinates, e.g. `-c em.gro -r em.gro`.
        restraint=str(in_gro_path) if _mdp_defines_restraints(mdp_path) else None,
    )
    grompp_result = GW.run(
        grompp_args,
        cwd=out_dir,
        progress_log=ws / "runner.log",
    )
    _record_grompp_warnings(ws, phase, grompp_result.stdout + grompp_result.stderr)
    if not grompp_result.ok:
        raise RuntimeError(
            f"grompp ({phase}) failed [{grompp_result.classification}]: "
            f"{grompp_result.stderr[-500:]}"
        )
    mdrun_result = GW.run(
        ["mdrun", "-v", "-deffnm", phase, "-ntomp",
         str(state.read(ws)["hardware"]["ntomp"])],
        cwd=out_dir,
        progress_log=ws / "runner.log",
    )
    if not mdrun_result.ok:
        raise RuntimeError(
            f"mdrun ({phase}) failed [{mdrun_result.classification}]: "
            f"{mdrun_result.stderr[-500:]}"
        )
    s = state.read(ws)
    step7 = s["step_outputs"].setdefault("step_7", {})
    step7[PHASE_TO_STATE_KEY[phase]] = f"stage2_md/{phase}.gro"
    s["current_step"] = 7
    phase_seq = step7.setdefault("phase_sequence", [])
    if phase not in phase_seq:
        phase_seq.append(phase)
    state.write(ws, s)


class PhaseFatal(Exception):
    pass


class PhaseRejectedByReview(Exception):
    """Raised when the LLM checkpoint rejects a completed phase."""


MUTATION_BY_CAUSE = {
    "unstable_energy": [{"nsteps": 100}, {"nsteps": 200, "dt": 0.001},
                        {"nsteps": 400, "dt": 0.0005}],
    "pressure_coupling": [{"tau_p": 5.0}, {"tau_p": 8.0}, {"tau_p": 10.0}],
    "temperature_coupling": [{"tau_t": 0.5}, {"tau_t": 1.0}, {"tau_t": 2.0}],
    "command_error": [{"grompp_maxwarn": 2}, {"grompp_maxwarn": 3}, {"grompp_maxwarn": 4}],
    # Membrane equilibration fails in two documented ways: the lipid headgroups
    # collapse inward, or the bilayer separates and a void opens in the
    # hydrophobic core. Both show up as LINCS warnings or a distorted cell.
    # See docs/tutorial/KALP15_in_DPPC/troubleshooting/.
    "lipid_collapse": [
        {"define": "-DPOSRES -DPOSRES_LIPID"},
        {"mdp_template": "anneal_npt", "define": "-DPOSRES -DPOSRES_LIPID"},
    ],
}


def _next_mutation(cause: str, history: list[dict]) -> dict[str, Any]:
    candidates = MUTATION_BY_CAUSE.get(cause, [{}])
    used = sum(1 for e in history if e.get("cause") == cause)
    if used >= len(candidates):
        raise PhaseFatal(f"no mutation candidates remaining for {cause}")
    return candidates[used]


def run_phase_with_recovery(workspace_dir: Path, phase: str,
                            phase_runner=None,
                            overrides: dict[str, Any] | None = None
                            ) -> "V.Judgment":
    """Execute `phase` with RETRYABLE mutation up to 3 attempts."""
    if phase_runner is None:
        phase_runner = _default_phase_runner
    overrides = dict(overrides or {})
    while True:
        s = state.read(workspace_dir)
        budget = V.retryable_budget_remaining(
            s["retry_history"], step=7, phase=phase)
        try:
            judgment = phase_runner(workspace_dir, phase, overrides)
        except RuntimeError as exc:
            judgment = V.Judgment(tier="retryable", metric="execution",
                                  cause="command_error", observed=str(exc))
        if judgment.tier == "pass":
            return judgment
        if judgment.tier == "fatal":
            raise PhaseFatal(f"fatal in phase {phase}: {judgment.cause}")
        if judgment.tier == "warning":
            return judgment   # handled by caller via decision flow
        if judgment.tier == "retryable":
            if budget <= 0:
                raise PhaseFatal(
                    f"retryable budget exhausted in {phase} ({judgment.cause})")
            mutation = _next_mutation(judgment.cause, s["retry_history"])
            s = state.read(workspace_dir)
            s["retry_history"].append({
                "step": 7, "phase": phase, "tier": "retryable",
                "cause": judgment.cause,
                "remediation": str(mutation),
                "command": "phase_runner", "parameters": dict(overrides),
            })
            state.write(workspace_dir, s)
            overrides.update(mutation)
            continue
        raise PhaseFatal(f"unknown tier {judgment.tier}")


def _default_phase_runner(workspace_dir: Path, phase: str,
                           overrides: dict[str, Any]) -> "V.Judgment":
    run_phase(workspace_dir, phase, overrides)
    # Default judgment: PASS. Real validators are wired in Task H6.
    return V.Judgment(tier="pass", metric=phase)


_NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


def _parse_change_value(target: str, change_str: str) -> Any:
    # "2.0 → 5.0" -> 5.0
    if "→" not in change_str and "->" not in change_str:
        return None
    m = _NUM_RE.findall(change_str)
    if not m:
        return change_str
    val = m[-1]
    try:
        return float(val) if "." in val else int(val)
    except ValueError:
        return val


def _record_warning(workspace_dir: Path, phase: str,
                    judgment: V.Judgment) -> dict[str, Any]:
    payload = {
        "warning_id": judgment.warning_id,
        "step": 7, "phase": phase,
        "metric": judgment.metric, "observed": judgment.observed,
        "expected_range": judgment.expected_range,
        "suggested_mutation": judgment.suggested_mutation,
        "cause": judgment.cause,
    }
    s = state.read(workspace_dir)
    s["pending_warnings"].append(payload)
    state.write(workspace_dir, s)
    return payload


def handle_phase_result(workspace_dir: Path, phase: str,
                        judgment: V.Judgment, interactive: bool) -> dict[str, Any]:
    if judgment.tier != "warning":
        return {"status": judgment.tier}
    payload = _record_warning(workspace_dir, phase, judgment)
    if interactive:
        return {"status": "warning_pending_decision",
                "warning_id": payload["warning_id"],
                "payload": payload}
    # auto-decline path
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": 7, "phase": phase, "tier": "warning",
        "cause": "auto_decline_noninteractive",
        "warning_id": payload["warning_id"],
        "remediation": "noninteractive=False; no mutation applied",
    })
    s["pending_warnings"] = [p for p in s["pending_warnings"]
                              if p["warning_id"] != payload["warning_id"]]
    state.write(workspace_dir, s)
    return {"status": "warning_declined",
            "warning_id": payload["warning_id"]}


def _apply_review_outcome(workspace_dir: Path, phase: str, judgment: V.Judgment,
                          overrides: dict[str, Any]) -> V.Judgment:
    """Call the LLM checkpoint for a just-completed phase and act on its
    verdict. Returns the judgment to proceed with — either the original one,
    or the judgment from a retried phase run if the LLM accepted a suggested
    mutation."""
    xvg_summary = {"metric": judgment.metric, "observed": judgment.observed,
                   "expected_range": judgment.expected_range}
    verdict = llm_assist.review_md_phase(
        phase, asdict(judgment), xvg_summary, overrides)
    if not verdict.proceed:
        raise PhaseRejectedByReview(
            f"LLM review rejected phase '{phase}' (tier={judgment.tier}): "
            f"{verdict.diagnosis}"
        )
    if judgment.tier != "warning":
        return judgment
    s = state.read(workspace_dir)
    if verdict.accept_mutation:
        mutation = judgment.suggested_mutation or {}
        new_overrides = dict(overrides)
        for k, v in (mutation.get("changes") or {}).items():
            parsed = _parse_change_value(mutation.get("target", ""), str(v))
            if parsed is None:
                continue
            new_overrides[k] = parsed
        s["retry_history"].append({
            "step": 7, "phase": phase, "tier": "warning", "cause": judgment.cause,
            "warning_id": judgment.warning_id,
            "remediation": f"llm_accepted: {new_overrides}",
        })
        state.write(workspace_dir, s)
        return run_phase_with_recovery(
            workspace_dir, phase=phase,
            phase_runner=_validating_phase_runner,
            overrides=new_overrides,
        )
    s["retry_history"].append({
        "step": 7, "phase": phase, "tier": "warning", "cause": "llm_declined",
        "warning_id": judgment.warning_id,
        "remediation": "llm declined; proceeding to next step",
    })
    state.write(workspace_dir, s)
    return judgment


def _pop_warning(workspace_dir: Path, warning_id: str) -> dict[str, Any] | None:
    s = state.read(workspace_dir)
    remaining = []
    found = None
    for p in s["pending_warnings"]:
        if p["warning_id"] == warning_id and found is None:
            found = p
        else:
            remaining.append(p)
    if found is None:
        return None
    s["pending_warnings"] = remaining
    state.write(workspace_dir, s)
    return found


def accept_warning(workspace_dir: Path, warning_id: str) -> dict[str, Any]:
    payload = _pop_warning(workspace_dir, warning_id)
    if not payload:
        raise KeyError(f"warning_id not found: {warning_id}")
    mutation = payload["suggested_mutation"] or {}
    overrides: dict[str, Any] = {}
    for k, v in (mutation.get("changes") or {}).items():
        parsed = _parse_change_value(mutation.get("target", ""), str(v))
        if parsed is None:
            continue
        overrides[k] = parsed
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": payload["step"], "phase": payload["phase"],
        "tier": "warning", "cause": payload["cause"],
        "warning_id": warning_id,
        "remediation": f"accepted: {overrides}",
    })
    state.write(workspace_dir, s)
    return overrides


def decline_warning(workspace_dir: Path, warning_id: str) -> None:
    payload = _pop_warning(workspace_dir, warning_id)
    if not payload:
        raise KeyError(f"warning_id not found: {warning_id}")
    s = state.read(workspace_dir)
    s["retry_history"].append({
        "step": payload["step"], "phase": payload["phase"],
        "tier": "warning", "cause": "user_decline",
        "warning_id": warning_id,
        "remediation": "user declined; proceeding to next step",
    })
    state.write(workspace_dir, s)


def _validate_phase(workspace_dir: Path, phase: str) -> V.Judgment:
    """Run gmx energy on the .edr and judge the most relevant metric."""
    ws = Path(workspace_dir)
    edr = ws / "stage2_md" / f"{phase}.edr"
    if not edr.exists():
        return V.Judgment(tier="pass", metric=phase)  # nothing to inspect
    # request density for npt, temperature for nvt, potential for em/production
    if phase == "nvt":
        return _judge_temperature(workspace_dir, phase)
    if phase in ("npt", "npt_pr"):
        return _judge_density(workspace_dir, phase)
    if phase in ("production", "umbrella", "free_energy"):
        return _judge_energy_drift(workspace_dir, phase)
    return V.Judgment(tier="pass", metric=phase)


def _gmx_energy(workspace_dir: Path, phase: str, term: str,
                out_xvg: str) -> Path:
    out_dir = Path(workspace_dir) / "stage2_md"
    GW.run(["energy", "-f", f"{phase}.edr", "-o", out_xvg],
           cwd=out_dir, interactive_inputs=[term, ""])
    return out_dir / out_xvg


def _judge_temperature(ws: Path, phase: str) -> V.Judgment:
    xvg = _gmx_energy(ws, phase, "Temperature", f"{phase}_temp.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] == 0:
        return V.Judgment(tier="pass", metric="temperature")
    return V.judge_temperature(observed=summary["mean"], target=300.0)


# Expected bulk-density ranges (kg/m^3) by tutorial pipeline variant. `None`
# means "skip the density gate" — the system is not a single-phase aqueous
# bulk, so a single expected-density window does not apply (e.g. membranes
# have a heterogeneous lipid/water density profile; biphasic systems have an
# immiscible interface with no single bulk density).
DENSITY_RANGE_BY_VARIANT: dict[str, tuple[float, float] | None] = {
    "protein_aqueous_standard": (995.0, 1005.0),
    "protein_ligand_complex": (995.0, 1005.0),
    "umbrella_sampling": (995.0, 1005.0),
    "free_energy_alchemical": (995.0, 1005.0),
    "membrane_md_standard": None,
    "biphasic_system": None,
    "virtual_sites_topology": None,
}


def _density_expected_range(ws: Path) -> tuple[float, float] | None:
    s = state.read(ws)
    variant = (s.get("tutorial") or {}).get("variant")
    if variant in DENSITY_RANGE_BY_VARIANT:
        return DENSITY_RANGE_BY_VARIANT[variant]
    return (995.0, 1005.0)  # unknown variant: default to water-like assumption


def _judge_density(ws: Path, phase: str) -> V.Judgment:
    expected_range = _density_expected_range(ws)
    if expected_range is None:
        return V.Judgment(tier="pass", metric="density",
                           cause="density_gate_not_applicable_for_system_type")
    xvg = _gmx_energy(ws, phase, "Density", f"{phase}_dens.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] == 0:
        return V.Judgment(tier="pass", metric="density")
    return V.judge_density(observed=summary["mean"],
                           expected_range=expected_range)


def _linregress_slope_per_ns(time_ps: list[float], y: list[float]) -> float:
    """Linear-regression slope of y vs time (time_ps assumed in ps, as
    reported by `gmx energy`), returned in units of [y] per ns."""
    if len(time_ps) < 2:
        return 0.0
    time_ns = [t / 1000.0 for t in time_ps]
    n = len(time_ns)
    mean_x = sum(time_ns) / n
    mean_y = sum(y) / n
    num = sum((x - mean_x) * (yy - mean_y) for x, yy in zip(time_ns, y))
    den = sum((x - mean_x) ** 2 for x in time_ns)
    if den == 0:
        return 0.0
    return num / den


def _judge_energy_drift(ws: Path, phase: str) -> V.Judgment:
    # Total energy (kinetic + potential), not potential alone, is the
    # quantity whose long-term drift indicates integrator instability.
    xvg = _gmx_energy(ws, phase, "Total-Energy", f"{phase}_total.xvg")
    summary = xvg_parser.summary(xvg)
    if summary["count"] < 2:
        return V.Judgment(tier="pass", metric="energy_drift")
    # Slope of total energy (kJ/mol) vs simulation time (ns), via linear
    # regression over the full series (not just first/last frame count).
    parsed = xvg_parser.parse(xvg, max_points=100000)
    cols = parsed["columns"]
    slope = _linregress_slope_per_ns(cols[0], cols[1])
    return V.judge_energy_drift(slope_per_ns=slope)


def _validating_phase_runner(workspace_dir: Path, phase: str,
                              overrides: dict[str, Any]) -> V.Judgment:
    run_phase(workspace_dir, phase, overrides)
    return _validate_phase(workspace_dir, phase)


def _free_energy_directives(item: dict[str, Any], couple_moltype: str) -> str:
    """MDP directives shared by every lambda-specific phase."""
    return "\n".join((
        "free_energy = yes",
        f"init_lambda_state = {item['init_lambda_state']}",
        "coul_lambdas = " + " ".join(map(str, item["coul_lambdas"])),
        "vdw_lambdas = " + " ".join(map(str, item["vdw_lambdas"])),
        f"couple_moltype = {couple_moltype}",
        "couple_lambda0 = vdw-q",
        "couple_lambda1 = none",
        "couple_intramol = no",
        "nstdhdl = 100",
        "",
    ))


def _run_local_phase(workspace_dir: Path, phase: str, out_dir: Path,
                     input_gro: Path, overrides: dict[str, Any],
                     input_cpt: Path | None = None,
                     index: Path | None = None,
                     free_energy: dict[str, Any] | None = None) -> Path:
    """Run a phase in an isolated workflow directory without global state writes."""
    ws, out_dir = Path(workspace_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template_phase = "free_energy" if phase == "free_energy" else phase
    render_overrides = dict(overrides)
    if free_energy and phase == "free_energy":
        item = free_energy["item"]
        render_overrides.update({
            "init_lambda_state": item["init_lambda_state"],
            "coul_lambdas": " ".join(map(str, item["coul_lambdas"])),
            "vdw_lambdas": " ".join(map(str, item["vdw_lambdas"])),
            "couple_moltype": free_energy["couple_moltype"],
        })
    mdp = MDP.render(template_phase, render_overrides, out_dir)
    if free_energy and phase != "free_energy":
        mdp.write_text(mdp.read_text() + _free_energy_directives(
            free_energy["item"], free_energy["couple_moltype"]
        ))
    args = ["grompp", "-f", mdp.name, "-c", str(input_gro),
            "-p", str(ws / "stage1_env" / "topol.top"), "-o", f"{phase}.tpr"]
    if input_cpt and input_cpt.is_file():
        args.extend(["-t", str(input_cpt)])
    if index:
        args.extend(["-n", str(index)])
    grompp = GW.run(args, cwd=out_dir, progress_log=ws / "runner.log")
    if not grompp.ok:
        raise RuntimeError(f"grompp ({phase}) failed [{grompp.classification}]: {grompp.stderr[-500:]}")
    ntomp = str((state.read(ws).get("hardware") or {}).get("ntomp", 1))
    mdrun = GW.run(["mdrun", "-v", "-deffnm", phase, "-ntomp", ntomp], cwd=out_dir,
                   progress_log=ws / "runner.log")
    if not mdrun.ok:
        raise RuntimeError(f"mdrun ({phase}) failed [{mdrun.classification}]: {mdrun.stderr[-500:]}")
    return out_dir / f"{phase}.gro"


def run_free_energy_workflow(workspace_dir: Path, workflow: dict[str, Any]) -> dict[str, Any]:
    """Run independent EM→NVT→NPT→production calculations for each lambda."""
    ws = Path(workspace_dir)
    coordinate = ws / workflow["coordinate"]
    if not coordinate.is_file():
        raise StateContractError(f"free-energy coordinate missing: {workflow['coordinate']}")
    completed: list[str] = []
    for item in workflow["lambda_schedule"]:
        ident = item["id"]
        out = ws / "stage2_md" / f"lambda_{ident}"
        final = out / "free_energy.gro"
        if final.is_file():
            completed.append(ident)
            continue
        common = {"has_protein": False}
        fep = {"item": item, "couple_moltype": workflow["couple_moltype"]}
        em = _run_local_phase(ws, "em", out, coordinate, common, free_energy=fep)
        nvt = _run_local_phase(ws, "nvt", out, em, common, free_energy=fep)
        npt = _run_local_phase(ws, "npt", out, nvt, common, out / "nvt.cpt", free_energy=fep)
        _run_local_phase(ws, "free_energy", out, npt, common, out / "npt.cpt", free_energy=fep)
        completed.append(ident)
    s = state.read(ws)
    step7 = s["step_outputs"].setdefault("step_7", {})
    step7["free_energy_lambdas"] = completed
    s["current_step"] = 7
    state.write(ws, s)
    return {"completed_lambdas": completed}


def run_umbrella_workflow(workspace_dir: Path, workflow: dict[str, Any]) -> dict[str, Any]:
    """Run independent NPT and restrained-production phases for every window."""
    ws = Path(workspace_dir)
    index = ws / workflow.get("index", "")
    if not index.is_file():
        raise StateContractError("umbrella index file missing")
    completed: list[str] = []
    for window in workflow["windows"]:
        ident = window["id"]
        coordinate = ws / window["coordinate"]
        if not coordinate.is_file():
            raise StateContractError(f"umbrella window coordinate missing: {window['coordinate']}")
        out = ws / "stage2_md" / "umbrella" / f"window_{ident}"
        final = out / "umbrella.gro"
        if final.is_file():
            completed.append(ident)
            continue
        npt = _run_local_phase(ws, "npt", out, coordinate, {"has_protein": True}, index=index)
        _run_local_phase(ws, "umbrella", out, npt, {
            "pull_group1": workflow["group1"], "pull_group2": workflow["group2"],
            "pull_coord_k": window.get("force_constant", 1000.0),
        }, out / "npt.cpt", index=index)
        completed.append(ident)
    s = state.read(ws)
    step7 = s["step_outputs"].setdefault("step_7", {})
    step7["umbrella_windows"] = completed
    s["current_step"] = 7
    state.write(ws, s)
    return {"completed_windows": completed}


def run_simulation(workspace_dir: Path,
                   phase_overrides: dict[str, dict[str, Any]] | None = None,
                   interactive: bool = True,
                   accept_warning_id: str | None = None,
                   decline_warning_id: str | None = None) -> dict[str, Any]:
    if accept_warning_id:
        ov = accept_warning(workspace_dir, accept_warning_id)
        # caller is expected to also supply the phase via phase_overrides
        return {"status": "warning_accepted", "applied_overrides": ov}
    if decline_warning_id:
        decline_warning(workspace_dir, decline_warning_id)
        return {"status": "warning_declined"}

    s = assert_ready(workspace_dir)
    variant = (s.get("tutorial") or {}).get("variant")
    if variant == "free_energy_alchemical":
        workflow = ((load_config(Path(workspace_dir)) or {}).get("advanced_workflow") or {}).get("free_energy")
        if not workflow:
            raise StateContractError("advanced_workflow.free_energy is required")
        result = run_free_energy_workflow(workspace_dir, workflow)
        s = state.read(workspace_dir)
        s["last_completed_stage"] = "md"
        state.write(workspace_dir, s)
        return {"status": "complete", **result}
    if variant == "umbrella_sampling":
        workflow = ((load_config(Path(workspace_dir)) or {}).get("advanced_workflow") or {}).get("umbrella")
        if not workflow:
            raise StateContractError("advanced_workflow.umbrella is required")
        result = run_umbrella_workflow(workspace_dir, workflow)
        s = state.read(workspace_dir)
        s["last_completed_stage"] = "md"
        state.write(workspace_dir, s)
        return {"status": "complete", **result}
    seq = phase_sequence_for_variant(variant)
    phase_overrides = phase_overrides or {}
    completed_phases = set(
        (s.get("step_outputs", {}).get("step_7", {}) or {}).get(
            "phase_sequence", []
        )
    )
    for phase in seq:
        # An interrupted caller can resume from a finished phase without
        # overwriting its coordinates or rerunning an equivalent command.
        if phase in completed_phases and (Path(workspace_dir) / "stage2_md" / f"{phase}.gro").exists():
            continue
        # Explicit System Builder controls are part of the protocol contract
        # and take precedence over caller/agent overrides.  This makes an
        # attempted LLM parameter change observable as a contract violation
        # rather than a silent scientific deviation.
        requested_overrides = {
            **phase_overrides.get(phase, {}),
            **PC.phase_overrides(workspace_dir, phase),
        }
        if variant == "membrane_md_standard" and phase in ("npt", "npt_pr", "production"):
            requested_overrides["pcoupltype"] = "semiisotropic"
            requested_overrides["ref_p_list"] = "1.0 1.0"
            requested_overrides["compressibility_list"] = "4.5e-5 4.5e-5"
            # build_index's own groups (skills/env_builder/membrane_assembly.py),
            # matching the tutorial's own mdp files. The default "Protein
            # Non-Protein" needs no index file, which left -n inert.
            requested_overrides["tc_grps"] = "Protein_DPPC Water_and_ions"
        judgment = run_phase_with_recovery(
            workspace_dir, phase=phase,
            phase_runner=_validating_phase_runner,
            overrides=requested_overrides,
        )
        _apply_review_outcome(workspace_dir, phase, judgment, requested_overrides)
    s = state.read(workspace_dir)
    s["last_completed_stage"] = "md"
    state.write(workspace_dir, s)
    return {"status": "complete"}
