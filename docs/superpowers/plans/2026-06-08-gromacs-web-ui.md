# Gromacs Harness Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI 백엔드 + vanilla JS 프론트엔드로 Gromacs 3-skill 파이프라인을 브라우저에서 실행·모니터링하는 웹 대시보드를 만든다.

**Architecture:** `harness/web/` 아래에 FastAPI 서버(`server.py`), 스킬 subprocess 런처(`runner.py`), run 상태 리더(`run_reader.py`), 프론트엔드(`static/index.html`)를 배치한다. 서버는 `harness/runs/` 디렉터리를 스캔해 runs를 관리하고, 각 스킬은 기존 `skills/env_builder/env_builder.py`, `skills/md_runner/md_runner.py`, `skills/illustrator/illustrator.py`를 그대로 호출한다.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, python-multipart, pytest-asyncio, httpx

---

## File Structure

```
harness/
  web/
    __init__.py              # 빈 파일
    run_reader.py            # run 디렉터리 스캔 + 상태 파생
    runner.py                # CLI: --skill env|md|viz --workspace <path> [--pdb <path>]
    server.py                # FastAPI 앱 (API + WS + static 서빙)
    static/
      index.html             # 전체 프론트엔드 (CSS/JS 인라인)
  tests/
    web/
      __init__.py
      test_run_reader.py
      test_server.py
```

각 run의 workspace 파일:
```
harness/runs/{protein}_{YYYYMMDD}_{HHMMSS}/
  inputs/input.pdb         # 업로드된 PDB
  state.json               # lib/state.py 포맷
  runner.pid               # 실행 중 subprocess PID
  runner.exit              # 종료 코드 (완료 후 작성)
  runner.log               # subprocess stdout+stderr
  runner.skill             # 현재/마지막 실행 스킬 ("env"|"md"|"viz")
```

---

## Task 1: 프로젝트 셋업

**Files:**
- Create: `harness/web/__init__.py`
- Create: `harness/tests/web/__init__.py`
- Modify: `harness/pyproject.toml`

- [ ] **Step 1: 디렉터리 생성**

```bash
mkdir -p harness/web/static
mkdir -p harness/tests/web
touch harness/web/__init__.py
touch harness/tests/web/__init__.py
```

- [ ] **Step 2: 의존성 추가 — pyproject.toml 수정**

`harness/pyproject.toml`의 `[project]` 섹션에 추가:

```toml
[project]
name = "gromacs-harness"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn>=0.30",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
test = [
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
markers = [
    "integration: requires gmx on PATH",
    "renderer: requires PyMOL or VMD",
    "animation: requires ffmpeg",
]
```

- [ ] **Step 3: 의존성 설치**

```bash
cd harness
pip install -e ".[test]"
```

Expected: `Successfully installed fastapi uvicorn python-multipart pytest-asyncio httpx ...`

- [ ] **Step 4: Commit**

```bash
git add harness/web/__init__.py harness/tests/web/__init__.py harness/pyproject.toml
git commit -m "feat: add web UI project skeleton and dependencies"
```

---

## Task 2: run_reader.py — run 상태 파생

**Files:**
- Create: `harness/web/run_reader.py`
- Create: `harness/tests/web/test_run_reader.py`

- [ ] **Step 1: 실패 테스트 작성**

`harness/tests/web/test_run_reader.py`:

```python
import json
import os
from pathlib import Path
import pytest
from web.run_reader import derive_status, read_run, list_runs, RunInfo


def _make_ws(tmp_path, run_id="aki_20260608_120000"):
    ws = tmp_path / "runs" / run_id
    ws.mkdir(parents=True)
    return ws


def test_pending_when_no_pid(tmp_path):
    ws = _make_ws(tmp_path)
    assert derive_status(ws) == "pending"


def test_running_when_pid_alive(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text(str(os.getpid()))
    assert derive_status(ws) == "running"


def test_aborted_when_pid_dead_no_exit(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    assert derive_status(ws) == "aborted"


def test_failed_when_nonzero_exit(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("1")
    assert derive_status(ws) == "failed"


def test_paused_after_env(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "env", "current_step": 5, "pending_warnings": []}))
    assert derive_status(ws) == "paused"


def test_paused_after_md(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "md", "current_step": 7, "pending_warnings": []}))
    assert derive_status(ws) == "paused"


def test_completed_after_viz(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": "viz", "current_step": 8, "pending_warnings": []}))
    assert derive_status(ws) == "completed"


def test_read_run_parses_protein_and_date(tmp_path):
    ws = _make_ws(tmp_path, "aki_20260608_120000")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": None, "current_step": 0, "pending_warnings": []}))
    info = read_run("aki_20260608_120000", tmp_path / "runs")
    assert info is not None
    assert info.protein == "aki"
    assert info.created_at == "2026-06-08T12:00:00"
    assert info.run_id == "aki_20260608_120000"


def test_list_runs_returns_newest_first(tmp_path):
    runs_dir = tmp_path / "runs"
    for rid in ["aki_20260608_100000", "aki_20260608_120000"]:
        ws = runs_dir / rid
        ws.mkdir(parents=True)
    infos = list_runs(runs_dir)
    assert [i.run_id for i in infos] == ["aki_20260608_120000", "aki_20260608_100000"]
```

