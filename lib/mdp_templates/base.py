# lib/mdp_templates/base.py
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent

DEFAULTS = {
    "em": {"emtol": 1000.0, "emstep": 0.01, "nsteps": 50000},
    "nvt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0},
    "npt": {"nsteps": 50000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0, "tau_p": 2.0},
    "production": {"nsteps": 500000, "dt": 0.002, "tau_t": 0.1, "ref_t": 300.0,
                    "tau_p": 2.0},
    "ions": {},
}

_FILES = {
    "em": "em.mdp",
    "nvt": "nvt.mdp",
    "npt": "npt.mdp",
    "production": "production.mdp",
    "ions": "ions.mdp",
}


def render(phase: str, overrides: dict[str, Any], output_dir: Path) -> Path:
    if phase not in _FILES:
        raise KeyError(f"unknown template: {phase}")
    template = (_DIR / _FILES[phase]).read_text()
    params = {**DEFAULTS[phase], **overrides}
    content = template.format(**params) if params else template
    out = Path(output_dir) / f"{phase}.mdp"
    out.write_text(content)
    return out
