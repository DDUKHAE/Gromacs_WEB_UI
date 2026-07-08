# 티어 C 구현 계획서 — v2/저널 승격 시

> **목표:** 프리프린트 v1 게시 **이후**, bioRxiv 개정(v2/v3)과 저널(SoftwareX→JCIM) 승격을 위한 심화 작업.
> **원칙:** v1으로 우선권을 확보한 뒤, 여기서 "완성도"와 "동료심사 방어력"을 쌓는다.
> **선행 참조:** `docs/journal_readiness_evaluation.md` §5.3 / 선행 조건: **티어 A + B 완료**
> **기준 커밋:** `b3b30d2`

## 에이전트 실행 규칙

1. C1~C6는 대체로 독립. C1은 B1(축소 벤치마크)을 8개 전 시스템 + 불확실도로 확장하는 연속선.
2. C3(코어 테스트)는 다른 리팩터링(C5)보다 **먼저** 하는 것을 권장 — 안전망 확보 후 구조 변경.
3. C2(스텁 분석)는 C1의 막/복합체 벤치마크가 의미 있으려면 선행 필요.
4. 대규모 리팩터링(C5)은 기능 회귀 위험 → C3 테스트 그린 상태에서만.

---

## C1 — 전체 벤치마크 확장 + 불확실도 정량

**목표:** B1의 3~4개를 8개 전 튜토리얼로 확장하고, **모든 관측량에 통계적 오차**를 부여.

**근거:** JCIM 리뷰어는 오차막대 없는 관측량을 리젝. 현재 모든 값이 원시 평균/표준편차(`lib/xvg_parser.py:62-73`), 블록평균·자기상관·신뢰구간 없음. FE는 5창 락스텝, BAR ΔG 파싱이 취약(`illustrator.py:210-218`). — 평가 기능 §2.2, §2.3

**대상 파일:** `lib/xvg_parser.py`, `skills/illustrator/illustrator.py`, `scripts/collect_metrics.py`, `scripts/reference_values.json`(B1), `lib/mdp_templates/base.py`.

**단계:**
1. `xvg_parser`/`illustrator`에 **블록평균 + 자기상관시간 기반 표준오차** 추가, 모든 요약·플롯에 오차막대.
2. FE 변형: BAR **통계오차**, umbrella: WHAM **부트스트랩** 신뢰구간.
3. 벤치마크를 8개 전 시스템으로 확장, 각 관측량을 오차와 함께 참조 대비.
4. BAR ΔG 파싱을 견고한 파서로 교체(문자열 스크랩 제거).

**완료 조건:** 모든 벤치 관측량이 ±오차 동반, 8개 시스템 Table 1, BAR/WHAM 오차 산출. 신규 테스트로 블록평균 정확성 검증.

**규모:** 大

---

## C2 — 막·복합체 분석 스텁 구현

**목표:** 스텁으로 남은 2개 도메인 분석을 실제 구현.

**근거:** `_run_membrane_analysis`·`_run_protein_ligand_analysis`가 `{"status":"stub"}`(`skills/illustrator/illustrator.py:221-228`) → KALP15/Protein-Ligand는 도메인 산출 0. — 평가 기능 §2.2

**대상 파일:** `skills/illustrator/illustrator.py`, `lib/xvg_parser.py`, (참조) `lib/membrane_builder.py`, `lib/ligand_params.py`.

**단계:**
1. 막: 면적/지질(area-per-lipid), 이중층 두께, 중수소 질서변수(order parameter).
2. 복합체: 리간드 RMSD, 단백질-리간드 접촉/H-bond 맵, (가능하면) MM-PBSA(gmx_MMPBSA 연동).
3. 각 분석에 플롯 + 요약 + 오차(C1 연계).

**완료 조건:** 두 변형이 실제 수치·플롯 산출(스텁 문자열 부재), 신규 테스트 통과.

**규모:** 大

---

## C3 — 핵심 코어 테스트 + CI 강화

**목표:** 논문 핵심 기여인 PTY/LLM 러너·run 생성 API·WebSocket에 테스트를 붙이고 CI를 매트릭스화.

**근거:** run 생성(`api_create_run`), `/api/runs/{id}/action`, WebSocket, `llm_runner`/PTY에 테스트 0 — novel/위험 코어가 무검증. CI는 단일(Python 3.11 × ubuntu). — 평가 구조 §3.5-2,5

**대상 파일:** (신규) `tests/test_api_runs.py`, `tests/test_llm_runner.py`, `tests/test_websocket.py`, `.github/workflows/ci.yml`, `pyproject.toml`(lint/type 설정).

