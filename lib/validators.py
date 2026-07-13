import statistics
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Judgment:
    tier: str  # "pass" | "warning" | "retryable" | "fatal"
    metric: str
    observed: Any = None
    expected_range: tuple[float, float] | None = None
    cause: str | None = None
    suggested_mutation: dict[str, Any] | None = None
    warning_id: str = field(default="")

    def __post_init__(self):
        if self.tier == "warning" and not self.warning_id:
            self.warning_id = str(uuid.uuid4())



class RetryContractError(Exception):
    """Raised when an attempt would violate the no-identical-retry rule."""

NEUTRALITY_WARNING_TOL = 0.1
NEUTRALITY_FATAL_TOL = 0.5
DENSITY_WARNING_FRAC = 0.02
DENSITY_RETRYABLE_FRAC = 0.10
TEMP_WARNING_K = 3.0
TEMP_RETRYABLE_K = 10.0
# Thresholds are for the *total* energy (kinetic + potential) linear-regression
# slope over simulation time, in kJ/mol per ns. Total energy (not potential
# energy) is the quantity that should be conserved/stable under NVT/NPT
# integration; potential energy alone routinely drifts with thermostat/
# barostat action and is not a valid integrator-stability signal.
# NOTE: these are coarse absolute thresholds and are not normalized by system
# size (atom count); a large solvated system will naturally show larger
# absolute total-energy fluctuation than a small one for the same per-atom
# stability. Treat as a blunt fatal-instability filter, not a precision gate.
ENERGY_DRIFT_WARNING = 10.0   # kJ/mol per ns
ENERGY_DRIFT_RETRY = 100.0
RMSD_PLATEAU_MAX_RANGE = 0.05  # nm tail-half range threshold
RETRYABLE_MAX = 3


def judge_neutrality(net_charge: float) -> Judgment:
    abs_q = abs(net_charge)
    if abs_q < 1e-6:
        return Judgment(tier="pass", metric="net_charge", observed=net_charge)
    if abs_q <= NEUTRALITY_WARNING_TOL:
        return Judgment(
            tier="warning",
            metric="net_charge",
            observed=net_charge,
            cause="charge_neutralization",
            suggested_mutation={
                "target": "genion",
                "changes": {"-conc": "0.15 → 0.20"},
                "rationale": "increase ion concentration to neutralize residual charge",
            },
        )
    if abs_q <= NEUTRALITY_FATAL_TOL:
        return Judgment(
            tier="retryable",
            metric="net_charge",
            observed=net_charge,
            cause="charge_neutralization",
        )
    return Judgment(tier="fatal", metric="net_charge", observed=net_charge,
                    cause="charge_neutralization")


def judge_density(observed: float, expected_range: tuple[float, float]) -> Judgment:
    lo, hi = expected_range
    center = (lo + hi) / 2
    if lo <= observed <= hi:
        return Judgment(tier="pass", metric="density", observed=observed,
                        expected_range=expected_range)
    deviation = abs(observed - center) / center
    if deviation <= DENSITY_RETRYABLE_FRAC and deviation > DENSITY_WARNING_FRAC:
        return Judgment(
            tier="warning",
            metric="density",
            observed=observed,
            expected_range=expected_range,
            cause="pressure_coupling",
            suggested_mutation={
                "target": "npt.mdp",
                "changes": {"tau_p": "2.0 → 5.0"},
                "rationale": "barostat coupling too tight; relax to re-equilibrate density",
            },
        )
    if deviation <= DENSITY_WARNING_FRAC:
        return Judgment(
            tier="warning", metric="density", observed=observed,
            expected_range=expected_range, cause="pressure_coupling",
            suggested_mutation={
                "target": "npt.mdp",
                "changes": {"tau_p": "2.0 → 3.0"},
                "rationale": "minor density drift; modest barostat relaxation",
            },
        )
    return Judgment(tier="retryable", metric="density", observed=observed,
                    expected_range=expected_range, cause="pressure_coupling")


def judge_temperature(observed: float, target: float) -> Judgment:
    dev = abs(observed - target)
    if dev <= TEMP_WARNING_K:
        return Judgment(tier="pass", metric="temperature", observed=observed)
    if dev <= TEMP_RETRYABLE_K:
        return Judgment(
            tier="warning", metric="temperature", observed=observed,
            cause="temperature_coupling",
            suggested_mutation={
                "target": "nvt.mdp",
                "changes": {"tau_t": "0.1 → 0.5"},
                "rationale": "thermostat too tight; relax tau_t",
            },
        )
    return Judgment(tier="retryable", metric="temperature", observed=observed,
                    cause="temperature_coupling")


def judge_energy_drift(slope_per_ns: float) -> Judgment:
    """slope_per_ns must be the linear-regression slope of TOTAL energy
    (kJ/mol) vs simulation time (ns) — not potential energy, not per-frame."""
    s = abs(slope_per_ns)
    if s <= ENERGY_DRIFT_WARNING:
        return Judgment(tier="pass", metric="energy_drift", observed=slope_per_ns)
    if s <= ENERGY_DRIFT_RETRY:
        return Judgment(
            tier="warning", metric="energy_drift", observed=slope_per_ns,
            cause="unstable_energy",
            suggested_mutation={
                "target": "production.mdp",
                "changes": {"dt": "0.002 → 0.001"},
                "rationale": "energy drift positive; shorten timestep",
            },
        )
    return Judgment(tier="retryable", metric="energy_drift", observed=slope_per_ns,
                    cause="unstable_energy")


def judge_rmsd_plateau(rmsd_series: list[float]) -> Judgment:
    if len(rmsd_series) < 4:
        return Judgment(tier="warning", metric="rmsd_plateau",
                        observed=len(rmsd_series),
                        cause="analysis_not_converged")
    tail = rmsd_series[len(rmsd_series) // 2:]
    spread = max(tail) - min(tail)
    if spread <= RMSD_PLATEAU_MAX_RANGE:
        return Judgment(tier="pass", metric="rmsd_plateau", observed=spread)
    return Judgment(
        tier="warning", metric="rmsd_plateau", observed=spread,
        cause="analysis_not_converged",
        suggested_mutation={
            "target": "production.mdp",
            "changes": {"nsteps": "extend by 50%"},
            "rationale": "RMSD has not plateaued; extend sampling",
        },
    )


def assert_unique_attempt(history: list[dict[str, Any]], command: str,
                          parameters: dict[str, Any]) -> None:
    for entry in history:
        if entry.get("command") == command and entry.get("parameters") == parameters:
            raise RetryContractError(
                f"retry must mutate command/parameters; identical attempt found "
                f"(cause={entry.get('cause')})"
            )


def retryable_budget_remaining(history: list[dict[str, Any]],
                               step: int, phase: str) -> int:
    used = sum(
        1 for e in history
        if e.get("step") == step
        and e.get("phase") == phase
        and e.get("tier") == "retryable"
    )
    return max(0, RETRYABLE_MAX - used)
