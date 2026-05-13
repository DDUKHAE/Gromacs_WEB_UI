import json
import os
import sys
import importlib.util
import shutil
import subprocess


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


def _append_retry_history(cwd, step, phase, command, attempts, status, summary):
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
    return history


def _mdp_overrides_from_compiled_args(args):
    overrides = {}
    if "__override_tau_t" in args:
        overrides["tau_t"] = args["__override_tau_t"]
    if "__override_tau_p" in args:
        overrides["tau_p"] = args["__override_tau_p"]
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
        if "-neutral" in mutated:
            mutated.pop("-neutral", None)
            mutated["-conc"] = "0.15"
        else:
            mutated["-neutral"] = ""
            mutated.pop("-conc", None)
    return mutated


def run(payload):
    cwd = payload.get("cwd", os.getcwd())
    prompt = payload.get("prompt", "")
    pdb_path = payload.get("pdb_path")
    retry_count = int(payload.get("retry_count", 0))
    target_name = payload.get("target_name", "protein")
    gmx_bin = _resolve_gmx_bin(payload.get("gmx_bin"))
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
                "forcefield": payload.get("forcefield", "charmm36"),
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
            },
            "cwd": cwd,
            "retry_count": retry_count,
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
    if not execute:
        return {
            "status": "success",
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
    for cmd_item in compiled.get("commands", []):
        refreshed = run_state_manager({"action": "read", "cwd": cwd})
        if refreshed.get("status") != "success":
            return {"status": "error", "message": "state_read_failed", "detail": refreshed}

        cmd_name = cmd_item["command"]
        args = dict(cmd_item.get("args", {}))
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
            args.pop("__override_tau_t", None)
            args.pop("__override_tau_p", None)

        attempt = 0
        result = None
        while attempt < max_retries:
            current_args = _mutate_args_for_retry(cmd_name, args, attempt)
            if cmd_item.get("requires_backup") and topology_backup is None:
                topology_backup = _backup_topol(cwd)

            result = run_gmx(
                {
                    "command": cmd_name,
                    "args": current_args,
                    "cwd": cwd,
                    "retry_count": attempt,
                    "previous_attempt_fingerprints": previous_fingerprints,
                    "interactive_responses": ["SOL"] if cmd_name == "genion" else [],
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
        execution_log.append(
            {
                "step": step,
                "phase": phase,
                "command": cmd_name,
                "status": result.get("status") if result else "error",
                "attempts": attempts_used,
                "summary": result.get("summary") if result else "no_result",
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
        )

        if not result or result.get("status") != "success":
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