- [ ] **Step 2: 실패 확인**

```bash
cd harness
pytest tests/web/test_run_reader.py -v
```

Expected: `ModuleNotFoundError: No module named 'web.run_reader'`

- [ ] **Step 3: run_reader.py 구현**

`harness/web/run_reader.py`:

```python
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class RunInfo:
    run_id: str
    workspace: Path
    status: str
    protein: str
    created_at: str
    last_completed_stage: str | None
    current_step: int
    pending_warnings: list = field(default_factory=list)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def derive_status(workspace: Path) -> str:
    pid_file = workspace / "runner.pid"
    exit_file = workspace / "runner.exit"
    state_file = workspace / "state.json"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            return "pending"
        if _process_alive(pid):
            return "running"
        if not exit_file.exists():
            return "aborted"

    if not exit_file.exists():
        return "pending"

    try:
        code = int(exit_file.read_text().strip())
    except ValueError:
        return "failed"
    if code != 0:
        return "failed"

    if state_file.exists():
        try:
            s = json.loads(state_file.read_text())
            if s.get("last_completed_stage") == "viz":
                return "completed"
            return "paused"
        except Exception:
            pass
    return "completed"


def read_run(run_id: str, runs_dir: Path) -> RunInfo | None:
    workspace = runs_dir / run_id
    if not workspace.is_dir():
        return None

    parts = run_id.rsplit("_", 2)
    protein = parts[0] if len(parts) == 3 else run_id
    try:
        created_at = datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S").isoformat()
    except (ValueError, IndexError):
        created_at = ""

    last_stage: str | None = None
    current_step = 0
    pending_warnings: list = []
    state_file = workspace / "state.json"
    if state_file.exists():
        try:
            s = json.loads(state_file.read_text())
            last_stage = s.get("last_completed_stage")
            current_step = s.get("current_step", 0)
            pending_warnings = s.get("pending_warnings", [])
        except Exception:
            pass

    return RunInfo(
        run_id=run_id,
        workspace=workspace,
        status=derive_status(workspace),
        protein=protein,
        created_at=created_at,
        last_completed_stage=last_stage,
        current_step=current_step,
        pending_warnings=pending_warnings,
    )


def list_runs(runs_dir: Path) -> list[RunInfo]:
    if not runs_dir.exists():
        return []
    items = []
    for d in sorted(runs_dir.iterdir(), reverse=True):
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("_"):
            info = read_run(d.name, runs_dir)
            if info:
                items.append(info)
    return items
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd harness
pytest tests/web/test_run_reader.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/run_reader.py harness/tests/web/test_run_reader.py
git commit -m "feat: add run_reader with status derivation"
```

---

## Task 3: FastAPI 앱 + GET /api/runs

**Files:**
- Create: `harness/web/server.py`
- Create: `harness/tests/web/test_server.py` (초기)

- [ ] **Step 1: 실패 테스트 작성**

`harness/tests/web/test_server.py`:

```python
import json
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def harness_dir(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


@pytest.fixture
def app(harness_dir):
    from web.server import create_app
    return create_app(harness_dir=harness_dir)


async def test_list_runs_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_runs_with_one_run(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env",
        "current_step": 5,
        "pending_warnings": [],
    }))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    item = data[0]
    assert item["run_id"] == "aki_20260608_120000"
    assert item["status"] == "paused"
    assert item["protein"] == "aki"
    assert item["last_completed_stage"] == "env"
```

- [ ] **Step 2: 실패 확인**

```bash
cd harness
pytest tests/web/test_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'web.server'`

- [ ] **Step 3: server.py 기본 뼈대 + GET /api/runs 구현**

`harness/web/server.py`:

```python
import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.run_reader import RunInfo, derive_status, list_runs, read_run

HARNESS_DIR: Path = Path(__file__).parent.parent
RUNNER_PY: Path = Path(__file__).parent / "runner.py"
STATIC_DIR: Path = Path(__file__).parent / "static"


def get_harness_dir() -> Path:
    return HARNESS_DIR


HarnessDir = Annotated[Path, Depends(get_harness_dir)]


def create_app(harness_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Gromacs Harness Web UI")

    if harness_dir is not None:
        app.dependency_overrides[get_harness_dir] = lambda: harness_dir

    @app.get("/api/runs")
    def api_list_runs(hd: HarnessDir) -> list[dict]:
        runs_dir = hd / "runs"
        infos = list_runs(runs_dir)
        return [_run_summary(i) for i in infos]

    return app


def _run_summary(info: RunInfo) -> dict:
    return {
        "run_id": info.run_id,
        "status": info.status,
        "protein": info.protein,
        "created_at": info.created_at,
        "last_completed_stage": info.last_completed_stage,
        "current_step": info.current_step,
    }


app = create_app()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd harness
pytest tests/web/test_server.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/server.py harness/tests/web/test_server.py
git commit -m "feat: add FastAPI skeleton and GET /api/runs"
```

---

## Task 4: GET /api/runs/{run_id}

**Files:**
- Modify: `harness/web/server.py`
- Modify: `harness/tests/web/test_server.py`

- [ ] **Step 1: 실패 테스트 추가** — `test_server.py`에 추가:

```python
async def test_get_run_detail(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env",
        "current_step": 5,
        "pending_warnings": [],
    }))
    (ws / "runner.log").write_text("step 1 done\nstep 2 done\n")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/aki_20260608_120000")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "aki_20260608_120000"
    assert data["status"] == "paused"
    assert data["log_tail"] == "step 1 done\nstep 2 done\n"


async def test_get_run_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/nonexistent")
    assert r.status_code == 404
```

- [ ] **Step 2: 실패 확인**

```bash
cd harness
pytest tests/web/test_server.py::test_get_run_detail tests/web/test_server.py::test_get_run_not_found -v
```

Expected: `FAILED` (404 or attribute error)

- [ ] **Step 3: GET /api/runs/{run_id} 구현** — `server.py`의 `create_app()` 안에 추가:

```python
    @app.get("/api/runs/{run_id}")
    def api_get_run(run_id: str, hd: HarnessDir) -> dict:
        runs_dir = hd / "runs"
        info = read_run(run_id, runs_dir)
        if info is None:
            raise HTTPException(status_code=404, detail="run not found")
        log_tail = ""
        log_file = info.workspace / "runner.log"
        if log_file.exists():
            log_tail = log_file.read_text(encoding="utf-8", errors="replace")
            # 마지막 500줄만
            lines = log_tail.splitlines()
            if len(lines) > 500:
                log_tail = "\n".join(lines[-500:]) + "\n"
        detail = _run_summary(info)
        detail["log_tail"] = log_tail
        detail["pending_warnings"] = info.pending_warnings
        return detail
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd harness
pytest tests/web/test_server.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/server.py harness/tests/web/test_server.py
git commit -m "feat: add GET /api/runs/{run_id} with log tail"
```

---

## Task 5: runner.py — 스킬 subprocess 래퍼

**Files:**
- Create: `harness/web/runner.py`

- [ ] **Step 1: runner.py 작성**

`harness/web/runner.py`:

```python
"""CLI wrapper — runs one skill against a workspace.

Usage:
    python web/runner.py --skill env --workspace runs/aki_20260608_120000 --pdb runs/.../inputs/input.pdb
    python web/runner.py --skill md  --workspace runs/aki_20260608_120000
    python web/runner.py --skill viz --workspace runs/aki_20260608_120000
"""
import argparse
import json
import sys
from pathlib import Path

# harness root on sys.path so skills/ and lib/ are importable
_HARNESS = Path(__file__).parent.parent
sys.path.insert(0, str(_HARNESS))


def _run_env(workspace: Path, pdb: Path) -> dict:
    from skills.env_builder.env_builder import build_environment
    return build_environment(pdb_path=pdb, prompt="", workspace_dir=workspace, interactive=False)


def _run_md(workspace: Path) -> dict:
    from skills.md_runner.md_runner import run_simulation
    return run_simulation(workspace_dir=workspace, interactive=False)


def _run_viz(workspace: Path) -> dict:
    from skills.illustrator.illustrator import run_core_analyses
    return run_core_analyses(workspace_dir=workspace)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a single GROMACS skill")
    parser.add_argument("--skill", choices=["env", "md", "viz"], required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--pdb", type=Path, help="PDB path (env only)")
    args = parser.parse_args()

    ws = args.workspace.resolve()
    skill_file = ws / "runner.skill"
    exit_file = ws / "runner.exit"

    skill_file.write_text(args.skill)

    try:
        if args.skill == "env":
            if not args.pdb:
                print("ERROR: --pdb required for env skill", flush=True)
                exit_file.write_text("1")
                return 1
            result = _run_env(ws, args.pdb.resolve())
        elif args.skill == "md":
            result = _run_md(ws)
        else:
            result = _run_viz(ws)

        print(json.dumps(result, indent=2, default=str), flush=True)
        exit_file.write_text("0")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        exit_file.write_text("1")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 문법 검사**

```bash
cd harness
python -c "import web.runner; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add harness/web/runner.py
git commit -m "feat: add runner.py skill subprocess wrapper"
```

---

## Task 6: POST /api/runs — 새 run 생성

**Files:**
- Modify: `harness/web/server.py`
- Modify: `harness/tests/web/test_server.py`

- [ ] **Step 1: 실패 테스트 추가** — `test_server.py`에 추가:

```python
import io
from unittest.mock import patch, MagicMock


async def test_create_run_spawns_subprocess(app, harness_dir):
    pdb_content = b"ATOM      1  N   ALA A   1       1.000   1.000   1.000\nEND\n"
    mock_proc = MagicMock()
    mock_proc.pid = 12345

    with patch("web.server.subprocess.Popen", return_value=mock_proc) as mock_popen:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/runs",
                files={"pdb_file": ("1AKI.pdb", io.BytesIO(pdb_content), "application/octet-stream")},
                data={"forcefield": "charmm36", "water": "tip3p", "box_type": "dodecahedron"},
            )
    assert r.status_code == 201
    data = r.json()
    run_id = data["run_id"]
    assert run_id.startswith("aki_")
    assert mock_popen.called

    # workspace and PDB were created
    ws = harness_dir / "runs" / run_id
    assert ws.is_dir()
    assert (ws / "inputs" / "input.pdb").exists()
    assert (ws / "runner.pid").read_text() == "12345"
