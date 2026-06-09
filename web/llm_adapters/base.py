from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

_ANSI_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-9;]*[mGKHFABCDJsr]"
    r"|\[\?[0-9;]*[hlr]"
    r"|[=>]"
    r")"
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


@dataclass
class PermissionRequest:
    id: str
    tool: str    # "bash", "write", "read", …
    detail: str  # command or file path shown to user


class LLMAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def cli(self) -> str: ...

    @abstractmethod
    def build_command(self, auto_approve: bool) -> list[str]:
        """Return argv list to spawn the LLM process (no initial prompt)."""
        ...

    def build_prompt(self, harness_dir: Path, workspace: Path, pdb_path: Path) -> str:
        return (
            f"You are a GROMACS molecular dynamics expert.\n\n"
            f"Harness directory : {harness_dir}\n"
            f"Workspace         : {workspace}\n"
            f"Input PDB         : {pdb_path}\n\n"
            f"Instructions:\n"
            f"1. Read {harness_dir}/AGENTS.md to understand the pipeline and rules.\n"
            f"2. Execute the complete pipeline (Steps 0-8) for the given protein.\n"
            f"3. Call skills in {harness_dir}/skills/ as Python functions.\n"
            f"4. Update {workspace}/state.json after each step via lib/state.py.\n\n"
            f"Begin now."
        )

    @abstractmethod
    def parse_permission(self, clean_text: str) -> PermissionRequest | None:
        """Detect a permission prompt in clean (ANSI-stripped) buffered output."""
        ...

    def approve_bytes(self) -> bytes:
        return b"y\n"

    def deny_bytes(self) -> bytes:
        return b"n\n"
