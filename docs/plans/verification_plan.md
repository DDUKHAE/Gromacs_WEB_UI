# 검증 계획서 — 로드맵 구현 검증 기준

> **목적:** 티어 A/B/C 로드맵(`docs/plans/tier_[abc]_implementation.md`)이 **실제로 구현되었는지** 객관적으로 확인하는 검증 기준·절차. 각 항목은 실행 가능한 명령 또는 명확한 수동 확인으로 pass/fail을 판정.
> **원칙:** 증거 없는 완료 주장 금지. 각 기준은 "무엇을 실행 → 무엇을 기대"로 기술.
> **선행 참조:** `docs/journal_readiness_evaluation.md` §5, `docs/plans/tier_*.md`
> **기준 커밋:** `b3b30d2` (라인 번호는 검증 시점에 재확인)

## 검증 게이트 개요

| 게이트 | 조건 | 산출물 |
|---|---|---|
| **G1 — v1 게시 가능** | 티어 A 전 항목 pass | 정직·정확한 프리프린트 v1 |
| **G2 — 강한 v1** | G1 + 티어 B 전 항목 pass | 벤치마크·재현성 갖춘 v1 |
| **G3 — 저널 승격** | G2 + 티어 C 전 항목 pass | SoftwareX/JCIM 원고 |

> G1은 필수. G2·G3는 §5.4 실행 순서에 따라 v1 이후로 미룰 수 있음.

## 공통 회귀 기준 (모든 게이트)

```bash
python -m pytest -q          # 기존 53개 + 신규 테스트 전부 통과, 실패 0
python scripts/check_gromacs_env.py   # gmx 탐지 JSON 정상
```
- 위가 그린이 아니면 어떤 게이트도 통과로 간주하지 않음.

---

## §A. 티어 A 검증 (게이트 G1)

### A1 — 목 데이터 제거·격리
- **검증:** `grep -rni "mock\|4 passed, 0 failed\|virtual run\|dummy\|fake" web/static/index.html`
- **기대:** 매치 0건, 또는 각 매치가 `demo`/`synthetic` 라벨 블록 내부(수동 확인).
- **수동:** 실제 런을 완료 → 감사/채팅 패널에 하드코딩 문자열 미출현.
- **판정:** 프로덕션 완료-런 경로에 조작 데이터가 실측처럼 노출되지 않으면 **PASS**.

### A2 — 문서 주장 ↔ 코드 일치
- **검증:** README/ARCHITECTURE의 각 기능 주장에 근거 파일:함수가 매핑되는지 수동 대조.
- **자동 보조:** `grep -rn "judge_neutrality" skills/` — A3 완료 후 env_builder 호출이 존재해야 "게이트 작동" 주장 허용.
- **기대:** "Limitations" 문단 존재; "최초 LLM" 류 과장 부재(`grep -rni "first llm\|최초" README*.md` 0건 또는 정당화).
- **판정:** 실행되지 않는 기능을 작동한다고 주장하지 않으면 **PASS**.

### A3 — 물리 버그 수정 (핵심)
- **에너지 드리프트:** `tests/`에 total-energy vs ns 회귀 검증 테스트 존재·통과. 코드에서 퍼텐셜÷프레임수 로직 부재.
  - `grep -n "Potential\|/ *count\|frame" skills/md_runner/md_runner.py` 로 옛 로직 잔존 여부 확인.
- **중성화 게이트:** `grep -rn "judge_neutrality" skills/env_builder/` 에 호출 존재. `grep -n "net_charge.*0.0" skills/env_builder/env_builder.py` 하드코딩 부재. 순전하≠0 입력에 FAIL 내는 테스트 통과.
- **tc-grps:** `grep -n "Protein Non-Protein" lib/mdp_templates/*.mdp` — 하드코딩 잔존 0(동적/분기 처리). 단백질 없는 조성 → `System` 유도 테스트 통과.
- **바로스탯:** `grep -n "pcoupl" lib/mdp_templates/*.mdp` — 초기 평형에 Berendsen/C-rescale 단계 존재.
- **밀도 게이트:** `md_runner.py`의 밀도 범위가 시스템 타입별 파라미터화(하드코딩 995~1005 조건부).
- **maxwarn:** `grep -rn "maxwarn" skills/` — 값 축소 또는 억제 경고 로깅.
- **판정:** 위 6종 각각 코드 증거 + 신규 테스트 통과면 **PASS**. (프리프린트에 수치를 싣는다면 A3 전체 필수)

