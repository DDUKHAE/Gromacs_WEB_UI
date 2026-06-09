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
            f"Read {harness_dir}/AGENTS.md for mandatory rules (state tracking, topology backups, retry policy).\n\n"
            f"Execute the pipeline by calling the three entry points below IN ORDER.\n"
            f"IMPORTANT: Do NOT write a new Python script. Do NOT run gmx commands directly.\n"
            f"Call each entry point interactively in this session.\n\n"
            f"Before each call, read {workspace}/state.json via:\n"
            f"  import sys; sys.path.insert(0, '{harness_dir}')\n"
            f"  from lib import state\n"
            f"  s = state.read('{workspace}')\n"
            f"  print(s.get('last_completed_stage'))  # skip step if already done\n\n"
            f"## Step 0-5: Build MD environment\n"
            f"```python\n"
            f"from skills.env_builder.env_builder import build_environment\n"
            f"build_environment(\n"
            f"    pdb_path='{pdb_path}',\n"
            f"    prompt='standard aqueous protein MD simulation',\n"
            f"    workspace_dir='{workspace}',\n"
            f"    interactive=False,\n"
            f")\n"
            f"```\n\n"
            f"## Step 6-7: Run MD simulation (EM → NVT → NPT → production)\n"
            f"```python\n"
            f"from skills.md_runner.md_runner import run_simulation\n"
            f"run_simulation(\n"
            f"    workspace_dir='{workspace}',\n"
            f"    interactive=False,\n"
            f")\n"
            f"```\n\n"
            f"## Step 8: Analyze results and generate report\n"
            f"```python\n"
            f"from skills.illustrator.illustrator import illustrate\n"
            f"illustrate(\n"
            f"    workspace_dir='{workspace}',\n"
            f"    interactive=False,\n"
            f")\n"
            f"```\n\n"
            f"Begin now."
        )
