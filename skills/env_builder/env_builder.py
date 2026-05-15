"""env-builder skill — Step 0–5 of the GROMACS pipeline."""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lib import state
from lib import tutorial_registry as TR
from lib import gmx_wrapper as GW
from lib.mdp_templates import base as MDP


class UnsupportedTutorialError(Exception):
    pass


def init_workspace(workspace_dir: Path) -> None:
    workspace_dir = Path(workspace_dir)
    for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
        (workspace_dir / sub).mkdir(parents=True, exist_ok=True)
    if not state.path(workspace_dir).exists():
        state.write(workspace_dir, state.initial(workspace_dir))


def _detect_gpu_ids() -> list[int]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            text=True, timeout=10,
        )
        return [int(x.strip()) for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def collect_hardware(workspace_dir: Path) -> None:
    cpu = os.cpu_count() or 1
    gpus = _detect_gpu_ids()
    ntomp = max(1, cpu // max(1, len(gpus) or 1))
    s = state.read(workspace_dir)
    s["hardware"] = {"cpu_count": cpu, "gpu_ids": gpus, "ntomp": ntomp}
    state.write(workspace_dir, s)


def _pdb_hints(pdb_path: Path) -> dict[str, bool]:
    text = Path(pdb_path).read_text()
    return {
        "has_protein": "ATOM" in text and any(
            res in text for res in ("ALA", "GLY", "LEU", "VAL", "ILE")),
        "has_membrane": any(
            lipid in text for lipid in ("DPPC", "POPC", "DMPC", "DOPC")),
        "has_ligand": "HETATM" in text,
    }


def select_tutorial(workspace_dir: Path, pdb_path: Path,
                    prompt: str, prerequisites: dict[str, Any]) -> TR.RoutingDecision:
    hints = _pdb_hints(pdb_path)
    decision = TR.route(prompt=prompt, pdb_hints=hints, prerequisites=prerequisites)
    if decision.unsupported_reason:
        raise UnsupportedTutorialError(decision.unsupported_reason)
    s = state.read(workspace_dir)
    s["tutorial"] = {
        "id": decision.tutorial_id,
        "variant": decision.pipeline_variant,
        "manifest_path": (
            f"docs/tutorial/{decision.tutorial_id}/tutorial.manifest.json"
        ),
    }
    state.write(workspace_dir, s)
    return decision


def run_step1_topology(workspace_dir: Path, forcefield: str, water: str) -> None:
    ws = Path(workspace_dir)
    pdb = ws / "inputs" / "input.pdb"
    out_dir = ws / "stage1_env"
    result = GW.run(
        ["pdb2gmx", "-f", str(pdb),
         "-o", "processed.gro", "-p", "topol.top",
         "-water", water, "-ff", forcefield, "-ignh"],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"pdb2gmx failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["step_outputs"]["step_1"] = {
        "forcefield": forcefield, "water_model": water,
        "top_file": "stage1_env/topol.top",
        "gro_file": "stage1_env/processed.gro",
    }
    s["current_step"] = 1
    state.write(ws, s)


def run_step2_box(workspace_dir: Path, box_type: str, distance_nm: float) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    result = GW.run(
        ["editconf", "-f", "processed.gro", "-o", "box.gro",
         "-c", "-d", str(distance_nm), "-bt", box_type],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"editconf failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["step_outputs"]["step_2"] = {
        "box_type": box_type, "box_distance": distance_nm,
        "box_gro": "stage1_env/box.gro",
    }
    s["current_step"] = 2
    state.write(ws, s)


def run_step3_solvate(workspace_dir: Path) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    top = out_dir / "topol.top"
    GW.backup_topology(top)
    s = state.read(ws)
    s["topology_backups"].append("stage1_env/topol.top.bak")
    state.write(ws, s)
    result = GW.run(
        ["solvate", "-cp", "box.gro", "-cs", "spc216.gro",
         "-o", "solv.gro", "-p", "topol.top"],
        cwd=out_dir,
    )
    if not result.ok:
        GW.restore_topology(top)
        raise RuntimeError(f"solvate failed: {result.stderr[-500:]}")
    n_sol = 0
    for line in result.stdout.splitlines():
        if "Number of solvent molecules" in line:
            n_sol = int(line.split()[-1])
            break
    s = state.read(ws)
    s["step_outputs"]["step_3"] = {
        "solv_gro": "stage1_env/solv.gro", "n_solvent_molecules": n_sol,
    }
    s["current_step"] = 3
    state.write(ws, s)


def run_step4_ions_prep(workspace_dir: Path) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    MDP.render("ions", overrides={}, output_dir=out_dir)
    result = GW.run(
        ["grompp", "-f", "ions.mdp", "-c", "solv.gro",
         "-p", "topol.top", "-o", "ions.tpr", "-maxwarn", "1"],
        cwd=out_dir,
    )
    if not result.ok:
        raise RuntimeError(f"grompp (ions) failed: {result.stderr[-500:]}")
    s = state.read(ws)
    s["current_step"] = 4
    state.write(ws, s)


def run_step5_genion(workspace_dir: Path, concentration: float = 0.15) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    top = out_dir / "topol.top"
    GW.backup_topology(top)
    s = state.read(ws)
    if "stage1_env/topol.top.bak" not in s["topology_backups"]:
        s["topology_backups"].append("stage1_env/topol.top.bak")
    state.write(ws, s)
    result = GW.run(
        ["genion", "-s", "ions.tpr", "-o", "ions.gro",
         "-p", "topol.top", "-pname", "NA", "-nname", "CL",
         "-neutral", "-conc", str(concentration)],
        cwd=out_dir, interactive_inputs=["SOL"],
    )
    if not result.ok:
        GW.restore_topology(top)
        raise RuntimeError(f"genion failed: {result.stderr[-500:]}")
    n_na = n_cl = 0
    for line in (result.stdout + result.stderr).splitlines():
        if "Will try to add" in line and "NA" in line:
            n_na = int(line.split()[3])
        if "Will try to add" in line and "CL" in line:
            n_cl = int(line.split()[3])
    s = state.read(ws)
    s["step_outputs"]["step_5"] = {
        "ion_gro": "stage1_env/ions.gro",
        "n_na": n_na, "n_cl": n_cl, "net_charge": 0.0,
    }
    s["current_step"] = 5
    s["last_completed_stage"] = "env"
    state.write(ws, s)
