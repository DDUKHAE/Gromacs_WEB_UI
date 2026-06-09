# Gromacs Harness Web UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4단계(기능 완성 → 디자인 → UX → 반응형/접근성)에 걸쳐 Gromacs Harness 웹 UI를 재설계하여 결과 갤러리·퍼미션 다이얼로그·온보딩·ARIA 지원을 완성한다.

**Architecture:** 모든 프론트엔드 변경은 `web/static/index.html` 단일 파일에 인라인 CSS/JS로 적용하고, 새 API 엔드포인트(`/api/runs/{run_id}/artifacts`)는 `web/server.py`에 추가, 퍼미션 감지 로직은 `web/llm_runner.py`에 추가한다. 외부 빌드 도구 없이 vanilla JS + Canvas 2D API만 사용한다.

**Tech Stack:** Python 3.11, FastAPI, vanilla JS (ES2020), Canvas 2D API, CSS custom properties, xterm.js (기존 유지)

---

## Current State (읽기 전 확인)

```
harness/web/
  server.py          ← API 엔드포인트들 (runs CRUD, WS, static 서빙)
  llm_runner.py      ← PTY 기반 LLM 에이전트 실행
  run_reader.py      ← run 상태 파생
  static/index.html  ← 497줄, GitHub dark 테마, xterm.js 터미널 내장
harness/lib/xvg_parser.py  ← parse(path, max_points) 함수 존재
harness/skills/illustrator/illustrator.py  ← stage3_viz/*.xvg 출력
```

기존 `index.html`의 주요 섹션:
- `#sidebar` (220px): run 목록, New Run 버튼
- `#run-view`: `#stepper` / `#terminal-panel` / `#stats-row` / `#action-row`
- `#new-run-view`: PDB 업로드 폼, 파라미터 그리드, LLM 섹션
- `#perm-overlay`: 퍼미션 다이얼로그 HTML + CSS 존재, **JS 없음**

---

## File Structure

```
수정:
  harness/web/server.py                      ← artifacts API 추가
  harness/web/llm_runner.py                  ← 퍼미션 감지 추가
  harness/web/static/index.html              ← 모든 UI 변경

신규:
  harness/tests/web/test_artifacts_api.py    ← artifacts API 테스트
```

---

## PHASE 1 — 기능 완성

---

## Task 1: GET /api/runs/{run_id}/artifacts 엔드포인트

**Files:**
- Modify: `harness/web/server.py`
- Create: `harness/tests/web/test_artifacts_api.py`

- [ ] **Step 1: 실패 테스트 작성**

`harness/tests/web/test_artifacts_api.py`:

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


def _make_run(harness_dir: Path, run_id="ubq_20260609_120000", stage="viz") -> Path:
    ws = harness_dir / "runs" / run_id
    viz = ws / "stage3_viz"
    viz.mkdir(parents=True)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": stage, "current_step": 8, "pending_warnings": []}))
    return ws


def _write_xvg(path: Path, title="RMSD", xlabel="Time (ns)", ylabel="RMSD (nm)") -> None:
    path.write_text(
        f'@ title "{title}"\n'
        f'@ xaxis label "{xlabel}"\n'
        f'@ yaxis label "{ylabel}"\n'
        '0.0 0.10\n'
        '0.1 0.12\n'
        '0.2 0.11\n'
    )


