# Mockup → Real API 연동 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `web/static/index.html`의 모든 Mock 함수를 실제 FastAPI 백엔드 API 호출로 교체하고, `server.py`에 DELETE 엔드포인트를 추가한다.

**Architecture:** `server.py`에 `DELETE /api/runs/{run_id}` 엔드포인트를 추가하고, `index.html`에서 Mock JS를 제거한 후 `fetch()` + WebSocket으로 실제 API와 연동한다. 데모 배너, 온보딩 모달, 하드코딩된 런 목록은 완전히 제거한다.

**Tech Stack:** FastAPI (Python), Vanilla JS (fetch API, WebSocket), xterm.js (local static files), Canvas 2D API

---

## File Map

| 파일 | 변경 |
|------|------|
| `web/server.py` | `DELETE /api/runs/{run_id}` 엔드포인트 추가 |
| `web/static/index.html` | Mock 제거 → 실제 API 연동 JS로 교체 |
| `tests/test_server_delete.py` | DELETE 엔드포인트 단위 테스트 (신규) |

---

## Task 1: DELETE 엔드포인트 추가 (server.py)

**Files:**
- Modify: `web/server.py`
- Create: `tests/test_server_delete.py`

- [ ] **Step 1: tests 디렉토리 및 테스트 파일 생성**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_server_delete.py`:
```python
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_harness(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    return tmp_path


@pytest.fixture
def client(tmp_harness):
    from web.server import create_app
    app = create_app(harness_dir=tmp_harness)
    return TestClient(app)


def _make_run(runs_dir: Path, run_id: str) -> Path:
    ws = runs_dir / run_id
    ws.mkdir()
    (ws / "runner.log").write_text("hello")
    return ws


def test_delete_run_removes_workspace(client, tmp_harness):
    run_id = "protein_20260101_120000"
    ws = _make_run(tmp_harness / "runs", run_id)
    assert ws.exists()

    resp = client.delete(f"/api/runs/{run_id}")

    assert resp.status_code == 200
    assert not ws.exists()


def test_delete_run_returns_404_when_not_found(client, tmp_harness):
    resp = client.delete("/api/runs/protein_20260101_120000")
    assert resp.status_code == 404


def test_delete_run_rejects_invalid_run_id(client):
    resp = client.delete("/api/runs/../secret")
    assert resp.status_code == 400


def test_delete_run_kills_process_before_deleting(client, tmp_harness):
    """프로세스가 살아 있지 않아도 삭제가 성공해야 한다 (pid 파일 존재 시)."""
    run_id = "protein_20260101_120000"
    ws = _make_run(tmp_harness / "runs", run_id)
    (ws / "runner.pid").write_text("99999999")  # 존재하지 않는 PID

    resp = client.delete(f"/api/runs/{run_id}")

    assert resp.status_code == 200
    assert not ws.exists()
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs_WEB_UI
pip install -e ".[test]" -q
pytest tests/test_server_delete.py -v
```

Expected: `AttributeError` 또는 `404` — DELETE 엔드포인트가 없으므로 실패

- [ ] **Step 4: server.py에 DELETE 엔드포인트 구현**

`web/server.py` 상단 import에 추가:
```python
import shutil
```

`create_app` 함수 내 `api_action` 엔드포인트 아래에 추가:
```python
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
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_server_delete.py -v
```

Expected: 4개 테스트 모두 PASSED

- [ ] **Step 6: 커밋**

```bash
git add web/server.py tests/test_server_delete.py tests/__init__.py
git commit -m "feat: add DELETE /api/runs/{run_id} endpoint"
```

---

## Task 2: 목업 HTML 제거

**Files:**
- Modify: `web/static/index.html`

- [ ] **Step 1: `#demo-control-bar` div 제거**

`index.html`에서 아래 블록 전체 삭제:
```html
  <!-- Demo Control Bar -->
  <div id="demo-control-bar">
    <span>💡 DESIGN PREVIEW REDESIGN - INTERACTIVE DEMO MODE AVAILABLE</span>
    <button id="btn-demo-trigger" onclick="runClientDemo()">Play Simulation Demo</button>
  </div>
```

- [ ] **Step 2: `#onboard-overlay` div 제거**

아래 블록 전체 삭제:
```html
<!-- Onboarding Modal -->
<div id="onboard-overlay" class="show" role="dialog" aria-modal="true">
  ...
</div>
```
(`</div>` 닫는 태그까지 포함)

- [ ] **Step 3: 하드코딩된 런 목록 제거**

`#run-list` 내부의 Mock 항목 3개 삭제:
```html
      <div id="run-list" role="list" aria-label="최근 실행 목록">
        <!-- Mock Items -->
        <div class="run-item active" id="run-item-ubiquitin" ...> ... </div>
        <div class="run-item" id="run-item-lysozyme" ...> ... </div>
        <div class="run-item" id="run-item-crambin" ...> ... </div>
      </div>
```
→ `<div id="run-list" ...></div>` (빈 상태)로 남긴다

- [ ] **Step 4: 하드코딩된 차트 카드 3개 제거**

`#gallery-grid` 내부의 하드코딩된 차트 카드 삭제:
```html
        <div id="gallery-grid">
            <!-- Chart 1 -->
            <div class="chart-card"> ... </div>
            <!-- Chart 2 -->
            <div class="chart-card"> ... </div>
            <!-- Chart 3 -->
            <div class="chart-card"> ... </div>
        </div>
```
→ `<div id="gallery-grid"></div>` (빈 상태)로 남긴다

- [ ] **Step 5: xterm CDN CSS를 로컬 파일로 교체**

`<head>` 안의 CDN link:
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
```
→ 아래로 교체:
```html
<link rel="stylesheet" href="/static/xterm.css">
```

- [ ] **Step 6: `</body>` 직전에 xterm.js 스크립트 태그 추가**

기존 `<script>` 블록 바로 앞에 추가:
```html
<script src="/static/xterm.js"></script>
<script src="/static/xterm-addon-fit.js"></script>
```

- [ ] **Step 7: `#demo-control-bar` 관련 CSS 제거**

`<style>` 블록 안의 아래 CSS 블록 삭제:
```css
/* Demo Control Bar */
#demo-control-bar { ... }
#btn-demo-trigger { ... }
```

- [ ] **Step 8: `#onboard-overlay` 관련 CSS 제거**

`<style>` 블록 안의 아래 CSS 블록 삭제:
```css
/* Onboarding Modal redone */
#onboard-overlay { ... }
#onboard-box { ... }
#onboard-box h2 { ... }
...
#onboard-got-it { ... }
```

- [ ] **Step 9: 커밋**

```bash
git add web/static/index.html
git commit -m "chore: remove mockup demo bar, onboarding modal, hardcoded run items"
```

---

## Task 3: 상태 변수 및 초기화 함수 추가

**Files:**
- Modify: `web/static/index.html` (`<script>` 블록)

- [ ] **Step 1: 기존 Mock 전역 변수 전체 교체**

`<script>` 블록 최상단의 Mock 전역 변수들:
```js
const MOCK_LOGS = [ ... ];
let logIndex = 0;
let demoTimer = null;
let currentMockStep = 1;
```
→ 아래로 교체:
```js
let currentRunId = null;
let runsData = [];
let pollTimer = null;
let wsConn = null;
let term = null;
let fitAddon = null;
let selectedPdb = null;
```

- [ ] **Step 2: 기존 Mock 함수 전체 삭제**

아래 함수들을 `<script>` 블록에서 삭제:
- `function dismissOnboard()` (두 개 있음 — 모두 삭제)
- `function showNewRunForm()`
- `function mockFileSelect(file)`
- `function startMockRun()`
- `function selectMockRun(runId)`
- `function deleteMockRun(event, elementId, runName)`
- `function showToastNotification(message, type)`
- `function toggleStats()`
- `function runClientDemo()`
- `function updateStepper(activeStageNum)` (숫자 기반 버전)
- `function drawAllCharts()`
- `function drawGradientLineChart(...)`

단, `function toggleTheme()` 는 유지한다 (다크/라이트 테마 기능은 실제로 필요).

- [ ] **Step 3: `window.addEventListener('load')` 콜백에서 Mock 호출 제거**

`load` 콜백 안의:
```js
  drawAllCharts();
```
→ 삭제 (실제 차트는 나중에 artifacts API로 그린다)

맨 아래의:
```js
selectMockRun('run-item-ubiquitin');
```
→ 삭제

- [ ] **Step 4: `showNewRunForm` 실제 버전 추가**

`<script>` 블록에 추가:
```js
function showNewRunForm() {
  document.getElementById('run-view').style.display = 'none';
  document.getElementById('new-run-view').style.display = 'flex';
  document.getElementById('view-title').textContent = 'Configure New Simulation';
  document.getElementById('btn-continue').style.display = 'none';
  document.getElementById('btn-abort').style.display = 'none';
  document.querySelectorAll('.run-item').forEach(el => el.classList.remove('active'));
  currentRunId = null;
  stopWs();
}
```

- [ ] **Step 5: `showToast` 실제 버전 추가**

```js
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed; bottom:20px; right:20px; padding:10px 16px;
    border-radius:8px; font-size:12px; font-weight:500; color:#fff;
    z-index:500; box-shadow:0 8px 24px rgba(0,0,0,0.5);
    transition:all 0.3s ease; opacity:0; transform:translateY(10px);
  `;
  toast.style.background = type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#333';
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}
```

- [ ] **Step 6: `stopWs` 함수 추가**

```js
function stopWs() {
  if (wsConn) { wsConn.close(); wsConn = null; }
  if (term) { term.dispose(); term = null; fitAddon = null; }
}
```

- [ ] **Step 7: `toggleTheme` 함수의 `drawAllCharts()` 호출 제거**

기존 `toggleTheme` 함수:
```js
function toggleTheme() {
  ...
  // Re-draw charts to fit current theme background grid lines
  drawAllCharts();
}
```
→ `drawAllCharts()` 한 줄 삭제 (`drawAllCharts` 함수가 더 이상 없으므로)

- [ ] **Step 8: 커밋**

```bash
git add web/static/index.html
git commit -m "refactor: replace mock globals with real state variables"
```

---

## Task 4: 런 목록 로드 및 사이드바 렌더링

**Files:**
- Modify: `web/static/index.html` (`<script>` 블록)

- [ ] **Step 1: `renderRunList` 함수 추가**

```js
function renderRunList(runs) {
  const list = document.getElementById('run-list');
  list.innerHTML = '';
  runs.forEach(run => {
    const el = document.createElement('div');
    el.className = 'run-item' + (run.run_id === currentRunId ? ' active' : '');
    el.id = 'run-item-' + run.run_id;
    el.onclick = () => selectRun(run.run_id);

    const dateStr = run.created_at
      ? run.created_at.replace('T', ' ').substring(0, 19)
      : '';
    const badgeClass = {
      running: 'badge-running', paused: 'badge-paused',
      completed: 'badge-completed', failed: 'badge-failed',
      aborted: 'badge-aborted',
    }[run.status] || 'badge-aborted';
    const badgeText = {
      running: '● running', paused: '⏸ paused',
      completed: '✓ completed', failed: '✕ failed',
      aborted: '○ aborted',
    }[run.status] || run.status;

    el.innerHTML = `
      <div class="run-item-header">
        <span class="run-item-name">${run.protein.toUpperCase()}</span>
        <button class="delete-btn" title="삭제">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
      <div class="run-item-date">${dateStr}</div>
      <div class="run-item-footer">
        <span class="run-item-badge ${badgeClass}">${badgeText}</span>
      </div>
    `;
    el.querySelector('.delete-btn').onclick = (e) => {
      e.stopPropagation();
      deleteRun(run.run_id, run.protein.toUpperCase());
    };
    list.appendChild(el);
  });
}
```

- [ ] **Step 2: `loadRuns` 함수 추가**

```js
async function loadRuns() {
  try {
    const resp = await fetch('/api/runs');
    if (!resp.ok) return;
    runsData = await resp.json();
    renderRunList(runsData);

    // 폴링 속도 조정: 현재 런이 running 상태면 2초, 아니면 5초
    const activeRun = runsData.find(r => r.run_id === currentRunId);
    const interval = activeRun && activeRun.status === 'running' ? 2000 : 5000;
    clearInterval(pollTimer);
    pollTimer = setInterval(loadRuns, interval);
  } catch (e) {
    console.error('loadRuns failed:', e);
  }
}
```

- [ ] **Step 3: `loadLlms` 함수 추가**

```js
async function loadLlms() {
  try {
    const resp = await fetch('/api/llms');
    if (!resp.ok) return;
    const llms = await resp.json();
    const select = document.getElementById('llm-select');
    select.innerHTML = '<option value="">None (direct pipeline)</option>';
    llms.forEach(llm => {
      const opt = document.createElement('option');
      opt.value = llm.key;
      opt.textContent = llm.name;
      select.appendChild(opt);
    });
  } catch (e) {
    console.error('loadLlms failed:', e);
  }
}
```

- [ ] **Step 4: `window.addEventListener('load')` 초기화 코드 교체**

기존 `load` 콜백 맨 위에 (`drawAllCharts()` 있던 자리에) 추가:
```js
  // 앱 초기화
  loadLlms();
  await loadRuns();
  if (runsData.length > 0) {
    selectRun(runsData[0].run_id);
  } else {
    showNewRunForm();
  }
