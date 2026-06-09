from __future__ import annotations

import re
import uuid

from .base import LLMAdapter, PermissionRequest

# Claude Code (interactive mode) shows permission prompts like:
#   Do you want to run the following bash command?
#     gmx pdb2gmx …
#   [y/n] (y):
_PERM_RE = re.compile(
    r"(?:Do you want to|Allow|Permission required|run the following)",
    re.IGNORECASE,
)
_YN_RE = re.compile(r"\[y/n\]|\[Y/n\]|\[y/N\]", re.IGNORECASE)


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

    def parse_permission(self, clean_text: str) -> PermissionRequest | None:
        if _YN_RE.search(clean_text) and _PERM_RE.search(clean_text):
            lines = [l for l in clean_text.splitlines() if l.strip()]
            detail = "\n".join(lines[-20:]) if lines else clean_text[-500:]
            return PermissionRequest(
                id=str(uuid.uuid4()),
                tool="bash",
                detail=detail,
            )
        return None
