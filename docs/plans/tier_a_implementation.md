# 티어 A 구현 계획서 — v1 게시 전 정직성·정확성 방어선

> **목표:** bioRxiv v1 게시 전에 **반드시** 끝내야 하는 항목. 규모는 대체로 작지만 평판·과학적 정직성에 직결되어 타협 불가.
> **원칙:** "공개하면 안 되는 것"을 제거한다 — 가짜 데이터, 없는 기능 주장, 틀린 물리로 얻은 수치.
> **선행 참조:** `docs/journal_readiness_evaluation.md` §5.1
> **기준 커밋:** `b3b30d2` — 라인 번호는 이 커밋 기준이며, 편집 전 반드시 재확인할 것.

## 에이전트 실행 규칙

1. 각 태스크는 독립적이며 A1–A5 순서 무관. 단 A2·A3는 같은 검증기/mdp 파일을 건드리므로 **동일 에이전트가 순차 처리**하거나 병합 충돌에 주의.
2. 물리/검증 로직 변경(A3)은 **TDD 필수** — 실패 테스트 먼저, 그 다음 구현.
3. 편집 전 대상 파일의 해당 라인을 Read로 재확인(라인 이동 가능성).
4. 완료 시 각 태스크의 **완료 조건(Acceptance)** 을 실제 명령 실행으로 증명. 증거 없이 완료 주장 금지.
5. 기존 53개 테스트가 계속 통과해야 함: `python -m pytest -q`.

---

## A1 — 가짜/목(mock) 데이터 경로 제거·격리

**목표:** 프리프린트 스크린샷·라이브 데모에 조작된 데이터가 실측처럼 노출되는 경로를 제거하거나 명시적 "Demo" 라벨 뒤로 격리.

**근거:** 프론트엔드에 하드코딩된 목 콘텐츠가 프로덕션 완료-런 경로와 뒤섞여 있어, 도구를 실행한 리뷰어/독자가 실제 산출과 플레이스홀더를 구분할 수 없음(신뢰성 최대 리스크). — 평가 UI §4.1, §4.6-4

**대상 파일:**
- `web/static/index.html:5785` — "Mock AI dialogue — injected into chat panel"
- `web/static/index.html:5752` — 정적 가짜 감사 블록("Lysozyme in Water — 4 passed, 0 failed")
- `web/static/index.html` — "Virtual Run" 모드 진입점(런타입 허브 카드, `:2764` 부근)

**단계:**
1. `grep -n -i "mock\|virtual run\|4 passed\|fake\|dummy\|sample" web/static/index.html` 로 목 콘텐츠 전수 목록화.
2. 각 항목을 (a) 완전 제거하거나 (b) 명시적 `Demo mode` 배너/모달 뒤로 격리. 실제 런 데이터가 흐르는 기본 경로에서 하드코딩 감사/채팅 샘플을 분리.
3. "Virtual Run"을 유지한다면 카드·화면 상단에 "DEMO / synthetic data — not a real simulation" 배너를 항상 표시.
4. 기본 완료-런 뷰(`status === 'completed'` 경로, `:4440-4446`)가 오직 실제 `state.json`/아티팩트만 렌더하는지 확인.

**완료 조건(Acceptance):**
- `grep -ni "mock\|4 passed, 0 failed" web/static/index.html` 결과가 0건이거나, 각 매치가 `demo`/`synthetic` 라벨 블록 내부임을 수동 확인.
- 실제 런을 완료했을 때 감사·채팅 패널에 하드코딩 문자열이 나타나지 않음(코드 경로 추적으로 증명).

**규모:** 小

---

## A2 — 원고 주장을 코드 실제 동작에 일치시키기

**목표:** 논문/README/문서가 주장하는 기능이 **실제로 실행되는 것만** 주장하도록 정리. 특히 "per-step validator gate", "config audit"의 실제 범위를 정확히 기술.

**근거:** 없는 기능을 주장하면 프리프린트가 코드로 즉시 반증됨. 현재:
- `judge_neutrality`(`lib/validators.py:38-62`)는 파이프라인에서 **호출되지 않음**(死코드) — 이온화 검증 게이트가 실제로 안 돎.
- `run_step5_genion`(`skills/env_builder/env_builder.py:204`)은 `net_charge`를 0.0으로 **하드코딩**.
- `system_config_validator.validate_run_against_config`(`lib/system_config_validator.py:69-101`)는 **3개 키만**(포스필드 접두·물모델·박스타입) 검사. — 평가 기능 §2.1, §2.4