async def test_artifacts_empty_before_viz(app, harness_dir):
    """stage3_viz 폴더가 없으면 빈 배열 반환."""
    ws = harness_dir / "runs" / "ubq_20260609_120000"
    ws.mkdir(parents=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/ubq_20260609_120000/artifacts")
    assert r.status_code == 200
    assert r.json() == []


async def test_artifacts_returns_parsed_xvg(app, harness_dir):
    ws = _make_run(harness_dir)
    _write_xvg(ws / "stage3_viz" / "rmsd.xvg", title="RMSD", ylabel="RMSD (nm)")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/ubq_20260609_120000/artifacts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    item = data[0]
    assert item["name"] == "rmsd"
    assert item["title"] == "RMSD"
    assert item["yaxis_label"] == "RMSD (nm)"
    assert "columns" in item
    assert len(item["columns"]) == 2  # x and y columns
    assert len(item["columns"][0]) == 3  # 3 data points


async def test_artifacts_invalid_run_id(app, harness_dir):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/../../etc/passwd/artifacts")
    assert r.status_code == 400
```

- [ ] **Step 2: 실패 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
pytest tests/web/test_artifacts_api.py -v
```

Expected: `FAILED` (404 — endpoint not found)

- [ ] **Step 3: server.py에 artifacts 엔드포인트 추가**

`harness/web/server.py` 맨 위 import 섹션에 추가:
```python
from lib import xvg_parser
```

`create_app()` 함수 안, `@app.get("/api/llms")` 라우트 바로 다음에 추가:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
pytest tests/web/test_artifacts_api.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/web/server.py harness/tests/web/test_artifacts_api.py
git commit -m "feat: add GET /api/runs/{run_id}/artifacts endpoint for XVG chart data"
```

---

## Task 2: 결과 갤러리 패널 HTML/CSS + JavaScript

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: `<style>` 블록에 갤러리 CSS 추가**

`index.html`의 `</style>` 바로 앞에 삽입:

```css
/* Results Gallery */
#gallery-panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
#gallery-panel.hidden { display: none; }
#gallery-title { font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 12px; }
#gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.chart-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px; }
.chart-card-title { font-size: 10px; color: #8b949e; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .04em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chart-canvas { width: 100%; height: 80px; display: block; }
.chart-stats { display: flex; justify-content: space-between; margin-top: 5px; font-size: 9px; color: #8b949e; }
.chart-stats span { color: #e6edf3; }
```

- [ ] **Step 2: `#run-view` 안에 갤러리 패널 HTML 추가**

`index.html`의 `#action-row` div 바로 다음에 삽입:

```html
    <!-- Results Gallery -->
    <div id="gallery-panel" class="hidden">
      <div id="gallery-title">Analysis Results</div>
      <div id="gallery-grid"></div>
    </div>
```

- [ ] **Step 3: 갤러리 렌더링 JavaScript 추가**

`index.html`의 `</script>` 바로 앞에 삽입:

```javascript
// ── 결과 갤러리 ───────────────────────────────────────
async function fetchAndRenderGallery(runId) {
  const panel = document.getElementById('gallery-panel');
  try {
    const r = await fetch(`/api/runs/${runId}/artifacts`);
    if (!r.ok) return;
    const artifacts = await r.json();
    if (artifacts.length === 0) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    renderGallery(artifacts);
  } catch (e) { console.error('fetchAndRenderGallery', e); }
}

function renderGallery(artifacts) {
  const grid = document.getElementById('gallery-grid');
  grid.innerHTML = '';
  artifacts.forEach(a => {
    const card = document.createElement('div');
    card.className = 'chart-card';
    const title = document.createElement('div');
    title.className = 'chart-card-title';
    title.textContent = a.title || a.name;
    title.title = `${a.xaxis_label || 'x'} vs ${a.yaxis_label || 'y'}`;

    const canvas = document.createElement('canvas');
    canvas.className = 'chart-canvas';
    canvas.width = 200;
    canvas.height = 80;

    const statsRow = document.createElement('div');
    statsRow.className = 'chart-stats';

    card.appendChild(title);
    card.appendChild(canvas);
    card.appendChild(statsRow);
    grid.appendChild(card);

    // Render after DOM insertion so canvas has layout
    requestAnimationFrame(() => {
      const cols = a.columns || [];
      const x = cols[0] || [];
      const y = cols[1] || [];
      drawSparkline(canvas, x, y, a.yaxis_label || '');
      if (y.length > 0) {
        const mn = Math.min(...y).toFixed(3);
        const mx = Math.max(...y).toFixed(3);
        const last = y[y.length - 1].toFixed(3);
        statsRow.innerHTML = `min <span>${mn}</span> max <span>${mx}</span> last <span>${last}</span>`;
      }
    });
  });
}

function drawSparkline(canvas, xData, yData, yLabel) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const pad = { top: 4, right: 4, bottom: 14, left: 4 };
  ctx.clearRect(0, 0, w, h);

  if (yData.length < 2) {
    ctx.fillStyle = '#8b949e';
    ctx.font = '9px monospace';
    ctx.fillText('No data', pad.left, h / 2);
    return;
  }

  const minY = Math.min(...yData), maxY = Math.max(...yData);
  const rangeY = maxY - minY || 1;
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const toX = (i) => pad.left + (i / (yData.length - 1)) * plotW;
  const toY = (v) => pad.top + plotH - ((v - minY) / rangeY) * plotH;

  // Fill area
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(yData[0]));
  for (let i = 1; i < yData.length; i++) ctx.lineTo(toX(i), toY(yData[i]));
  ctx.lineTo(toX(yData.length - 1), h - pad.bottom);
  ctx.lineTo(pad.left, h - pad.bottom);
  ctx.closePath();
  ctx.fillStyle = 'rgba(56, 139, 253, 0.12)';
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(yData[0]));
  for (let i = 1; i < yData.length; i++) ctx.lineTo(toX(i), toY(yData[i]));
  ctx.strokeStyle = '#388bfd';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Y-axis label
  ctx.fillStyle = '#8b949e';
  ctx.font = '8px monospace';
  ctx.fillText(yLabel.substring(0, 20), pad.left, h - 2);
}
```

- [ ] **Step 4: `refreshRunDetail()` 함수에 갤러리 호출 연결**

`index.html`의 기존 `refreshRunDetail()` 함수 안에서:

현재 코드:
```javascript
    renderStats(run);
    renderActions(run);
    document.getElementById('term-status').textContent = run.status;
```

교체:
```javascript
    renderStats(run);
    renderActions(run);
    document.getElementById('term-status').textContent = run.status;
    if (run.status === 'completed') {
      fetchAndRenderGallery(currentRunId);
    } else {
      document.getElementById('gallery-panel').classList.add('hidden');
    }
```

- [ ] **Step 5: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# completed 상태 run 선택 → gallery-panel 표시, 차트 렌더링 확인
# stage3_viz/*.xvg 없는 run → gallery-panel hidden 확인
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: add results gallery panel with Canvas sparkline charts"
```

---

## Task 3: 퍼미션 다이얼로그 — 서버 감지

**Files:**
- Modify: `harness/web/llm_runner.py`

- [ ] **Step 1: llm_runner.py에 패턴 및 감지 로직 추가**

`harness/web/llm_runner.py` 파일 상단 import 뒤에 추가:

```python
import json
```

(이미 있으면 skip)

`_ANSI_RE` 정의 아래에 추가:

```python
_PERM_RE = re.compile(
    r'Allow\?\s*\[|'           # Claude Code: "Allow? ["
    r'\[y/n\]|'                # Generic [y/n]
    r'\[Y/n\]|'                # Generic [Y/n]
    r'\(y/n\)',                # Generic (y/n)
    re.IGNORECASE,
)
```

- [ ] **Step 2: `_pty_reader()` 함수에 퍼미션 감지 추가**

`llm_runner.py`의 `_pty_reader()` 내부 while 루프를:

현재:
```python
    def _pty_reader() -> None:
        """Read PTY output in a thread; write to log + enqueue for WebSocket."""
        with open(log_path, "a", encoding="utf-8", errors="replace") as log_fh:
            while True:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                log_fh.write(strip_ansi(data.decode("utf-8", errors="replace")))
                log_fh.flush()
                loop.call_soon_threadsafe(output_q.put_nowait, data)

        loop.call_soon_threadsafe(output_q.put_nowait, None)   # EOF sentinel
```

교체:
```python
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
                    perm_context.clear()

        loop.call_soon_threadsafe(output_q.put_nowait, None)   # EOF sentinel
```

- [ ] **Step 3: 문법 검사**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
python -c "from web.llm_runner import run_llm_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add harness/web/llm_runner.py
git commit -m "feat: detect LLM permission prompts and emit JSON events via WebSocket"
```

---

## Task 4: 퍼미션 다이얼로그 — 클라이언트 JavaScript

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: perm-overlay HTML 확인 (이미 존재)**

`index.html`에 이미 아래 HTML이 있는지 확인:
```html
<div id="perm-overlay">
  <div id="perm-box">
    <h3>Permission Required</h3>
    ...
    <div id="perm-actions">
      <button id="perm-deny">Deny</button>
      <button id="perm-allow">Allow</button>
    </div>
  </div>
</div>
```
없으면 `</body>` 바로 앞에 삽입:

```html
<div id="perm-overlay">
  <div id="perm-box">
    <h3 id="perm-title">Permission Required</h3>
    <div id="perm-tool-label">LLM agent is requesting to execute:</div>
    <pre id="perm-detail"></pre>
    <div id="perm-actions">
      <button id="perm-deny" onclick="permRespond(false)">✕ Deny</button>
      <button id="perm-allow" onclick="permRespond(true)">✓ Allow</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: 퍼미션 다이얼로그 JavaScript 추가**

`index.html` `</script>` 바로 앞에 삽입:

```javascript
// ── 퍼미션 다이얼로그 ─────────────────────────────────
function showPermissionDialog(detail) {
  const detailEl = document.getElementById('perm-detail');
  if (detailEl) detailEl.textContent = detail;
  const overlay = document.getElementById('perm-overlay');
  if (overlay) overlay.classList.add('show');
}

function hidePermissionDialog() {
  const overlay = document.getElementById('perm-overlay');
  if (overlay) overlay.classList.remove('show');
}

function permRespond(allow) {
  hidePermissionDialog();
  if (wsConn && wsConn.readyState === WebSocket.OPEN) {
    // Send y or n as raw bytes through the PTY
    wsConn.send(new TextEncoder().encode(allow ? 'y\r' : 'n\r'));
  }
}
```

- [ ] **Step 3: WebSocket onmessage에서 퍼미션 이벤트 라우팅**

`index.html`의 기존 `wsConn.onmessage` 핸들러:

현재:
```javascript
  wsConn.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) {
      if (term) term.write(new Uint8Array(e.data));
    } else {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'exit') document.getElementById('term-status').textContent = 'finished';
      } catch {}
    }
  };