```

`load` 콜백을 `async function` 으로 변경:
```js
window.addEventListener('load', async () => {
  // ... 위 초기화 코드 ...
  // 기존 Resizable Sidebar 코드 유지
  // 기존 toggleSidebar 코드 유지
  // 기존 alignToggleBtn 코드 유지
});
```

- [ ] **Step 5: 서버 실행 후 사이드바에 실제 런 목록이 나타나는지 확인**

```bash
cd /Users/ydj_mac/Library/CloudStorage/OneDrive-개인/Gromacs_WEB_UI
python main.py --no-browser
```

브라우저에서 `http://127.0.0.1:8000` 열기 → `runs/` 디렉토리가 비어 있으면 New Run 폼이 표시되어야 함

- [ ] **Step 6: 커밋**

```bash
git add web/static/index.html
git commit -m "feat: load run list and LLMs from API on page load"
```

---

## Task 5: 런 선택 및 WebSocket 터미널

**Files:**
- Modify: `web/static/index.html` (`<script>` 블록)

- [ ] **Step 1: `updateStepper` 함수 추가 (stage 기반)**

```js
function updateStepper(info) {
  // 스테퍼 8단계 → 백엔드 3 stage 매핑
  // env: steps 1-5, md: steps 6-7, viz: step 8
  const stage = info.last_completed_stage;
  const status = info.status;

  let activeStep;
  if (!stage) {
    activeStep = (status === 'completed') ? 9 : 1;
  } else if (stage === 'env') {
    activeStep = (status === 'paused' || status === 'running') ? 6 : 6;
  } else if (stage === 'md') {
    activeStep = (status === 'paused' || status === 'running') ? 8 : 8;
  } else if (stage === 'viz') {
    activeStep = 9; // 전체 완료
  } else {
    activeStep = 1;
  }

  const steps = document.querySelectorAll('#stepper .step-node');
  const connectors = document.querySelectorAll('#stepper .step-connector');

  steps.forEach((step, idx) => {
    const circle = step.querySelector('.step-circle');
    step.className = 'step-node';
    if (idx + 1 < activeStep) {
      step.classList.add('done');
      circle.textContent = '✓';
    } else if (idx + 1 === activeStep) {
      step.classList.add('active');
      circle.textContent = String(idx + 1);
    } else {
      step.classList.add('pending');
      circle.textContent = String(idx + 1);
    }
  });

  connectors.forEach((conn, idx) => {
    conn.className = 'step-connector';
    if (idx + 1 < activeStep) conn.classList.add('done');
    else if (idx + 1 === activeStep) conn.classList.add('active');
  });
}
```

