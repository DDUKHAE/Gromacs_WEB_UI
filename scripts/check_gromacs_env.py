#!/usr/bin/env python3
"""Probe runtime dependencies for the GROMACS harness.

Checks GROMACS (required for env-builder/md-runner), plus optional tools the
illustrator skill uses: PyMOL/VMD for structural rendering, ffmpeg for
animation, matplotlib/plotly for plots and HTML reports. Prints a JSON
summary so the LLM agent (or CI) can decide which features will degrade.
"""
import importlib.util
import json
import os
import shutil
import subprocess
from typing import Any


def run_cmd(cmd: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=timeout,
        )
        return {"ok": p.returncode == 0, "code": p.returncode,
                "output": p.stdout.strip()[:400]}
    except Exception as e:
        return {"ok": False, "code": -1, "output": str(e)[:400]}


def find_candidates(names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        p = shutil.which(name)
        if p:
            out[name] = p
    return out


def _resolve_gmx() -> str | None:
    env_bin = os.environ.get("GMX_BIN")
    if env_bin and shutil.which(env_bin):
        return env_bin
    for name in ("gmx", "gmx_mpi"):
        if shutil.which(name):
            return name
    return None


def _check_python_module(name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(name)
    if spec is None:
        return {"ok": False, "reason": "module not installed"}
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "unknown")
        return {"ok": True, "version": version}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def main() -> None:
    # GROMACS (required)
    env_bin = os.environ.get("GMX_BIN")
    gmx_candidates = find_candidates(["gmx", "gmx_mpi"])
    resolved_gmx = _resolve_gmx()
    gmx_checks: dict[str, Any] = {}
    if resolved_gmx:
        gmx_checks["version"] = run_cmd([resolved_gmx, "--version"])
    else:
        gmx_checks["version"] = {
            "ok": False, "code": -1,
            "output": "No runnable GROMACS binary found.",
        }

    # Illustrator dependencies (optional)
    renderer_candidates = find_candidates(["pymol", "vmd"])
    ffmpeg_path = shutil.which("ffmpeg")
    matplotlib_check = _check_python_module("matplotlib")
    plotly_check = _check_python_module("plotly")

    if "pymol" in renderer_candidates:
        renderer = "pymol"
    elif "vmd" in renderer_candidates:
        renderer = "vmd"
    else:
        renderer = "none"

    payload = {
        "gromacs": {
            "env_bin": env_bin,
            "found_binaries": gmx_candidates,
            "resolved_binary": resolved_gmx,
            "checks": gmx_checks,
            "ready": bool(resolved_gmx and gmx_checks["version"]["ok"]),
        },
        "illustrator": {
            "renderer": renderer,
            "renderer_paths": renderer_candidates,
            "ffmpeg": {"path": ffmpeg_path, "available": ffmpeg_path is not None},
            "matplotlib": matplotlib_check,
            "plotly": plotly_check,
            "capabilities": {
                "plots": matplotlib_check["ok"],
                "structure_render": renderer != "none",
                "animation": renderer != "none" and ffmpeg_path is not None,
                "html_report": plotly_check["ok"],
            },
        },
        "ready_for_pipeline": bool(
            resolved_gmx
            and gmx_checks["version"]["ok"]
            and matplotlib_check["ok"]
        ),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