```

- [ ] **Step 2: 실패 확인**

```bash
cd harness
pytest tests/web/test_server.py::test_create_run_spawns_subprocess -v
```

Expected: `FAILED` (405 Method Not Allowed)

- [ ] **Step 3: POST /api/runs 구현** — 필요한 import를 server.py 상단에 추가하고 `create_app()` 안에 다음을 추가:

```python
    @app.post("/api/runs", status_code=201)
    async def api_create_run(
        hd: HarnessDir,
        pdb_file: UploadFile = File(...),
        forcefield: str = Form("charmm36"),
        water: str = Form("tip3p"),
        box_type: str = Form("dodecahedron"),
    ) -> dict:
        stem = Path(pdb_file.filename or "protein").stem
        protein = re.sub(r"^\d+", "", stem).lower() or "protein"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{protein}_{stamp}"
        ws = hd / "runs" / run_id
        inputs_dir = ws / "inputs"
        inputs_dir.mkdir(parents=True)

        pdb_path = inputs_dir / "input.pdb"
        content = await pdb_file.read()
        pdb_path.write_bytes(content)

        log_file = ws / "runner.log"
        proc = subprocess.Popen(
            [sys.executable, str(RUNNER_PY), "--skill", "env",
             "--workspace", str(ws), "--pdb", str(pdb_path)],
            cwd=str(hd),
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
        )
        (ws / "runner.pid").write_text(str(proc.pid))
        return {"run_id": run_id}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd harness
pytest tests/web/test_server.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/server.py harness/tests/web/test_server.py
git commit -m "feat: add POST /api/runs with PDB upload and subprocess spawn"
```

---

## Task 7: POST /api/runs/{run_id}/action — Continue / Abort

**Files:**
- Modify: `harness/web/server.py`
- Modify: `harness/tests/web/test_server.py`

- [ ] **Step 1: 실패 테스트 추가** — `test_server.py`에 추가:

```python
async def test_abort_run(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text(str(os.getpid()))  # 살아있는 PID

    with patch("web.server.os.kill") as mock_kill:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "abort"})
    assert r.status_code == 200
    mock_kill.assert_called_once_with(os.getpid(), signal.SIGTERM)


async def test_continue_run_spawns_md(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({
        "last_completed_stage": "env", "current_step": 5, "pending_warnings": [],
    }))

    mock_proc = MagicMock()
    mock_proc.pid = 99001
    with patch("web.server.subprocess.Popen", return_value=mock_proc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "continue"})
    assert r.status_code == 200
    assert (ws / "runner.pid").read_text() == "99001"


async def test_action_invalid(app, harness_dir):
    ws = harness_dir / "runs" / "aki_20260608_120000"
    ws.mkdir()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/runs/aki_20260608_120000/action", json={"action": "explode"})
    assert r.status_code == 400
```

- [ ] **Step 2: 실패 확인**

```bash
cd harness
pytest tests/web/test_server.py::test_abort_run tests/web/test_server.py::test_continue_run_spawns_md tests/web/test_server.py::test_action_invalid -v
```

Expected: `FAILED` (404 or 405)

- [ ] **Step 3: POST /api/runs/{run_id}/action 구현** — `create_app()` 안에 추가:

```python
    _NEXT_SKILL = {"env": "md", "md": "viz"}

    @app.post("/api/runs/{run_id}/action")
    def api_action(run_id: str, body: dict, hd: HarnessDir) -> dict:
        action = body.get("action")
        if action not in ("continue", "abort"):
            raise HTTPException(status_code=400, detail="action must be 'continue' or 'abort'")

        runs_dir = hd / "runs"
        info = read_run(run_id, runs_dir)
        if info is None:
            raise HTTPException(status_code=404, detail="run not found")

        if action == "abort":
            pid_file = info.workspace / "runner.pid"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, signal.SIGTERM)
                except (ValueError, ProcessLookupError, OSError):
                    pass
            return {"status": "aborted"}

        # continue
        if info.status != "paused":
            raise HTTPException(status_code=409, detail=f"run is '{info.status}', not paused")
        next_skill = _NEXT_SKILL.get(info.last_completed_stage or "")
        if not next_skill:
            raise HTTPException(status_code=409, detail="no next skill to continue")

        log_file = info.workspace / "runner.log"
        proc = subprocess.Popen(
            [sys.executable, str(RUNNER_PY), "--skill", next_skill,
             "--workspace", str(info.workspace)],
            cwd=str(hd),
            stdout=open(log_file, "a"),
            stderr=subprocess.STDOUT,
        )
        (info.workspace / "runner.pid").write_text(str(proc.pid))
        (info.workspace / "runner.exit").unlink(missing_ok=True)
        return {"status": "started", "skill": next_skill}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd harness