```

교체:
```javascript
  wsConn.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) {
      if (term) term.write(new Uint8Array(e.data));
    } else {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'exit') {
          document.getElementById('term-status').textContent = 'finished';
        } else if (msg.type === 'permission_request') {
          showPermissionDialog(msg.detail || '');
        }
      } catch {}
    }
  };
```

- [ ] **Step 4: perm-overlay CSS에 `show` 클래스 동작 확인**

`index.html` CSS에 이미 있는지 확인:
```css
#perm-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 200; align-items: center; justify-content: center; }
#perm-overlay.show { display: flex; }
```
없으면 `</style>` 바로 앞에 삽입.

- [ ] **Step 5: 브라우저 수동 테스트**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저 콘솔에서 테스트:
# showPermissionDialog("Bash\nls -la /tmp")
# → 오버레이 표시, Allow/Deny 버튼 동작 확인
# hidePermissionDialog() → 오버레이 사라짐 확인
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: wire permission dialog JS to WebSocket permission_request events"
```

---

## Task 5: 스테퍼 애니메이션 + 스텝 서브프로그레스

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 스테퍼 CSS 개선**

`index.html` CSS에서 스테퍼 관련 부분 교체:

현재:
```css
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
```

교체:
```css
#stepper { display: flex; align-items: center; gap: 0; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 20px; }
.step-node { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.step-circle-wrap { display: flex; align-items: center; gap: 6px; }
.step-circle { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; transition: background .3s, border-color .3s, transform .2s; }
.step-circle.done { background: #238636; color: #fff; transform: scale(1.05); }
.step-circle.active { background: transparent; border: 2px solid #388bfd; color: #388bfd; position: relative; }
.step-circle.active::after { content: ''; display: block; width: 10px; height: 10px; background: #388bfd; border-radius: 50%; animation: pulse 1.2s ease-in-out infinite; position: absolute; }
.step-circle.pending { background: #21262d; color: #8b949e; }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .35; transform: scale(0.75); } }
.step-label { font-size: 10px; color: #8b949e; text-align: center; }
.step-label.done { color: #3fb950; }
.step-label.active { color: #388bfd; font-weight: 600; }
.step-sublabel { font-size: 9px; color: #8b949e; text-align: center; margin-top: 1px; }
.step-connector { flex: 1; height: 2px; background: #30363d; margin: 0 10px; margin-bottom: 14px; transition: background .4s ease; }
.step-connector.done { background: #3fb950; }
.step-connector.active { background: linear-gradient(to right, #3fb950 40%, #30363d 40%); animation: connector-fill 2s ease infinite; }
@keyframes connector-fill { 0% { background-position: -200px 0; } 100% { background-position: 200px 0; } }
```

- [ ] **Step 2: renderStepper() 함수 개선**

`index.html`의 기존 `renderStepper()` 함수 교체:

현재:
```javascript
function renderStepper(lastStage, status) {
  const stages = {
    env: stageState('env', lastStage, status),
    md:  stageState('md',  lastStage, status),
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
```

교체:
```javascript
const STAGE_LABELS = {
  env: { en: 'env-builder', ko: '환경 구축' },
  md:  { en: 'md-runner',   ko: '시뮬레이션' },
  viz: { en: 'illustrator', ko: '분석' },
};
const STAGE_STEPS = { env: '0–5', md: '6–7', viz: '8' };

function renderStepper(lastStage, status, currentStep) {
  const order = ['env', 'md', 'viz'];
  const states = {};
  order.forEach(s => { states[s] = stageState(s, lastStage, status); });

  let html = '';
  order.forEach((s, i) => {
    const st = states[s];
    const icon = st === 'done' ? '✓' : st === 'active' ? '' : '○';
    const lbl = STAGE_LABELS[s];
    const connState = states[order[i]] === 'done' ? 'done' : (states[order[i]] === 'active' ? 'active' : '');
    html += `<div class="step-node">
      <div class="step-circle-wrap">
        <div class="step-circle ${st}" title="${lbl.en} (Steps ${STAGE_STEPS[s]})">${icon}</div>
      </div>
      <span class="step-label ${st}">${lbl.en}</span>
      <span class="step-sublabel">${lbl.ko}</span>
    </div>`;
    if (i < 2) html += `<div class="step-connector ${connState}"></div>`;
  });
  document.getElementById('stepper').innerHTML = html;
}
```

