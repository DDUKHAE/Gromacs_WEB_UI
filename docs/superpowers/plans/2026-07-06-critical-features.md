# Critical Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 저널 제출 수준을 위한 4가지 Critical Feature 구현: 결과 ZIP 다운로드, PDB 프로토네이션 전처리 실제 작동, 분자 파일 재귀 탐색 버그 수정(NGL Viewer 연동), NGL.js 로컬 번들링.

**Architecture:**
- Task 1: `GET /api/runs/{run_id}/download` 엔드포인트 신규 추가 + 프론트엔드 Download 버튼
- Task 2: `lib/pdb_preprocessor.py` 신규 생성 (HIS 잔기 rename) + `api_create_run`에 전처리 훅 연결
- Task 3: `api_get_run_file`의 top-level 전용 탐색을 재귀 탐색으로 수정 → NGL Viewer 자동 로드 활성화
- Task 4: CDN NGL.js → 로컬 `/static/ngl.js`로 교체

**Tech Stack:** FastAPI, pytest + httpx (기존), zipfile/io (stdlib), NGL Viewer 2.0.0-dev.37 (로컬 번들)

## Global Constraints

- Python ≥ 3.11, FastAPI ≥ 0.111
- 프론트엔드: vanilla JS, 번들러 없음 — 모든 신규 JS는 `index.html` 내 `<script>` 태그에 작성
- 테스트: `pytest`, `fastapi.testclient.TestClient` (동기), `tests/` 하위 `test_*.py`
- 경로 보안: 모든 파일 서빙은 `_check_run_id()` + path-traversal 가드 통과 필수
- 신규 Python 패키지 추가 금지 (stdlib만 사용)
- NGL.js는 현재 CDN URL과 동일한 버전(2.0.0-dev.37) 다운로드
- ZIP 다운로드에서 `.xtc`, `.trr`, `.tpr`, `.edr`, `.cpt` 제외 (수 GB 이상 가능)
- `run_id` 형식: `^[a-z0-9][a-z0-9\-]*_\d{8}_\d{6}$` (기존 `_RUN_ID_RE` 동일)

---

## File Map

| 파일 | 변경 종류 | 담당 기능 |
|------|-----------|-----------|
| `tests/conftest.py` | 신규 | 공용 `workspace` 픽스처 |
| `tests/test_api_download.py` | 신규 | ZIP 다운로드 엔드포인트 테스트 |
| `tests/test_pdb_preprocessor.py` | 신규 | HIS rename 유닛 테스트 |
| `tests/test_api_mol_files.py` | 신규 | 재귀 파일 서빙 테스트 |
| `tests/test_api_static.py` | 신규 | ngl.js 정적 파일 서빙 테스트 |
| `lib/pdb_preprocessor.py` | 신규 | `apply_his_states()` 구현 |
| `web/server.py` | 수정 | download 엔드포인트 추가, api_get_run_file 재귀 수정, api_create_run 전처리 훅 |
| `web/static/index.html` | 수정 | Download 버튼, CDN → 로컬 ngl.js |
| `web/static/ngl.js` | 신규 | NGL Viewer 로컬 번들 |

---

## Task 1: Results ZIP Download

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_api_download.py`
- Modify: `web/server.py` (add endpoint after `api_get_run_file`)
- Modify: `web/static/index.html` (add Download button)

**Interfaces:**
- Produces: `GET /api/runs/{run_id}/download` → `StreamingResponse` (application/zip)
- Produces: `window.downloadRun()` JS 함수

---

- [ ] **Step 1: tests/conftest.py 생성**

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def ws_factory(tmp_path):
    """Return a factory that creates a valid run workspace under tmp_path/runs/."""
    def _make(run_id: str, files: dict[str, str | bytes] | None = None) -> tuple[Path, Path]:
        ws = tmp_path / "runs" / run_id
        ws.mkdir(parents=True)
        (ws / "state.json").write_text('{"status": "completed", "step": 8}')
        (ws / "runner.log").write_text("simulation completed\n")
        (ws / "inputs").mkdir()
        (ws / "inputs" / "input.pdb").write_text("ATOM      1  CA  ALA A   1      0.0   0.0   0.0\n")
        if files:
            for rel_path, content in files.items():
                target = ws / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    target.write_bytes(content)
                else:
                    target.write_text(content)
        return tmp_path, ws
    return _make
```

- [ ] **Step 2: 실패하는 다운로드 테스트 작성**

