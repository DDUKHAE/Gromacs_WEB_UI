import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lib import xvg_parser
from web.llm_adapters import ADAPTERS
from web import llm_runner
from web.run_reader import RunInfo, list_runs, read_run

HARNESS_DIR: Path = Path(__file__).parent.parent
RUNNER_PY: Path = Path(__file__).parent / "runner.py"
STATIC_DIR: Path = Path(__file__).parent / "static"
_NEXT_SKILL: dict[str, str] = {"env": "md", "md": "viz"}
_MAX_PDB_BYTES: int = 50 * 1024 * 1024  # 50 MB
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*_\d{8}_\d{6}$")


def get_harness_dir() -> Path:
    return HARNESS_DIR


HarnessDir = Annotated[Path, Depends(get_harness_dir)]


def _check_run_id(run_id: str, runs_dir: Path) -> Path:
    """Validate run_id and return its resolved workspace path.

    Raises HTTPException 400 if the run_id format is invalid or the resolved
    path escapes runs_dir (path traversal guard).
    """
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="invalid run_id format")
    resolved = (runs_dir / run_id).resolve()
    if not str(resolved).startswith(str(runs_dir.resolve()) + os.sep):
        raise HTTPException(status_code=400, detail="invalid run_id")
    return resolved


def _run_summary(info: RunInfo) -> dict:
    return {
        "run_id": info.run_id,
        "status": info.status,
        "protein": info.protein,
        "created_at": info.created_at,
        "last_completed_stage": info.last_completed_stage,
        "current_step": info.current_step,
    }


