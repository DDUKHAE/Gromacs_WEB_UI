from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LLMAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def cli(self) -> str: ...

    @abstractmethod
    def build_command(self, auto_approve: bool) -> list[str]:
        """Return argv to spawn the LLM process (no initial prompt argument)."""
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
