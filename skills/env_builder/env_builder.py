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
from lib import protocol_contract as PC
from lib import run_plan as RP
from lib import run_parameters as RPARAM
from lib import berger_forcefield as BFF
from lib.system_config import load_config
from lib import ligand_params as LP
from lib import llm_assist
from lib.pdb_analyzer import PDBAnalyzer
from skills.env_builder import membrane_assembly


_NET_CHARGE_RE = re.compile(
    r"non-zero total charge:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE
)
_GENION_ADD_RE = re.compile(
    r"Will try to add\s+(\d+)\s+NA ions?\s+and\s+(\d+)\s+CL ions?", re.IGNORECASE
)
_GROMPP_WARNING_RE = re.compile(r"^WARNING\s+\d+\s+\[.*", re.MULTILINE)


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
    # Capture gmx_version/platform provenance as early as possible (Step 0).
    # Gracefully records None if gmx isn't installed; never raises.
    state.capture_provenance(workspace_dir)


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


#: Residues that cap a terminus instead of being one. A capped terminus has no
#: N (or no C/O), so pdb2gmx's default charged terminus cannot be built and it
#: dies with "atom N not found in buiding block 1ACE" (its own typo).
_TERMINUS_CAPS = frozenset({"ACE", "FOR", "NH2", "NME", "NAC"})

#: Answers to pdb2gmx's -ter menus, in the order it asks (start, then end).
#: Both menus list "None" third: 0 NH3+ / 1 NH2 / 2 None and
#: 0 COO- / 1 COOH / 2 None. 0 is also pdb2gmx's non-interactive default, so
#: answering it for an uncapped terminus reproduces the behaviour without -ter.
_TER_NONE, _TER_DEFAULT = "2", "0"


def _terminus_answers(pdb_path: Path) -> list[str] | None:
    """-ter answers for a capped structure, or None if neither end is capped."""
    residues = [line[17:20].strip() for line in Path(pdb_path).read_text().splitlines()
                if line.startswith(("ATOM", "HETATM"))]
    if not residues:
        return None
    answers = [_TER_NONE if res in _TERMINUS_CAPS else _TER_DEFAULT
               for res in (residues[0], residues[-1])]
    return answers if _TER_NONE in answers else None


