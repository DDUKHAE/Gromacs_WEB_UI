# skills/md_runner/md_runner.py
from pathlib import Path
from typing import Any
from lib import state
from lib.state import StateContractError
from lib import gmx_wrapper as GW
from lib.mdp_templates import base as MDP


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