### A4 — 메타데이터·DOI·공개
- **검증:** `grep -n "Author\|<org>\|Institution\|TODO\|XXXX\|FIXME" CITATION.cff .zenodo.json` → **0건**.
- **수동:** Zenodo DOI 발급·README 링크 확인; GitHub 저장소 공개 확인.
- **판정:** 플레이스홀더 0 + 유효 DOI 링크면 **PASS**.

### A5 — 신규성 프레이밍·인용
- **검증:** 원고/README 초안에 필수 인용 존재 — `grep -rni "DynaMate\|MDCrow\|4c01653\|CHARMM-GUI\|BioBB" <원고>`.
- **기대:** DynaMate(2512.10034), MDCrow, JCIM 2024(10.1021/acs.jcim.4c01653) 최소 포함 + 대조표 + 차별 문단.
- **판정:** 4개 차별 축 + 필수 인용 + 과장 부재면 **PASS**.

### ✅ G1 판정
A1–A5 전부 PASS + 공통 회귀 그린 → **v1 게시 가능**.

---

## §B. 티어 B 검증 (게이트 G2)

### B1 — 축소 벤치마크
- **검증:** `scripts/reference_values.json` 존재 + 각 항목에 출처 DOI. Table 1 산출물(`docs/benchmark/`) 존재.
- **자동:** `python scripts/compute_reference_deviation.py`(신규) 실행 → 시스템별 편차·pass/fail 표 출력.
- **기대:** ≥3 시스템, 각 행에 계산값±오차·참조값·편차·pass/fail. 최소 1개 FE ΔG가 참조 오차범위 내(또는 이탈 원인 문서화).
- **판정:** 위 충족 + 재실행 재현 확인이면 **PASS**.

### B2 — 교차모델 신뢰성 표
- **검증:** `grep -n "TODO.*auto" web/llm_adapters/gemini.py` → **0건**(플래그 확정).
- **자동:** 신뢰성 표 산출물 존재 — ≥2 시스템 × 3 모델 × (N≥3) 반복, 성공률·표준편차·리트라이·복구율.
- **판정:** 표 존재 + gemini TODO 해소 + 비결정성 정량화면 **PASS**.

### B3 — 컨테이너·환경 정합
- **자동:**
  ```bash
  docker build -t gromacs-web-ui .        # 성공(또는 conda env create -f environment.yml)
  # 컨테이너/환경 내부:
  python -m pytest -q                      # 통과
  python scripts/check_gromacs_env.py      # gmx 탐지
  ```
- **정합 검증:** `matplotlib`·`propka`가 `requirements.txt`·`pyproject.toml` **양쪽**에 존재(`grep -n "matplotlib\|propka" requirements.txt pyproject.toml`).
- **판정:** 빌드 성공 + 컨테이너 내 테스트 통과 + 의존성 정합이면 **PASS**.

### B4 — 출판급 플롯·내보내기
- **코드 검증:** `grep -n "devicePixelRatio" web/static/index.html` 존재; `grep -n "255,255,255" web/static/index.html`가 차트 그리기 경로(`:4740,4748,4758`)에서 제거/토큰화; export 버튼 코드 존재(`toBlob`/CSV).
- **백엔드:** `skills/illustrator/illustrator.py` matplotlib dpi≥300, `_pubstyle` 적용.
- **수동:** 라이트테마에서 축·그리드 가시; PNG/SVG/CSV 내보내기 동작.
- **판정:** dpr 스케일 + 축 단위 + 내보내기 + 라이트테마 수정이면 **PASS**.