- [ ] **Step 3: refreshRunDetail()에서 currentStep 전달**

`index.html`의 `refreshRunDetail()` 함수에서:

현재:
```javascript
    renderStepper(run.last_completed_stage, run.status);
```

교체:
```javascript
    renderStepper(run.last_completed_stage, run.status, run.current_step);
```

- [ ] **Step 4: 브라우저 시각 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# running 상태 run → active 단계 pulse 애니메이션 확인
# completed 상태 run → 모든 done 상태, 초록색 연결선 확인
# 스텝 라벨 한영 병기 확인
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add harness/web/static/index.html
git commit -m "feat: improve stepper with bilingual labels, transitions, and connector animation"
```

---

## PHASE 2 — 디자인 개선

---

## Task 6: CSS 커스텀 프로퍼티 + 타이포그래피 계층

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: CSS 커스텀 프로퍼티 추가**

`index.html` `<style>` 블록 맨 앞에 삽입:

```css
:root {
  --bg-base:    #0d1117;
  --bg-surface: #161b22;
  --bg-raised:  #21262d;
  --border:     #30363d;
  --text-primary:   #e6edf3;
  --text-secondary: #a0aab4;
  --text-muted:     #8b949e;
  --accent-blue:    #388bfd;
  --accent-green:   #3fb950;
  --accent-yellow:  #d29922;
  --accent-red:     #f85149;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,.4);
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
}
```

- [ ] **Step 2: 기존 하드코딩 색상을 커스텀 프로퍼티로 교체**

`index.html` `<style>` 블록에서 아래 치환을 `replace_all`로 적용:

`#0d1117` → `var(--bg-base)`  
`#161b22` → `var(--bg-surface)`  
`#21262d` → `var(--bg-raised)`  
`#30363d` → `var(--border)`  
`#e6edf3` → `var(--text-primary)`  
`#8b949e` → `var(--text-muted)`  
`#388bfd` → `var(--accent-blue)`  
`#3fb950` → `var(--accent-green)`  
`#d29922` → `var(--accent-yellow)`  
`#f85149` → `var(--accent-red)`

- [ ] **Step 3: 타이포그래피 스케일 업데이트**

`index.html` CSS에서:

현재:
```css
#sidebar-title { font-size: 12px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
```

교체:
```css
#sidebar-title { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
```

현재:
```css
#new-run-form h2 { font-size: 18px; color: #e6edf3; }
```

교체:
```css
#new-run-form h2 { font-size: 20px; font-weight: 700; color: var(--text-primary); letter-spacing: -.3px; }
```

현재:
```css
.stat-label { font-size: 9px; color: #8b949e; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 4px; }
.stat-value { font-size: 16px; font-weight: 600; color: #e6edf3; }
```

교체:
```css
.stat-label { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
.stat-value { font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -.5px; }
```

- [ ] **Step 4: 브라우저 시각 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: 사이드바 타이틀, stat-card 레이블/값, New Run 헤딩 크기 확인
# DevTools > Elements > --bg-base 커스텀 프로퍼티 존재 확인
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add harness/web/static/index.html
git commit -m "design: add CSS custom properties and improve typography hierarchy"
```

---

## Task 7: 카드 컴포넌트 통일 + 쉐도우

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: `.card` 공통 클래스 추가**

`index.html` CSS `:root` 블록 바로 아래에 추가:

```css
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.card-header {
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
```

- [ ] **Step 2: 기존 패널들에 `.card` 클래스 적용 (HTML 수정)**

`index.html` HTML에서:

`<div id="stepper">` → `<div id="stepper" class="card">`  
`<div id="terminal-panel">` → `<div id="terminal-panel" class="card">`  
`<div id="gallery-panel" class="hidden">` → `<div id="gallery-panel" class="card hidden">`

`<div id="terminal-header" ...>` → `<div id="terminal-header" class="card-header">`

- [ ] **Step 3: 기존 중복 border/background/border-radius CSS 정리**

`index.html` CSS에서 card가 적용된 패널들의 중복 스타일 제거:

현재 `#stepper` 스타일:
```css
#stepper { display: flex; align-items: center; gap: 0; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 20px; }
```

교체 (중복 제거):
```css
#stepper { display: flex; align-items: center; gap: 0; padding: 14px 20px; }
```

현재 `#terminal-panel` 스타일:
```css
#terminal-panel { flex: 1; background: var(--bg-base); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; display: flex; flex-direction: column; min-height: 260px; }
#terminal-header { padding: 8px 14px; background: var(--bg-surface); border-bottom: 1px solid var(--border); font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between; flex-shrink: 0; }
```

교체:
```css
#terminal-panel { flex: 1; background: var(--bg-base); overflow: hidden; display: flex; flex-direction: column; min-height: 260px; }
```

현재 `#gallery-panel` 스타일:
```css
#gallery-panel { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-md); }
```

교체:
```css
#gallery-panel { padding: var(--space-md); }
```

- [ ] **Step 4: stat-card에 box-shadow 추가**

현재:
```css
.stat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px 16px; }
```

교체:
```css
.stat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px 16px; box-shadow: var(--shadow-sm); transition: box-shadow .2s; }
.stat-card:hover { box-shadow: var(--shadow-md); }
```

- [ ] **Step 5: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 터미널 패널, 스테퍼, 갤러리의 border-radius/shadow 통일 확인
# stat-card hover 시 shadow 심화 확인
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "design: unify card components with shared CSS class and consistent shadows"
```

---

## Task 8: 스켈레톤 로딩 + 진행 애니메이션

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 스켈레톤 CSS 추가**

`index.html` CSS `</style>` 바로 앞에 삽입:

```css
/* Skeleton loading */
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
.skeleton {
  background: linear-gradient(90deg, var(--bg-raised) 25%, var(--border) 50%, var(--bg-raised) 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s infinite linear;
  border-radius: var(--radius-sm);
}
.skeleton-text { height: 12px; margin-bottom: 6px; }
.skeleton-value { height: 20px; width: 60%; }
```

- [ ] **Step 2: stat-card 스켈레톤 렌더 함수 추가**

`index.html` `</script>` 바로 앞에 삽입:

```javascript
function renderStatsSkeleton() {
  ['stat-step', 'stat-stage', 'stat-status'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.innerHTML = '<div class="skeleton skeleton-value"></div>';
    }
  });
}
```

- [ ] **Step 3: selectRun()에서 스켈레톤 표시**

`index.html`의 `selectRun()` 함수에서, `renderSidebar(runsData)` 호출 바로 다음에:

```javascript
  renderStatsSkeleton();
