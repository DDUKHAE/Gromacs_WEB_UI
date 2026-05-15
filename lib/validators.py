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


NEUTRALITY_WARNING_TOL = 0.1
NEUTRALITY_FATAL_TOL = 0.5
DENSITY_WARNING_FRAC = 0.02
DENSITY_RETRYABLE_FRAC = 0.10


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
