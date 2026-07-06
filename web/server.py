import asyncio
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from lib import xvg_parser
from lib.system_config import validate_solution_config
from web.llm_adapters import ADAPTERS
from web import llm_runner
from web.run_reader import RunInfo, list_runs, read_run

# Lines matching this pattern are stripped from the chat view entirely
_CHAT_STRIP = re.compile(
    r'^\s*[\$>]\s'                      # shell prompts
    r'|^:-\)'                           # GROMACS smiley
    r'|^GROMACS'                        # GROMACS header
    r'|^Executable:'
    r'|^Data prefix:'
    r'|^Working dir:'
    r'|^Command line:'
    r'|^\s*gmx\b'                       # gmx commands
    r'|^\s*NOTE:'
    r'|^\s*WARNING:'
    r'|^\s*Error\s*in\s*user\s*input'
    r'|^\s*Fatal\s*error'
    r'|^[-=+*]{4,}'                     # separator lines
    r'|^\s*Step\s+Time'                 # MD progress header
    r'|^\s*\d+\s+\d+\.\d+'             # MD step/time rows
    r'|^\s*#\s*gmx\b'                   # commented gmx commands
    r'|Allow\?\s*\[y/n\]\s*$'
    r'|\[y/n\]\s*$|\[Y/n\]\s*$|\(y/n\)\s*$'
    r'|^\s*$',
    re.IGNORECASE,
)

# Purely technical/numeric lines (energy tables, etc.)
_TECH_LINE = re.compile(
    r'^\s*[-\d\s.eE+]+$'
    r'|^\s*Energies\s*\(kJ/mol\)'
    r'|^\s*Bond\s+Angle'
    r'|^\s*Potential\s+Kinetic',
    re.IGNORECASE,
)

_PRESETS_DIR = "presets"


def _filter_chat_log(raw: str) -> str:
    """Return only AI narrative text from runner.log, stripping GROMACS output."""
    lines = raw.splitlines()
    kept: list[str] = []
    for line in lines:
        if _CHAT_STRIP.search(line):
            continue
        if _TECH_LINE.search(line):
            continue
        kept.append(line)

    # Collapse more than 1 consecutive blank line
    result: list[str] = []
    prev_blank = False
    for line in kept:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return "\n".join(result).strip()


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
        "display_name": info.display_name,
    }