pytest tests/web/test_server.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/server.py harness/tests/web/test_server.py
git commit -m "feat: add POST /api/runs/{run_id}/action for continue and abort"
```

---

## Task 8: WebSocket /ws/runs/{run_id} — 로그 스트리밍

**Files:**
- Modify: `harness/web/server.py`

- [ ] **Step 1: WebSocket 엔드포인트 구현** — `create_app()` 안에 추가:

```python
    @app.websocket("/ws/runs/{run_id}")
    async def ws_logs(websocket: WebSocket, run_id: str, hd: HarnessDir):
        await websocket.accept()
        log_file = hd / "runs" / run_id / "runner.log"

        # 로그 파일 생성 대기 (최대 15초)
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
                        info = read_run(run_id, hd / "runs")
                        if info is None or info.status not in ("running",):
                            break
                        await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass
```

- [ ] **Step 2: 문법 검사**

```bash
cd harness
python -c "from web.server import create_app; app = create_app(); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add harness/web/server.py
git commit -m "feat: add WebSocket /ws/runs/{run_id} for log streaming"
```

---

## Task 9: Static 파일 서빙 + GET /

**Files:**
- Modify: `harness/web/server.py`

- [ ] **Step 1: static 서빙 + 홈 라우트 추가** — `create_app()` 끝에 추가:

```python
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        html = STATIC_DIR / "index.html"
        if not html.exists():
            return {"message": "index.html not yet created"}
        return FileResponse(str(html))

    return app