```

삽입.

- [ ] **Step 4: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: run 선택 시 stat-card에 shimmer 스켈레톤 표시 확인 (0.1초 정도 보임)
# 데이터 로드 후 실제 값으로 대체 확인
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add harness/web/static/index.html
git commit -m "design: add skeleton shimmer loading for stat cards"
```

---

## PHASE 3 — 접근성 & UX

---

## Task 9: 에러 Toast 시스템 (alert() 대체)

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: Toast CSS 추가**

`index.html` CSS `</style>` 바로 앞에 삽입:

```css
/* Toast notifications */
#toast-container { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 300; }
.toast { padding: 10px 16px; border-radius: var(--radius-md); font-size: 12px; color: #fff; max-width: 320px; opacity: 0; transform: translateY(8px); transition: opacity .25s, transform .25s; pointer-events: none; display: flex; align-items: center; gap: 8px; box-shadow: var(--shadow-md); }
.toast.show { opacity: 1; transform: none; pointer-events: auto; }
.toast.error   { background: #6e2020; border: 1px solid var(--accent-red); }
.toast.success { background: #163a1f; border: 1px solid var(--accent-green); }
.toast.warning { background: #3d2b00; border: 1px solid var(--accent-yellow); }
.toast.info    { background: #0f2240; border: 1px solid var(--accent-blue); }
```

- [ ] **Step 2: Toast 컨테이너 HTML 추가**

`index.html` `</body>` 바로 앞에 삽입:

```html
<div id="toast-container" role="status" aria-live="polite"></div>
```

- [ ] **Step 3: showToast() 함수 추가**

`index.html` `</script>` 바로 앞에 삽입:

```javascript
// ── Toast 알림 ────────────────────────────────────────
const TOAST_ICONS = { error: '✕', success: '✓', warning: '⚠', info: 'ℹ' };

function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${TOAST_ICONS[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
```

- [ ] **Step 4: 기존 alert() 호출 교체**

`index.html`의 `doAction()` 함수에서:

현재:
```javascript
    if (!r.ok) { alert(await r.text()); return; }
```

교체:
```javascript
    if (!r.ok) { showToast(await r.text(), 'error'); return; }
```

`submitNewRun()` 함수에서:

현재:
```javascript
      alert('Failed to start run: ' + await r.text());
```

교체:
```javascript
      showToast('Failed to start run: ' + await r.text(), 'error');
```

- [ ] **Step 5: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저 콘솔에서 테스트:
# showToast('Run started successfully', 'success')
# showToast('Connection error', 'error')
# showToast('Step 3 warning', 'warning')
# → 오른쪽 하단에 fade-in → 4초 후 fade-out 확인
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "ux: replace alert() with toast notification system"
```

---

## Task 10: 첫 접속 온보딩 모달

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 온보딩 모달 CSS 추가**

`index.html` CSS `</style>` 바로 앞에 삽입:

```css
/* Onboarding Modal */
#onboard-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.65); z-index: 400; align-items: center; justify-content: center; }
#onboard-overlay.show { display: flex; }
#onboard-box { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px 32px; max-width: 480px; width: 90%; box-shadow: var(--shadow-md); }
#onboard-box h2 { font-size: 18px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
#onboard-box p  { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.6; }
.onboard-steps { display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px; }
.onboard-step { display: flex; align-items: flex-start; gap: 12px; }
.onboard-step-icon { width: 28px; height: 28px; border-radius: 50%; background: var(--bg-raised); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: var(--accent-blue); flex-shrink: 0; }
.onboard-step-text strong { display: block; font-size: 12px; color: var(--text-primary); margin-bottom: 2px; }
.onboard-step-text span { font-size: 11px; color: var(--text-muted); }
#onboard-got-it { width: 100%; padding: 10px; background: var(--accent-blue); border: none; color: #fff; font-size: 14px; border-radius: var(--radius-md); cursor: pointer; font-weight: 600; }
#onboard-got-it:hover { background: #58a6ff; }
```

- [ ] **Step 2: 온보딩 모달 HTML 추가**

`index.html` `#toast-container` 바로 앞에 삽입:

```html
<div id="onboard-overlay" role="dialog" aria-modal="true" aria-labelledby="onboard-title">
  <div id="onboard-box">
    <h2 id="onboard-title">Gromacs Harness에 오신 것을 환영합니다</h2>
    <p>이 대시보드로 분자 동역학 시뮬레이션을 브라우저에서 실행하고 모니터링할 수 있습니다.</p>
    <div class="onboard-steps">
      <div class="onboard-step">
        <div class="onboard-step-icon">1</div>
        <div class="onboard-step-text">
          <strong>PDB 파일 업로드</strong>
          <span>New Run 버튼 → PDB 파일 드래그&드롭 또는 클릭하여 선택</span>
        </div>
      </div>
      <div class="onboard-step">
        <div class="onboard-step-icon">2</div>
        <div class="onboard-step-text">
          <strong>파라미터 설정 후 실행</strong>
          <span>포스필드·수모델·박스 타입 선택 → ▶ Start Run</span>
        </div>
      </div>
      <div class="onboard-step">
        <div class="onboard-step-icon">3</div>
        <div class="onboard-step-text">
          <strong>3단계 파이프라인 진행</strong>
          <span>env-builder(환경 구축) → md-runner(시뮬레이션) → illustrator(분석)</span>
        </div>
      </div>
      <div class="onboard-step">
        <div class="onboard-step-icon">4</div>
        <div class="onboard-step-text">
          <strong>결과 확인</strong>
          <span>완료 후 Analysis Results 섹션에서 RMSD·RMSF·에너지 차트 확인</span>
        </div>
      </div>
    </div>
    <button id="onboard-got-it" onclick="dismissOnboarding()">시작하기</button>
  </div>
</div>
```

