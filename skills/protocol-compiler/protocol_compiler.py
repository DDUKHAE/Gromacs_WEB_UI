import json
import os
import sys


def _join(cwd, filename):
    if not filename:
        return filename
    if os.path.isabs(filename):
        return filename
    return os.path.join(cwd, filename)


def compile_protocol(input_data):
    workflow = input_data.get("workflow", [])
    state = input_data.get("state", {})
    cwd = input_data.get("cwd", os.getcwd())
    retry_count = int(input_data.get("retry_count", 0))

    top_file = state.get("top_file", "topol.top")
    gro_file = state.get("gro_file", "protein_processed.gro")
    target = state.get("target_name", "protein")
    phases = input_data.get("phases", ["minim", "nvt", "npt", "md"])
    box_distance = 1.0 + (0.1 * retry_count)
    tau_t = "0.1 0.1" if retry_count == 0 else "0.08 0.08"
    tau_p = "2.0" if retry_count == 0 else "2.5"

    compiled = []
    for item in workflow:
        step = int(item.get("step"))
        cmd = None
        args = {}
        requires_backup = False
        topology_mutates = False

        if step == 1:
            cmd = "pdb2gmx"
        elif step == 2:
            cmd = "editconf"
            args = {"-f": gro_file, "-o": f"{target}_box.gro", "-c": "", "-d": f"{box_distance:.2f}", "-bt": "cubic"}
            gro_file = f"{target}_box.gro"
        elif step == 3:
            cmd = "solvate"
            args = {"-cp": gro_file, "-cs": "spc216.gro", "-p": top_file, "-o": f"{target}_solv.gro"}
            gro_file = f"{target}_solv.gro"
            requires_backup = True
            topology_mutates = True
        elif step == 4:
            cmd = "grompp"
            args = {"-f": "ions.mdp", "-c": gro_file, "-p": top_file, "-o": "ions.tpr"}
        elif step == 5:
            cmd = "genion"
            args = {"-s": "ions.tpr", "-o": f"{target}_solv_ions.gro", "-p": top_file, "-pname": "NA", "-nname": "CL", "-neutral": ""}
            gro_file = f"{target}_solv_ions.gro"
            requires_backup = True
            topology_mutates = True
        elif step == 6:
            for phase in phases:
                args = {"-f": f"{phase}.mdp", "-c": gro_file, "-p": top_file, "-o": f"{phase}.tpr"}
                if phase != "minim":
                    prev = "minim" if phase == "nvt" else ("nvt" if phase == "npt" else "npt")
                    args["-t"] = f"{prev}.cpt"
                if phase in ["nvt", "npt", "md"]:
                    args["__override_tau_t"] = tau_t
                if phase in ["npt", "md"]:
                    args["__override_tau_p"] = tau_p
                fingerprint = f"grompp|{json.dumps(args, sort_keys=True)}|retry={retry_count}"
                compiled.append(
                    {
                        "step": step,
                        "phase": phase,
                        "command": "grompp",
                        "args": args,
                        "requires_backup": False,
                        "topology_mutates": False,
                        "retry_count": retry_count,
                        "fingerprint": fingerprint,
                        "cwd": _join(cwd, "."),
                    }
                )
            continue
        elif step == 7:
            for phase in phases:
                args = {"-deffnm": phase}
                if phase != "minim":
                    args["-cpi"] = f"{phase}.cpt"
                fingerprint = f"mdrun|{json.dumps(args, sort_keys=True)}|retry={retry_count}"
                compiled.append(
                    {
                        "step": step,
                        "phase": phase,
                        "command": "mdrun",
                        "args": args,
                        "requires_backup": False,
                        "topology_mutates": False,
                        "retry_count": retry_count,
                        "fingerprint": fingerprint,
                        "cwd": _join(cwd, "."),
                    }
                )
                gro_file = f"{phase}.gro"
            continue
        elif step == 8:
            cmd = "analysis_bundle"

        if cmd is None:
            continue

        fingerprint = f"{cmd}|{json.dumps(args, sort_keys=True)}|retry={retry_count}"
        compiled.append(
            {
                "step": step,
                "command": cmd,
                "args": args,
                "requires_backup": requires_backup,
                "topology_mutates": topology_mutates,
                "retry_count": retry_count,
                "fingerprint": fingerprint,
                "cwd": _join(cwd, "."),
            }
        )

    return {"status": "success", "commands": compiled}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            payload = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                payload = json.load(f)
    else:
        payload = json.loads(sys.stdin.read())

    result = compile_protocol(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