```

- [ ] **Step 2: index.html placeholder 생성**

`harness/web/static/index.html`:

```html
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>Gromacs Harness</title></head>
<body><h1>Gromacs Harness Web UI</h1><p>Coming soon...</p></body>
</html>
```

- [ ] **Step 3: 서버 기동 확인**

```bash
cd harness
uvicorn web.server:app --port 8765 &
sleep 1
curl -s http://localhost:8765/ | head -3
kill %1
```

Expected: `<!DOCTYPE html>`

- [ ] **Step 4: Commit**

```bash
git add harness/web/server.py harness/web/static/index.html
git commit -m "feat: add static file serving and GET /"
```

---

## Task 10: index.html — 레이아웃 + CSS + 사이드바

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 전체 HTML 구조 + CSS + 사이드바 작성**

`harness/web/static/index.html` 전체 교체:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Gromacs Harness</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", monospace; background: #0d1117; color: #e6edf3; height: 100vh; display: flex; overflow: hidden; }

/* Sidebar */
#sidebar { width: 220px; min-width: 220px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; overflow: hidden; }
#sidebar-header { padding: 14px 12px 10px; border-bottom: 1px solid #30363d; }
#sidebar-title { font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
#new-run-btn { width: 100%; padding: 6px 10px; background: #238636; border: none; color: #fff; font-size: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; }
#new-run-btn:hover { background: #2ea043; }
#run-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.run-item { padding: 8px 12px; cursor: pointer; border-left: 3px solid transparent; }
.run-item:hover { background: #21262d; }
.run-item.active { background: #21262d; border-left-color: #388bfd; }
.run-item-name { font-size: 12px; font-weight: 600; color: #e6edf3; }
.run-item-date { font-size: 10px; color: #8b949e; margin-top: 2px; }
.run-item-badge { display: inline-block; padding: 1px 5px; border-radius: 10px; font-size: 9px; font-weight: 600; margin-top: 3px; }
.badge-running { background: #388bfd22; color: #388bfd; }
.badge-paused   { background: #d2992222; color: #d29922; }
.badge-completed { background: #23863622; color: #3fb950; }
.badge-failed   { background: #da363322; color: #f85149; }
.badge-aborted  { background: #8b949e22; color: #8b949e; }
.badge-pending  { background: #8b949e22; color: #8b949e; }

/* Main panel */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* Run view */
#run-view { flex: 1; display: flex; flex-direction: column; padding: 20px; gap: 16px; overflow: auto; }
#run-view.hidden, #new-run-view.hidden { display: none; }

/* Stepper */
#stepper { display: flex; align-items: center; gap: 0; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 20px; }
.step-node { display: flex; align-items: center; gap: 6px; }
.step-circle { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.step-circle.done { background: #238636; color: #fff; }
.step-circle.active { background: transparent; border: 2px solid #388bfd; color: #388bfd; }
.step-circle.active::after { content: ''; display: block; width: 8px; height: 8px; background: #388bfd; border-radius: 50%; animation: pulse 1s ease-in-out infinite; }
.step-circle.active { display: flex; align-items: center; justify-content: center; }
.step-circle.pending { background: #21262d; color: #8b949e; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
.step-label { font-size: 11px; color: #8b949e; }
.step-label.done { color: #3fb950; }
.step-label.active { color: #388bfd; font-weight: 600; }
.step-connector { flex: 1; height: 2px; background: #30363d; margin: 0 10px; }
.step-connector.done { background: #3fb950; }

/* Log panel */
#log-panel { flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; min-height: 200px; }
#log-header { padding: 8px 14px; background: #161b22; border-bottom: 1px solid #30363d; font-size: 11px; color: #8b949e; display: flex; justify-content: space-between; }
#log-body { flex: 1; overflow-y: auto; padding: 10px 14px; font-family: "SF Mono", "Fira Code", monospace; font-size: 11px; line-height: 1.6; color: #c9d1d9; white-space: pre-wrap; word-break: break-all; }

/* Stats row */
#stats-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; }
.stat-label { font-size: 9px; color: #8b949e; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 4px; }
.stat-value { font-size: 16px; font-weight: 600; color: #e6edf3; }

/* Action buttons */
#action-row { display: flex; gap: 10px; }
#btn-continue { padding: 8px 20px; background: #238636; border: none; color: #fff; font-size: 13px; border-radius: 6px; cursor: pointer; font-weight: 600; }
#btn-continue:hover:not(:disabled) { background: #2ea043; }
#btn-continue:disabled { opacity: .4; cursor: default; }
#btn-abort { padding: 8px 20px; background: transparent; border: 1px solid #f8514966; color: #f85149; font-size: 13px; border-radius: 6px; cursor: pointer; }
#btn-abort:hover:not(:disabled) { background: #f8514911; }
#btn-abort:disabled { opacity: .4; cursor: default; }

/* New run view */
#new-run-view { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; overflow: auto; }
#new-run-form { width: 100%; max-width: 480px; display: flex; flex-direction: column; gap: 16px; }
#new-run-form h2 { font-size: 18px; color: #e6edf3; }
#drop-zone { border: 2px dashed #388bfd66; border-radius: 8px; padding: 32px; text-align: center; cursor: pointer; background: #388bfd08; transition: background .15s; }
#drop-zone.drag-over { background: #388bfd18; border-color: #388bfd; }
#drop-zone p { font-size: 13px; color: #388bfd; margin-bottom: 4px; }
#drop-zone small { font-size: 11px; color: #8b949e; }
#pdb-input { display: none; }
#selected-file { font-size: 11px; color: #3fb950; margin-top: 4px; }
.param-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.param-field label { display: block; font-size: 11px; color: #8b949e; margin-bottom: 4px; }
.param-field select, .param-field input { width: 100%; padding: 6px 10px; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; border-radius: 6px; font-size: 12px; }
#btn-start { padding: 10px; background: #238636; border: none; color: #fff; font-size: 14px; border-radius: 6px; cursor: pointer; font-weight: 600; width: 100%; }
#btn-start:hover { background: #2ea043; }
#btn-start:disabled { opacity: .5; cursor: default; }
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-header">
    <div id="sidebar-title">Gromacs Harness</div>
    <button id="new-run-btn" onclick="showNewRunForm()">+ New Run</button>
  </div>
  <div id="run-list"></div>
</div>

<div id="main">
  <!-- Run detail view -->
  <div id="run-view" class="hidden">
    <div id="stepper">
      <!-- rendered by JS -->
    </div>
    <div id="log-panel">
      <div id="log-header">
        <span>Output Log</span>
        <span id="log-status">—</span>
      </div>
      <div id="log-body"></div>
    </div>
    <div id="stats-row">
      <div class="stat-card"><div class="stat-label">Current Step</div><div class="stat-value" id="stat-step">—</div></div>
      <div class="stat-card"><div class="stat-label">Stage</div><div class="stat-value" id="stat-stage">—</div></div>
      <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" id="stat-status">—</div></div>
    </div>
    <div id="action-row">
      <button id="btn-continue" disabled onclick="doAction('continue')">Continue</button>
      <button id="btn-abort" disabled onclick="doAction('abort')">⏹ Abort</button>
    </div>
  </div>

  <!-- New run form -->
  <div id="new-run-view" class="hidden">
    <form id="new-run-form" onsubmit="submitNewRun(event)">
      <h2>New Simulation Run</h2>
      <div id="drop-zone" onclick="document.getElementById('pdb-input').click()"
           ondragover="event.preventDefault();this.classList.add('drag-over')"
           ondragleave="this.classList.remove('drag-over')"
           ondrop="handleDrop(event)">
        <p>Drop PDB file here</p>
        <small>or click to browse</small>
        <div id="selected-file"></div>
      </div>
      <input type="file" id="pdb-input" accept=".pdb" onchange="handleFileSelect(this.files[0])">
      <div class="param-grid">
        <div class="param-field">
          <label>Forcefield</label>
          <select name="forcefield">
            <option value="charmm36">CHARMM36</option>
            <option value="amber99sb-ildn">AMBER99SB-ILDN</option>
            <option value="oplsaa">OPLS-AA</option>
          </select>
        </div>
        <div class="param-field">
          <label>Water Model</label>
          <select name="water">
            <option value="tip3p">TIP3P</option>
            <option value="spc">SPC</option>
            <option value="tip4p">TIP4P</option>
          </select>
        </div>
        <div class="param-field">
          <label>Box Type</label>
          <select name="box_type">
            <option value="dodecahedron">Dodecahedron</option>
            <option value="cubic">Cubic</option>
            <option value="triclinic">Triclinic</option>
          </select>
        </div>
      </div>
      <button type="submit" id="btn-start" disabled>▶ Start Run</button>
    </form>
  </div>
</div>

<script>
// ── 상태 ──────────────────────────────────────────────
let currentRunId = null;
let wsConn = null;
let selectedPdb = null;
let pollTimer = null;
let runsData = [];

// ── 초기화 ────────────────────────────────────────────
(function init() {
  fetchRuns();
  setInterval(fetchRuns, 10000);
})();

// ── 사이드바 ─────────────────────────────────────────
async function fetchRuns() {
  try {
    const r = await fetch('/api/runs');
    if (!r.ok) return;
    runsData = await r.json();
    renderSidebar(runsData);
  } catch (e) { console.error('fetchRuns', e); }
}

function renderSidebar(runs) {
  const list = document.getElementById('run-list');
  list.innerHTML = '';
  if (runs.length === 0) {
    list.innerHTML = '<div style="padding:12px;font-size:11px;color:#8b949e;">No runs yet.</div>';
    return;
  }
  runs.forEach(run => {
    const el = document.createElement('div');
    el.className = 'run-item' + (run.run_id === currentRunId ? ' active' : '');
    el.onclick = () => selectRun(run.run_id);
    const date = run.created_at ? run.created_at.replace('T', ' ').substring(0, 16) : '';
    el.innerHTML = `
      <div class="run-item-name">${run.protein.toUpperCase()}</div>
      <div class="run-item-date">${date}</div>
      <span class="run-item-badge badge-${run.status}">${run.status}</span>`;
    list.appendChild(el);
  });
}
</script>
</body>
</html>
```

