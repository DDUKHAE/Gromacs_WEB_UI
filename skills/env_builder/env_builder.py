"""env-builder skill — Step 0–5 of the GROMACS pipeline."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import re

from lib import state
from lib import tutorial_registry as TR
from lib import gmx_wrapper as GW
from lib import validators as V
from lib.mdp_templates import base as MDP


_NET_CHARGE_RE = re.compile(
    r"non-zero total charge:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE
)
_GENION_ADD_RE = re.compile(
    r"Will try to add\s+(\d+)\s+NA ions?\s+and\s+(\d+)\s+CL ions?", re.IGNORECASE
)


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


_SOLVENT_AND_IONS = frozenset({
    "HOH", "WAT", "SOL", "NA", "CL", "MG", "CA", "K", "ZN",
    "FE", "CU", "MN", "NI", "CO", "LI", "BR", "F", "I",
})


def _pdb_hints(pdb_path: Path) -> dict[str, bool]:
    text = Path(pdb_path).read_text()
    has_ligand = any(
        line.startswith("HETATM") and line[17:20].strip() not in _SOLVENT_AND_IONS
        for line in text.splitlines()
    )
    return {
        "has_protein": "ATOM" in text and any(
            res in text for res in ("ALA", "GLY", "LEU", "VAL", "ILE")),
        "has_membrane": any(
            lipid in text for lipid in ("DPPC", "POPC", "DMPC", "DOPC")),
        "has_ligand": has_ligand,
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
        # Recorded so md_runner can derive tc-grps correctly (protein-free
        # systems have no "Protein"/"Non-Protein" index groups).
        "has_protein": hints.get("has_protein", True),
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
    for line in (result.stdout + result.stderr).splitlines():
        if "Number of solvent molecules" in line:
            try:
                n_sol = int(line.split()[-1])
            except ValueError:
                pass
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
    # grompp emits "System has non-zero total charge: X.XXXXXX" as a WARNING
    # when the pre-neutralization system is charged; absence of the message
    # means the system is already neutral (charge 0.0).
    m = _NET_CHARGE_RE.search(result.stdout + result.stderr)
    initial_net_charge = float(m.group(1)) if m else 0.0
    s = state.read(ws)
    s["step_outputs"]["step_4"] = {"initial_net_charge": initial_net_charge}
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
    # genion reports both counts on a single line, e.g.
    # "Will try to add 3 NA ions and 0 CL ions." — a naive per-substring
    # scan (checking "NA" and "CL" independently) matches both branches on
    # that one line and silently overwrites n_cl with the NA count. Parse
    # both numbers from the same match instead.
    n_na = n_cl = 0
    m = _GENION_ADD_RE.search(result.stdout + result.stderr)
    if m:
        n_na, n_cl = int(m.group(1)), int(m.group(2))
    s = state.read(ws)
    initial_net_charge = (s["step_outputs"].get("step_4") or {}).get(
        "initial_net_charge", 0.0)
    # NA/CL are the hardcoded monovalent ion species used above (+1/-1 e);
    # the actual post-genion system charge is the pre-neutralization charge
    # plus the ions genion actually added, not an assumed 0.0.
    net_charge = initial_net_charge + n_na - n_cl
    judgment = V.judge_neutrality(net_charge)
    s["step_outputs"]["step_5"] = {
        "ion_gro": "stage1_env/ions.gro",
        "n_na": n_na, "n_cl": n_cl, "net_charge": net_charge,
        "neutrality_tier": judgment.tier,
    }
    if judgment.tier != "pass":
        s["pending_warnings"].append({
            "step": 5, "phase": "genion",
            "metric": "net_charge", "observed": net_charge,
            "cause": judgment.cause, "tier": judgment.tier,
            "suggested_mutation": judgment.suggested_mutation,
        })
    state.write(ws, s)
    if judgment.tier == "fatal":
        GW.restore_topology(top)
        raise RuntimeError(
            f"genion neutralization gate FATAL: residual net charge "
            f"{net_charge:+.3f} e after adding {n_na} NA / {n_cl} CL ions "
            f"(pre-neutralization charge was {initial_net_charge:+.3f} e)"
        )
    s = state.read(ws)
    s["current_step"] = 5
    s["last_completed_stage"] = "env"
    state.write(ws, s)


def _strip_hetatm_water(pdb_path: Path) -> None:
    """Remove HETATM water/ion records in-place (pdb2gmx handles them poorly)."""
    lines = pdb_path.read_text().splitlines(keepends=True)
    cleaned = [
        l for l in lines
        if not (l.startswith("HETATM") and l[17:20].strip() in _SOLVENT_AND_IONS)
    ]
    pdb_path.write_text("".join(cleaned))


def _available_forcefields() -> set[str]:
    """Return ff names available in the effective GMXLIB."""
    gmxlib = GW.get_gmxlib()
    if not gmxlib:
        return set()
    top_dir = Path(gmxlib)
    if not top_dir.is_dir():
        return set()
    return {p.name[:-3] for p in top_dir.iterdir() if p.name.endswith(".ff")}


def _resolve_forcefield(requested: str) -> str:
    """Return requested ff if available, else raise with helpful message."""
    available = _available_forcefields()
    if not available or requested in available:
        return requested
    raise RuntimeError(
        f"Force field '{requested}' not found in GMXLIB. "
        f"Available: {sorted(available)}. "
        f"Update the tutorial manifest or set GMXLIB to a directory that contains '{requested}.ff'."
    )


def build_environment(pdb_path: Path, prompt: str, workspace_dir: Path,
                      prerequisites: dict[str, Any] | None = None,
                      interactive: bool = True) -> dict[str, Any]:
    init_workspace(workspace_dir)
    collect_hardware(workspace_dir)
    inputs_pdb = Path(workspace_dir) / "inputs" / "input.pdb"
    if Path(pdb_path).resolve() != inputs_pdb.resolve():
        shutil.copy(pdb_path, inputs_pdb)
    _strip_hetatm_water(inputs_pdb)
    user_prefs: dict = {}
    meta: dict = {}
    meta_file = Path(workspace_dir) / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            user_prefs = meta.get("user_preferences", {})
        except Exception:
            pass
    # Use user-selected tutorial if provided; otherwise auto-route
    user_tutorial_id = meta.get("tutorial_id", "")
    if user_tutorial_id:
        from dataclasses import replace as _dc_replace
        _base = select_tutorial(workspace_dir, inputs_pdb, prompt, prerequisites or {})
        decision = _dc_replace(_base, tutorial_id=user_tutorial_id)
    else:
        decision = select_tutorial(workspace_dir, inputs_pdb, prompt,
                                   prerequisites or {})
    manifest = TR.load_manifest(decision.tutorial_id) or {}
    defaults = manifest.get("defaults", {})
    user_prefs: dict = {}
    meta_file = Path(workspace_dir) / "meta.json"
    if meta_file.exists():
        try:
            user_prefs = json.loads(meta_file.read_text()).get("user_preferences", {})
        except Exception:
            pass
    ff = _resolve_forcefield(
        user_prefs.get("forcefield") or defaults.get("forcefield", "charmm36")
    )
    water = user_prefs.get("water") or defaults.get("water_model", "tip3p")
    box_type = user_prefs.get("box_type") or defaults.get("box_type", "cubic")
    box_d = defaults.get("box_distance_nm", 1.0)
    run_step1_topology(workspace_dir, ff, water)
    run_step2_box(workspace_dir, box_type, box_d)
    run_step3_solvate(workspace_dir)
    run_step4_ions_prep(workspace_dir)
    run_step5_genion(workspace_dir, concentration=0.15)
    return state.read(workspace_dir)