def run_step1_topology(workspace_dir: Path, forcefield: str, water: str) -> None:
    ws = Path(workspace_dir)
    pdb = ws / "inputs" / "input.pdb"
    out_dir = ws / "stage1_env"
    # -ignh: the tutorial's ACE cap carries HA1/HA2/HA3, which no united-atom
    # rtp entry has. Harmless elsewhere -- pdb2gmx rebuilds hydrogens anyway.
    args = ["pdb2gmx", "-f", str(pdb),
            "-o", "processed.gro", "-p", "topol.top",
            "-water", water, "-ff", forcefield, "-ignh"]
    answers = _terminus_answers(pdb)
    if answers:
        args.append("-ter")
    result = GW.run(
        args, interactive_inputs=answers,
        cwd=out_dir, progress_log=ws / "runner.log",
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
    state.record_force_field(ws, forcefield)


def integrate_cgenff_ligand(workspace_dir: Path) -> None:
    """Merge pre-converted CGenFF files into the CHARMM36 protein topology.

    Builder files live below ``inputs/`` and are copied into ``stage1_env`` so
    every GROMACS include is run-local and archived with the run.
    """
    ws = Path(workspace_dir)
    config = load_config(ws) or {}
    ligand = config.get("ligand") or {}
    if ligand.get("parameterization") != "cgenff":
        return
    required = {key: ws / ligand.get(key, "") for key in ("itp_file", "prm_file", "gro_file")}
    missing = [key for key, file_path in required.items() if not file_path.is_file()]
    if missing:
        raise UnsupportedTutorialError("CGenFF builder files missing: " + ", ".join(missing))
    stage = ws / "stage1_env"
    result = LP.assemble_complex(
        stage / "processed.gro", required["gro_file"], required["itp_file"],
        stage / "topol.top", stage, required["prm_file"],
    )
    (stage / "processed.gro").write_text(result["complex_gro"])
    (stage / "topol.top").write_text(result["topol_top"])
    s = state.read(ws)
    s["step_outputs"]["step_1"]["ligand"] = {
        "parameterization": "cgenff", "residue_name": ligand.get("residue_name"),
        "itp": "stage1_env/" + required["itp_file"].name,
        "prm": "stage1_env/" + required["prm_file"].name,
    }
    state.write(ws, s)


def prepare_prebuilt_membrane(workspace_dir: Path, gro_text: str, top_text: str,
                              tutorial_id: str = "KALP15_in_DPPC") -> None:
    """Stage a packmol-memgen GROMACS system as a completed environment build."""
    ws = Path(workspace_dir)
    init_workspace(ws)
    stage = ws / "stage1_env"
    (stage / "processed.gro").write_text(gro_text)
    (stage / "ions.gro").write_text(gro_text)
    (stage / "topol.top").write_text(top_text)
    collect_hardware(ws)
    manifest = TR.load_manifest(tutorial_id) or {}
    s = state.read(ws)
    s["tutorial"] = {"id": tutorial_id, "variant": manifest.get("pipeline_variant"),
                     "has_protein": True, "manifest_path": f"docs/tutorial/{tutorial_id}/tutorial.manifest.json"}
    s["step_outputs"].update({
        "step_1": {"forcefield": "charmm36", "water_model": "tip3p", "top_file": "stage1_env/topol.top", "gro_file": "stage1_env/processed.gro"},
        "step_2": {"box_type": "prebuilt", "box_distance": "prebuilt", "box_gro": "stage1_env/ions.gro"},
        "step_3": {"solv_gro": "stage1_env/ions.gro", "n_solvent_molecules": "prebuilt"},
        "step_5": {"ion_gro": "stage1_env/ions.gro", "n_na": "prebuilt", "n_cl": "prebuilt", "net_charge": "unverified"},
    })
    s["current_step"], s["last_completed_stage"] = 5, "env"
    state.write(ws, s)
    (ws / "builder_handoff.json").write_text(json.dumps({"kind": "membrane", "environment": "prebuilt"}, indent=2))


def run_step2_box(workspace_dir: Path, box_type: str, distance_nm: float) -> None:
    ws = Path(workspace_dir)
    out_dir = ws / "stage1_env"
    result = GW.run(
        ["editconf", "-f", "processed.gro", "-o", "box.gro",
         "-c", "-d", str(distance_nm), "-bt", box_type],
        cwd=out_dir, progress_log=ws / "runner.log",
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
        cwd=out_dir, progress_log=ws / "runner.log",
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
    ions_mdp = MDP.render("ions", overrides={}, output_dir=out_dir)
    state.record_mdp_hash(ws, "ions", ions_mdp)
    # GROMACS 2026 emits two expected pre-genion warnings for charged GROMOS
    # systems: the legacy GROMOS cutoff notice and PME on the deliberately
    # not-yet-neutral system. Keep the normal limit for other force fields.
    s = state.read(ws)
    ff = str((s["step_outputs"].get("step_1") or {}).get("forcefield", "")).lower()
    maxwarn = "2" if ff.startswith("gromos") else "1"
    result = GW.run(
        ["grompp", "-f", "ions.mdp", "-c", "solv.gro",
         "-p", "topol.top", "-o", "ions.tpr", "-maxwarn", maxwarn],
        cwd=out_dir, progress_log=ws / "runner.log",
    )
    if not result.ok:
        raise RuntimeError(f"grompp (ions) failed: {result.stderr[-500:]}")
    # grompp emits "System has non-zero total charge: X.XXXXXX" as a WARNING
    # when the pre-neutralization system is charged; absence of the message
    # means the system is already neutral (charge 0.0).
    m = _NET_CHARGE_RE.search(result.stdout + result.stderr)
    initial_net_charge = float(m.group(1)) if m else 0.0
    warnings = _GROMPP_WARNING_RE.findall(result.stdout + result.stderr)
    s = state.read(ws)
    s["step_outputs"]["step_4"] = {
        "initial_net_charge": initial_net_charge,
        "grompp_maxwarn": int(maxwarn),
        "grompp_warnings": warnings,
    }
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
        cwd=out_dir, interactive_inputs=["SOL"], progress_log=ws / "runner.log",
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
    if judgment.tier != "pass":
        from dataclasses import asdict
        verdict = llm_assist.review_gro(asdict(judgment))
        if not verdict.proceed:
            GW.restore_topology(top)
            raise RuntimeError(
                f"LLM review rejected GRO checkpoint (tier={judgment.tier}): "
                f"{verdict.diagnosis}"
            )
    s = state.read(ws)
    s["current_step"] = 5
    s["last_completed_stage"] = "env"
    state.write(ws, s)


def _review_pdb_flags(pdb_path: Path) -> None:
    """Run the deterministic PDB analyzer; if it flags anything, ask the LLM
    checkpoint whether the pipeline should proceed. Raises RuntimeError if
    the LLM rejects. No-op (and no LLM call) when nothing is flagged."""
    try:
        pdb_summary = PDBAnalyzer(pdb_path).analyze()
    except Exception:
        return  # advisory-only analyzer must never block the pipeline
    pdb_flags = {
        k: pdb_summary[k] for k in
        ("missing_residues", "altloc_residues", "disulfide_candidates")
        if pdb_summary.get(k)
    }
    if not pdb_flags:
        return
    verdict = llm_assist.review_pdb(pdb_flags, pdb_summary)
    if not verdict.proceed:
        raise RuntimeError(
            f"LLM review rejected PDB checkpoint: {verdict.diagnosis}"
        )


def _strip_hetatm_water(pdb_path: Path) -> None:
    """Remove HETATM water/ion records in-place (pdb2gmx handles them poorly)."""
    lines = pdb_path.read_text().splitlines(keepends=True)
    cleaned = [
        l for l in lines
        if not (l.startswith("HETATM") and l[17:20].strip() in _SOLVENT_AND_IONS)
    ]
    pdb_path.write_text("".join(cleaned))


def prepare_berger_forcefield(workspace_dir: Path) -> str | None:
    """Build gromos53a6_lipid.ff in-place when the run supplies Berger lipids.

    The membrane tutorial's force field does not exist in GMXLIB: it is a copy
    of gromos53a6.ff with lipid.itp's parameters merged in. Build it into
    stage1_env, which is pdb2gmx's working directory and therefore searched
    before GMXLIB.

    Returns the force field name to use, or None when this run has no lipid.itp
    and should fall back to the resolved parameter.
    """
    ws = Path(workspace_dir)
    lipid_itp = next((p for p in (ws / "inputs" / "lipid.itp", ws / "lipid.itp") if p.is_file()), None)
    if lipid_itp is None:
        return None

    gmxlib = GW.get_gmxlib()
    if not gmxlib:
        raise RuntimeError(
            "lipid.itp was supplied but GMXLIB could not be located, so "
            f"{BFF.FF_SOURCE}.ff cannot be extended. Install GROMACS or set GMXLIB."
        )
    stage = ws / "stage1_env"
    summary = BFF.build(lipid_itp, Path(gmxlib), stage)

    # Copy the moleculetype definition next to the force field so the
    # `#include "dppc.itp"` the tutorial adds to topol.top resolves.
    for extra in ("dppc.itp",):
        src = next((p for p in (ws / "inputs" / extra, ws / extra) if p.is_file()), None)
        if src is not None:
            shutil.copy2(src, stage / extra)
            summary.setdefault("copied_includes", []).append(extra)

    s = state.read(ws)
    s["step_outputs"].setdefault("step_0", {})["berger_forcefield"] = summary
    state.write(ws, s)
    return summary["forcefield"]


def integrate_lipid_topology(workspace_dir: Path) -> None:
    """Point topol.top at the lipid moleculetype definitions.

    Runs after pdb2gmx because topol.top does not exist before it. pdb2gmx
    already wrote the `#include` for gromos53a6_lipid.ff (it follows `-ff`), so
    the only edit left from the tutorial is the dppc.itp include.
    """
    ws = Path(workspace_dir)
    s = state.read(ws)
    berger = (s["step_outputs"].get("step_0") or {}).get("berger_forcefield")
    if not berger:
        return
    topol = ws / "stage1_env" / "topol.top"
    if not topol.is_file():
        return
    redirected = BFF.ensure_forcefield_include(topol, berger["forcefield"])
    added = [name for name in berger.get("copied_includes", [])
             if BFF.add_include(topol, name)]
    if added or redirected:
        s = state.read(ws)
        step1 = s["step_outputs"]["step_1"]
        if added:
            step1["lipid_includes"] = added
        if redirected:
            step1["forcefield_include_redirected"] = berger["forcefield"]
        state.write(ws, s)


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


def dispatch_environment_build(workspace_dir: Path, params: dict[str, Any],
                               variant: str | None) -> None:
    """Build the solvated, ionised system for this tutorial's pipeline variant.

    Both arms end at the same contract: stage1_env/ions.gro exists and
    step_outputs.step_5 is populated, so md_runner does not need to know which
    route was taken.

    Deliberately not wrapped in try/except: MembraneAssemblyError subclasses
    Exception, not RuntimeError, precisely so a fatal topology or packing
    failure cannot be demoted into a retryable judgment.
    """
    if variant == "membrane_md_standard":
        membrane_assembly.assemble(workspace_dir, params)
        return
    run_step2_box(workspace_dir, params["box_type"], params["box_distance_nm"])
    run_step3_solvate(workspace_dir)
    run_step4_ions_prep(workspace_dir)
    run_step5_genion(workspace_dir, concentration=params["ion_concentration_M"])


def build_environment(pdb_path: Path, prompt: str, workspace_dir: Path,
                      prerequisites: dict[str, Any] | None = None,
                      interactive: bool = True) -> dict[str, Any]:
    init_workspace(workspace_dir)
    if (Path(workspace_dir) / "builder_handoff.json").exists():
        # A prebuilt membrane already includes its box, solvent, and ions.
        # Do not silently rebuild it with the aqueous protein path.
        return state.read(workspace_dir)
    collect_hardware(workspace_dir)
    inputs_pdb = Path(workspace_dir) / "inputs" / "input.pdb"
    if Path(pdb_path).resolve() != inputs_pdb.resolve():
        shutil.copy(pdb_path, inputs_pdb)
    _strip_hetatm_water(inputs_pdb)
    _review_pdb_flags(inputs_pdb)
    user_prefs: dict = {}
    meta: dict = {}
    meta_file = Path(workspace_dir) / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            user_prefs = meta.get("user_preferences", {})
        except Exception:
            pass
    if prerequisites:
        user_prefs.update(prerequisites)
    target_tutorial_id = user_prefs.get("tutorial_id") or meta.get("tutorial_id")
    if target_tutorial_id:
        plan = RP.materialize(workspace_dir, inputs_pdb, target_tutorial_id)
        contract = PC.materialize(workspace_dir, target_tutorial_id)
    else:
        plan = RP.assert_valid(workspace_dir)
        if plan is None:
            plan = RP.materialize(workspace_dir, inputs_pdb, meta.get("tutorial_id") or None)
        contract = PC.assert_valid(workspace_dir)
        if contract is None:
            contract = PC.materialize(workspace_dir, plan["tutorial"]["id"])
    user_tutorial_id = target_tutorial_id or (contract or {}).get("tutorial_id") or plan["tutorial"]["id"]
    if user_tutorial_id:
        entry = TR.get_entry(user_tutorial_id)
        manifest_for_choice = TR.load_manifest(user_tutorial_id)
        if entry is None or manifest_for_choice is None:
            raise UnsupportedTutorialError(f"unknown selected tutorial: {user_tutorial_id}")
        # Preflight already resolved user-supplied builder inputs (including
        # ligand/membrane configuration) into the plan. Do not re-evaluate
        # only the legacy ``prerequisites`` argument and contradict it.
        missing = list(plan["missing_inputs"])
        unsupported = (f"{user_tutorial_id} requires missing inputs: {missing}"
                       if missing else None)
        decision = TR.RoutingDecision(
            tutorial_id=user_tutorial_id,
            pipeline_variant=manifest_for_choice.get("pipeline_variant"),
            confidence="explicit",
            missing_inputs=missing,
            unsupported_reason=unsupported,
            selected_docs=entry.get("recommended_docs", {}).get("minimal", []),
        )
        if unsupported:
            raise UnsupportedTutorialError(unsupported)
        s = state.read(workspace_dir)
        s["tutorial"] = {"id": decision.tutorial_id, "variant": decision.pipeline_variant,
                         "has_protein": _pdb_hints(inputs_pdb).get("has_protein", True),
                         "manifest_path": f"docs/tutorial/{decision.tutorial_id}/tutorial.manifest.json"}
        state.write(workspace_dir, s)
    else:
        decision = select_tutorial(workspace_dir, inputs_pdb, prompt,
                                   prerequisites or {})
    manifest = TR.load_manifest(decision.tutorial_id) or {}
    if decision.pipeline_variant in ("free_energy_alchemical", "free_energy", "biphasic_system", "topology_modeling") or ((load_config(Path(workspace_dir)) or {}).get("advanced_workflow") or {}).get("free_energy"):
        workflow = ((load_config(Path(workspace_dir)) or {}).get("advanced_workflow") or {}).get("free_energy") or {}
        coordinate = Path(workspace_dir) / workflow.get("coordinate", "")
        topology = Path(workspace_dir) / workflow.get("topology", "")
        if not coordinate.is_file() or not topology.is_file():
            raise UnsupportedTutorialError("free-energy coordinate/topology files are required")
        stage = Path(workspace_dir) / "stage1_env"
        shutil.copy2(coordinate, stage / "processed.gro")
        shutil.copy2(coordinate, stage / "ions.gro")
        shutil.copy2(topology, stage / "topol.top")
        top_text = (stage / "topol.top").read_text()
        for include_name in workflow.get("topology_includes", []):
            include = Path(workspace_dir) / include_name
            if not include.is_file():
                raise UnsupportedTutorialError(f"free-energy topology include missing: {include_name}")
            destination = stage / include.name
            if destination.name == "topol.top":
                raise UnsupportedTutorialError("topology include cannot overwrite topol.top")
            shutil.copy2(include, destination)
            top_text = top_text.replace(include_name, include.name)
        (stage / "topol.top").write_text(top_text)
        s = state.read(workspace_dir)
        s["step_outputs"].update({
            "step_1": {"forcefield": manifest.get("defaults", {}).get("forcefield"), "water_model": manifest.get("defaults", {}).get("water_model"), "top_file": "stage1_env/topol.top", "gro_file": "stage1_env/processed.gro"},
            "step_2": {"box_type": manifest.get("defaults", {}).get("box_type"), "box_distance": manifest.get("defaults", {}).get("box_distance_nm"), "box_gro": "stage1_env/processed.gro"},
            "step_3": {"solv_gro": "stage1_env/processed.gro", "n_solvent_molecules": 0},
            "step_5": {"ion_gro": "stage1_env/ions.gro", "n_na": 0, "n_cl": 0, "net_charge": 0.0},
        })
        s["current_step"], s["last_completed_stage"] = 5, "env"
        state.write(workspace_dir, s)
        return s
    defaults = manifest.get("defaults", {})
    # Every build parameter is decided in one place, layering the tutorial's
    # defaults, the System Builder submission, this run's locked contract and
    # any legacy per-run preference. See lib/run_parameters.py for the rules.
    params = RPARAM.resolve(
        tutorial_defaults=defaults,
        system_config=load_config(Path(workspace_dir)) or {},
        locked=(contract or {}).get("locked_parameters", {}),
        user_prefs=user_prefs,
    )
    # Record which layer supplied each value so a finished run can be audited
    # without re-deriving the precedence by hand.
    s = state.read(workspace_dir)
    s["step_outputs"].setdefault("step_0", {})["resolved_parameters"] = {
        "values": params.values, "sources": params.provenance,
    }
    state.write(workspace_dir, s)

    ff = prepare_berger_forcefield(workspace_dir) or _resolve_forcefield(params.values["forcefield"])
    run_step1_topology(workspace_dir, ff, params.values["water_model"])
    integrate_lipid_topology(workspace_dir)
    integrate_cgenff_ligand(workspace_dir)
    dispatch_environment_build(workspace_dir, params.values,
                               decision.pipeline_variant)
    return state.read(workspace_dir)
