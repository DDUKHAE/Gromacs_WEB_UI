# lib/mdp_templates/base.py
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent

DEFAULTS = {
    "em": {"emtol": 1000.0, "emstep": 0.01, "nsteps": 50000},
    "nvt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0},
    "npt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0, "tau_p": 2.0,
            # Initial equilibration: Berendsen (or C-rescale) barostat is
            # recommended before switching to Parrinello-Rahman, which can
            # oscillate wildly when started far from equilibrium.
            "pcoupl": "Berendsen"},
    "production": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
                    "tau_p": 2.0,
                    # Production runs from an already-equilibrated NPT state,
                    # so Parrinello-Rahman (correct NPT ensemble sampling) is
                    # appropriate here.
                    "pcoupl": "Parrinello-Rahman"},
    "ions": {},
    "umbrella": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.5, "ref_t": 300.0,
                  "tau_p": 2.0, "pull_group1": "Chain_A", "pull_group2": "Chain_B",
                  "pull_coord_init": 0.0, "pull_coord_k": 1000.0},
    "free_energy": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.5, "ref_t": 300.0,
                     "tau_p": 2.0, "init_lambda_state": 0,
                     "coul_lambdas": "0.0 0.25 0.5 0.75 1.0",
                     "vdw_lambdas": "0.0 0.25 0.5 0.75 1.0",
                     "couple_moltype": "LIG"},
}

_FILES = {
    "em": "em.mdp",
    "nvt": "nvt.mdp",
    "npt": "npt.mdp",
    "production": "production.mdp",
    "ions": "ions.mdp",
    "umbrella": "umbrella.mdp",
    "free_energy": "free_energy.mdp",
}


_TC_GRPS_PHASES = ("nvt", "npt", "production")


def render(phase: str, overrides: dict[str, Any], output_dir: Path) -> Path:
    if phase not in _FILES:
        raise KeyError(f"unknown template: {phase}")
    template = (_DIR / _FILES[phase]).read_text()
    params = {**DEFAULTS[phase], **overrides}
    if phase in _TC_GRPS_PHASES:
        # tc-grps must reflect the actual system composition: "Protein
        # Non-Protein" only exists as an index group when there is a
        # protein. Protein-free systems (Methane/Ethanol hydration,
        # biphasic boxes, etc.) must couple the whole system instead, or
        # grompp fails outright with an unknown group error.
        has_protein = params.pop("has_protein", True)
        tc_grps = params.pop("tc_grps", None)
        if tc_grps is None:
            tc_grps = "Protein Non-Protein" if has_protein else "System"
        n_groups = max(1, len(tc_grps.split()))
        params["tc_grps"] = tc_grps
        params["tau_t_list"] = " ".join([str(params["tau_t"])] * n_groups)
        params["ref_t_list"] = " ".join([str(params["ref_t"])] * n_groups)
    content = template.format(**params) if params else template
    out = Path(output_dir) / f"{phase}.mdp"
    out.write_text(content)
    return out