- [ ] **Step 3: 온보딩 JavaScript 추가**

`index.html` `</script>` 바로 앞에 삽입:

```javascript
// ── 온보딩 모달 ───────────────────────────────────────
function checkOnboarding() {
  if (!localStorage.getItem('gmx_onboarded')) {
    document.getElementById('onboard-overlay').classList.add('show');
  }
}

function dismissOnboarding() {
  localStorage.setItem('gmx_onboarded', '1');
  document.getElementById('onboard-overlay').classList.remove('show');
}
```

- [ ] **Step 4: `init()` 함수에 온보딩 체크 추가**

`index.html`의 `(function init()` IIFE:

현재:
```javascript
(function init() {
  fetchRuns();
  setInterval(fetchRuns, 10000);
})();
```

교체:
```javascript
(function init() {
  fetchRuns();
  setInterval(fetchRuns, 10000);
  checkOnboarding();
})();
```

- [ ] **Step 5: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# → 첫 접속 시 온보딩 모달 표시 확인
# "시작하기" 클릭 → 모달 닫힘, localStorage에 'gmx_onboarded'='1' 저장 확인
# 새로고침 → 모달 미표시 확인
# DevTools > Application > localStorage 에서 'gmx_onboarded' 삭제 후 재확인
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "ux: add first-visit onboarding modal with workflow steps"
```

---

## Task 11: 파라미터 툴팁 추가

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 툴팁 CSS 추가**

`index.html` CSS `</style>` 바로 앞에 삽입:

```css
/* Tooltips */
.tooltip-wrap { position: relative; display: inline-block; }
.tooltip-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 10px; padding: 0 2px; vertical-align: middle; border-radius: 50%; width: 14px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--border); }
.tooltip-btn:hover { color: var(--accent-blue); border-color: var(--accent-blue); }
.tooltip-content { display: none; position: absolute; left: 0; top: calc(100% + 4px); background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 11px; color: var(--text-secondary); line-height: 1.5; min-width: 220px; max-width: 260px; z-index: 100; box-shadow: var(--shadow-md); }
.tooltip-wrap:focus-within .tooltip-content,
.tooltip-btn:focus + .tooltip-content,
.tooltip-btn:hover + .tooltip-content { display: block; }
.tooltip-content strong { display: block; color: var(--text-primary); margin-bottom: 3px; }
```

- [ ] **Step 2: Forcefield 라벨에 툴팁 추가**

`index.html` HTML에서 Forcefield 파라미터 필드:

현재:
```html
        <div class="param-field">
          <label>Forcefield</label>
          <select name="forcefield">
```

교체:
```html
        <div class="param-field">
          <label>Forcefield
            <span class="tooltip-wrap">
              <button type="button" class="tooltip-btn" aria-label="Forcefield 설명">?</button>
              <div class="tooltip-content" role="tooltip">
                <strong>포스필드 (Force Field)</strong>
                원자 간 상호작용을 기술하는 파라미터 세트입니다.<br>
                · CHARMM36: 단백질·막 시스템에 적합<br>
                · AMBER99SB-ILDN: 단백질 폴딩 연구에 검증<br>
                · OPLS-AA: 유기 분자 시뮬레이션에 강점
              </div>
            </span>
          </label>
          <select name="forcefield">
```

- [ ] **Step 3: Water Model 라벨에 툴팁 추가**

현재:
```html
        <div class="param-field">
          <label>Water Model</label>
          <select name="water">
```

교체:
```html
        <div class="param-field">
          <label>Water Model
            <span class="tooltip-wrap">
              <button type="button" class="tooltip-btn" aria-label="수모델 설명">?</button>
              <div class="tooltip-content" role="tooltip">
                <strong>수모델 (Water Model)</strong>
                솔벤트 물 분자의 전하·형태 파라미터입니다.<br>
                · TIP3P: 계산 비용 낮고 널리 사용<br>
                · SPC: 간단하고 빠름, 유전율 낮음<br>
                · TIP4P: 밀도·상변화 특성 향상
              </div>
            </span>
          </label>
          <select name="water">
```

- [ ] **Step 4: Box Type 라벨에 툴팁 추가**

현재:
```html
        <div class="param-field">
          <label>Box Type</label>
          <select name="box_type">
```

교체:
```html
        <div class="param-field">
          <label>Box Type
            <span class="tooltip-wrap">
              <button type="button" class="tooltip-btn" aria-label="박스 타입 설명">?</button>
              <div class="tooltip-content" role="tooltip">
                <strong>시뮬레이션 박스</strong>
                주기적 경계 조건(PBC)의 단위 셀 형태입니다.<br>
                · Dodecahedron: 구형 단백질에 최적, 물 분자 절약<br>
                · Cubic: 가장 단순, 비구형 시스템에 큰 박스 필요<br>
                · Triclinic: 임의 형태, 결정·막 시뮬레이션에 사용
              </div>
            </span>
          </label>
          <select name="box_type">
```

- [ ] **Step 5: 브라우저 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: New Run 클릭 → Forcefield/Water/BoxType 라벨 옆 [?] 버튼 확인
# [?] 호버/클릭 → 툴팁 팝업 내용 확인 (한국어 설명)
kill %1
```

- [ ] **Step 6: Commit**

```bash
git add harness/web/static/index.html
git commit -m "ux: add bilingual parameter tooltips for forcefield, water model, box type"
```

---

## PHASE 4 — 반응형 & 접근성

---

## Task 12: Viewport 메타태그 + 반응형 레이아웃

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: viewport 메타태그 추가**

`index.html` `<head>` 섹션의 `<meta charset="UTF-8">` 바로 다음에:

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

- [ ] **Step 2: 모바일 반응형 CSS 추가**

`index.html` CSS `</style>` 바로 앞에 삽입:

```css
/* Responsive — mobile */
@media (max-width: 768px) {
  body { flex-direction: column; }

  #sidebar {
    width: 100%;
    min-width: unset;
    height: auto;
    border-right: none;
    border-bottom: 1px solid var(--border);
    flex-direction: row;
    align-items: center;
  }

  #sidebar-header {
    border-bottom: none;
    border-right: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    flex-shrink: 0;
  }

  #sidebar-title { display: none; }

  #run-list {
    display: flex;
    flex-direction: row;
    overflow-x: auto;
    padding: 4px;
    gap: 4px;
    flex: 1;
  }

  .run-item {
    padding: 6px 10px;
    border-left: none;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .run-item.active { border-bottom-color: var(--accent-blue); border-left: none; }

  .run-item-date { display: none; }

  #run-view { padding: 12px; gap: 12px; }
  #new-run-view { padding: 16px; }

  #stats-row { grid-template-columns: 1fr 1fr; }

  .param-grid { grid-template-columns: 1fr; }

  #gallery-grid { grid-template-columns: 1fr 1fr; }

  #stepper { flex-wrap: wrap; gap: 8px; padding: 12px; }
  .step-connector { display: none; }

  #action-row { flex-wrap: wrap; }
  #btn-continue, #btn-abort { flex: 1; text-align: center; }
}

@media (max-width: 480px) {
  #stats-row { grid-template-columns: 1fr; }
  #gallery-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: 브라우저 반응형 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저 DevTools > Toggle Device Toolbar
# 375px (iPhone SE) 너비에서 레이아웃 확인:
#   - 사이드바가 상단 가로 방향으로 변환
#   - stat-cards 2열 그리드
#   - 파라미터 그리드 1열
# 768px에서 tablet 레이아웃 확인
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add harness/web/static/index.html
git commit -m "responsive: add viewport meta and mobile/tablet responsive layout"
```

---

## Task 13: ARIA 레이블 + Role 속성

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 사이드바 ARIA 속성 추가**

`index.html` HTML에서:

현재:
```html
<div id="sidebar">
  <div id="sidebar-header">
```

교체:
```html
<nav id="sidebar" aria-label="시뮬레이션 실행 목록">
  <div id="sidebar-header">
```

닫는 태그도:
```html
</nav>
```

현재:
```html
  <div id="run-list"></div>
```

교체:
```html
  <div id="run-list" role="list" aria-label="최근 실행 목록"></div>
```

- [ ] **Step 2: 메인 영역 ARIA + 버튼 속성**

현재:
```html
<div id="main">
```

교체:
```html
<main id="main">
```

닫는 태그:
```html
</main>
```

현재:
```html
      <button id="btn-continue" disabled onclick="doAction('continue')">Continue</button>
      <button id="btn-abort" disabled onclick="doAction('abort')">⏹ Abort</button>
```

교체:
```html
      <button id="btn-continue" disabled onclick="doAction('continue')" aria-label="다음 단계로 계속">Continue</button>
      <button id="btn-abort" disabled onclick="doAction('abort')" aria-label="실행 중단">⏹ Abort</button>
```

- [ ] **Step 3: 스테퍼 ARIA 추가**

현재:
```html
    <div id="stepper">
```

교체:
```html
    <div id="stepper" role="progressbar" aria-label="파이프라인 진행 상태">
```

- [ ] **Step 4: 터미널 패널 ARIA 추가**

현재:
```html
    <div id="terminal-panel">
      <div id="terminal-header">
        <span>Terminal</span>
        <span id="term-status">—</span>
```

교체:
```html
    <div id="terminal-panel" role="region" aria-label="실행 터미널">
      <div id="terminal-header" class="card-header">
        <span>Terminal</span>
        <span id="term-status" aria-live="polite">—</span>
```

- [ ] **Step 5: 통계 카드 ARIA 추가**

현재:
```html
    <div id="stats-row">
      <div class="stat-card"><div class="stat-label">Current Step</div><div class="stat-value" id="stat-step">—</div></div>
      <div class="stat-card"><div class="stat-label">Stage</div><div class="stat-value" id="stat-stage">—</div></div>
      <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" id="stat-status">—</div></div>
    </div>
```

교체:
```html
    <div id="stats-row" role="region" aria-label="실행 통계">
      <div class="stat-card" role="status"><div class="stat-label">Current Step</div><div class="stat-value" id="stat-step" aria-live="polite">—</div></div>
      <div class="stat-card" role="status"><div class="stat-label">Stage</div><div class="stat-value" id="stat-stage" aria-live="polite">—</div></div>
      <div class="stat-card" role="status"><div class="stat-label">Status</div><div class="stat-value" id="stat-status" aria-live="polite">—</div></div>
    </div>
```

- [ ] **Step 6: New Run 폼 ARIA**

현재:
```html
    <form id="new-run-form" onsubmit="submitNewRun(event)">
      <h2>New Simulation Run</h2>
```

교체:
```html
    <form id="new-run-form" onsubmit="submitNewRun(event)" aria-label="새 시뮬레이션 실행 설정">
      <h2>New Simulation Run</h2>
```

현재:
```html
      <input type="file" id="pdb-input" accept=".pdb" onchange="handleFileSelect(this.files[0])">
```

교체:
```html
      <input type="file" id="pdb-input" accept=".pdb" onchange="handleFileSelect(this.files[0])" aria-label="PDB 파일 선택">
```

- [ ] **Step 7: run-list 렌더러에 ARIA role 추가**

`index.html`의 `renderSidebar()` 함수에서 `el` 요소 생성 부분:

현재:
```javascript
    const el = document.createElement('div');
    el.className = 'run-item' + (run.run_id === currentRunId ? ' active' : '');
    el.onclick = () => selectRun(run.run_id);
```

교체:
```javascript
    const el = document.createElement('div');
    el.className = 'run-item' + (run.run_id === currentRunId ? ' active' : '');
    el.onclick = () => selectRun(run.run_id);
    el.setAttribute('role', 'listitem');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-label', `${run.protein.toUpperCase()} 실행, 상태: ${run.status}`);
    el.setAttribute('aria-current', run.run_id === currentRunId ? 'true' : 'false');
    el.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectRun(run.run_id); } };
```

- [ ] **Step 8: Commit**

```bash
git add harness/web/static/index.html
git commit -m "a11y: add ARIA labels, roles, live regions, and keyboard navigation"
```

