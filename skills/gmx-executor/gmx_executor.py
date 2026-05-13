import sys
import json
import subprocess
import os
import time
import shutil
from datetime import datetime
import hashlib


INPUT_FILE_FLAGS = {
    "-f", "-s", "-c", "-r", "-n", "-p", "-cp", "-t", "-pi", "-po", "-ref", "-table",
    "-tablep", "-ei", "-if", "-rerun", "-multi", "-membed", "-mn"
}


def detect_hardware():
    cpu_cores = os.cpu_count() or 1
    gpu_count = 0
    gpu_ids = []
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
            gpu_ids = ids
            gpu_count = len(ids)
    except Exception:
        pass

    return {
        "cpu_cores": cpu_cores,
        "gpu_count": gpu_count,
        "gpu_ids": gpu_ids,
    }


def tune_mdrun_args(command, args):
    tuning = {}
    if command != "mdrun":
        return args, tuning

    hardware = detect_hardware()
    tuned = dict(args)

    if "-ntmpi" not in tuned:
        tuned["-ntmpi"] = "1"
        tuning["-ntmpi"] = "1"

    if "-ntomp" not in tuned:
        ntomp = min(8, max(1, hardware["cpu_cores"]))
        tuned["-ntomp"] = str(ntomp)
        tuning["-ntomp"] = str(ntomp)

    if hardware["gpu_count"] > 0 and "-gpu_id" not in tuned:
        tuned["-gpu_id"] = hardware["gpu_ids"][0] if hardware["gpu_ids"] else "0"
        tuning["-gpu_id"] = tuned["-gpu_id"]

    return tuned, {"hardware": hardware, "applied": tuning}


def build_cmd(command, args, gmx_bin="gmx"):
    cmd = [gmx_bin, command]
    for k, v in args.items():
        cmd.append(k)
        if str(v).strip() != "":
            cmd.append(str(v))
    return cmd


