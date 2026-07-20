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
        return ["codex", "--approval-mode", "suggest"]