### B5 — 프로버넌스
- **검증:** 완료된 런의 `state.json`에 `gmx_version`·`mdp_hashes`·`seed`(또는 기록) 필드 존재(`python -c "import json; d=json.load(open('runs/<id>/.../state.json')); print(d.get('provenance'))"`).
- **수동:** `docs/STATE_SCHEMA.md`에 provenance 스키마 문서화. 동일 시드 재실행 재현 확인(B1 연계).
- **판정:** provenance 필드 + 문서 + 재현 확인이면 **PASS**.

### ✅ G2 판정
G1 + B1–B5 전부 PASS → **강한 v1** (SoftwareX/J.Cheminform. 투고 준비).

---

## §C. 티어 C 검증 (게이트 G3)

### C1 — 전체 벤치마크 + 불확실도
- **검증:** Table 1이 8개 시스템; 모든 관측량에 ±오차. 블록평균 정확성 단위테스트 통과. BAR/WHAM 오차 산출물 존재.
- **판정:** 8시스템 + 오차막대 + FE/umbrella 통계오차면 **PASS**.

### C2 — 막·복합체 분석
- **검증:** `grep -rn "\"status\": \"stub\"\|status.*stub" skills/illustrator/illustrator.py` → **0건**. 두 변형이 실제 수치·플롯 산출. 신규 테스트 통과.
- **판정:** 스텁 부재 + 실산출이면 **PASS**.

### C3 — 코어 테스트·CI
- **검증:** `tests/test_api_runs.py`·`test_llm_runner.py`·`test_websocket.py` 존재·통과. 커버리지 리포트에 `web/llm_runner.py` 포함.
- **CI:** `.github/workflows/ci.yml`에 Python×OS 매트릭스 + `ruff`+`mypy`+커버리지 임계.
  - `grep -n "matrix\|ruff\|mypy" .github/workflows/ci.yml`.
- **판정:** 4개 코어 경로 테스트 + CI 매트릭스/lint/type이면 **PASS**.

### C4 — GUI 승인 다이얼로그
- **수동:** 실제 LLM 런에서 승인 요청이 Approve/Deny 버튼으로 표시·동작, 터미널 타이핑 불필요.
- **코드:** 백엔드 구조화 WS 메시지 + 프론트 모달 렌더 존재.
- **판정:** 버튼 승인 동작이면 **PASS**.

### C5 — 구조 리팩터링
- **검증:** `web/routers/` 디렉터리·라우터 모듈 존재; `wc -l web/server.py`가 대폭 감소. `index.html`이 ES 모듈로 분해(또는 `<script type=module>` 다수). 위협모델 문서 존재. `grep -c "@media" web/static/index.html` ≥1; 캔버스에 `role="img"`/`aria-label` 존재.
- **회귀:** C3 테스트 계속 그린.
- **판정:** 라우터 분리 + 프론트 모듈화 + 위협모델 + 반응형/a11y + 회귀 그린이면 **PASS**.

### C6 — FE 창 세분화
- **검증:** `lib/mdp_templates/base.py`/`free_energy.mdp`에서 coul/vdw 분리 + 각 ≥10창. 재계산 ΔG가 참조 오차범위 내(C1 연계).
- **판정:** 분리·세분화 + ΔG 재현이면 **PASS**.

### ✅ G3 판정
G2 + C1–C6 전부 PASS → **저널 승격 준비**(JCIM 목표).

---

## 검증 실행 체크리스트 (요약)

```
공통:  pytest -q 그린 · check_gromacs_env 정상
─────────────────────────────────────────────
G1:  [ ]A1 [ ]A2 [ ]A3 [ ]A4 [ ]A5        → v1 게시
G2:  [ ]B1 [ ]B2 [ ]B3 [ ]B4 [ ]B5        → 강한 v1 / SoftwareX
G3:  [ ]C1 [ ]C2 [ ]C3 [ ]C4 [ ]C5 [ ]C6  → JCIM
```

각 항목 PASS 시 증거(명령 출력·산출물 경로·수동 확인 메모)를 기록하여 재현 가능한 검증 이력을 남길 것.