- [ ] **Step 2: 브라우저에서 레이아웃 확인**

```bash
cd harness && uvicorn web.server:app --port 8765 &
# 브라우저에서 http://localhost:8765 열기
# 사이드바 렌더링, "+ New Run" 버튼 확인
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: add sidebar layout and run list rendering"
```

---

## Task 11: index.html — Run 상세 뷰 (Stepper + 통계 + 액션)

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: `<script>` 블록에 run 상세 함수 추가** — 기존 `</script>` 바로 앞에 삽입:

```javascript
// ── Run 선택 ─────────────────────────────────────────
async function selectRun(runId) {
  currentRunId = runId;
  stopWs();
  clearInterval(pollTimer);
  document.querySelectorAll('.run-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.run-item').forEach(el => {
    if (el.querySelector('.run-item-name')) {
      const name = runsData.find(r => r.run_id === runId);
      if (el.onclick.toString().includes(runId)) el.classList.add('active');
    }
  });
  renderSidebar(runsData); // re-render with active state
  document.getElementById('run-view').classList.remove('hidden');
  document.getElementById('new-run-view').classList.add('hidden');
  await refreshRunDetail();
  pollTimer = setInterval(refreshRunDetail, 5000);
  connectWs(runId);
}

async function refreshRunDetail() {
  if (!currentRunId) return;
  try {
    const r = await fetch(`/api/runs/${currentRunId}`);
    if (!r.ok) return;
    const run = await r.json();
    renderStepper(run.last_completed_stage, run.status);
    renderStats(run);
    renderActions(run);
    document.getElementById('log-status').textContent = run.status;
  } catch (e) { console.error('refreshRunDetail', e); }
}

function renderStepper(lastStage, status) {
  const stages = {
    env: stageState('env', lastStage, status),
    md: stageState('md', lastStage, status),
    viz: stageState('viz', lastStage, status),
  };
  const labels = { env: 'env-builder', md: 'md-runner', viz: 'illustrator' };
  const order = ['env', 'md', 'viz'];
  let html = '';
  order.forEach((s, i) => {
    const st = stages[s];
    const check = st === 'done' ? '✓' : '';
    html += `<div class="step-node">
      <div class="step-circle ${st}">${st === 'active' ? '' : check}</div>
      <span class="step-label ${st}">${labels[s]}</span>
    </div>`;
    if (i < 2) html += `<div class="step-connector ${stages[order[i]] === 'done' ? 'done' : ''}"></div>`;
  });
  document.getElementById('stepper').innerHTML = html;
}

function stageState(skill, lastStage, status) {
  const order = ['env', 'md', 'viz'];
  const lastIdx = order.indexOf(lastStage);
  const skillIdx = order.indexOf(skill);
  if (skillIdx < lastIdx) return 'done';
  if (skillIdx === lastIdx) return status === 'running' ? 'done' : 'done';
  if (skillIdx === lastIdx + 1 && status === 'running') return 'active';
  if (lastStage === null && status === 'running' && skillIdx === 0) return 'active';
  return 'pending';
}

function renderStats(run) {
  document.getElementById('stat-step').textContent = `${run.current_step} / 8`;
  document.getElementById('stat-stage').textContent = run.last_completed_stage || '—';
  document.getElementById('stat-status').textContent = run.status;
}

function renderActions(run) {
  const btnContinue = document.getElementById('btn-continue');
  const btnAbort = document.getElementById('btn-abort');
  const nextLabels = { env: 'md-runner', md: 'illustrator' };
  if (run.status === 'paused' && nextLabels[run.last_completed_stage]) {
    btnContinue.disabled = false;
    btnContinue.textContent = `▶ Continue (${nextLabels[run.last_completed_stage]})`;
  } else {
    btnContinue.disabled = true;
    btnContinue.textContent = 'Continue';
  }
  btnAbort.disabled = run.status !== 'running';
}

async function doAction(action) {
  if (!currentRunId) return;
  try {
    const r = await fetch(`/api/runs/${currentRunId}/action`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action}),
    });
    if (!r.ok) { alert(await r.text()); return; }
    await refreshRunDetail();
    if (action === 'continue') connectWs(currentRunId);
  } catch (e) { console.error('doAction', e); }
}
```

