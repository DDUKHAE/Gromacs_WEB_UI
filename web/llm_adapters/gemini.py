from __future__ import annotations

import re
import uuid

from .base import LLMAdapter, PermissionRequest

# agy (Gemini 3.5 CLI) permission prompt patterns.
# NOTE: exact flags may need adjustment for the installed agy version.
_PERM_RE = re.compile(
    r"(?:Do you want to|Allow|approve|permission|confirm)",
    re.IGNORECASE,
)
_YN_RE = re.compile(r"\[y/n\]|\[Y/n\]|\[y/N\]|yes/no", re.IGNORECASE)


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
            # TODO: replace with the actual agy auto-approve flag if different
            cmd.append("--auto-accept")
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