def create_app(harness_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Gromacs Harness Web UI")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
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

    # ── Tutorial list ────────────────────────────────────────────────────────
    @app.get("/api/tutorials")
    def api_list_tutorials() -> list[dict]:
        index_path = Path("docs/tutorial/tutorial_index.json")
        if not index_path.exists():
            return []
        try:
            index = json.loads(index_path.read_text())
        except Exception:
            return []
        result = []
        for e in index.get("entries", []):
            result.append({
                "id": e["id"],
                "domain": e.get("domain", ""),
                "difficulty": e.get("difficulty", ""),
                "system_type": e.get("system_type", []),
                "supported": e.get("unsupported_autonomy_level", "none") in ("none", "partial"),
            })
        return result

    # ── Force field endpoints ─────────────────────────────────────────────────
    @app.get("/api/forcefields")
    def api_list_forcefields() -> list[str]:
        from lib.gmx_wrapper import get_gmxlib
        gmxlib = get_gmxlib()
        if not gmxlib or not Path(gmxlib).is_dir():
            return []
        return sorted(
            p.name[:-3] for p in Path(gmxlib).iterdir() if p.name.endswith(".ff")
        )

    _FF_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$")
    _MAX_FF_BYTES = 200 * 1024 * 1024  # 200 MB

    def _install_ff_dir(src: Path, gmxlib: str) -> str:
        """Copy a .ff directory into gmxlib. Returns the installed FF name."""
        if not src.name.endswith(".ff"):
            raise ValueError(f"Expected a directory ending in .ff, got: {src.name}")
        if not (src / "forcefield.itp").exists():
            raise ValueError(f"Not a valid force field directory (missing forcefield.itp)")
        dest = Path(gmxlib) / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return src.name[:-3]

    @app.post("/api/forcefields/upload", status_code=201)
    async def api_upload_forcefield(ff_archive: UploadFile = File(...)) -> dict:
        from lib.gmx_wrapper import get_gmxlib
        gmxlib = get_gmxlib()
        if not gmxlib or not Path(gmxlib).is_dir():
            raise HTTPException(status_code=503, detail="GMXLIB not found or not writable")
        fname = ff_archive.filename or ""
        if not (fname.endswith(".tar.gz") or fname.endswith(".tgz") or fname.endswith(".zip")):
            raise HTTPException(status_code=400, detail="Only .tar.gz, .tgz, or .zip files are accepted")
        content = await ff_archive.read(_MAX_FF_BYTES + 1)
        if len(content) > _MAX_FF_BYTES:
            raise HTTPException(status_code=413, detail="Archive too large (max 200 MB)")
        import tarfile, zipfile, tempfile as _tmp
        with _tmp.TemporaryDirectory() as td:
            extract_dir = Path(td) / "extracted"
            extract_dir.mkdir()
            archive_path = Path(td) / fname
            archive_path.write_bytes(content)
            try:
                if fname.endswith(".zip"):
                    with zipfile.ZipFile(archive_path) as zf:
                        for member in zf.namelist():
                            if ".." in member or member.startswith("/"):
                                raise HTTPException(status_code=400, detail="Archive contains unsafe paths")
                        zf.extractall(extract_dir)
                else:
                    with tarfile.open(archive_path) as tf:
                        for member in tf.getmembers():
                            if ".." in member.name or member.name.startswith("/"):
                                raise HTTPException(status_code=400, detail="Archive contains unsafe paths")
                        tf.extractall(extract_dir)
            except (tarfile.TarError, zipfile.BadZipFile) as e:
                raise HTTPException(status_code=400, detail=f"Failed to extract archive: {e}")
            ff_dirs = [p for p in extract_dir.rglob("*.ff") if p.is_dir() and (p / "forcefield.itp").exists()]
            if not ff_dirs:
                raise HTTPException(status_code=400, detail="No valid .ff directory found in archive (missing forcefield.itp)")
            try:
                installed = _install_ff_dir(ff_dirs[0], gmxlib)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        return {"installed": installed}

    @app.post("/api/forcefields/install", status_code=201)
    def api_install_forcefield_path(body: dict) -> dict:
        from lib.gmx_wrapper import get_gmxlib
        gmxlib = get_gmxlib()
        if not gmxlib or not Path(gmxlib).is_dir():
            raise HTTPException(status_code=503, detail="GMXLIB not found or not writable")
        raw_path = (body.get("path") or "").strip()
        if not raw_path:
            raise HTTPException(status_code=400, detail="path is required")
        src = Path(raw_path).expanduser().resolve()
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {src}")
        if not src.is_dir():
            raise HTTPException(status_code=400, detail="Path must be a directory")
        try:
            installed = _install_ff_dir(src, gmxlib)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"installed": installed}

    @app.get("/api/forcefields/{ff_name}/watermodels")
    def api_list_watermodels(ff_name: str) -> list[dict]:
        if not _FF_NAME_RE.match(ff_name):
            raise HTTPException(status_code=400, detail="invalid force field name")
        from lib.gmx_wrapper import get_gmxlib
        gmxlib = get_gmxlib()
        if not gmxlib:
            raise HTTPException(status_code=404, detail="GMXLIB not found")
        wm_file = Path(gmxlib) / f"{ff_name}.ff" / "watermodels.dat"
        if not wm_file.exists():
            return []
        models = []
        for line in wm_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            parts = line.split(None, 2)
            if len(parts) >= 2:
                models.append({"value": parts[0], "label": parts[1]})
        return models

    # ── Preset endpoints ──────────────────────────────────────────────────────
    @app.get("/api/presets")
    def api_list_presets(hd: HarnessDir) -> list[dict]:
        presets_dir = hd / _PRESETS_DIR
        if not presets_dir.exists():
            return []
        result = []
        for p in sorted(presets_dir.glob("*.json")):
            try:
                result.append({"name": p.stem, "config": json.loads(p.read_text())})
            except Exception:
                pass
        return result

    @app.post("/api/presets", status_code=201)
    def api_save_preset(body: dict, hd: HarnessDir) -> dict:
        name = (body.get("name") or "").strip()
        config = body.get("config")
        if not name or not config:
            raise HTTPException(status_code=400, detail="name and config are required")
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)[:64]
        if not safe_name:
            raise HTTPException(status_code=400, detail="invalid preset name")
        presets_dir = hd / _PRESETS_DIR
        presets_dir.mkdir(exist_ok=True)
        (presets_dir / f"{safe_name}.json").write_text(json.dumps(config, indent=2))
        return {"name": safe_name}

    @app.delete("/api/presets/{preset_name}", status_code=200)
    def api_delete_preset(preset_name: str, hd: HarnessDir) -> dict:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", preset_name)[:64]
        preset_path = hd / _PRESETS_DIR / f"{safe_name}.json"
        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="preset not found")
        preset_path.unlink()
        return {"deleted": safe_name}

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

    @app.get("/api/runs/{run_id}/audit")
    def api_audit_run(run_id: str, hd: HarnessDir) -> dict:
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        from lib.tutorial_auditor import audit_run
        from lib.system_config_validator import validate_run_against_config
        report = audit_run(workspace)
        config_report = validate_run_against_config(workspace)
        result = report.to_dict()
        result["config_audit"] = config_report.to_dict()
        return result

    _MOL_EXTENSIONS = {'.gro', '.pdb', '.xtc', '.tpr'}

    @app.get("/api/runs/{run_id}/mol_files")
    def api_list_mol_files(run_id: str, hd: HarnessDir) -> list[str]:
        workspace = _check_run_id(run_id, hd / "runs")
        ws_resolved = workspace.resolve()
        found = set()
        for ext in _MOL_EXTENSIONS:
            for f in workspace.rglob(f"*{ext}"):
                if str(f.resolve()).startswith(str(ws_resolved) + os.sep):
                    found.add(f.name)
        return sorted(found)

    @app.get("/api/runs/{run_id}/file/{filename}")
    def api_get_run_file(run_id: str, filename: str, hd: HarnessDir):
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="invalid filename")
        ext = Path(filename).suffix.lower()
        if ext not in _MOL_EXTENSIONS:
            raise HTTPException(status_code=400, detail="file type not allowed")
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.\-]*', filename):
            raise HTTPException(status_code=400, detail="invalid filename")
        workspace = _check_run_id(run_id, hd / "runs")
        ws_resolved = workspace.resolve()
        candidate = workspace / filename
        if not candidate.exists():
            raise HTTPException(status_code=404, detail="file not found")
        resolved = candidate.resolve()
        if not str(resolved).startswith(str(ws_resolved) + os.sep):
            raise HTTPException(status_code=400, detail="invalid filename")
        return FileResponse(str(resolved), filename=filename)

    _EXCLUDE_DOWNLOAD = {'.xtc', '.trr', '.tpr', '.edr', '.cpt'}

    @app.get("/api/runs/{run_id}/download")
    def api_download_run(run_id: str, hd: HarnessDir):
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        ws_resolved = workspace.resolve()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(workspace.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix.lower() in _EXCLUDE_DOWNLOAD:
                    continue
                resolved = f.resolve()
                if not str(resolved).startswith(str(ws_resolved) + os.sep):
                    continue
                zf.write(f, str(f.relative_to(workspace)))
        buf.seek(0)

        return StreamingResponse(
            iter([buf.read()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'},
        )

    @app.post("/api/runs", status_code=201)
    async def api_create_run(
        hd: HarnessDir,
        pdb_file: UploadFile = File(...),
        forcefield: str = Form("charmm36"),
        water: str = Form("tip3p"),
        box_type: str = Form("dodecahedron"),
        tutorial_id: str = Form(""),
        llm: str = Form(""),
        auto_approve: str = Form("false"),
        system_config: str = Form(""),
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

        meta: dict = {
            "user_preferences": {
                "forcefield": forcefield,
                "water": water,
                "box_type": box_type,
            }
        }
        if tutorial_id:
            meta["tutorial_id"] = tutorial_id
        (ws / "meta.json").write_text(json.dumps(meta, indent=2))

        if system_config.strip():
            try:
                config_data = json.loads(system_config)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="system_config is not valid JSON")
            errors = validate_solution_config(config_data)
            if errors:
                raise HTTPException(status_code=400, detail="; ".join(errors))
            (ws / "system_config.json").write_text(json.dumps(config_data, indent=2))

            # Apply protonation preprocessing if HIS states are specified
            prot = config_data.get("protonation", {})
            his_states = prot.get("his_states", {})
            if his_states:
                from lib.pdb_preprocessor import apply_his_states
                original = pdb_path.read_text(encoding="utf-8", errors="replace")
                pdb_path.write_text(apply_his_states(original, his_states), encoding="utf-8")

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
                [sys.executable, str(RUNNER_PY), "--skill", "all",
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
                    try:
                        time.sleep(0.3)
                    except Exception:
                        pass
            except (ValueError, ProcessLookupError, OSError):
                pass
        shutil.rmtree(workspace, ignore_errors=True)
        return {"status": "deleted"}

    @app.patch("/api/runs/{run_id}", status_code=200)
    def api_rename_run(run_id: str, body: dict, hd: HarnessDir) -> dict:
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        raw = (body.get("display_name") or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="display_name must not be empty")
        if len(raw) > 80:
            raise HTTPException(status_code=400, detail="display_name too long (max 80 chars)")
        meta_file = workspace / "meta.json"
        meta: dict = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                pass
        meta["display_name"] = raw
        meta_file.write_text(json.dumps(meta, indent=2))
        return {"display_name": raw}

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

    @app.get("/api/runs/{run_id}/chat_log", response_class=PlainTextResponse)
    def api_chat_log(run_id: str, hd: HarnessDir) -> str:
        workspace = _check_run_id(run_id, hd / "runs")
        if not workspace.is_dir():
            raise HTTPException(status_code=404, detail="run not found")
        log_file = workspace / "runner.log"
        if not log_file.exists():
            return ""
        raw = log_file.read_text(encoding="utf-8", errors="replace")
        if len(raw) > 200_000:
            raw = raw[-200_000:]
            nl = raw.find('\n')
            if nl != -1:
                raw = raw[nl + 1:]
        return _filter_chat_log(raw)

    # ── XVG visualization (stateless, in-memory) ─────────────────────────────
    _MAX_XVG_FILES = 20
    _MAX_XVG_BYTES = 50 * 1024 * 1024  # 50 MB total

    @app.post("/api/xvg/parse")
    async def api_parse_xvg(files: list[UploadFile] = File(...)) -> list[dict]:
        if len(files) > _MAX_XVG_FILES:
            raise HTTPException(status_code=400,
                detail=f"Too many files: max {_MAX_XVG_FILES}")
        total_bytes = 0
        results = []
        for f in files:
            content = await f.read()
            total_bytes += len(content)
            if total_bytes > _MAX_XVG_BYTES:
                raise HTTPException(status_code=413, detail="Total upload size exceeds 50 MB")
            try:
                text = content.decode("utf-8", errors="replace")
            except Exception:
                raise HTTPException(status_code=400,
                    detail=f"Cannot decode file: {f.filename}")
            try:
                parsed = xvg_parser.parse_text(text, max_points=1000)
                stats = xvg_parser.summary_all(text)
            except Exception as exc:
                raise HTTPException(status_code=422,
                    detail=f"Failed to parse {f.filename}: {exc}")
            results.append({"filename": f.filename, **parsed, "stats": stats})
        return results

    @app.post("/api/pdb/analyze")
    async def api_pdb_analyze(pdb_file: UploadFile = File(...)) -> dict:
        from lib.pdb_analyzer import PDBAnalyzer
        import tempfile, os
        content = await pdb_file.read()
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return PDBAnalyzer(tmp_path).analyze()
        finally:
            os.unlink(tmp_path)

    @app.get("/api/pdb/fetch")
    async def api_pdb_fetch(pdb_id: str) -> dict:
        import urllib.request, urllib.error
        if not (len(pdb_id) == 4 and pdb_id.isalnum()):
            raise HTTPException(status_code=400, detail="PDB ID must be exactly 4 alphanumeric characters")
        pdb_id = pdb_id.upper()
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                content = resp.read().decode("utf-8")
        except urllib.error.HTTPError:
            raise HTTPException(status_code=404, detail=f"PDB ID {pdb_id} not found in RCSB")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"RCSB fetch failed: {exc}")
        tmp_dir = harness_dir / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        (tmp_dir / f"{pdb_id}.pdb").write_text(content)
        return {"pdb_id": pdb_id, "content": content}

    @app.post("/api/pdb/protonate")
    async def api_pdb_protonate(
        pdb_file: UploadFile = File(...),
        ph: Annotated[float, Form(ge=0.0, le=14.0)] = 7.0,
    ) -> dict:
        from lib.protonation import run_propka
        import tempfile, os
        content = await pdb_file.read()
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return run_propka(tmp_path, ph=ph)
        finally:
            os.unlink(tmp_path)

    # ── Ligand Parameterization ──────────────────────────────────────────────
    from lib import ligand_params as _lp

    @app.get("/api/ligand/status")
    def api_ligand_status() -> dict:
        available = _lp.is_acpype_available()
        version: str | None = None
        if available:
            try:
                r = subprocess.run(
                    ["acpype", "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                version = (r.stdout or r.stderr).strip()[:80] or None
            except Exception:
                pass
        return {"available": available, "version": version}

    @app.post("/api/ligand/parameterize")
    async def api_ligand_parameterize(
        ligand: UploadFile,
        charge: Annotated[int, Form(ge=-10, le=10)] = 0,
        atom_type: Annotated[str, Form()] = "gaff2",
        residue_name: Annotated[str, Form()] = "LIG",
    ) -> dict:
        if not _lp.is_acpype_available():
            raise HTTPException(
                status_code=503,
                detail="acpype not installed. Run: conda install -c conda-forge ambertools",
            )
        import tempfile as _tmpfile
        suffix = Path(ligand.filename or "ligand.pdb").suffix or ".pdb"
        with _tmpfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(await ligand.read())
            tmp_path = Path(f.name)
        try:
            result = _lp.run_acpype(tmp_path, charge=charge, atom_type=atom_type, residue_name=residue_name)
            if result.get("error"):
                raise HTTPException(status_code=500, detail=result["error"])
            return result
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @app.post("/api/ligand/assemble")
    async def api_ligand_assemble(
        protein_gro: UploadFile,
        ligand_gro: UploadFile,
        ligand_itp: UploadFile,
        topol_top: UploadFile,
    ) -> dict:
        import tempfile as _tmpfile2
        import shutil as _shutil
        workspace = Path(_tmpfile2.mkdtemp())
        try:
            async def _save(upload: UploadFile, name: str) -> Path:
                p = workspace / name
                p.write_bytes(await upload.read())
                return p

            p_gro = await _save(protein_gro, "protein.gro")
            l_gro = await _save(ligand_gro, "LIG.gro")
            l_itp = await _save(ligand_itp, "LIG.itp")
            t_top = await _save(topol_top, "topol.top")

            return _lp.assemble_complex(p_gro, l_gro, l_itp, t_top, workspace)
        finally:
            _shutil.rmtree(workspace, ignore_errors=True)

    # ── Membrane Builder ────────────────────────────────────────────────────
    from lib import membrane_builder as _mb

    @app.get("/api/membrane/status")
    def api_membrane_status() -> dict:
        available = _mb.is_packmol_memgen_available()
        version: str | None = None
        if available:
            try:
                r = subprocess.run(
                    ["packmol-memgen", "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                version = (r.stdout or r.stderr).strip()[:80] or None
            except Exception:
                pass
        return {"available": available, "version": version}

    @app.get("/api/membrane/lipids")
    def api_membrane_lipids() -> list[dict]:
        return _mb.list_supported_lipids()

    @app.post("/api/membrane/build")
    async def api_membrane_build(
        hd: HarnessDir,
        config_json: Annotated[str, Form()],
        protein_pdb: UploadFile | None = None,
    ) -> dict:
        import json as _json
        if not _mb.is_packmol_memgen_available():
            raise HTTPException(
                status_code=503,
                detail="packmol-memgen not installed. Run: conda install -c conda-forge ambertools",
            )
        try:
            config = _json.loads(config_json)
        except Exception:
            raise HTTPException(status_code=422, detail="config_json is not valid JSON")

        for leaflet_key in ("lipids_upper", "lipids_lower"):
            leaflet = config.get(leaflet_key, [])
            if leaflet:
                total = sum(e.get("fraction", 0) for e in leaflet)
                if abs(total - 1.0) > 0.001:
                    raise HTTPException(
                        status_code=422,
                        detail=f"{leaflet_key} fractions must sum to 1.0, got {total:.4f}",
                    )

        tmp_dir = hd / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        tmp_protein: Path | None = None

        try:
            if protein_pdb:
                import tempfile
                suffix = Path(protein_pdb.filename or "protein.pdb").suffix or ".pdb"
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix, dir=tmp_dir
                ) as f:
                    f.write(await protein_pdb.read())
                    tmp_protein = Path(f.name)
                config["protein_pdb"] = str(tmp_protein)

            try:
                result = _mb.build_membrane(config, tmp_dir)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

            if result.get("error"):
                raise HTTPException(status_code=500, detail=result["error"])

            return result
        finally:
            if tmp_protein and tmp_protein.exists():
                tmp_protein.unlink()

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
