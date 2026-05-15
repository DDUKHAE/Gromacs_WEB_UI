import os
import re
import shutil
import subprocess
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


def _resolve_gmx_bin(default: str = "gmx") -> str:
    env_bin = os.environ.get("GMX_BIN")
    if env_bin:
        return env_bin
    found = shutil.which(default)
    if found:
        return found
    return default


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
        timeout: int | None = None) -> GmxResult:
    cmd = [_resolve_gmx_bin()] + list(args)
    proc_input = "\n".join(interactive_inputs) + "\n" if interactive_inputs else None
    completed = subprocess.run(
        cmd, cwd=str(cwd), input=proc_input, text=True,
        capture_output=True, env={**os.environ, **(env or {})},
        timeout=timeout,
    )
    return GmxResult(
        command=cmd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        classification=_classify(completed.returncode, completed.stderr or ""),
    )