**대상 파일:** `README.md`, `README.ko.md`, `ARCHITECTURE.md`, `docs/ARCHITECTURE.md`, 향후 원고 초안. (코드는 A3에서 수정; 여기선 **주장의 정확성**만 정렬)

**단계:**
1. README/ARCHITECTURE에서 "validator", "gate", "audit", "enforce", "guarantee" 등 강한 주장을 전수 검색.
2. 각 주장을 실제 실행 코드 경로와 대조. A3에서 실제로 고쳐 실행되게 만들 항목(중성화·드리프트)은 A3 완료 후 "실행됨"으로 기술, 그렇지 않은 항목은 범위를 축소 기술(예: "config audit는 force field·water model·box type 3개 파라미터를 검증한다"로 명시).
3. LLM 오케스트레이션의 한계(환각·조작 단계에 대한 구조적 탐지 없음)를 "Limitations" 문단으로 솔직히 기술.
4. 두 개의 상충하는 `ARCHITECTURE.md`(루트=폐기된 TutorialRouter 서술) 정합 — 최소한 루트 파일의 낡은 서술 수정. (구조 §3.4)

**완료 조건(Acceptance):**
- README/ARCHITECTURE의 모든 기능 주장이 실제 코드 경로로 추적 가능(각 주장 옆에 근거 파일:함수 메모).
- "Limitations" 문단 존재.
- A3 완료 전이라면 중성화/드리프트 게이트를 "작동함"으로 주장하지 않음.

**규모:** 小

---

## A3 — 결과를 보고한다면 물리 버그부터 수정

**목표:** 프리프린트에 MD 수치를 하나라도 싣는다면, 그 수치를 만든/검증한 코드의 물리적 오류를 먼저 수정. **TDD 필수.**

**근거:** 틀린 물리로 얻은 값을 프리프린트에 실으면 철회 수준의 사고. — 평가 기능 §2.1, §2.5-2,5

**대상 버그 & 파일:**
1. **에너지 드리프트 검증** — `skills/md_runner/md_runner.py:320-326`(`_judge_energy_drift`)가 **퍼텐셜 에너지 ÷ 프레임 수**를 `slope_per_ns`로 `validators.py:117`(`judge_energy_drift`)에 전달. → **전체(total) 에너지 vs 시뮬레이션 시간(ns) 선형회귀 기울기**로 재작성, 임계값 재튜닝.
2. **중성화 게이트 死코드** — `judge_neutrality`(`validators.py:38-62`)를 `run_step5_genion`(`env_builder.py:177-208`)에 연결. `net_charge` 하드코딩 0.0(`:204`) 제거하고 **실제 `gmx` 시스템 전하**(genion 로그/topol 파싱 또는 `gmx grompp` 후 전하 확인)로 대체.
3. **`tc-grps` 하드코딩** — `lib/mdp_templates/nvt.mdp`·`npt.mdp`·`production.mdp`의 `tc-grps = Protein Non-Protein`을 **실제 시스템 조성에서 유도**(단백질 없으면 `System`, FE/umbrella 경로는 이미 올바름). 비단백질 튜토리얼(Methane/Ethanol/Biphasic)에서 grompp 실패 방지.
4. **바로스탯 단계화** — `npt.mdp`·`production.mdp`가 첫 NPT부터 `Parrinello-Rahman`. **Berendsen 또는 C-rescale로 초기 평형 후 P-R** 단계 도입.
5. **밀도 게이트 물 전용** — `md_runner.py:316-317`의 `expected_range=(995,1005)`를 **시스템 타입별 파라미터화**(막/이상/비수용매 제외 또는 범위 조정).
6. **경고 은폐** — 모든 grompp의 `-maxwarn 2`(`md_runner.py:75`)를 축소(가능하면 0~1). 억제한다면 어떤 경고인지 로그·state에 기록.

**단계(각 버그 공통, TDD):**
1. `tests/`에 해당 버그를 드러내는 **실패 테스트** 작성(예: 알려진 total-energy 시계열 → 드리프트 기울기가 물리적으로 옳은 값을 반환하는지; 순전하 -3 시스템 → 중성화 게이트가 FAIL을 내는지; 단백질 없는 조성 → `tc-grps=System` 유도).
2. 최소 수정으로 통과.
3. 회귀 없는지 전체 스위트 실행.

