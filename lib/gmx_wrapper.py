import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class GmxResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    classification: str  # success | grompp_warning | topology_mismatch | command_error

    @property
    def ok(self) -> bool:
        return self.classification == "success"


CLASSIFIERS = [
    ("topology_mismatch",
     re.compile(r"does not match topology|moltype.*not found", re.I)),
    ("grompp_warning",
     re.compile(r"WARNING\s+\d+\s+\[", re.I)),
]

_COMMON_GMX_PATHS = [
    "/usr/local/gromacs/bin/gmx",
    "/usr/bin/gmx",
    "/opt/gromacs/bin/gmx",
    "/opt/local/bin/gmx",
]

# Glob patterns for conda-style installs where the bin dir may vary by arch
_CONDA_GMX_GLOBS = [
    "~/anaconda3/envs/*/bin*/gmx",
    "~/miniconda3/envs/*/bin*/gmx",
    "~/mambaforge/envs/*/bin*/gmx",
    "/opt/conda/envs/*/bin*/gmx",
]


def _resolve_gmx_bin(default: str = "gmx") -> str:
    if env_bin := os.environ.get("GMX_BIN"):
        return env_bin
    if found := shutil.which(default):
        return found
    for p in _COMMON_GMX_PATHS:
        if Path(p).exists():
            return p
    import glob
    for pattern in _CONDA_GMX_GLOBS:
        matches = sorted(glob.glob(os.path.expanduser(pattern)))
        if matches:
            return matches[0]
    return default


def _resolve_gmxlib(gmx_bin: str) -> str | None:
    """Infer GMXLIB from gmx binary path when not already set in environment."""
    if os.environ.get("GMXLIB"):
        return None
    p = Path(gmx_bin)
    if p.is_file():
        candidate = p.parent.parent / "share" / "gromacs" / "top"
        if candidate.is_dir():
            return str(candidate)
    return None


def get_gmxlib() -> str | None:
    """Return the effective GMXLIB path (env var or auto-detected)."""
    if lib := os.environ.get("GMXLIB"):
        return lib
    return _resolve_gmxlib(_resolve_gmx_bin())


def get_version() -> str | None:
    """Return the `gmx --version` version string (e.g. "2023.3"), or None if
    the `gmx` binary is unavailable/unresponsive. Never raises — provenance
    capture must degrade gracefully when GROMACS isn't installed."""
    gmx_bin = _resolve_gmx_bin()
    try:
        completed = subprocess.run(
            [gmx_bin, "--version"], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        if "GROMACS version" in line:
            return line.split(":", 1)[-1].strip()
    return None


def _classify(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "success"
    for tag, pat in CLASSIFIERS:
        if pat.search(stderr):
            return tag
    return "command_error"


def run(args: Sequence[str], cwd: Path,
        interactive_inputs: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        progress_log: Path | None = None) -> GmxResult:
    gmx_bin = _resolve_gmx_bin()
    auto_gmxlib = _resolve_gmxlib(gmx_bin)
    merged_env = {**os.environ}
    if auto_gmxlib:
        merged_env["GMXLIB"] = auto_gmxlib
    if env:
        merged_env.update(env)
    cmd = [gmx_bin] + list(args)
    proc_input = "\n".join(interactive_inputs) + "\n" if interactive_inputs else None

    if progress_log is None:
        completed = subprocess.run(
            cmd, cwd=str(cwd), input=proc_input, text=True,
            capture_output=True, env=merged_env,
            timeout=timeout,
        )
        return GmxResult(
            command=cmd,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            classification=_classify(completed.returncode, completed.stderr or ""),
        )

    # Streaming mode: write combined stdout+stderr to progress_log in real-time
    stdout_buf: list[str] = []
    stderr_buf: list[str] = []

    proc = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdin=subprocess.PIPE if proc_input else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=merged_env,
    )

    log_lock = threading.Lock()

    def _reader(stream, buf: list[str], log_fh) -> None:
        for line in stream:
            buf.append(line)
            with log_lock:
                log_fh.write(line)
                log_fh.flush()

    with open(progress_log, "a", encoding="utf-8", errors="replace") as log_fh:
        t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_buf, log_fh), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_buf, log_fh), daemon=True)
        t_out.start(); t_err.start()
        if proc_input:
            try:
                proc.stdin.write(proc_input)
                proc.stdin.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        finally:
            t_out.join()
            t_err.join()

    stdout = "".join(stdout_buf)
    stderr = "".join(stderr_buf)
    return GmxResult(
        command=cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        classification=_classify(proc.returncode, stderr),
    )


def backup_topology(top: Path) -> Path:
    bak = top.with_suffix(top.suffix + ".bak")
    shutil.copy2(top, bak)
    return bak


def restore_topology(top: Path) -> None:
    bak = top.with_suffix(top.suffix + ".bak")
    if not bak.exists():
        raise FileNotFoundError(f"no backup found: {bak}")
    shutil.copy2(bak, top)
