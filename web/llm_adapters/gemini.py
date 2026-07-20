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
        # Do not rely on an unverified auto-accept flag or bypass approvals.
        return ["agy"]
