"""LLM-driven simulation runner.

Spawns the selected LLM CLI via a PTY so interactive permission prompts work,
streams output to runner.log, and bridges permission requests/responses between
the LLM process and the WebSocket layer via asyncio queues.
"""
from __future__ import annotations

import asyncio
import os
import pty
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

from web.llm_adapters import ADAPTERS, LLMAdapter, PermissionRequest, strip_ansi

# Limit permission-detection buffer to avoid false positives on large output
_PERM_BUF_SIZE = 4096


@dataclass
class LLMRunState:
    request_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    response_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    pid: int = 0


_run_states: dict[str, LLMRunState] = {}


def get_run_state(run_id: str) -> LLMRunState | None:
    return _run_states.get(run_id)


def check_cli(adapter: LLMAdapter) -> bool:
    return shutil.which(adapter.cli) is not None


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

    log_path = workspace / "runner.log"
    exit_path = workspace / "runner.exit"
    pid_path = workspace / "runner.pid"

    # Build command and initial prompt
    cmd = adapter.build_command(auto_approve)
    prompt = adapter.build_prompt(harness_dir, workspace, pdb_path)

    # Open PTY so the CLI thinks it has a terminal
    master_fd, slave_fd = pty.openpty()

    loop = asyncio.get_running_loop()
    pty_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def _pty_reader() -> None:
        while True:
            try:
                data = os.read(master_fd, 4096)
                loop.call_soon_threadsafe(pty_queue.put_nowait, data)
            except OSError:
                break
        loop.call_soon_threadsafe(pty_queue.put_nowait, None)

    import subprocess
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
        log_path.write_text(f"[error] CLI not found: {cmd[0]}\n")
        exit_path.write_text("1")
        _run_states.pop(run_id, None)
        return

    os.close(slave_fd)
    state.pid = proc.pid
    pid_path.write_text(str(proc.pid))

    threading.Thread(target=_pty_reader, daemon=True).start()

    # Send initial prompt (simulate user typing)
    try:
        os.write(master_fd, (prompt + "\n").encode())
    except OSError:
        pass

    perm_buffer = ""
    awaiting_perm = False

    with open(log_path, "a", encoding="utf-8") as log_file:
        while True:
            try:
                chunk = await asyncio.wait_for(pty_queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                if proc.poll() is not None:
                    break
                continue

            if chunk is None:
                break

            clean = strip_ansi(chunk.decode("utf-8", errors="replace"))
            log_file.write(clean)
            log_file.flush()

            if auto_approve or awaiting_perm:
                continue

            perm_buffer += clean
            if len(perm_buffer) > _PERM_BUF_SIZE:
                perm_buffer = perm_buffer[-_PERM_BUF_SIZE:]

            req = adapter.parse_permission(perm_buffer)
            if req:
                awaiting_perm = True
                await state.request_queue.put(req)

                # Block until browser responds
                granted: bool = await state.response_queue.get()

                perm_buffer = ""
                awaiting_perm = False

                try:
                    response = adapter.approve_bytes() if granted else adapter.deny_bytes()
                    os.write(master_fd, response)
                except OSError:
                    pass

    exit_code = proc.wait()
    exit_path.write_text(str(exit_code))

    try:
        os.close(master_fd)
    except OSError:
        pass

    _run_states.pop(run_id, None)
