from __future__ import annotations

import re
import uuid

from .base import LLMAdapter, PermissionRequest

# OpenAI Codex CLI with --approval-mode suggest shows:
#   > gmx pdb2gmx …
#   Run this command? [y/N]
_YN_RE = re.compile(r"Run this command\?|Approve\?|\[y/N\]|\[Y/n\]", re.IGNORECASE)


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

    def parse_permission(self, clean_text: str) -> PermissionRequest | None:
        if _YN_RE.search(clean_text):
            lines = [l for l in clean_text.splitlines() if l.strip()]
            detail = "\n".join(lines[-20:]) if lines else clean_text[-500:]
            return PermissionRequest(
                id=str(uuid.uuid4()),
                tool="bash",
                detail=detail,
            )
        return None
