from __future__ import annotations

from .base import LLMAdapter


class ClaudeAdapter(LLMAdapter):
    @property
    def name(self) -> str:
        return "Claude"

    @property
    def cli(self) -> str:
        return "claude"

    def build_command(self, auto_approve: bool) -> list[str]:
        cmd = ["claude"]
        if auto_approve:
            cmd.append("--dangerously-skip-permissions")
        return cmd
