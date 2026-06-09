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
        if auto_approve:
            return ["codex", "--approval-mode", "full-auto"]
        return ["codex", "--approval-mode", "suggest"]
