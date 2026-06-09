# Gromacs Harness Web UI — Phase 1 MVP Design

**Date:** 2026-06-08  
**Scope:** 웹 대시보드 Phase 1. 새 run 생성, 실시간 파이프라인 모니터링, Continue/Abort 액션.

---

## 1. Goals

- 브라우저에서 PDB 파일을 업로드하고 시뮬레이션 run을 시작할 수 있다.
- 실행 중인 run의 3-skill 파이프라인 진행 상태와 로그를 실시간으로 볼 수 있다.
- Continue / Abort 액션을 브라우저에서 트리거할 수 있다.
- 과거 runs 목록을 사이드바에서 빠르게 전환할 수 있다.

빌드 툴, npm, 외부 CDN 의존성 없음. 순수 HTML/CSS/vanilla JS + Python FastAPI.

---

## 2. Layout

```
┌──────────────┬────────────────────────────────────────┐
│  사이드바     │  메인 패널                              │
│  200px 고정   │                                        │
│  [+ New Run]  │  상태에 따라:                          │
│  ─────────    │  (a) 실행 중 뷰                        │
│  run 목록     │  (b) New Run 폼                        │
│  최신순       │  (c) 완료 요약                          │
└──────────────┴────────────────────────────────────────┘
```

사이드바 "+ New Run" 클릭 → 메인 패널 전체가 New Run 폼으로 전환.  
run 목록 항목 클릭 → 해당 run의 실행 중 뷰 또는 완료 요약으로 전환.

---

## 3. 메인 패널 — 실행 중 뷰

```
[env-builder ✓] ──── [md-runner ●] ──── [illustrator ○]

┌──────────────────────────────────────────────────────┐
│  ✓ Step 5: ionization complete                       │
│  → Step 6: grompp -f minim.mdp -c solv_ions.gro ... │
│  Steepest Descents converging to Fmax < 1000         │
│  Step 47, Epot = -5.23e+05, Fmax = 823.4             │
│  █                                                   │
└──────────────────────────────────────────────────────┘

┌──────────────┬───────────────┬────────────────┐
│ CURRENT STEP │     PHASE     │    ELAPSED     │
│   Step 7/8   │     minim     │    2m 14s      │
└──────────────┴───────────────┴────────────────┘

[▶ Continue (md-runner)]        [⏹ Abort]
```

**Stepper:** `last_completed_stage` 값 기준으로 3개 노드 색상 결정.
- 완료: 초록 + 체크마크
- 진행 중: 파란 펄스
- 대기: 회색

**로그:** WebSocket(`/ws/runs/{run_id}`) 연결. 서버에서 로그 파일을 tail하며 line 단위 push. 최대 500줄 유지 (오래된 줄 자동 제거).

**통계 카드:** `GET /api/runs/{run_id}` 5초 폴링. `current_step`, `last_status`, `last_updated` 사용.

**액션 버튼:** `POST /api/runs/{run_id}/action` → `{"action": "continue"}` 또는 `{"action": "abort"}`.  
Continue는 `last_completed_stage`가 `env` 또는 `md`일 때만 활성.  
Abort는 subprocess SIGTERM.

---

## 4. New Run 폼 (메인 패널 전환)

```
New Simulation Run

┌─────────────────────────────────────────────────────┐
│           Drop PDB file  /  Click to browse         │
│                  (파일명 표시)                       │
└─────────────────────────────────────────────────────┘

┌──────────────────┬──────────────────┐
│   Forcefield     │   Water Model    │
│   CHARMM36-m ▾  │   TIP3P ▾        │
├──────────────────┼──────────────────┤
│   Tutorial       │   Box Type       │
│   Auto-detect ▾ │   dodecahedron ▾ │
└──────────────────┴──────────────────┘

[▶ Start Run]
```

**파라미터 기본값:**
- Forcefield: `charmm36-jul2022`
- Water: `tip3p`
- Tutorial: `auto` (TutorialRouter가 PDB로부터 선택)
- Box type: `dodecahedron`

**제출 흐름:**
1. `POST /api/runs` (multipart: PDB 파일 + JSON 파라미터)
2. 서버: `runs/{protein}_{timestamp}/` 디렉터리 생성, PDB 저장, `simulation_state.json` 초기화
3. 서버: `run_autonomy.py` subprocess 시작 (백그라운드)
4. 응답: `{"run_id": "aki_20260608_120000"}`
5. 브라우저: 사이드바에 새 항목 추가 → 해당 run의 실행 중 뷰로 자동 전환

---

## 5. 사이드바 — Runs 목록

- `GET /api/runs` 10초 폴링으로 목록 갱신
- 항목당 표시: 단백질명, 타임스탬프, 상태 뱃지 (running / completed / failed / aborted)
- 현재 선택된 run 하이라이트
- "+ New Run" 버튼: 메인 패널을 폼으로 전환

---

## 6. 백엔드 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/runs` | runs 목록 (run_id, status, protein, created_at) |
| GET | `/api/runs/{run_id}` | run 상세 (simulation_state.json 내용 + 파생 필드) |
| POST | `/api/runs` | 새 run 생성 (multipart) |
| POST | `/api/runs/{run_id}/action` | `{"action": "continue"\|"abort"}` |
| WS | `/ws/runs/{run_id}` | 로그 스트리밍 |
| GET | `/` | index.html 서빙 |

**상태 파생 규칙 (GET /api/runs/{run_id} 응답):**
- subprocess가 살아 있음 → `running`
- `last_completed_stage == "viz"` → `completed`
- subprocess exit code != 0 → `failed`
- Abort로 종료 → `aborted`

subprocess PID는 `runs/{run_id}/server.pid` 파일에 저장.

---

## 7. 파일 구조 (신규 생성)

```
harness/
  web/
    server.py          # FastAPI 앱 (API + WS + static 서빙)
    static/
      index.html       # 전체 UI (CSS + JS 인라인)
```

기존 파일 변경 없음. `run_autonomy.py`는 subprocess로만 호출.

---

## 8. 실행 방법

```bash
cd harness
pip install fastapi uvicorn python-multipart
uvicorn web.server:app --port 8000
# → http://localhost:8000
```

---

## 9. Out of Scope (Phase 1)

- 인증/로그인
- mdp 파일 직접 편집 UI
- 여러 run 동시 실행 (단일 subprocess 가정)
- 결과 시각화 (illustrator 출력 이미지 표시) — Phase 2
- run 삭제
