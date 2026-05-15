# skills/md_runner/md_runner.py
from pathlib import Path
from typing import Any
from dataclasses import dataclass
import re
from lib import state
from lib.state import StateContractError
from lib import gmx_wrapper as GW
from lib.mdp_templates import base as MDP
from lib import validators as V
from lib import xvg_parser


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
    return s


PHASE_SEQUENCES = {
    "protein_aqueous_standard": ["em", "nvt", "npt", "production"],
    "membrane_md_standard": ["em", "nvt", "npt", "npt", "production"],
    "protein_ligand_complex": ["em", "nvt", "npt", "production"],
    "umbrella_sampling": ["em", "nvt", "npt", "umbrella"],
    "free_energy_alchemical": ["em", "nvt", "npt", "free_energy"],
    "biphasic_system": ["em", "nvt", "npt", "production"],
    "virtual_sites_topology": ["em", "production"],
}


def phase_sequence_for_variant(variant: str | None) -> list[str]:
    return PHASE_SEQUENCES.get(variant or "", ["em", "nvt", "npt", "production"])


PHASE_INPUT_GRO = {
    "em":         ("stage1_env", "ions.gro"),
    "nvt":        ("stage2_md", "em.gro"),
    "npt":        ("stage2_md", "nvt.gro"),
    "production": ("stage2_md", "npt.gro"),
    "umbrella":   ("stage2_md", "npt.gro"),
    "free_energy":("stage2_md", "npt.gro"),
}

PHASE_TO_STATE_KEY = {
    "em": "em_gro", "nvt": "nvt_gro", "npt": "npt_gro",
    "production": "production_gro",
    "umbrella": "production_gro", "free_energy": "production_gro",
}


def run_phase(workspace_dir: Path, phase: str,
              overrides: dict[str, Any] | None = None) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage2_md"
    mdp_path = MDP.render(phase, overrides or {}, output_dir=out_dir)
    in_dir_rel, in_gro = PHASE_INPUT_GRO[phase]
    in_gro_path = ws / in_dir_rel / in_gro
    top_path = ws / "stage1_env" / "topol.top"
    tpr_path = out_dir / f"{phase}.tpr"
    grompp_result = GW.run(
        ["grompp", "-f", mdp_path.name,
         "-c", str(in_gro_path),
         "-p", str(top_path),
         "-o", tpr_path.name, "-maxwarn", "2"],
        cwd=out_dir,
    )
    if not grompp_result.ok:
        raise RuntimeError(
            f"grompp ({phase}) failed [{grompp_result.classification}]: "
            f"{grompp_result.stderr[-500:]}"
        )
    mdrun_result = GW.run(
        ["mdrun", "-deffnm", phase, "-ntomp",
         str(state.read(ws)["hardware"]["ntomp"])],
        cwd=out_dir,
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
    state.write(ws, s)


class PhaseFatal(Exception):
    pass


MUTATION_BY_CAUSE = {
    "unstable_energy": [{"nsteps": 100}, {"nsteps": 200, "dt": 0.001},
                        {"nsteps": 400, "dt": 0.0005}],
    "pressure_coupling": [{"tau_p": 5.0}, {"tau_p": 8.0}, {"tau_p": 10.0}],
    "temperature_coupling": [{"tau_t": 0.5}, {"tau_t": 1.0}, {"tau_t": 2.0}],
    "command_error": [{"-maxwarn": 2}, {"-maxwarn": 3}, {"-maxwarn": 4}],
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
        judgment = phase_runner(workspace_dir, phase, overrides)
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
        overrides[k] = _parse_change_value(mutation.get("target", ""), str(v))
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