```python
# tests/test_api_download.py
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from web.server import create_app

RUN_ID = "protein_20260101_120000"


def _client(root: "Path"):
    return TestClient(create_app(root))


def test_download_returns_zip(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    assert f"{RUN_ID}.zip" in resp.headers.get("content-disposition", "")


def test_download_zip_contains_state_and_pdb(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("state.json" in n for n in names)
    assert any("input.pdb" in n for n in names)


def test_download_excludes_large_binary_files(ws_factory):
    root, ws = ws_factory(
        RUN_ID,
        files={
            "traj.xtc": b"\x00" * 200,
            "run.edr": b"\x00" * 200,
            "run.tpr": b"\x00" * 200,
            "run.cpt": b"\x00" * 200,
            "run.trr": b"\x00" * 200,
        },
    )
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    for ext in (".xtc", ".edr", ".tpr", ".cpt", ".trr"):
        assert all(not n.endswith(ext) for n in names), f"{ext} found in zip"


def test_download_includes_nested_files(ws_factory):
    root, ws = ws_factory(
        RUN_ID,
        files={"stage2_md/em.gro": "GROMACS\n", "stage3_viz/rmsd.xvg": "@ title\n"},
    )
    resp = _client(root).get(f"/api/runs/{RUN_ID}/download")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("em.gro" in n for n in names)
    assert any("rmsd.xvg" in n for n in names)


def test_download_unknown_run_returns_404(ws_factory):
    root, _ = ws_factory(RUN_ID)
    resp = _client(root).get("/api/runs/ghost_20260101_120000/download")
    assert resp.status_code == 404
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

```bash
cd /home/ydj/Project/Gromacs_WEB_UI
pytest tests/test_api_download.py -v 2>&1 | head -30
```
Expected: 5 tests FAILED (404 / attribute error, endpoint not found)

- [ ] **Step 4: web/server.py에 download 엔드포인트 추가**

`api_get_run_file` 함수 (line 372) 바로 뒤에 다음 코드 삽입:

```python
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
```

`server.py` 상단 import에 `io`, `zipfile` 추가 (이미 있으면 생략):

```python
import io
import zipfile
```

그리고 `from fastapi.responses import` 줄에 `StreamingResponse` 추가.

- [ ] **Step 5: 테스트 재실행해서 통과 확인**

```bash
pytest tests/test_api_download.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: 프론트엔드 Download 버튼 추가**

`web/static/index.html` line 2101-2104의 `open-3d-btn` 블록 바로 뒤에 삽입:

**추가할 HTML** (`</button>` 태그 이후, `</div>` 이전):
```html
          <button id="download-run-btn" onclick="downloadRun()"
                  style="display:none;padding:7px 16px;border-radius:var(--radius-sm);border:1px solid var(--accent-green);background:transparent;color:var(--accent-green);font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;flex-shrink:0;">
            ↓ Download
          </button>
```

- [ ] **Step 7: JS 함수 추가 및 visibility 연결**

`index.html`에서 `openRunIn3dViewer` 함수 정의 바로 뒤에 추가:

```javascript
function downloadRun() {
  if (!currentRunId) return;
  window.location.href = `/api/runs/${currentRunId}/download`;
}
```

`index.html`에서 `open3dBtn.style.display` 변경 코드(line ~4299-4302)를 찾아, 바로 아래에 추가:

```javascript
  const dlBtn = document.getElementById('download-run-btn');
  if (dlBtn) {
    dlBtn.style.display = (status === 'done' || status === 'completed') ? 'inline-block' : 'none';
  }
```

또한 `clearRunView()` 또는 run deselect 함수(line ~4040)에서 `_o3d.style.display = 'none'` 바로 뒤에:
```javascript
  const _dl = document.getElementById('download-run-btn');
  if (_dl) _dl.style.display = 'none';
```

- [ ] **Step 8: 커밋**

```bash
git add tests/conftest.py tests/test_api_download.py web/server.py web/static/index.html
git commit -m "feat: add ZIP download endpoint and Download button for completed runs"
```

---

## Task 2: PDB Protonation Preprocessing

PROPKA 결과로 UI에서 선택한 HIS 상태(`HSD`/`HSE`/`HSP`)가 `system_config.json`에 저장되지만, 실제 `inputs/input.pdb`에 반영되지 않아 `gmx pdb2gmx`가 무시한다. 이 태스크는 런 생성 시 PDB를 전처리해서 HIS 잔기를 rename한다.

**Files:**
- Create: `lib/pdb_preprocessor.py`
- Create: `tests/test_pdb_preprocessor.py`
- Modify: `web/server.py` (`api_create_run` 내 전처리 훅 추가)

