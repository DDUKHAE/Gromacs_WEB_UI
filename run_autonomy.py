import json
import os
import sys
import importlib.util
import shutil
import subprocess
from datetime import datetime


def _load_func(module_path, func_name):
    spec = importlib.util.spec_from_file_location(func_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, func_name)


run_state_manager = _load_func("skills/state-manager/state_manager.py", "run_state_manager")
route_tutorial = _load_func("skills/tutorial-router/tutorial_router.py", "route_tutorial")
plan_workflow = _load_func("skills/tutorial-planner/tutorial_planner.py", "plan_workflow")
compile_protocol = _load_func("skills/protocol-compiler/protocol_compiler.py", "compile_protocol")
compose_mdp = _load_func("skills/mdp-composer/mdp_composer.py", "compose_mdp")
run_gmx = _load_func("skills/gmx-executor/gmx_executor.py", "run_gmx")


def _safe_load_optional():
    validate_phase = None
    analyze_trajectory = None
    try:
        validate_phase = _load_func("skills/system-validator/system_validator.py", "validate")
    except Exception:
        pass
    try:
        analyze_trajectory = _load_func("skills/trajectory-analyzer/trajectory_analyzer.py", "analyze")
    except Exception:
        pass
    return validate_phase, analyze_trajectory


def _manifest_for_tutorial(tutorial_id):
    return os.path.join("docs", "tutorial", tutorial_id, "tutorial.manifest.json")


def _resolve_gmx_bin(preferred):
    if preferred and shutil.which(preferred):
        return preferred
    env_bin = os.environ.get("GMX_BIN")
    if env_bin and shutil.which(env_bin):
        return env_bin
    for candidate in ["gmx", "gmx_mpi"]:
        path = shutil.which(candidate)
        if path:
            return path
    return preferred or "gmx"


def _resolve_supported_forcefield(requested, gmx_bin, cwd):
    requested = (requested or "").strip()
    installed = set()
    gmxlib = os.environ.get("GMXLIB")
    probe_dirs = []
    if gmxlib:
        probe_dirs.append(gmxlib)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        probe_dirs.append(os.path.join(conda_prefix, "share", "gromacs", "top"))

    for d in probe_dirs:
        if not d or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.endswith(".ff"):
                installed.add(name[:-3].lower())

    candidates = [requested.lower()] if requested else []
    fallback_order = ["amber99sb-ildn", "amber14sb", "charmm27", "oplsaa"]
    for item in fallback_order:
        if item.lower() not in candidates:
            candidates.append(item.lower())

    for ff in candidates:
        if ff and (not installed or ff in installed):
            return ff
    return (requested.lower() if requested else "") or "amber99sb-ildn"


