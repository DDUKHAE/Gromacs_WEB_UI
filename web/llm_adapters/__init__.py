from .base import LLMAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .gemini import GeminiAdapter

ADAPTERS: dict[str, LLMAdapter] = {
    "claude": ClaudeAdapter(),
    "gemini": GeminiAdapter(),
    "codex": CodexAdapter(),
}

__all__ = ["ADAPTERS", "LLMAdapter"]
