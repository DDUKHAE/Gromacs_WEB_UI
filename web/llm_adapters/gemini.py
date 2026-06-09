from __future__ import annotations

from .base import LLMAdapter


class GeminiAdapter(LLMAdapter):
    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def cli(self) -> str:
        return "agy"

    def build_command(self, auto_approve: bool) -> list[str]:
        cmd = ["agy"]
        if auto_approve:
            # TODO: confirm exact auto-approve flag for the installed agy version
            cmd.append("--auto-accept")
        return cmd
