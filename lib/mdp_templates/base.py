# lib/mdp_templates/base.py
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent

# Fixed seed used when a caller opts into "reproducible mode" for velocity
# generation (gen_vel) instead of the production default of gen_seed=-1
# (GROMACS draws a fresh random seed each run, which is scientifically
# correct for production sampling but non-reproducible bit-for-bit). Any
# integer works; this one is just a stable, documented convention.
REPRODUCIBLE_SEED = 20240101

DEFAULTS = {
    # coulombtype/rcoulomb/rvdw were hardcoded in em.mdp; they are parameters so
    # the membrane assembly's packing minimisations can use the plain cut-off the
    # KALP-15/DPPC tutorial specifies. The defaults are the previous literals, so
    # every other caller renders byte-identically.
    "em": {"emtol": 1000.0, "emstep": 0.01, "nsteps": 50000, "define": "",
           "coulombtype": "PME", "rcoulomb": 1.0, "rvdw": 1.0},
    "nvt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
            "gen_seed": -1, "define": "-DPOSRES"},
    "npt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0, "tau_p": 2.0,
            # Initial equilibration: Berendsen (or C-rescale) barostat is
            # recommended before switching to Parrinello-Rahman, which can
            # oscillate wildly when started far from equilibrium.
            "pcoupl": "Berendsen", "pcoupltype": "isotropic", "define": "-DPOSRES"},
    # Keep the second NPT stage distinct. Reusing the ``npt`` name would
    # overwrite files and make a restart falsely appear to have completed
    # both barostat stages.
    "npt_pr": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
               "tau_p": 2.0, "pcoupl": "Parrinello-Rahman", "pcoupltype": "isotropic", "define": "-DPOSRES"},
    "production": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
                    "tau_p": 2.0,
                    # Production runs from an already-equilibrated NPT state,
                    # so Parrinello-Rahman (correct NPT ensemble sampling) is
                    # appropriate here.
                    "pcoupl": "Parrinello-Rahman", "pcoupltype": "isotropic"},
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

# Common MDP controls intentionally exposed by the System Builder.  Keeping
# them in template defaults makes a user choice executable rather than merely
# an instruction in an LLM prompt.
for _phase in ("nvt", "npt", "npt_pr", "production"):
    DEFAULTS[_phase].update({
        "constraint_algorithm": "lincs", "constraints": "h-bonds",
        "rcoulomb": 1.0, "rvdw": 1.0, "coulombtype": "PME",
        "pme_order": 4, "fourierspacing": 0.16, "tcoupl": "V-rescale",
    })
for _phase in ("npt", "npt_pr", "production"):
    DEFAULTS[_phase]["ref_p"] = 1.0

_FILES = {
    "em": "em.mdp",
    "nvt": "nvt.mdp",
    "npt": "npt.mdp",
    "npt_pr": "npt.mdp",
    "production": "production.mdp",
    "ions": "ions.mdp",
    "umbrella": "umbrella.mdp",
    "free_energy": "free_energy.mdp",
}


_TC_GRPS_PHASES = ("nvt", "npt", "npt_pr", "production")


def render(phase: str, overrides: dict[str, Any], output_dir: Path) -> Path:
    if phase not in _FILES:
        raise KeyError(f"unknown template: {phase}")
    template = (_DIR / _FILES[phase]).read_text()
    params = {**DEFAULTS[phase], **overrides}
    if phase == "nvt":
        # "reproducible_mode" is a render-time flag, not an mdp key: it picks
        # a fixed, documented gen_seed for reproducible velocity generation.
        # An explicit gen_seed override always wins over reproducible_mode.
        reproducible_mode = params.pop("reproducible_mode", False)
        if reproducible_mode and "gen_seed" not in overrides:
            params["gen_seed"] = REPRODUCIBLE_SEED
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
    if "nsteps" in params:
        try:
            nsteps_val = int(params["nsteps"])
            interval = max(1, min(5000, nsteps_val // 50))
            params.setdefault("nstenergy", interval)
            params.setdefault("nstlog", interval)
            params.setdefault("nstxout_compressed", interval)
        except (ValueError, TypeError):
            params.setdefault("nstenergy", 500)
            params.setdefault("nstlog", 500)
            params.setdefault("nstxout_compressed", 500)
    content = template.format(**params) if params else template
    out = Path(output_dir) / f"{phase}.mdp"
    out.write_text(content)
    return out
