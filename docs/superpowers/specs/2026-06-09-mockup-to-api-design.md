# Mockup → Real API 연동 전환 설계

**Date:** 2026-06-09  
**Scope:** `web/static/index.html` (프론트엔드), `web/server.py` (백엔드)  
**Approach:** 인플레이스 교체 — UI 디자인 유지, Mock JS를 실제 API 호출로 전환

---

## 1. 제거 항목

### `index.html`에서 제거
- `#demo-control-bar` div (배너 + "Play Simulation Demo" 버튼)
- `#onboard-overlay` div (온보딩 팝업 모달)
- 하드코딩된 런 목록 HTML (UBIQUITIN, LYSOZYME, CRAMBIN)
- Mock 함수들: `startMockRun`, `selectMockRun`, `deleteMockRun`, `mockFileSelect`, `runClientDemo`, `MOCK_LOGS` 배열

### `server.py`에 추가
```
DELETE /api/runs/{run_id}
```
- `runner.pid` 파일이 있으면 프로세스에 SIGTERM 먼저 전송
- workspace 디렉토리 전체를 `shutil.rmtree`로 삭제
- path traversal 방지: 기존 `_check_run_id` 헬퍼 재사용

---

## 2. 페이지 초기화

`window.addEventListener('load')` 시:

1. `GET /api/llms` → LLM 드롭다운 옵션 동적 생성
2. `loadRuns()` 호출 → 사이드바 런 목록 렌더링
3. 런이 1개 이상이면 첫 번째 런 자동 선택(`selectRun`), 없으면 New Run 폼 표시
4. 5초 폴링 시작 (`setInterval(loadRuns, 5000)`)
   - 현재 선택된 런이 `running` 상태이면 폴링을 2초로 가속
   - `completed` / `failed` / `paused` 시 5초로 복귀

---

## 3. 런 목록 (`loadRuns`)

- `GET /api/runs` 호출 → `RunSummary[]` 수신
- 현재 사이드바 항목과 비교: 추가/제거/상태변경만 DOM 업데이트 (전체 재렌더 방지)
- 각 항목 클릭 시 `selectRun(run_id)` 호출
- 휴지통 버튼 클릭 시 `deleteRun(run_id)` 호출

---

## 4. 런 선택 (`selectRun`)

1. `GET /api/runs/{run_id}` 호출 → 상세 정보 수신
2. `updateStepper(info)` 호출:
   - `last_completed_stage: null` → 1단계(Topology) active
   - `"env"` → env done, md active
   - `"md"` → md done, viz active
   - `"viz"` → 전체 완료(8단계 done)
3. 버튼 상태 갱신:
   - `running` → Continue 비활성, Abort 활성
   - `paused` → Continue 활성, Abort 활성
   - `completed` / `failed` / `aborted` → 둘 다 비활성
4. 기존 WebSocket 닫기 → `new WebSocket('/ws/runs/{run_id}')` 연결
5. xterm.js 터미널에 바이너리/텍스트 메시지 스트리밍
6. `{ type: "exit" }` 메시지 수신 시 WebSocket 닫기, 상태 재조회
7. `status === 'completed'`이면 `loadArtifacts(run_id)` 호출

---

## 5. 새 런 생성

폼 submit 시 (`startRun()`):

1. `<input type="file">` 파일 선택 → `btn-start` 활성화
2. `FormData` 구성:
   - `pdb_file`: 선택된 파일
   - `forcefield`, `water`, `box_type`: select 값
   - `llm`, `auto_approve`: LLM 섹션 값
3. `POST /api/runs` (multipart) 전송 → `{ run_id }` 수신
4. `selectRun(run_id)` 호출 → 런 뷰로 전환

---

## 6. Continue / Abort

- `POST /api/runs/{run_id}/action` `{ "action": "continue" }` 또는 `{ "action": "abort" }`
- 응답 후 즉시 `GET /api/runs/{run_id}` 재조회 → 버튼 상태 갱신

---

## 7. 차트 (`loadArtifacts`)

- `GET /api/runs/{run_id}/artifacts` 호출
- 응답: `[{ name, xs, ys, ... }]`
- `name`으로 canvas ID 매핑 (`rmsd` → `canvas-rmsd` 등)
- 매핑되지 않는 이름은 동적으로 chart-card 생성
- artifact가 없으면 `#gallery-panel` 숨김
- `status === 'completed'` 전환 시 자동 호출

---

## 8. 런 삭제 (`deleteRun`)

1. `confirm()` 다이얼로그
2. `DELETE /api/runs/{run_id}` 호출
3. 성공 시 사이드바에서 해당 항목 제거
4. 삭제된 런이 현재 선택된 런이면: 남은 런 중 첫 번째 자동 선택, 없으면 New Run 폼 표시
5. 실패 시 에러 토스트 표시

---

## 9. 에러 처리

- API 호출 실패(네트워크 에러, 4xx/5xx) 시 토스트 알림 표시
- WebSocket 연결 실패 시 `#fallback-terminal-text`에 에러 메시지 표시
- 폴링 중 에러는 조용히 무시 (다음 폴링에서 재시도)

---

## 변경 파일 목록

| 파일 | 변경 유형 |
|------|---------|
| `web/static/index.html` | 수정 (Mock JS 제거, 실제 API 연동 추가) |
| `web/server.py` | 수정 (`DELETE /api/runs/{run_id}` 엔드포인트 추가) |