- [ ] **Step 2: `updateButtons` 함수 추가**

```js
function updateButtons(status) {
  const btnContinue = document.getElementById('btn-continue');
  const btnAbort = document.getElementById('btn-abort');
  btnContinue.style.display = 'inline-flex';
  btnAbort.style.display = 'inline-flex';
  btnContinue.disabled = status !== 'paused';
  btnAbort.disabled = status !== 'running' && status !== 'paused';

  const termStatus = document.getElementById('term-status');
  if (termStatus) {
    const cls = { running: 'badge-running', paused: 'badge-paused',
                  completed: 'badge-completed', failed: 'badge-failed',
                  aborted: 'badge-aborted' }[status] || 'badge-aborted';
    termStatus.className = 'run-item-badge ' + cls;
    termStatus.textContent = status;
  }
}
```

- [ ] **Step 3: xterm.js 터미널 초기화 함수 추가**

```js
function initTerminal() {
  const container = document.getElementById('terminal-container');
  // fallback pre 요소 숨기기
  const fallback = document.getElementById('fallback-terminal-text');
  if (fallback) fallback.style.display = 'none';

  if (term) { term.dispose(); term = null; fitAddon = null; }

  if (typeof Terminal === 'undefined') {
    // xterm.js 미로드 시 fallback
    if (fallback) { fallback.style.display = 'block'; fallback.textContent = ''; }
    return;
  }

  term = new Terminal({
    theme: { background: '#04060f', foreground: '#a7f3d0', cursor: '#06b6d4' },
    cursorBlink: true,
    fontSize: 11,
    fontFamily: '"Fira Code", "SF Mono", "Menlo", monospace',
    scrollback: 5000,
    convertEol: false,
  });
  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  container.innerHTML = '';
  term.open(container);
  fitAddon.fit();
}
```