- [ ] **Step 2: 브라우저에서 run 선택 동작 확인**

```bash
cd harness && uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# runs/ 디렉터리에 테스트용 run이 있으면 클릭해서 stepper/stats 렌더링 확인
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: add run detail view with stepper, stats, and action buttons"
```

---

## Task 12: index.html — WebSocket 로그 패널

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: WebSocket 함수 추가** — `</script>` 바로 앞에 삽입:

```javascript
// ── WebSocket 로그 ────────────────────────────────────
function connectWs(runId) {
  stopWs();
  const logBody = document.getElementById('log-body');
  logBody.textContent = '';
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  wsConn = new WebSocket(`${proto}://${location.host}/ws/runs/${runId}`);
  wsConn.onmessage = (e) => {
    logBody.textContent += e.data;
    // 500줄 초과 시 오래된 줄 제거
    const lines = logBody.textContent.split('\n');
    if (lines.length > 500) {
      logBody.textContent = lines.slice(-500).join('\n');
    }
    logBody.scrollTop = logBody.scrollHeight;
  };
  wsConn.onerror = () => { document.getElementById('log-status').textContent = 'ws error'; };
  wsConn.onclose = () => { wsConn = null; };
}

function stopWs() {
  if (wsConn) { wsConn.close(); wsConn = null; }
}
```

- [ ] **Step 2: 브라우저 확인**

```bash
cd harness && uvicorn web.server:app --port 8765 &
# 브라우저에서 실행 중인 run 선택 시 로그 스트리밍 확인
# 또는 runner.log 파일이 있는 run 선택하면 기존 로그 표시 확인
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: add WebSocket log streaming to log panel"
```

---

## Task 13: index.html — New Run 폼

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: New Run 폼 함수 추가** — `</script>` 바로 앞에 삽입:

```javascript
// ── New Run 폼 ────────────────────────────────────────
function showNewRunForm() {
  document.getElementById('run-view').classList.add('hidden');
  document.getElementById('new-run-view').classList.remove('hidden');
  currentRunId = null;
  clearInterval(pollTimer);
  stopWs();
  renderSidebar(runsData);
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
}

function handleFileSelect(file) {
  if (!file) return;
  selectedPdb = file;
  document.getElementById('selected-file').textContent = `Selected: ${file.name}`;
  document.getElementById('btn-start').disabled = false;
}

async function submitNewRun(e) {
  e.preventDefault();
  if (!selectedPdb) return;
  const form = document.getElementById('new-run-form');
  const fd = new FormData();
  fd.append('pdb_file', selectedPdb, selectedPdb.name);
  fd.append('forcefield', form.querySelector('[name=forcefield]').value);
  fd.append('water', form.querySelector('[name=water]').value);
  fd.append('box_type', form.querySelector('[name=box_type]').value);

  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-start').textContent = 'Starting…';

  try {
    const r = await fetch('/api/runs', { method: 'POST', body: fd });
    if (!r.ok) {
      alert('Failed to start run: ' + await r.text());
      document.getElementById('btn-start').disabled = false;
      document.getElementById('btn-start').textContent = '▶ Start Run';
      return;
    }
    const data = await r.json();
    selectedPdb = null;
    document.getElementById('selected-file').textContent = '';
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-start').textContent = '▶ Start Run';
    await fetchRuns();
    selectRun(data.run_id);
  } catch (err) {
    console.error('submitNewRun', err);
    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-start').textContent = '▶ Start Run';
  }
}
```

- [ ] **Step 2: 브라우저 E2E 확인**

```bash
cd harness && uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# 1. "+ New Run" 클릭 → 폼 표시 확인
# 2. PDB 파일 드래그 앤드 드롭 → "Selected: xxx.pdb" 표시 확인
# 3. "▶ Start Run" 버튼 활성화 확인
# (실제 GROMACS 없으면 subprocess 오류 → runner.exit에 1 기록, status = failed)
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: add new run form with PDB upload and parameter selection"
```

---

## 자체 검토 (Self-Review)

**Spec 커버리지 체크:**
- [x] 레이아웃 A (사이드바 + 메인패널) → Task 10
- [x] 메인 패널 A (Stepper + 로그 + 통계 + Continue/Abort) → Task 11, 12
- [x] New Run 폼 B (전용 페이지, PDB 드롭존, 파라미터 그리드) → Task 13
- [x] GET /api/runs → Task 3
- [x] GET /api/runs/{run_id} → Task 4
- [x] POST /api/runs → Task 6
- [x] POST /api/runs/{run_id}/action → Task 7
- [x] WS /ws/runs/{run_id} → Task 8
- [x] GET / → Task 9
- [x] run 상태 파생 (running/paused/completed/failed/aborted) → Task 2

**타입 일관성:**
- `RunInfo.last_completed_stage` → `str | None` — Task 2에서 정의, Task 4/7 서버, Task 11 JS에서 모두 일관
- `runner.exit` 파일 형식 → 항상 `str(int)` — Task 5 runner.py, Task 2 run_reader.py 일치
- `/api/runs/{run_id}/action` body → `dict` (FastAPI가 JSON 파싱) — Task 7 구현 일치
