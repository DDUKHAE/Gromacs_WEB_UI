from __future__ import annotations

from .base import LLMAdapter


class CodexAdapter(LLMAdapter):
    @property
    def name(self) -> str:
        return "Codex"

    @property
    def cli(self) -> str:
        return "codex"

    def build_command(self, auto_approve: bool) -> list[str]:
        # Do not grant an external agent unattended host command execution.
        # The API always launches this adapter with interactive approvals.
        return ["codex", "--ask-for-approval", "on-request"]

    @property
    def accepts_initial_prompt_argument(self) -> bool:
        # Codex accepts an optional prompt argument and submits it after the
        # TUI/MCP startup sequence.  PTY injection during startup can be lost.
        return True