def command_fingerprint(cmd, cwd, interactive_responses):
    payload = {
        "cwd": os.path.abspath(cwd),
        "cmd": cmd,
        "interactive_responses": interactive_responses,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_input_files(args, cwd):
    missing = []
    for flag, value in args.items():
        if flag not in INPUT_FILE_FLAGS:
            continue
        value_str = str(value).strip()
        if not value_str:
            continue
        candidate = value_str if os.path.isabs(value_str) else os.path.join(cwd, value_str)
        if not os.path.exists(candidate):
            missing.append({"flag": flag, "path": candidate})
    return missing


def backup_topology_file(cwd):
    top_path = os.path.join(cwd, "topol.top")
    if not os.path.exists(top_path):
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = f"{top_path}.bak_{timestamp}"
    shutil.copy2(top_path, bak_path)
    return bak_path


def rollback_topology(backup_path, cwd):
    if not backup_path:
        return False
    top_path = os.path.join(cwd, "topol.top")
    if not os.path.exists(backup_path):
        return False
    shutil.copy2(backup_path, top_path)
    return True

def get_available_groups(command, args, cwd, gmx_bin="gmx"):
    """Runs a command that usually asks for a group and returns the list of available groups."""
    cmd = build_cmd(command, args, gmx_bin)
    try:
        # We send an empty string to trigger the group selection prompt and then capture stdout
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        stdout, _ = proc.communicate(input="\n", timeout=10)
        groups = []
        capture = False
        for line in stdout.splitlines():
            if "Group" in line and ":" in line:
                groups.append(line.strip())
        return groups
    except Exception:
        return []


def run_gmx(input_data):
    command = input_data.get("command")
    args = input_data.get("args", {})
    interactive_responses = input_data.get("interactive_responses", [])
    backup_topology = input_data.get("backup_topology", False)
    
    # Enforce backup for destructive steps
    if command in ["solvate", "genion"]:
        backup_topology = True
        
    retry_count = input_data.get("retry_count", 0)
    timeout_seconds = input_data.get("timeout_seconds", 3600)
    cwd = input_data.get("cwd", os.getcwd())
    gmx_bin = input_data.get("gmx_bin", os.environ.get("GMX_BIN", "gmx"))
    
    # Helper to get groups if requested
    if input_data.get("list_groups_only", False):
        groups = get_available_groups(command, args, cwd, gmx_bin)
        return {"status": "success", "available_groups": groups}

    previous_attempt_fingerprints = input_data.get("previous_attempt_fingerprints", [])

    if retry_count >= 3:
        return {
            "status": "error",
            "fatal_error": "Max retry count (3) exceeded.",
            "summary": "Agent exceeded retry limits."
        }

    if not os.path.exists(cwd):
        os.makedirs(cwd, exist_ok=True)

    args, tuning_meta = tune_mdrun_args(command, args)
    missing_inputs = validate_input_files(args, cwd)
    if missing_inputs:
        return {
            "status": "error",
            "fatal_error": "Missing required input files.",
            "summary": "Input file validation failed before execution.",
            "missing_inputs": missing_inputs,
        }

    cmd = build_cmd(command, args, gmx_bin)
    fingerprint = command_fingerprint(cmd, cwd, interactive_responses)
    if fingerprint in previous_attempt_fingerprints:
        return {
            "status": "error",
            "fatal_error": "Retry uses identical command/input fingerprint.",
            "summary": "Modify parameters before retry to avoid infinite loop.",
            "command_fingerprint": fingerprint,
        }

    bak_path = backup_topology_file(cwd) if backup_topology else None

    start_time = time.time()
    
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        input_str = ""
        if interactive_responses:
            input_str = "\n".join(interactive_responses) + "\n"
        
        stdout, _ = proc.communicate(input=input_str, timeout=timeout_seconds)
        elapsed = time.time() - start_time
        
        lines = stdout.split('\n')
        
        # Check for fatal error
        fatal_idx = -1
        for i, line in enumerate(lines):
            if "Fatal error:" in line:
                fatal_idx = i
                break
                
        if proc.returncode != 0 or fatal_idx != -1:
            fatal_error = "Unknown error"
            if fatal_idx != -1:
                fatal_error = "\n".join(lines[fatal_idx:fatal_idx+5])
            
            summary_lines = [line for line in lines if line.strip()][-5:]
            return {
                "status": "error",
                "fatal_error": fatal_error.strip(),
                "summary": "\n".join(summary_lines).strip(),
                "elapsed_seconds": round(elapsed, 2),
                "command_fingerprint": fingerprint,
                "topology_rolled_back": rollback_topology(bak_path, cwd) if backup_topology else False,
                "tuning": tuning_meta,
            }
            
        # Find newly created or modified files
        output_files = []
        for f in os.listdir(cwd):
            fpath = os.path.join(cwd, f)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) >= start_time:
                output_files.append(f)
                
        summary_lines = [line for line in lines if line.strip()][-5:]
        return {
            "status": "success",
            "output_files": output_files,
            "summary": "\n".join(summary_lines).strip(),
            "elapsed_seconds": round(elapsed, 2),
            "command_fingerprint": fingerprint,
            "topology_backup": bak_path,
            "tuning": tuning_meta,
        }
        
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        elapsed = time.time() - start_time
        return {
            "status": "timeout",
            "fatal_error": f"Command timed out after {timeout_seconds} seconds.",
            "summary": "Timeout reached.",
            "elapsed_seconds": round(elapsed, 2),
            "command_fingerprint": fingerprint,
            "tuning": tuning_meta,
        }
    except Exception as e:
        return {
            "status": "error",
            "fatal_error": str(e),
            "summary": "Exception occurred during execution.",
            "elapsed_seconds": round(time.time() - start_time, 2),
            "command_fingerprint": fingerprint,
            "topology_rolled_back": rollback_topology(bak_path, cwd) if backup_topology else False,
            "tuning": tuning_meta,
        }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            input_data = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r") as f:
                input_data = json.load(f)
    else:
        input_data = json.loads(sys.stdin.read())
        
    result = run_gmx(input_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
