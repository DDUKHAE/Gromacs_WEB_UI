"""LLM-driven runner using a PTY so interactive CLIs work in full.

PTY output → output_queue (raw bytes) → WebSocket → xterm.js
User input ← input_queue  (raw bytes) ← WebSocket ← xterm.js
Resize events → set_winsize() called directly from WebSocket handler.

The PTY reader thread also writes ANSI-stripped output to runner.log
for persistence, so re-connecting browsers can replay history.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import re
import shutil
import struct
import subprocess
import termios
import threading
from dataclasses import dataclass, field
from pathlib import Path

from web.llm_adapters import ADAPTERS, LLMAdapter
from lib.system_config import load_config, build_constraint_prompt

_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;]*[mGKHFABCDJsr]|\[\?[0-9;]*[hlr]|[=>])")

_PERM_RE = re.compile(
    r'Allow\?\s*\[\s*y\s*/\s*n\s*\]|'  # Claude Code: "Allow? [y/n]"
    r'\[y/n\]|'                          # Generic [y/n]
    r'\[Y/n\]|'                          # Generic [Y/n]
    r'\(y/n\)',                           # Generic (y/n)
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _apply_system_config_constraint(workspace: Path) -> str:
    """Return constraint block if system_config.json exists, else empty string."""
    config = load_config(workspace)
    if config is None:
        return ""
    return build_constraint_prompt(config)


@dataclass
class LLMRunState:
    output_queue: asyncio.Queue[bytes | None] = field(default_factory=asyncio.Queue)
    input_queue:  asyncio.Queue[bytes]        = field(default_factory=asyncio.Queue)
    master_fd: int = -1
    pid: int = 0


_run_states: dict[str, LLMRunState] = {}


def get_run_state(run_id: str) -> LLMRunState | None:
    return _run_states.get(run_id)


def check_cli(adapter: LLMAdapter) -> bool:
    return shutil.which(adapter.cli) is not None


def set_winsize(master_fd: int, rows: int, cols: int) -> None:
    try:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


async def run_llm_agent(
    run_id: str,
    workspace: Path,
    pdb_path: Path,
    harness_dir: Path,
    llm_key: str,
    auto_approve: bool,
) -> None:
    adapter = ADAPTERS[llm_key]
    state = LLMRunState()
    _run_states[run_id] = state

    log_path  = workspace / "runner.log"
    exit_path = workspace / "runner.exit"
    pid_path  = workspace / "runner.pid"

    cmd    = adapter.build_command(auto_approve)
    prompt = adapter.build_prompt(harness_dir, workspace, pdb_path)
    prompt += _apply_system_config_constraint(workspace)

    master_fd, slave_fd = pty.openpty()
    set_winsize(master_fd, rows=50, cols=220)
    state.master_fd = master_fd

    loop     = asyncio.get_running_loop()
    output_q = state.output_queue

    def _pty_reader() -> None:
        """Read PTY output in a thread; write to log + enqueue for WebSocket."""
        perm_context: list[str] = []
        with open(log_path, "a", encoding="utf-8", errors="replace") as log_fh:
            while True:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                text = data.decode("utf-8", errors="replace")
                stripped = strip_ansi(text)
                log_fh.write(stripped)
                log_fh.flush()
                loop.call_soon_threadsafe(output_q.put_nowait, data)

                # Accumulate context lines for permission dialog
                perm_context.extend(stripped.splitlines())
                if len(perm_context) > 20:
                    perm_context = perm_context[-20:]

                if _PERM_RE.search(stripped):
                    detail = "\n".join(perm_context[-8:])
                    event = json.dumps({
                        "type": "permission_request",
                        "detail": detail,
                    })
                    loop.call_soon_threadsafe(output_q.put_nowait, event.encode("utf-8"))
                    perm_context = perm_context[-8:]

        loop.call_soon_threadsafe(output_q.put_nowait, None)   # EOF sentinel

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            cwd=str(harness_dir),
        )
    except FileNotFoundError:
        os.close(slave_fd)
        os.close(master_fd)
        msg = f"[error] CLI not found: {cmd[0]}\r\n"
        loop.call_soon_threadsafe(output_q.put_nowait, msg.encode())
        loop.call_soon_threadsafe(output_q.put_nowait, None)
        log_path.write_text(msg)
        exit_path.write_text("1")
        _run_states.pop(run_id, None)
        return

    os.close(slave_fd)
    state.pid = proc.pid
    pid_path.write_text(str(proc.pid))

    threading.Thread(target=_pty_reader, daemon=True).start()

    # Deliver initial prompt (simulates the user's first message)
    try:
        os.write(master_fd, (prompt + "\n").encode())
    except OSError:
        pass

    async def _pty_writer() -> None:
        """Forward keystrokes from WebSocket to PTY stdin."""
        while True:
            data = await state.input_queue.get()
            try:
                os.write(master_fd, data)
            except OSError:
                break

    writer_task = asyncio.create_task(_pty_writer())

    # Wait for process to finish
    await asyncio.get_event_loop().run_in_executor(None, proc.wait)

    writer_task.cancel()
    exit_code = proc.returncode
    exit_path.write_text(str(exit_code))

    try:
        os.close(master_fd)
    except OSError:
        pass

    _run_states.pop(run_id, None)
