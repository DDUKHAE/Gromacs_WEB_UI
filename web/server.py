import asyncio
import os
import re
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

    @app.post("/api/runs", status_code=201)
    async def api_create_run(
        hd: HarnessDir,
        pdb_file: UploadFile = File(...),
        forcefield: str = Form("charmm36"),
        water: str = Form("tip3p"),
        box_type: str = Form("dodecahedron"),
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

    @app.websocket("/ws/runs/{run_id}")
    async def ws_logs(websocket: WebSocket, run_id: str, hd: HarnessDir):
        await websocket.accept()
        try:
            workspace = _check_run_id(run_id, hd / "runs")
        except HTTPException:
            await websocket.close()
            return
        log_file = workspace / "runner.log"
        for _ in range(30):
            if log_file.exists():
                break
            await asyncio.sleep(0.5)
        if not log_file.exists():
            await websocket.close()
            return
        try:
            with open(log_file, encoding="utf-8", errors="replace") as f:
                existing = f.read()
                if existing:
                    await websocket.send_text(existing)
                while True:
                    line = f.readline()
                    if line:
                        await websocket.send_text(line)
                    else:
                        info = read_run(run_id, workspace.parent)
                        if info is None or info.status != "running":
                            break
                        await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            pass
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