---

## Task 14: 색상 외 상태 표시 — 아이콘 + 색상 병용

**Files:**
- Modify: `harness/web/static/index.html`

- [ ] **Step 1: 배지 아이콘 추가**

`index.html` CSS에서 badge 스타일을 확장:

현재 badge 스타일들:
```css
.badge-running { background: #388bfd22; color: #388bfd; }
.badge-paused   { background: #d2992222; color: #d29922; }
.badge-completed { background: #23863622; color: #3fb950; }
.badge-failed   { background: #da363322; color: #f85149; }
.badge-aborted  { background: #8b949e22; color: #8b949e; }
.badge-pending  { background: #8b949e22; color: #8b949e; }
```

교체:
```css
.run-item-badge { display: inline-flex; align-items: center; gap: 3px; padding: 1px 6px; border-radius: 10px; font-size: 9px; font-weight: 600; margin-top: 3px; }
.badge-running  { background: rgba(56,139,253,.13); color: var(--accent-blue); }
.badge-paused   { background: rgba(210,153,34,.13);  color: var(--accent-yellow); }
.badge-completed{ background: rgba(35,134,54,.13);   color: var(--accent-green); }
.badge-failed   { background: rgba(218,54,51,.13);   color: var(--accent-red); }
.badge-aborted  { background: rgba(139,148,158,.13); color: var(--text-muted); }
.badge-pending  { background: rgba(139,148,158,.13); color: var(--text-muted); }
```

- [ ] **Step 2: renderSidebar()에서 아이콘 포함 badge 렌더링**

`index.html`의 `renderSidebar()` 함수에서 badge 생성 부분:

현재:
```javascript
    const badge = document.createElement('span');
    const safeStatus = ['running','paused','completed','failed','aborted','pending'].includes(run.status)
      ? run.status : 'pending';
    badge.className = `run-item-badge badge-${safeStatus}`;
    badge.textContent = safeStatus;
```

교체:
```javascript
    const badge = document.createElement('span');
    const safeStatus = ['running','paused','completed','failed','aborted','pending'].includes(run.status)
      ? run.status : 'pending';
    const STATUS_ICONS = { running:'●', paused:'⏸', completed:'✓', failed:'✕', aborted:'◼', pending:'○' };
    badge.className = `run-item-badge badge-${safeStatus}`;
    badge.setAttribute('aria-label', `상태: ${safeStatus}`);
    badge.innerHTML = `<span aria-hidden="true">${STATUS_ICONS[safeStatus]}</span>${safeStatus}`;
```

- [ ] **Step 3: stat-status 값에도 아이콘 추가**

`index.html`의 `renderStats()` 함수에서:

현재:
```javascript
  document.getElementById('stat-status').textContent = run.status;
```

교체:
```javascript
  const STATUS_ICONS = { running:'●', paused:'⏸', completed:'✓', failed:'✕', aborted:'◼', pending:'○' };
  const STATUS_COLORS = { running:'var(--accent-blue)', paused:'var(--accent-yellow)', completed:'var(--accent-green)', failed:'var(--accent-red)', aborted:'var(--text-muted)', pending:'var(--text-muted)' };
  const statusEl = document.getElementById('stat-status');
  statusEl.innerHTML = `<span aria-hidden="true" style="color:${STATUS_COLORS[run.status]||'inherit'}">${STATUS_ICONS[run.status]||'○'}</span> ${run.status}`;
```

- [ ] **Step 4: 브라우저 최종 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs/harness
uvicorn web.server:app --port 8765 &
# 브라우저: http://localhost:8765
# 사이드바 배지: 아이콘 + 텍스트 병기 확인 (running=●, completed=✓ 등)
# stat-status 카드: 아이콘 + 색상 + 텍스트 확인
# 색맹 시뮬레이션: DevTools > Rendering > Emulate vision deficiency > Deuteranopia
# 아이콘만으로도 상태 구분 가능 확인
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add harness/web/static/index.html
git commit -m "a11y: add status icons alongside color badges for color-independent status display"
```

---

## 자체 검토 (Self-Review)

### Spec 커버리지

**PHASE 1:**
- [x] artifacts API 추가 → Task 1
- [x] 결과 갤러리 패널 구현 (Canvas sparkline) → Task 2
- [x] Permission 다이얼로그 서버 감지 → Task 3
- [x] Permission 다이얼로그 완전 연동 (JS, overlay, WS routing) → Task 4
- [x] 단계별 스테퍼 애니메이션 + 한영 라벨 → Task 5

**PHASE 2:**
- [x] CSS 커스텀 프로퍼티 + 타이포그래피 계층 → Task 6
- [x] 카드 컴포넌트 통일 (border-radius, shadow, spacing) → Task 7
- [x] 스켈레톤 로딩 + shimmer 애니메이션 → Task 8

**PHASE 3:**
- [x] Toast 에러 알림 (alert() 제거) → Task 9
- [x] 첫 접속 온보딩 모달 → Task 10
- [x] Forcefield/Water/BoxType 파라미터 툴팁 (한영 설명) → Task 11

**PHASE 4:**
- [x] viewport 메타태그 + 반응형 레이아웃 (모바일/태블릿) → Task 12
- [x] ARIA 레이블, role, live region, 키보드 탐색 → Task 13
- [x] 색상 외 상태 표시 (아이콘 + 색상 병용) → Task 14

### 타입 일관성

- `renderStepper(lastStage, status, currentStep)` — Task 5에서 정의, `refreshRunDetail()`에서 호출 (3인수 일치)
- `STATUS_ICONS` 객체 — Task 14에서 `renderSidebar()`와 `renderStats()` 두 곳에서 독립 정의 (인라인 상수로 충분)
- `showToast(msg, type)` — Task 9 정의, Task 9에서 호출 (시그니처 일치)
- `fetchAndRenderGallery(runId)` — Task 2 정의, `refreshRunDetail()`에서 호출 (일치)

### Placeholder 스캔

- 모든 단계에 실제 코드 포함 — TBD 없음
- 모든 CSS 선택자가 HTML ID/class와 일치
- 모든 JavaScript 함수 이름이 호출 위치와 일치