- [ ] **Step 4: `connectWs` 함수 추가**

```js
function connectWs(runId) {
  stopWs();
  initTerminal();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  wsConn = new WebSocket(`${proto}://${location.host}/ws/runs/${runId}`);
  wsConn.binaryType = 'arraybuffer';

  wsConn.onopen = () => {
    if (term && fitAddon) {
      fitAddon.fit();
      wsConn.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    }
  };

  wsConn.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) {
      if (term) {
        term.write(new Uint8Array(e.data));
      } else {
        const fallback = document.getElementById('fallback-terminal-text');
        if (fallback) fallback.textContent += new TextDecoder().decode(e.data);
      }
    } else {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'exit') {
          wsConn.close();
          wsConn = null;
          // 종료 후 런 상태 재조회
          setTimeout(() => selectRun(runId, false), 500);
        }
      } catch {}
    }
  };

  wsConn.onerror = () => {
    const termStatus = document.getElementById('term-status');
    if (termStatus) termStatus.textContent = 'ws error';
  };
  wsConn.onclose = () => { wsConn = null; };

  if (term) {
    term.onData((data) => {
      if (wsConn && wsConn.readyState === WebSocket.OPEN) {
        wsConn.send(new TextEncoder().encode(data));
      }
    });
  }
}
```

- [ ] **Step 5: `selectRun` 함수 추가**

`connectWs` 함수 뒤에 추가:
```js
async function selectRun(runId, reconnectWs = true) {
  currentRunId = runId;

  // 사이드바 active 상태 갱신
  document.querySelectorAll('.run-item').forEach(el => {
    el.classList.toggle('active', el.id === 'run-item-' + runId);
  });

  document.getElementById('new-run-view').style.display = 'none';
  document.getElementById('run-view').style.display = 'flex';

  try {
    const resp = await fetch(`/api/runs/${runId}`);
    if (!resp.ok) { showToast('런 정보를 가져오지 못했습니다.', 'error'); return; }
    const info = await resp.json();

    document.getElementById('view-title').textContent =
      'Simulation: ' + info.protein.toUpperCase();
    updateStepper(info);
    updateButtons(info.status);

    if (reconnectWs) connectWs(runId);

    if (info.status === 'completed') {
      loadArtifacts(runId);
    } else {
      document.getElementById('gallery-panel').style.display = 'none';
    }
  } catch (e) {
    showToast('서버 연결 오류', 'error');
  }
}
```

- [ ] **Step 6: `window.resize` 이벤트에 터미널 리사이즈 추가**

`load` 콜백 안의 `window.addEventListener('resize', alignToggleBtn)` 줄 아래에 추가:
```js
  window.addEventListener('resize', () => {
    if (fitAddon && term) {
      try {
        fitAddon.fit();
        if (wsConn && wsConn.readyState === WebSocket.OPEN) {
          wsConn.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      } catch {}
    }
  });
```

- [ ] **Step 7: 서버 실행 후 WebSocket 터미널 동작 확인**

```bash
python main.py --no-browser
```

`tutorial_data/` 에 PDB 파일이 있으면 New Run 폼에서 업로드 → 터미널에 로그가 실시간으로 나타나는지 확인.

- [ ] **Step 8: 커밋**

```bash
git add web/static/index.html
git commit -m "feat: implement selectRun with xterm.js WebSocket terminal"
```

---

## Task 6: 새 런 생성 (파일 업로드)

**Files:**
- Modify: `web/static/index.html` (HTML + `<script>`)

- [ ] **Step 1: 폼의 `onsubmit` 교체**

```html
<form id="new-run-form" onsubmit="event.preventDefault(); startRun();" ...>
```

- [ ] **Step 2: 파일 input의 `onchange` 교체**

```html
<input type="file" id="pdb-input" accept=".pdb" onchange="handleFileSelect(this.files[0])">
```

- [ ] **Step 3: drop-zone drag 이벤트 핸들러 추가**

```html
<div id="drop-zone"
  onclick="document.getElementById('pdb-input').click()"
  ondragover="event.preventDefault(); this.style.borderColor='var(--accent-primary)'"
  ondragleave="this.style.borderColor=''"
  ondrop="event.preventDefault(); this.style.borderColor=''; handleFileSelect(event.dataTransfer.files[0])">
```

- [ ] **Step 4: `handleFileSelect` 함수 추가**

```js
function handleFileSelect(file) {
  if (!file) return;
  selectedPdb = file;
  document.getElementById('selected-file').textContent = `✓ ${file.name}`;
  document.getElementById('btn-start').disabled = false;
}
```

- [ ] **Step 5: `startRun` 함수 추가**

```js
async function startRun() {
  if (!selectedPdb) return;

  const form = document.getElementById('new-run-form');
  const data = new FormData();
  data.append('pdb_file', selectedPdb);
  data.append('forcefield', form.querySelector('[name="forcefield"]').value);
  data.append('water', form.querySelector('[name="water"]').value);
  data.append('box_type', form.querySelector('[name="box_type"]').value);
  data.append('llm', form.querySelector('[name="llm"]').value);
  data.append('auto_approve', form.querySelector('[name="auto_approve"]').value);

  const btnStart = document.getElementById('btn-start');
  btnStart.disabled = true;
  btnStart.textContent = 'Starting...';

  try {
    const resp = await fetch('/api/runs', { method: 'POST', body: data });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || '런 시작에 실패했습니다.', 'error');
      btnStart.disabled = false;
      btnStart.textContent = 'Start Simulation Run';
      return;
    }
    const { run_id } = await resp.json();
    selectedPdb = null;
    document.getElementById('selected-file').textContent = '';
    btnStart.textContent = 'Start Simulation Run';
    await loadRuns();
    selectRun(run_id);
  } catch (e) {
    showToast('서버 연결 오류', 'error');
    btnStart.disabled = false;
    btnStart.textContent = 'Start Simulation Run';
  }
}
```

- [ ] **Step 6: 서버 실행 후 파일 업로드 → 런 시작 확인**

```bash
python main.py --no-browser
```

New Run 폼에서 `tutorial_data/` 안의 PDB 파일 업로드 → Start 클릭 → 사이드바에 새 런이 나타나고 터미널에 로그가 스트리밍되면 OK

- [ ] **Step 7: 커밋**

```bash
git add web/static/index.html
git commit -m "feat: implement file upload and startRun API call"
```

---

## Task 7: Continue / Abort 버튼 연동

**Files:**
- Modify: `web/static/index.html` (HTML + `<script>`)

- [ ] **Step 1: Continue 버튼 `onclick` 교체**

```html
<button id="btn-continue" class="btn" disabled
  onclick="doAction('continue')"
  style="display: inline-flex !important; align-items: center !important; flex-shrink: 0 !important;">