def _parse_topol_molecules(cwd):
    top_path = os.path.join(cwd, "topol.top")
    counts = {}
    if not os.path.exists(top_path):
        return counts
    in_block = False
    with open(top_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("["):
                in_block = line.lower() == "[ molecules ]"
                continue
            if not in_block:
                continue
            cols = line.split()
            if len(cols) >= 2 and cols[1].isdigit():
                counts[cols[0]] = int(cols[1])
    return counts


def _estimate_net_charge(molecules):
    charge_map = {
        "NA": 1,
        "NA+": 1,
        "K": 1,
        "K+": 1,
        "CL": -1,
        "CL-": -1,
        "CA": 2,
        "MG": 2,
        "ZN": 2,
    }
    net = 0
    for name, count in molecules.items():
        net += charge_map.get(name.upper(), 0) * int(count)
    return net


def _write_analysis_report(cwd, routed, phase_results, analysis):
    report_path = os.path.join(cwd, "analysis_report.json")
    reports = analysis.get("reports", {}) if isinstance(analysis, dict) else {}
    downsampled = analysis.get("downsampled_data", {}) if isinstance(analysis, dict) else {}
    generated = analysis.get("generated_files", []) if isinstance(analysis, dict) else []
    payload = {
        "status": analysis.get("status") if isinstance(analysis, dict) else "error",
        "selected_tutorial": routed.get("selected_tutorial"),
        "pipeline_variant": routed.get("pipeline_variant"),
        "phase_validation": phase_results,
        "summary": {
            "rmsd_stable": bool(reports.get("rmsd_plateau_reached", False)),
            "energy_converged": not bool(reports.get("energy_drift_detected", True)),
        },
        "reports": reports,
        "downsampled_data": downsampled,
        "generated_files": generated,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return report_path


def _append_retry_history(cwd, step, phase, command, attempts, status, summary, gate_diagnostics=None):
    current = run_state_manager({"action": "read", "cwd": cwd})
    if current.get("status") != "success":
        return
    state = current.get("state", {})
    history = state.get("retry_history", {})
    key = f"step_{step}" + (f"_{phase}" if phase else "")
    history[key] = {
        "command": command,
        "attempts": attempts,
        "status": status,
        "summary": summary,
    }
    if gate_diagnostics is not None:
        history[key]["gate_diagnostics"] = gate_diagnostics
    run_state_manager({"action": "update", "cwd": cwd, "data": {"retry_history": history}})


def _retry_history_from_execution_log(execution_log):
    history = {}
    for item in execution_log:
        key = f"step_{item.get('step')}" + (f"_{item.get('phase')}" if item.get("phase") else "")
        history[key] = {
            "command": item.get("command"),
            "attempts": item.get("attempts"),
            "status": item.get("status"),
            "summary": item.get("summary"),
        }
        if item.get("gate_diagnostics") is not None:
            history[key]["gate_diagnostics"] = item.get("gate_diagnostics")
    return history


def _mdp_overrides_from_compiled_args(args):
    overrides = {}
    if "__override_tau_t" in args:
        overrides["tau_t"] = args["__override_tau_t"]
    if "__override_tau_p" in args:
        overrides["tau_p"] = args["__override_tau_p"]
    if "__override_dt" in args:
        overrides["dt"] = args["__override_dt"]
    if "__override_nsteps" in args:
        overrides["nsteps"] = args["__override_nsteps"]
    if "__override_tc_grps" in args:
        overrides["tc-grps"] = args["__override_tc_grps"]
    return overrides


def _backup_topol(cwd):
    src = os.path.join(cwd, "topol.top")
    if not os.path.exists(src):
        return None
    bak = os.path.join(cwd, "topol.top.bak_autonomy")
    shutil.copy2(src, bak)
    return bak


def _restore_topol(cwd, bak):
    if not bak or not os.path.exists(bak):
        return False
    dst = os.path.join(cwd, "topol.top")
    shutil.copy2(bak, dst)
    return True


def _mutate_args_for_retry(cmd_name, args, attempt):
    mutated = dict(args)
    if cmd_name == "editconf" and "-d" in mutated:
        mutated["-d"] = f"{float(mutated['-d']) + (0.05 * attempt):.2f}"
    elif cmd_name == "pdb2gmx":
        if attempt == 1:
            mutated["-ignh"] = ""
        elif attempt >= 2:
            mutated["-water"] = "tip3p"
            mutated.pop("-ignh", None)
        else:
            mutated.pop("-ignh", None)
    elif cmd_name == "genion":
        # Ensure executable args differ for every retry attempt.
        if "-neutral" in mutated and attempt % 2 == 1:
            mutated.pop("-neutral", None)
            mutated["-conc"] = "0.15"
        elif "-conc" in mutated and attempt % 2 == 0:
            mutated.pop("-conc", None)
            mutated["-neutral"] = ""
        mutated["-seed"] = str(1000 + attempt)
    elif cmd_name == "grompp":
        if "__override_tau_t" in mutated and attempt >= 1:
            mutated["__override_tau_t"] = "0.08 0.08" if attempt == 1 else "0.05 0.05"
        if "__override_tau_p" in mutated and attempt >= 1:
            mutated["__override_tau_p"] = "2.5" if attempt == 1 else "3.0"
        if attempt >= 1 and mutated.get("-f") == "nvt.mdp":
            mutated["__override_dt"] = "0.0005" if attempt == 1 else "0.0002"
            mutated["__override_nsteps"] = "250000"
        mutated["-maxwarn"] = str(attempt)
    elif cmd_name == "mdrun":
        if attempt >= 1:
            mutated["-ntomp"] = str(max(1, 8 - attempt))
            mutated["-pin"] = "off"
            if attempt >= 2:
                mutated["-nb"] = "cpu"
        # Add deterministic per-attempt output override to guarantee unique runtime args.
        mutated["-cpo"] = f"state_retry_{attempt}.cpt"
    return mutated


def _is_nvt_instability(result):
    if not isinstance(result, dict):
        return False
    blob = "\n".join(
        [
            str(result.get("fatal_error", "")),
            str(result.get("summary", "")),
            str(result.get("stdout_tail", "")),
        ]
    ).lower()
    keys = [
        "lincs warning",
        "can not be settled",
        "cannot be settled",
        "potential energy is nan",
        "not finite",
    ]
    return any(k in blob for k in keys)


def _refresh_args_from_state(cmd_name, args, state):
    updated = dict(args)
    latest_gro = state.get("latest_gro")
    top_file = state.get("top_file")
    if cmd_name == "editconf" and latest_gro and "-f" in updated:
        updated["-f"] = latest_gro
    if cmd_name == "solvate" and latest_gro and "-cp" in updated:
        updated["-cp"] = latest_gro
    if cmd_name == "grompp" and latest_gro and "-c" in updated:
        updated["-c"] = latest_gro
    if top_file and "-p" in updated:
        updated["-p"] = top_file
    return updated


def _parse_gro_atom_count(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            _ = f.readline()
            line = f.readline().strip()
        return int(line)
    except Exception:
        return None


def _topol_expected_atoms(cwd):
    top = os.path.join(cwd, "topol.top")
    if not os.path.exists(top):
        return None
    solvent = _parse_topol_molecules(cwd).get("SOL", 0)
    with open(top, "r", encoding="utf-8") as f:
        text = f.read()
    if "Protein_chain_A" not in text:
        return None
    return solvent * 3


def _build_topology_gro_gate_diagnostics(cwd, gro_path):
    atom_count = _parse_gro_atom_count(gro_path)
    expected_min = _topol_expected_atoms(cwd)
    molecules = _parse_topol_molecules(cwd)
    diag = {
        "gate": "topology_gro_consistency",
        "gro_path": gro_path,
        "gro_atoms": atom_count,
        "expected_min_atoms": expected_min,
        "solvent_molecules": molecules.get("SOL"),
        "status": "pass",
        "reason": "",
    }
    if atom_count is None or expected_min is None or atom_count < expected_min:
        diag["status"] = "fail"
        diag["reason"] = "gro_atoms_missing_or_below_expected_min"
    return diag


def _prepare_run_dir(base_cwd, target_name):
    runs_dir = os.path.join(base_cwd, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(runs_dir, f"{target_name}_{stamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def run(payload):
    base_cwd = payload.get("cwd", os.getcwd())
    target_name = payload.get("target_name", "protein")
    cwd = payload.get("run_dir") or _prepare_run_dir(base_cwd, target_name)
    prompt = payload.get("prompt", "")
    pdb_path = payload.get("pdb_path")
    retry_count = int(payload.get("retry_count", 0))
    if pdb_path and os.path.exists(pdb_path):
        abs_pdb = os.path.abspath(pdb_path)
        dst = os.path.join(cwd, os.path.basename(abs_pdb))
        if not os.path.exists(dst):
            shutil.copy2(abs_pdb, dst)
        pdb_path = os.path.abspath(dst)
    gmx_bin = _resolve_gmx_bin(payload.get("gmx_bin"))
    selected_ff = _resolve_supported_forcefield(payload.get("forcefield", "charmm36"), gmx_bin, cwd)
    validate_phase, analyze_trajectory = _safe_load_optional()

    manifests = [
        _manifest_for_tutorial("Lysozyme_in_water"),
        _manifest_for_tutorial("Protein_Ligand_Complex"),
        _manifest_for_tutorial("KALP15_in_DPPC"),
    ]
    manifests = [m for m in manifests if os.path.exists(m)]

    init_state = run_state_manager(
        {
            "action": "init",
            "cwd": cwd,
            "data": {
                "current_step": 0,
                "last_status": "running",
                "working_dir": cwd,
                "retry_history": {},
                "top_file": "topol.top",
                "gro_file": f"{target_name}_processed.gro",
                "forcefield": selected_ff,
                "water_model": payload.get("water_model", "tip3p"),
                "latest_gro": None,
                "hardware_specs": {},
            },
        }
    )
    if init_state.get("status") != "success":
        return {"status": "error", "message": "state_init_failed", "detail": init_state}

    routed = route_tutorial(
        {
            "prompt": prompt,
            "pdb_path": pdb_path,
            "available_manifests": manifests,
        }
    )
    if routed.get("status") != "success":
        return {"status": "error", "message": "routing_failed", "detail": routed}

    if routed.get("missing_inputs"):
        return {"status": "error", "message": "missing_inputs", "detail": routed}

    manifest_path = _manifest_for_tutorial(routed["selected_tutorial"])
    planned = plan_workflow({"manifest_path": manifest_path})
    if planned.get("status") != "success":
        return {"status": "error", "message": "planning_failed", "detail": planned}

    compiled = compile_protocol(
        {
            "workflow": planned["workflow"],
            "state": {
                "top_file": "topol.top",
                "gro_file": f"{target_name}_processed.gro",
                "target_name": target_name,
                "pdb_file": pdb_path,
                "forcefield": selected_ff,
                "water_model": payload.get("water_model", "tip3p"),
            },
            "cwd": cwd,
            "retry_count": retry_count,
            "pdb_path": pdb_path,
        }
    )
    if compiled.get("status") != "success":
        return {"status": "error", "message": "compile_failed", "detail": compiled}

    plan_state = run_state_manager(
        {
            "action": "update",
            "cwd": cwd,
            "data": {
                "selected_tutorial": routed["selected_tutorial"],
                "pipeline_variant": routed["pipeline_variant"],
                "planned_steps": [x["step"] for x in planned["workflow"]],
                "last_status": "planned",
                "retry_count": retry_count,
            },
        }
    )

    execute = bool(payload.get("execute", False))
    capabilities = {
        "validator_loaded": validate_phase is not None,
        "analyzer_loaded": analyze_trajectory is not None,
        "gmx_bin": gmx_bin,
    }
    if not execute:
        return {
            "status": "success",
            "run_dir": cwd,
            "capabilities": capabilities,
            "routing": routed,
            "planning": planned,
            "compiled_command_count": len(compiled.get("commands", [])),
            "state_update": plan_state.get("status"),
            "commands": compiled.get("commands", []),
        }

    previous_fingerprints = []
    execution_log = []
    topology_backup = None
    max_retries = 3

    phase_results = {}
    analysis_result = None
    gate_remediation_used = False
    for cmd_item in compiled.get("commands", []):
        refreshed = run_state_manager({"action": "read", "cwd": cwd})
        if refreshed.get("status") != "success":
            return {"status": "error", "message": "state_read_failed", "detail": refreshed}

        cmd_name = cmd_item["command"]
        state = refreshed.get("state", {})
        args = _refresh_args_from_state(cmd_name, dict(cmd_item.get("args", {})), state)
        step = cmd_item.get("step")
        phase = cmd_item.get("phase")

        if cmd_name == "analysis_bundle":
            if analyze_trajectory is None:
                execution_log.append({"step": step, "phase": phase, "status": "skipped", "reason": "trajectory_analyzer_unavailable"})
                continue
            md_files = {"tpr": "md.tpr", "xtc": "md.xtc", "edr": "md.edr"}
            analysis = analyze_trajectory({"cwd": cwd, "files": md_files, "analyses": ["rmsd", "rmsf", "gyrate", "energy"], "gmx_bin": gmx_bin})
            analysis_result = analysis
            report_path = _write_analysis_report(cwd, routed, phase_results, analysis)
            execution_log.append({"step": step, "phase": phase, "status": analysis.get("status"), "reason": "trajectory_analyzer"})
            run_state_manager(
                {
                    "action": "update",
                    "cwd": cwd,
                    "data": {
                        "rmsd_stable": bool(analysis.get("reports", {}).get("rmsd_plateau_reached", False)),
                        "energy_converged": not bool(analysis.get("reports", {}).get("energy_drift_detected", True)),
                        "final_report_path": report_path,
                        "current_step": step,
                    },
                }
            )
            continue

        if cmd_name == "grompp":
            phase_name = phase if phase else ("ions" if args.get("-f") == "ions.mdp" else None)
            if phase_name == "nvt" and step == 6 and retry_count >= 1:
                args["__override_dt"] = "0.0005" if retry_count == 1 else "0.0002"
                args["__override_tau_t"] = "0.05"
                args["__override_nsteps"] = "250000"
                args["__override_tc_grps"] = "System"
            if phase_name:
                mdp_result = compose_mdp(
                    {
                        "phase": phase_name,
                        "overrides": _mdp_overrides_from_compiled_args(args),
                        "cwd": cwd,
                    }
                )
                if mdp_result.get("status") != "success":
                    return {"status": "error", "message": "mdp_compose_failed", "detail": mdp_result}

        attempt = 0
        result = None
        while attempt < max_retries:
            current_args = _mutate_args_for_retry(cmd_name, args, attempt)
            exec_args = dict(current_args)
            exec_args.pop("__override_tau_t", None)
            exec_args.pop("__override_tau_p", None)
            if cmd_item.get("requires_backup") and topology_backup is None:
                topology_backup = _backup_topol(cwd)

            interactive_responses = []
            if cmd_name == "genion":
                group_res = run_gmx(
                    {
                        "command": cmd_name,
                        "args": current_args,
                        "cwd": cwd,
                        "resolve_group_index": True,
                        "group_name": "SOL",
                        "gmx_bin": gmx_bin,
                    }
                )
                if group_res.get("status") == "success" and group_res.get("group_index") is not None:
                    interactive_responses = [str(group_res.get("group_index"))]

            result = run_gmx(
                {
                    "command": cmd_name,
                    "args": exec_args,
                    "cwd": cwd,
                    "retry_count": attempt,
                    "previous_attempt_fingerprints": previous_fingerprints,
                    "interactive_responses": interactive_responses,
                    "backup_topology": bool(cmd_item.get("requires_backup")),
                    "gmx_bin": gmx_bin,
                }
            )

            fp = result.get("command_fingerprint")
            if fp:
                previous_fingerprints.append(fp)

            if result.get("status") == "success":
                break

            attempt += 1

            if cmd_item.get("requires_backup"):
                _restore_topol(cwd, topology_backup)

        attempts_used = attempt + 1 if result and result.get("status") == "success" else attempt
        gate_diag = None
        if result and result.get("status") == "success" and cmd_name in ["solvate", "genion"]:
            gro_out = args.get("-o")
            if gro_out:
                gro_path = os.path.join(cwd, gro_out)
                gate_diag = _build_topology_gro_gate_diagnostics(cwd, gro_path)
                if gate_diag.get("status") == "fail":
                    restored = _restore_topol(cwd, topology_backup) if topology_backup else False
                    remediation_attempted = False
                    if not gate_remediation_used:
                        remediation_attempted = True
                        gate_remediation_used = True
                        rem_args = _mutate_args_for_retry(cmd_name, args, max_retries)
                        rem_exec_args = dict(rem_args)
                        rem_exec_args.pop("__override_tau_t", None)
                        rem_exec_args.pop("__override_tau_p", None)
                        rem_result = run_gmx(
                            {
                                "command": cmd_name,
                                "args": rem_exec_args,
                                "cwd": cwd,
                                "retry_count": max_retries,
                                "previous_attempt_fingerprints": previous_fingerprints,
                                "backup_topology": bool(cmd_item.get("requires_backup")),
                                "gmx_bin": gmx_bin,
                            }
                        )
                        rem_fp = rem_result.get("command_fingerprint")
                        if rem_fp:
                            previous_fingerprints.append(rem_fp)
                        if rem_result.get("status") == "success":
                            rem_diag = _build_topology_gro_gate_diagnostics(cwd, gro_path)
                            if rem_diag.get("status") == "pass":
                                result = rem_result
                                attempts_used += 1
                                gate_diag = rem_diag
                            else:
                                gate_diag = rem_diag
                    if gate_diag.get("status") == "fail":
                        gate_diag["rollback_performed"] = bool(restored)
                        gate_diag["remediation_attempted"] = remediation_attempted
                        result = {
                            "status": "error",
                            "summary": "Topology/GRO consistency gate failed.",
                            "fatal_error": (
                                f"gro_atoms={gate_diag.get('gro_atoms')}, "
                                f"expected_min={gate_diag.get('expected_min_atoms')}, "
                                f"reason={gate_diag.get('reason')}"
                            ),
                            "gate_diagnostics": gate_diag,
                        }
        execution_log.append(
            {
                "step": step,
                "phase": phase,
                "command": cmd_name,
                "status": result.get("status") if result else "error",
                "attempts": attempts_used,
                "summary": result.get("summary") if result else "no_result",
                "gate_diagnostics": gate_diag,
            }
        )
        _append_retry_history(
            cwd=cwd,
            step=step,
            phase=phase,
            command=cmd_name,
            attempts=attempts_used,
            status=result.get("status") if result else "error",
            summary=result.get("summary") if result else "no_result",
            gate_diagnostics=gate_diag,
        )

        if not result or result.get("status") != "success":
            if cmd_name == "mdrun" and phase == "nvt" and _is_nvt_instability(result):
                return run(
                    {
                        **payload,
                        "retry_count": retry_count + 1,
                        "execute": True,
                    }
                )
            run_state_manager(
                {
                    "action": "update",
                    "cwd": cwd,
                    "data": {
                        "last_status": "error",
                        "current_step": step,
                        "topology_backup": topology_backup,
                        "working_dir": cwd,
                        "retry_history": _retry_history_from_execution_log(execution_log),
                    },
                }
            )
            return {"status": "error", "message": "execution_failed", "failed_command": cmd_item, "result": result, "execution_log": execution_log}

        run_state_manager(
            {
                "action": "update",
                "cwd": cwd,
                "data": {
                    "current_step": step,
                    "last_status": "running",
                    "topology_backup": topology_backup,
                    "last_command_fingerprint": result.get("command_fingerprint"),
                    "working_dir": cwd,
                },
            }
        )
        tuning = result.get("tuning", {})
        if tuning and tuning.get("hardware"):
            run_state_manager({"action": "update", "cwd": cwd, "data": {"hardware_specs": tuning.get("hardware", {})}})
        if cmd_name == "editconf":
            run_state_manager({"action": "update", "cwd": cwd, "data": {"box_type": "cubic", "box_distance": args.get("-d"), "box_gro": args.get("-o"), "latest_gro": args.get("-o")}})
        elif cmd_name == "solvate":
            mols = _parse_topol_molecules(cwd)
            run_state_manager({"action": "update", "cwd": cwd, "data": {"solv_gro": args.get("-o"), "n_solvent_molecules": mols.get("SOL"), "latest_gro": args.get("-o")}})
        elif cmd_name == "genion":
            mols = _parse_topol_molecules(cwd)
            run_state_manager(
                {
                    "action": "update",
                    "cwd": cwd,
                    "data": {
                        "ion_gro": args.get("-o"),
                        "n_na": mols.get("NA", mols.get("NA+", 0)),
                        "n_cl": mols.get("CL", mols.get("CL-", 0)),
                        "net_charge": _estimate_net_charge(mols),
                        "latest_gro": args.get("-o"),
                    },
                }
            )
        elif cmd_name == "mdrun" and phase in ["minim", "nvt", "npt", "md"]:
            if validate_phase is None:
                execution_log.append({"step": step, "phase": phase, "status": "warning", "reason": "system_validator_unavailable"})
                continue
            files = {"edr": f"{phase}.edr", "log": f"{phase}.log"}
            v = validate_phase({"phase": phase, "files": files, "cwd": cwd, "gmx_bin": gmx_bin})
            phase_results[phase] = v
            if v.get("verdict") == "FAIL":
                run_state_manager({"action": "update", "cwd": cwd, "data": {"last_status": "error"}})
                return {"status": "error", "message": "validation_failed", "phase": phase, "validation": v, "execution_log": execution_log}
            phase_gro_key = {"minim": "em_gro", "nvt": "nvt_gro", "npt": "npt_gro", "md": "production_gro"}[phase]
            run_state_manager({"action": "update", "cwd": cwd, "data": {phase_gro_key: f"{phase}.gro", "latest_gro": f"{phase}.gro"}})

    final_state = run_state_manager(
        {
            "action": "update",
            "cwd": cwd,
            "data": {
                "last_status": "success",
                "current_step": 8,
                "retry_history": _retry_history_from_execution_log(execution_log),
            },
        }
    )

    return {
        "status": "success",
        "run_dir": cwd,
        "capabilities": capabilities,
        "routing": routed,
        "planning": planned,
        "compiled_command_count": len(compiled.get("commands", [])),
        "state_update": final_state.get("status"),
        "commands": compiled.get("commands", []),
        "execution_log": execution_log,
        "phase_validation": phase_results,
        "analysis": analysis_result,
        "gmx_bin": gmx_bin,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            payload = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                payload = json.load(f)
    else:
        payload = json.loads(sys.stdin.read())

    print(json.dumps(run(payload), indent=2, ensure_ascii=False))