**완료 조건(Acceptance):**
- 신규 테스트가 각 버그의 수정을 증명(`python -m pytest -q tests/test_validators.py tests/test_md_*.py` 등 통과).
- `grep -n "Protein Non-Protein" lib/mdp_templates/*.mdp` → 조건부/동적 처리로 대체되어 하드코딩 잔존 없음(또는 단백질 계 전용으로 분기).
- `judge_neutrality`가 실제 파이프라인에서 호출됨(`grep -rn judge_neutrality skills/` 에 env_builder 호출 존재).
- 드리프트 검증이 total energy·ns 기반임을 코드/주석·테스트로 확인.

**규모:** 中 (물리 정확성 핵심)

---

## A4 — 공개 저장소 · Zenodo DOI · 실제 메타데이터

**목표:** 프리프린트의 "Code/Data Availability"에 유효한 링크를 제공.

**근거:** `CITATION.cff`·`.zenodo.json`에 플레이스홀더(`family-names: Author`, `<org>`, `Institution`) 잔존. — 평가 구조 §3.3

**대상 파일:** `CITATION.cff`, `.zenodo.json`, `README.md`(배지/링크), (신규) 릴리스 태그.

**단계:**
1. `CITATION.cff`·`.zenodo.json`의 저자명·ORCID·소속·라이선스·저장소 URL을 **실제 값**으로 채움.
2. GitHub 저장소 공개 상태 확인(SoftwareX/bioRxiv는 공개 GitHub 선호).
3. Zenodo–GitHub 연동으로 릴리스 태그 → **DOI 발급**. `README.md`·`CITATION.cff`에 DOI 배지 반영.
4. `LICENSE`(MIT) 존재·헤더 확인. GROMACS는 외부 바이너리(LGPL)임을 명시(이미 README에 있음 — 유지).

**완료 조건(Acceptance):**
- `grep -n "Author\|<org>\|Institution\|TODO\|XXXX" CITATION.cff .zenodo.json` 결과 0건.
- DOI가 발급되어 README에 링크됨(수동 확인).
- 저장소가 공개이며 clone→설치가 문서대로 동작(A/B 컨테이너 완성 시 재검증).

**규모:** 小

---

## A5 — 신규성 정직 프레이밍 & 선행연구 인용

**목표:** 기여를 정확히 위치시키고 경쟁작을 명시 인용·차별.

**근거:** "MD용 최초 LLM"은 거짓(DynaMate·MDCrow·JCIM 2024 선점). 방어 가능한 신규성은 **"투명·브라우저 전달 에이전트 하니스 + 모델무관 백엔드 + 튜토리얼 접지"**. 선행연구 누락은 프리프린트 신뢰도와 후속 저널 모두 훼손. — 평가 웹 §1.2-1.3

**대상:** 원고 초안(신규 `docs/manuscript/` 또는 별도), README 소개 문단.

**필수 인용(최소):**
- DynaMate — arXiv:2512.10034 (GROMACS+AmberTools 멀티에이전트 자율 MD)
- MDCrow — *MLST* 2025 / arXiv:2502.09565 (LangChain LLM 에이전트, 주로 OpenMM)
- JCIM 2024 LLM 시뮬 워크플로 — 10.1021/acs.jcim.4c01653
- CHARMM-GUI(JCTC 2016), BioBB-Wfs(*NAR* 2022), Making it Rain(JCIM 2021), WebGRO — 결정론적 웹 도구 대비군

**차별 주장(4개 축):** ① 제로설치 브라우저 UI 전달, ② 실행 트레이스 투명성(라이브 `gmx` 명령 스트리밍), ③ 튜토리얼 접지(RAG형), ④ 모델무관 백엔드(교차모델 신뢰성 비교 가능).

**단계:**
1. 위 도구를 대조표(도구·인터페이스·자동화·출판처)로 정리(평가 §1.1 재사용).
2. "우리 기여는 X가 아니라 Y"를 명시하는 한 문단 작성.
3. 각 차별 축이 코드의 어느 기능에 대응하는지 근거 표기.

**완료 조건(Acceptance):**
- 초안에 위 4개 필수 인용이 모두 포함.
- "최초 LLM" 류의 과장 주장 부재(검색으로 확인).
- 대조표 + 차별 문단 존재.

**규모:** 小

---

## 티어 A 완료 게이트

아래를 모두 만족해야 v1 게시 진행:
- [ ] A1: 목 데이터 제거/격리 — grep 증거
- [ ] A2: 문서 주장이 코드와 일치 + Limitations 문단
- [ ] A3: 물리 버그 4~6종 수정 + 신규 테스트 통과 + 전체 53+개 스위트 그린
- [ ] A4: 실제 메타데이터 + DOI + 공개 저장소
- [ ] A5: 정직 신규성 프레이밍 + 필수 인용

검증 절차는 `docs/plans/verification_plan.md` §A 참조.
