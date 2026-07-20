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
        # Host-side automatic permission bypass is intentionally unsupported.
        # `auto_approve` remains in the interface for backwards-compatible
        # callers; the web API rejects it before reaching an adapter.
        return ["claude"]