**Interfaces:**
- Produces: `apply_his_states(pdb_text: str, his_states: dict[str, str]) -> str`
  - `his_states`: `{"A:42": "HSD", "B:15": "HSP"}` — chain:resseq → state
  - Returns: modified PDB text (HIS residues renamed)
- Consumes: `system_config.json["protonation"]["his_states"]` in `api_create_run`

---

- [ ] **Step 1: 실패하는 유닛 테스트 작성**

```python
# tests/test_pdb_preprocessor.py
import pytest
from lib.pdb_preprocessor import apply_his_states


# Minimal 80-col PDB ATOM line for chain A, resseq 42, residue HIS
_HIS_ATOM = (
    "ATOM      1  ND1 HIS A  42       1.000   2.000   3.000  1.00  0.00           N  \n"
)
_ALA_ATOM = (
    "ATOM      2  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C  \n"
)


def test_renames_his_to_hsd():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSD"})
    assert "HSD" in result
    assert "HIS" not in result


def test_renames_his_to_hse():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSE"})
    assert "HSE" in result
    assert "HIS" not in result


def test_renames_his_to_hsp():
    result = apply_his_states(_HIS_ATOM, {"A:42": "HSP"})
    assert "HSP" in result
    assert "HIS" not in result


def test_leaves_non_his_unchanged():
    result = apply_his_states(_ALA_ATOM, {"A:1": "HSD"})
    assert "ALA" in result
    assert "HSD" not in result


def test_leaves_unmapped_his_unchanged():
    result = apply_his_states(_HIS_ATOM, {"B:42": "HSD"})  # different chain
    assert "HIS" in result


def test_multiple_his_residues():
    pdb = (
        "ATOM      1  ND1 HIS A  10       0.0   0.0   0.0  1.00  0.00           N  \n"
        "ATOM      2  ND1 HIS A  20       0.0   0.0   0.0  1.00  0.00           N  \n"
        "ATOM      3  CA  ALA A  30       0.0   0.0   0.0  1.00  0.00           C  \n"
    )
    result = apply_his_states(pdb, {"A:10": "HSD", "A:20": "HSP"})
    lines = result.splitlines()
    assert lines[0][17:20] == "HSD"
    assert lines[1][17:20] == "HSP"
    assert lines[2][17:20] == "ALA"


def test_empty_his_states_is_noop():
    result = apply_his_states(_HIS_ATOM, {})
    assert result == _HIS_ATOM


def test_non_atom_records_untouched():
    pdb = "REMARK  HIS references are not renamed in REMARK lines\n" + _HIS_ATOM
    result = apply_his_states(pdb, {"A:42": "HSD"})
    assert result.startswith("REMARK  HIS")
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

```bash
pytest tests/test_pdb_preprocessor.py -v 2>&1 | head -20
```
Expected: ImportError — `lib.pdb_preprocessor` not found

- [ ] **Step 3: lib/pdb_preprocessor.py 구현**

```python
# lib/pdb_preprocessor.py
from __future__ import annotations

_ATOM_RECORDS = {"ATOM", "HETATM"}


def apply_his_states(pdb_text: str, his_states: dict[str, str]) -> str:
    """Rename HIS residues in PDB ATOM/HETATM records.

    his_states maps "chain:resseq" → new_residue_name (e.g. "A:42" → "HSD").
    Only residues currently named "HIS" are modified; other residues are unchanged.
    Residue name occupies columns 18-20 (0-indexed 17:20) in standard PDB format.
    """
    if not his_states:
        return pdb_text

    lines = pdb_text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        rec = line[:6].strip()
        if rec in _ATOM_RECORDS and len(line) >= 26:
            resname = line[17:20]
            if resname == "HIS":
                chain = line[21]
                resseq = line[22:26].strip()
                key = f"{chain}:{resseq}"
                if key in his_states:
                    new_name = his_states[key][:3]  # HSD, HSE, or HSP
                    line = line[:17] + new_name + line[20:]
        result.append(line)
    return "".join(result)
```

- [ ] **Step 4: 테스트 재실행해서 통과 확인**

```bash
pytest tests/test_pdb_preprocessor.py -v
```
Expected: 9 PASSED

- [ ] **Step 5: api_create_run에 전처리 훅 연결**

`web/server.py`의 `api_create_run` 함수 내, `system_config.json` 저장 직후 (line ~435) 에 삽입:

현재 코드:
```python
            (ws / "system_config.json").write_text(json.dumps(config_data, indent=2))