```

- [ ] **Step 2: Abort 버튼 `onclick` 교체**

```html
<button id="btn-abort" class="btn"
  onclick="doAction('abort')"
  style="display: inline-flex !important; align-items: center !important; flex-shrink: 0 !important;">
```

- [ ] **Step 3: `doAction` 함수 추가**

```js
async function doAction(action) {
  if (!currentRunId) return;
  try {
    const resp = await fetch(`/api/runs/${currentRunId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || `${action} 실패`, 'error');
      return;
    }
    // 즉시 상태 재조회
    await selectRun(currentRunId, action === 'continue');
  } catch (e) {
    showToast('서버 연결 오류', 'error');
  }
}
```

- [ ] **Step 4: 동작 확인**

`paused` 상태인 런이 있으면 Continue 버튼 클릭 → 터미널에 다음 스테이지 로그가 이어서 나타나야 함.  
없으면 `runs/` 디렉토리에 수동으로 `runner.exit=0`과 `state.json`(`last_completed_stage: "env"`)을 만들어 `paused` 상태를 재현 가능.

- [ ] **Step 5: 커밋**

```bash
git add web/static/index.html
git commit -m "feat: wire Continue/Abort buttons to POST /api/runs/{id}/action"
```

---

## Task 8: 차트 렌더링 및 런 삭제

**Files:**
- Modify: `web/static/index.html` (`<script>` 블록)

- [ ] **Step 1: `drawSparkline` 함수 추가 (artifact 컬럼 기반)**

```js
function drawSparkline(canvas, yData, color) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (!yData || yData.length < 2) {
    ctx.fillStyle = 'var(--text-muted)';
    ctx.font = '9px monospace';
    ctx.fillText('No data', 8, h / 2);
    return;
  }

  const minY = Math.min(...yData), maxY = Math.max(...yData);
  const rangeY = maxY - minY || 1;
  const pad = { t: 6, r: 6, b: 6, l: 6 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

  const toX = i => pad.l + (i / (yData.length - 1)) * pw;
  const toY = v => pad.t + ph - ((v - minY) / rangeY) * ph;

  // 그라디언트 채움
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + '30');
  grad.addColorStop(1, color + '00');
  ctx.beginPath();
  ctx.moveTo(toX(0), h - pad.b);
  yData.forEach((v, i) => ctx.lineTo(toX(i), toY(v)));
  ctx.lineTo(toX(yData.length - 1), h - pad.b);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // 선
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(yData[0]));
  for (let i = 1; i < yData.length; i++) {
    const xc = (toX(i) + toX(i - 1)) / 2;
    const yc = (toY(yData[i]) + toY(yData[i - 1])) / 2;
    ctx.quadraticCurveTo(toX(i - 1), toY(yData[i - 1]), xc, yc);
  }
  ctx.lineTo(toX(yData.length - 1), toY(yData[yData.length - 1]));
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.shadowColor = color;
  ctx.shadowBlur = 6;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // 마지막 점 dot
  const lx = toX(yData.length - 1), ly = toY(yData[yData.length - 1]);
  ctx.beginPath();
  ctx.arc(lx, ly, 3, 0, Math.PI * 2);
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.fill();
  ctx.stroke();
}
```

- [ ] **Step 2: `loadArtifacts` 함수 추가**

```js
const CHART_COLORS = ['#06b6d4', '#6366f1', '#10b981', '#f59e0b', '#ef4444'];

async function loadArtifacts(runId) {
  const panel = document.getElementById('gallery-panel');
  try {
    const resp = await fetch(`/api/runs/${runId}/artifacts`);
    if (!resp.ok) { panel.style.display = 'none'; return; }
    const artifacts = await resp.json();
    if (artifacts.length === 0) { panel.style.display = 'none'; return; }

    panel.style.display = '';
    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = '';

    artifacts.forEach((a, idx) => {
      const cols = a.columns || [];
      const yData = cols[1] || [];
      const color = CHART_COLORS[idx % CHART_COLORS.length];

      const mn = yData.length ? Math.min(...yData).toFixed(3) : '—';
      const mx = yData.length ? Math.max(...yData).toFixed(3) : '—';
      const last = yData.length ? yData[yData.length - 1].toFixed(3) : '—';

      const card = document.createElement('div');
      card.className = 'chart-card';
      card.innerHTML = `
        <div class="chart-card-title">${a.title || a.name}</div>
        <canvas class="chart-canvas" width="280" height="90"></canvas>
        <div class="chart-stats">min <span>${mn}</span> max <span>${mx}</span> last <span>${last}</span></div>
      `;
      grid.appendChild(card);

      requestAnimationFrame(() => {
        drawSparkline(card.querySelector('canvas'), yData, color);
      });
    });
  } catch (e) {
    console.error('loadArtifacts:', e);
    panel.style.display = 'none';
  }
}
```

- [ ] **Step 3: `deleteRun` 함수 추가**

```js
async function deleteRun(runId, displayName) {
  if (!confirm(`[ ${displayName} ] 실행 내역을 삭제하시겠습니까?`)) return;
  try {
    const resp = await fetch(`/api/runs/${runId}`, { method: 'DELETE' });
    if (!resp.ok) {
      showToast('삭제에 실패했습니다.', 'error');
      return;
    }
    if (currentRunId === runId) {
      currentRunId = null;
      stopWs();
    }
    await loadRuns();
    if (runsData.length > 0) {
      selectRun(runsData[0].run_id);
    } else {
      showNewRunForm();
    }
    showToast(`${displayName} 삭제 완료`, 'success');
  } catch (e) {
    showToast('서버 연결 오류', 'error');
  }
}
```

- [ ] **Step 4: 서버 실행 후 전체 흐름 최종 확인**

```bash
python main.py --no-browser
```

체크리스트:
- [ ] 런 목록이 API에서 로드됨
- [ ] 런 없으면 New Run 폼 자동 표시
- [ ] PDB 파일 업로드 → 런 시작 → 터미널 로그 스트리밍
- [ ] `completed` 상태 런 선택 시 차트 패널 표시
- [ ] 휴지통 버튼 → 삭제 확인 → 사이드바에서 제거
- [ ] Continue / Abort 버튼 올바른 활성화
- [ ] 다크/라이트 테마 전환이 오류 없이 동작

- [ ] **Step 5: 최종 커밋**

```bash
git add web/static/index.html
git commit -m "feat: implement loadArtifacts charts and deleteRun from API"
```