**단계:**
1. `TestClient`로 `api_create_run`(직접-러너 경로, subprocess 목), continue/abort 액션 테스트.
2. 가짜 CLI(`cat`/`echo`) PTY 테스트로 `run_llm_agent` — EOF·권한탐지(`_PERM_RE`)·재접속 리플레이 커버.
3. WebSocket 프록시/로그-테일 모드 테스트.
4. CI를 Python(3.11/3.12/3.13) × OS 매트릭스로 확장, `ruff`(lint)+`mypy`(type)+커버리지 임계 게이트 추가.
5. fire-and-forget `asyncio.create_task`(`server.py:482`)에 태스크 레지스트리·예외 로깅 추가.

**완료 조건:** 신규 테스트가 4개 코어 경로 커버, CI 매트릭스 그린, lint/type 게이트 통과, 커버리지 리포트에 llm_runner 포함.

**규모:** 中~大

---

## C4 — GUI 승인 다이얼로그

**목표:** 터미널 Y/N 타이핑 대신 Approve/Deny 버튼 GUI로 LLM 툴콜 승인.

**근거:** 승인이 xterm 터미널 안에서 처리(`term.onData→ws.send`) — 셸 모르는 구조생물학자엔 장벽. GUI 승인창 부재. — 평가 UI §4.3, §4.6-2

**대상 파일:** `web/llm_runner.py`(구조화 메시지 방출), `web/server.py`(WS 핸들러), `web/static/index.html`(WS `onmessage` JSON 분기 `:4371-4381`, 모달 UI).

**단계:**
1. 백엔드가 대기 툴콜별 **구조화 WS 메시지**(툴명·명령·대상파일) 방출(`_PERM_RE` 탐지 확장).
2. 프론트가 모달/인라인 카드로 "Approve/Deny/Approve all" 렌더, 결정을 WS로 회신.
3. 원시 터미널은 "고급 뷰"로 유지.

**완료 조건:** 실제 LLM 런에서 승인 요청이 버튼 UI로 표시·동작(수동 확인), 터미널 타이핑 없이 승인 가능.

**규모:** 中

---

## C5 — 구조 리팩터링 (백엔드/프론트/보안)

**목표:** 유지보수성·리뷰가능성·보안 경계 개선.

**근거:** `web/server.py`(940줄) 6개 도메인 ~30 엔드포인트 모놀리스; `index.html`(6250줄) 단일 파일; `auto_approve` 무샌드박스 셸 실행; 라우팅 키워드 하드코딩(`tutorial_registry.py:47`). — 평가 구조 §3.2, §3.5-3,4

**대상 파일:** `web/server.py` → `web/routers/*.py`, `web/static/index.html` → ES 모듈, `lib/tutorial_registry.py`, `web/llm_adapters/gemini.py`, 문서.

**단계:**
1. `server.py`를 `APIRouter`(runs/forcefields/ligand/membrane/presets/analysis)로 분해, 비즈니스 로직을 `lib/`로 이전.
2. `index.html`을 관심사별 ES 모듈(터미널/런목록/설정폼/뷰어)로 분해 + 최소 빌드(esbuild/vite) 또는 `<script type=module>`. 인라인 `onclick`→위임 리스너.
3. LLM 실행 **위협모델을 문서화** + `auto_approve`를 컨테이너/비특권 사용자 경계 뒤로.
4. 라우팅 키워드를 매니페스트로 이동(데이터 주도 복원).
5. 반응형(`@media`, 사이드바 드로어)·a11y(`role`/`aria-label`·포커스트랩)·실패 에러카드·온보딩·폰트 로컬 번들.

**완료 조건:** server.py 라우터 분리, index.html 모듈화, 위협모델 문서 존재, 반응형/a11y 개선(수동+코드 확인), C3 테스트 계속 그린.

**규모:** 大

---

## C6 — 자유에너지 스케줄 세분화

**목표:** 출판급 수화 자유에너지를 위해 λ 창을 세분·분리.

**근거:** 5창 락스텝(`0,0.25,0.5,0.75,1.0`)에서 coul/vdw 동시 변환(`lib/mdp_templates/base.py:17-21`) — 과소·비최적. — 평가 기능 §2.2

**대상 파일:** `lib/mdp_templates/base.py`, `lib/mdp_templates/free_energy.mdp`.

**단계:** decharge(coul)와 vdw 분리 변환, 각 ≥10창(권장), 소프트코어 유지. BAR로 창간 겹침 확인.

**완료 조건:** FE 스케줄이 분리·세분화, 재계산한 ΔG_hyd가 참조 오차범위 내(C1 연계).

**규모:** 中

---

## 티어 C 완료 게이트 (저널 승격)

- [ ] C1: 8시스템 + 오차막대 + BAR/WHAM 오차
- [ ] C2: 막·복합체 분석 실구현
- [ ] C3: 코어 테스트 + CI 매트릭스 + lint/type
- [ ] C4: GUI 승인 다이얼로그
- [ ] C5: 백엔드/프론트 모듈화 + 위협모델 + 반응형/a11y
- [ ] C6: FE 창 세분화

> 검증 절차는 `docs/plans/verification_plan.md` §C 참조.