```

그 다음 줄에 추가:
```python
            # Apply protonation preprocessing if HIS states are specified
            prot = config_data.get("protonation", {})
            his_states = prot.get("his_states", {})
            if his_states:
                from lib.pdb_preprocessor import apply_his_states
                original = pdb_path.read_text(encoding="utf-8", errors="replace")
                pdb_path.write_text(apply_his_states(original, his_states), encoding="utf-8")
```

- [ ] **Step 6: 통합 테스트 추가**

`tests/test_api_download.py` 파일에 다음 테스트 추가 (또는 별도 파일 `tests/test_api_protonation_preprocessing.py`):

```python
# tests/test_api_protonation_preprocessing.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from web.server import create_app

HIS_PDB = (
    "ATOM      1  ND1 HIS A  42       1.000   2.000   3.000  1.00  0.00           N  \n"
)
RUN_ID = "prot_20260101_120000"


def test_create_run_preprocesses_his_states(tmp_path):
    pdb_bytes = HIS_PDB.encode()
    system_config = json.dumps({
        "protonation": {"ph": 7.0, "his_states": {"A:42": "HSD"}}
    })

    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"llm": "", "system_config": system_config},
        files={"pdb_file": ("test.pdb", pdb_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    pdb_path = tmp_path / "runs" / run_id / "inputs" / "input.pdb"
    content = pdb_path.read_text()
    assert "HSD" in content
    assert "HIS" not in content


def test_create_run_without_protonation_leaves_pdb_unchanged(tmp_path):
    pdb_bytes = HIS_PDB.encode()

    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/runs",
        data={"llm": ""},
        files={"pdb_file": ("test.pdb", pdb_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]
    pdb_path = tmp_path / "runs" / run_id / "inputs" / "input.pdb"
    content = pdb_path.read_text()
    assert "HIS" in content
```

- [ ] **Step 7: 통합 테스트 실행**

```bash
pytest tests/test_api_protonation_preprocessing.py -v
```
Expected: 2 PASSED

- [ ] **Step 8: 커밋**

```bash
git add lib/pdb_preprocessor.py tests/test_pdb_preprocessor.py tests/test_api_protonation_preprocessing.py web/server.py
git commit -m "feat: add PDB protonation preprocessor, apply HIS states before LLM run"
```

---

## Task 3: Fix Recursive Mol File Serving (NGL Viewer Auto-Load)

`api_list_mol_files`는 `rglob`으로 서브디렉토리를 재귀 탐색하지만, `api_get_run_file`은 `workspace / filename`만 확인한다. 런 워크스페이스의 파일들이 `stage2_md/npt.gro` 등 하위 경로에 있으면 목록에는 보이지만 서빙이 실패한다.

**Files:**
- Create: `tests/test_api_mol_files.py`
- Modify: `web/server.py` (`api_get_run_file` 재귀 탐색으로 수정)

**Interfaces:**
- Consumes: 기존 `GET /api/runs/{run_id}/mol_files` — 변경 없음
- Produces: `GET /api/runs/{run_id}/file/{filename}` — 서브디렉토리 파일도 서빙 가능

---

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_api_mol_files.py
import pytest
from fastapi.testclient import TestClient
from web.server import create_app

RUN_ID = "protein_20260101_120000"


def _client(root):
    return TestClient(create_app(root))


def test_mol_files_returns_gro_in_subdirectory(ws_factory):
    root, ws = ws_factory(RUN_ID, files={"stage2_md/npt.gro": "GROMACS\n"})
    resp = _client(root).get(f"/api/runs/{RUN_ID}/mol_files")
    assert resp.status_code == 200
    assert "npt.gro" in resp.json()


def test_get_run_file_serves_subdirectory_file(ws_factory):
    root, ws = ws_factory(RUN_ID, files={"stage2_md/npt.gro": "GROMACS structure\n"})
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/npt.gro")
    assert resp.status_code == 200
    assert b"GROMACS structure" in resp.content


def test_get_run_file_top_level_still_works(ws_factory):
    root, ws = ws_factory(RUN_ID)
    # input.pdb is at inputs/input.pdb (subdirectory), let's add a top-level pdb too
    (ws / "final.pdb").write_text("ATOM top-level\n")
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/final.pdb")
    assert resp.status_code == 200


def test_get_run_file_missing_returns_404(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/ghost.gro")
    assert resp.status_code == 404


def test_get_run_file_path_traversal_rejected(ws_factory):
    root, ws = ws_factory(RUN_ID)
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/../../etc/passwd")
    assert resp.status_code in (400, 422)


def test_get_run_file_wrong_extension_rejected(ws_factory):
    root, ws = ws_factory(RUN_ID)
    (ws / "notes.txt").write_text("notes")
    resp = _client(root).get(f"/api/runs/{RUN_ID}/file/notes.txt")
    assert resp.status_code == 400
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

```bash
pytest tests/test_api_mol_files.py -v 2>&1 | head -30
```
Expected: `test_get_run_file_serves_subdirectory_file` FAILED (404)

- [ ] **Step 3: api_get_run_file 재귀 탐색으로 수정**

`web/server.py`에서 `api_get_run_file` 함수(line ~372-389)를 수정:

현재 코드:
```python
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
```

수정 후:
```python
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
        # Search recursively — files may be nested in stage subdirectories
        candidate = None
        for f in workspace.rglob(filename):
            resolved = f.resolve()
            if str(resolved).startswith(str(ws_resolved) + os.sep):
                candidate = f
                break
        if candidate is None:
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(str(candidate.resolve()), filename=filename)
```

- [ ] **Step 4: 테스트 재실행해서 통과 확인**

```bash
pytest tests/test_api_mol_files.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: 커밋**

```bash
git add tests/test_api_mol_files.py web/server.py
git commit -m "fix: search subdirectories in api_get_run_file to enable NGL auto-load for stage files"
```

---

## Task 4: Bundle NGL.js Locally

현재 NGL Viewer는 CDN(`cdn.jsdelivr.net`)에서 로드된다. 오프라인 환경(HPC 클러스터, 폐쇄망 연구소)에서는 작동하지 않는다. 동일 버전을 로컬에 번들한다.

**Files:**
- Create: `web/static/ngl.js` (다운로드)
- Create: `tests/test_api_static.py`
- Modify: `web/static/index.html` (CDN URL → 로컬 경로)

**Interfaces:**
- Produces: `GET /static/ngl.js` → NGL Viewer JS (Content-Type: application/javascript)

---

- [ ] **Step 1: 실패하는 정적 파일 테스트 작성**

```python
# tests/test_api_static.py
from fastapi.testclient import TestClient
from web.server import create_app
from pathlib import Path


def test_ngl_js_is_served(tmp_path):
    """NGL.js must be served from /static/ngl.js (not CDN)."""
    client = TestClient(create_app(Path(__file__).parent.parent))
    resp = client.get("/static/ngl.js")
    assert resp.status_code == 200
    assert len(resp.content) > 100_000, "ngl.js is suspiciously small — may not have downloaded"
    # NGL exports a Stage class; its name appears in the bundle
    assert b"Stage" in resp.content
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

```bash
pytest tests/test_api_static.py -v 2>&1 | head -20
```
Expected: FAILED (404 or file not found)

- [ ] **Step 3: NGL.js 다운로드**

```bash
curl -L -o web/static/ngl.js \
  https://cdn.jsdelivr.net/npm/ngl@2.0.0-dev.37/dist/ngl.js
ls -lh web/static/ngl.js
```
Expected: 파일 크기 1.5MB 이상

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_api_static.py -v
```
Expected: PASSED

- [ ] **Step 5: index.html CDN 태그 교체**

`web/static/index.html` line 1993에서:
```html
<script src="https://cdn.jsdelivr.net/npm/ngl@2.0.0-dev.37/dist/ngl.js"></script>
```
를 다음으로 교체:
```html
<script src="/static/ngl.js"></script>
```

- [ ] **Step 6: 전체 테스트 수트 실행**

```bash
pytest tests/ -v
```
Expected: 모든 테스트 PASSED

- [ ] **Step 7: 커밋**

```bash
git add web/static/ngl.js web/static/index.html tests/test_api_static.py
git commit -m "feat: bundle NGL.js locally to remove CDN dependency for offline use"
```

---

## 전체 완료 후 검증

- [ ] 서버 구동 후 수동 확인:

```bash
python main.py --no-browser
```

1. 완료된 런에서 "Download" 버튼 클릭 → ZIP 다운로드 확인
2. System Builder Step 2에서 "Analyze" 버튼 → PROPKA 결과 표시 확인 (propka 설치 시)
3. HIS 상태 선택 후 런 시작 → `inputs/input.pdb` 내 HIS→HSD 변경 확인
4. 완료된 런에서 "3D Viewer" 버튼 → NGL Viewer 모달에 분자 구조 표시 확인
5. 브라우저 DevTools Network 탭 → `ngl.js`가 `/static/ngl.js` (로컬)에서 로드됨 확인
