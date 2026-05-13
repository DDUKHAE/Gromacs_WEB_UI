#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
from typing import Dict, Any, List


def run_cmd(cmd: List[str]) -> Dict[str, Any]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10)
        return {"ok": p.returncode == 0, "code": p.returncode, "output": p.stdout.strip()}
    except Exception as e:
        return {"ok": False, "code": -1, "output": str(e)}


def find_candidates() -> Dict[str, str]:
    out = {}
    for name in ["gmx", "gmx_mpi"]:
        p = shutil.which(name)
        if p:
            out[name] = p
    return out


def main() -> None:
    env_bin = os.environ.get("GMX_BIN")
    candidates = find_candidates()
    resolved = None
    if env_bin and shutil.which(env_bin):
        resolved = env_bin
    elif "gmx" in candidates:
        resolved = "gmx"
    elif "gmx_mpi" in candidates:
        resolved = "gmx_mpi"

    checks = {}
    if resolved:
        checks["version"] = run_cmd([resolved, "--version"])
        checks["help"] = run_cmd([resolved, "help"])
    else:
        checks["version"] = {"ok": False, "code": -1, "output": "No runnable GROMACS binary found."}

    payload = {
        "gmxb_env": env_bin,
        "found_binaries": candidates,
        "resolved_binary": resolved,
        "checks": checks,
        "ready": bool(resolved and checks.get("version", {}).get("ok")),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