def create_app(harness_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Gromacs Harness Web UI")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    if harness_dir is not None:
        app.dependency_overrides[get_harness_dir] = lambda: harness_dir

    @app.get("/api/runs")
    def api_list_runs(hd: HarnessDir) -> list[dict]:
        return [_run_summary(i) for i in list_runs(hd / "runs")]

    @app.get("/api/runs/{run_id}")
    def api_get_run(run_id: str, hd: HarnessDir) -> dict:
        _check_run_id(run_id, hd / "runs")
        info = read_run(run_id, hd / "runs")
        if info is None:
            raise HTTPException(status_code=404, detail="run not found")
        log_tail = ""
        log_file = info.workspace / "runner.log"
        if log_file.exists():
            log_tail = log_file.read_text(encoding="utf-8", errors="replace")
            lines = log_tail.splitlines()
            if len(lines) > 500:
                log_tail = "\n".join(lines[-500:]) + "\n"
        detail = _run_summary(info)
        detail["log_tail"] = log_tail
        detail["pending_warnings"] = info.pending_warnings
        return detail

    @app.get("/api/llms")
    def api_list_llms() -> list[dict]:
        return [{"key": k, "name": a.name, "cli": a.cli} for k, a in ADAPTERS.items()]

    @app.get("/api/runs/{run_id}/artifacts")
    def api_get_artifacts(run_id: str, hd: HarnessDir) -> list[dict]:
        workspace = _check_run_id(run_id, hd / "runs")
        viz_dir = workspace / "stage3_viz"
        if not viz_dir.exists():
            return []
        results = []
        for xvg_path in sorted(viz_dir.glob("*.xvg")):
            try:
                parsed = xvg_parser.parse(xvg_path, max_points=300)
                results.append({"name": xvg_path.stem, **parsed})
            except Exception:
                pass
        return results

    @app.post("/api/runs", status_code=201)
    async def api_create_run(
        hd: HarnessDir,
        pdb_file: UploadFile = File(...),
        forcefield: str = Form("charmm36"),
        water: str = Form("tip3p"),
        box_type: str = Form("dodecahedron"),
        llm: str = Form(""),
        auto_approve: str = Form("false"),
    ) -> dict:
        raw_stem = Path(pdb_file.filename or "protein").stem
        protein = re.sub(r"[^a-z0-9\-]", "", re.sub(r"^\d+", "", raw_stem).lower())[:40] or "protein"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{protein}_{stamp}"
        ws = hd / "runs" / run_id
        inputs_dir = ws / "inputs"
        inputs_dir.mkdir(parents=True)
        pdb_path = inputs_dir / "input.pdb"
        content = await pdb_file.read(_MAX_PDB_BYTES + 1)
        if len(content) > _MAX_PDB_BYTES:
            raise HTTPException(status_code=413, detail="PDB file too large (max 50 MB)")
        pdb_path.write_bytes(content)

        if llm and llm in ADAPTERS:
            if not llm_runner.check_cli(ADAPTERS[llm]):
                raise HTTPException(status_code=400, detail=f"'{ADAPTERS[llm].cli}' CLI not found. Install and log in first.")
            (ws / "runner.log").write_text("")
            asyncio.create_task(llm_runner.run_llm_agent(
                run_id=run_id,
                workspace=ws,
                pdb_path=pdb_path,
                harness_dir=hd,
                llm_key=llm,
                auto_approve=(auto_approve.lower() == "true"),
            ))
        else:
            log_file = ws / "runner.log"
            log_fd = open(log_file, "w")
            proc = subprocess.Popen(
                [sys.executable, str(RUNNER_PY), "--skill", "env",
                 "--workspace", str(ws), "--pdb", str(pdb_path)],
                cwd=str(hd),
                stdout=log_fd,
                stderr=subprocess.STDOUT,
            )
            log_fd.close()
            (ws / "runner.pid").write_text(str(proc.pid))
        return {"run_id": run_id}

    @app.post("/api/runs/{run_id}/action")
    def api_action(run_id: str, body: dict, hd: HarnessDir) -> dict:
        action = body.get("action")
        if action not in ("continue", "abort"):
            raise HTTPException(status_code=400, detail="action must be 'continue' or 'abort'")
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        if action == "abort":
            pid_file = workspace / "runner.pid"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    if pid <= 0:
                        raise ValueError
                    os.kill(pid, signal.SIGTERM)
                except (ValueError, ProcessLookupError, OSError):
                    pass
            return {"status": "aborted"}
        info = read_run(run_id, hd / "runs")
        if info is None:
            raise HTTPException(status_code=404, detail="run not found")
        if info.status != "paused":
            raise HTTPException(status_code=409, detail=f"run is '{info.status}', not paused")
        next_skill = _NEXT_SKILL.get(info.last_completed_stage or "")
        if not next_skill:
            raise HTTPException(status_code=409, detail="no next skill to continue")
        log_file = info.workspace / "runner.log"
        log_fd = open(log_file, "a")
        proc = subprocess.Popen(
            [sys.executable, str(RUNNER_PY), "--skill", next_skill,
             "--workspace", str(info.workspace)],
            cwd=str(hd),
            stdout=log_fd,
            stderr=subprocess.STDOUT,
        )
        log_fd.close()
        (info.workspace / "runner.pid").write_text(str(proc.pid))
        (info.workspace / "runner.exit").unlink(missing_ok=True)
        return {"status": "started", "skill": next_skill}

    @app.delete("/api/runs/{run_id}", status_code=200)
    def api_delete_run(run_id: str, hd: HarnessDir) -> dict:
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        pid_file = workspace / "runner.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if pid > 0:
                    os.kill(pid, signal.SIGTERM)
            except (ValueError, ProcessLookupError, OSError):
                pass
        shutil.rmtree(workspace, ignore_errors=True)
        return {"status": "deleted"}

    @app.websocket("/ws/runs/{run_id}")
    async def ws_terminal(websocket: WebSocket, run_id: str, hd: HarnessDir):
        await websocket.accept()
        try:
            workspace = _check_run_id(run_id, hd / "runs")
        except HTTPException:
            await websocket.close()
            return

        run_state = llm_runner.get_run_state(run_id)

        if run_state:
            # ── LLM run: full bidirectional PTY proxy ────────────────────────
            async def _send_output() -> None:
                # Replay log history first so reconnects see prior output
                log_file = workspace / "runner.log"
                if log_file.exists():
                    history = log_file.read_bytes()
                    if history:
                        await websocket.send_bytes(history)
                while True:
                    data = await run_state.output_queue.get()
                    if data is None:
                        await websocket.send_text(json.dumps({"type": "exit"}))
                        break
                    await websocket.send_bytes(data)

            async def _recv_input() -> None:
                while True:
                    try:
                        msg = await websocket.receive()
                    except WebSocketDisconnect:
                        break
                    if msg.get("bytes"):
                        await run_state.input_queue.put(msg["bytes"])
                    elif msg.get("text"):
                        try:
                            ctrl = json.loads(msg["text"])
                            if ctrl.get("type") == "resize":
                                llm_runner.set_winsize(
                                    run_state.master_fd,
                                    int(ctrl.get("rows", 50)),
                                    int(ctrl.get("cols", 220)),
                                )
                        except Exception:
                            pass

            tasks = [
                asyncio.create_task(_send_output()),
                asyncio.create_task(_recv_input()),
            ]
        else:
            # ── Direct run: stream runner.log (read-only) ─────────────────────
            log_file = workspace / "runner.log"
            for _ in range(30):
                if log_file.exists():
                    break
                await asyncio.sleep(0.5)

            async def _stream_log() -> None:
                if not log_file.exists():
                    return
                with open(log_file, "rb") as f:
                    while True:
                        data = f.read(4096)
                        if data:
                            await websocket.send_bytes(data)
                            continue
                        info = read_run(run_id, workspace.parent)
                        if info and info.status not in ("running", "pending"):
                            await websocket.send_text(json.dumps({"type": "exit"}))
                            break
                        await asyncio.sleep(0.1)

            async def _recv_ignore() -> None:
                while True:
                    try:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                    except WebSocketDisconnect:
                        break

            tasks = [
                asyncio.create_task(_stream_log()),
                asyncio.create_task(_recv_ignore()),
            ]

        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
        except WebSocketDisconnect:
            for t in tasks:
                t.cancel()
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        html = STATIC_DIR / "index.html"
        if not html.exists():
            return {"message": "index.html not yet created"}
        return FileResponse(str(html))

    return app


app = create_app()
