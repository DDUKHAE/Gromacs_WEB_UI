# GROMACS Web UI — 최상위 저널 제출 준비도 평가 보고서

**평가일:** 2026-07-08
**평가 대상 커밋:** `b3b30d2` (main)
**평가 방식:** 4개 서브에이전트 병렬 평가 — (1) 경쟁 지형 웹 리서치, (2) 기능/과학적 역량, (3) 구조/아키텍처, (4) UI/UX
**목표 저널:** JCIM (J. Chem. Inf. Model.) 급 · 대안으로 SoftwareX / J. Cheminformatics

---

## 0. 총평 (Executive Summary)

이 프로젝트는 **잘 설계된 연구 프로토타입**이다. `lib/` 계층 분리가 깔끔하고(웹/과학 로직 분리, 53개 단위테스트 전부 통과), 상태머신·파이프라인 계약 문서가 출판 수준이며, LLM CLI를 브라우저에서 구동한다는 **차별화된 컨셉**을 갖췄다.

그러나 **"소프트웨어로서의 완성도"와 "과학 도구로서의 검증"이 크게 벌어져 있다.** 배관(plumbing)은 견고하지만 그 안을 흐르는 과학은 얇다. 최상위 저널이 요구하는 세 가지 — **(a) 참조 데이터 대비 정확도 검증, (b) LLM 신뢰성/재현성 정량화, (c) 재현 아티팩트(컨테이너·핀 고정 환경)** — 가 모두 비어 있다.

**핵심 판단:** 현재 상태로는 JCIM 데스크리젝트 위험이 높다. 그러나 **차별점(브라우저 전달 + 투명한 실행 트레이스 + 모델 무관 백엔드)** 은 진짜 출판 가치가 있으며, 아래 로드맵을 이행하면 SoftwareX/J.Cheminform.은 단기, JCIM은 중기 목표로 현실적이다.

| 축 | 강점 | 치명적 부족 | 성숙도 |
|---|---|---|---|
| 경쟁/신규성 | 웹 GUI + 에이전트 + 라이브 터미널 조합은 유일 | "LLM이 MD 구동"은 이미 선점됨(DynaMate/MDCrow) | ★★★☆☆ |
| 기능/과학 | 표준 수용액 파이프라인 완성, 리트라이 엔진 견고 | 검증 게이트 死코드·물리 버그, 참조 벤치마크 전무 | ★★☆☆☆ |
| 구조/공학 | 3계층 분리, 보안·경로검증 우수, 문서 충실 | 컨테이너 없음, 핵심(PTY/run API) 테스트 0, 6250줄 단일 HTML | ★★★☆☆ |
| UI/UX | 6트랙 허브, XVG 축 파싱·통계 등 좋은 디테일 | 그림 비출판급·내보내기 불가, GUI 승인창 없음, 반응형 0 | ★★☆☆☆ |

---

## 1. 경쟁 지형 및 신규성 (Web Research)

### 1.1 지형도

| 도구 | 기능 | 인터페이스 | 자동화 | 출판처 |
|---|---|---|---|---|
| **CHARMM-GUI** | 용매/막/당/리간드 시스템 빌드 → GROMACS/NAMD/AMBER/OpenMM 입력 생성 | 웹 GUI (다단계 폼) | 결정론적 템플릿 마법사(실행 없음) | JCTC 2016 등 |
| **WebGRO** | 단백질/복합체 GROMACS MD 서버 실행 후 플롯 반환 | 웹 폼 + 서버 실행 | 고정 프로토콜 완전 자동 | 호스팅 서비스 |
| **MDWeb/MDMoby** | PDB에서 "전문가 모방" 셋업·테스트런·분석 | 웹 포털 + 웹서비스 API | 사전구축 파이프라인 | *Bioinformatics* 2012 |
| **BioBB / BioBB-Wfs** | GROMACS/AmberTools 래핑, 재현가능 워크플로 | Python + 웹 GUI | 스크립트형·파라미터화 | *Sci.Data* 2019, *NAR* 2022 |
| **Making it Rain** | Colab에서 OpenMM MD, 저사양 랩 대상 | Jupyter/Colab | 노트북 셀 고정 프로토콜 | **JCIM 2021** |
| **HTMD / PlayMolecule** | 고처리량 준비·적응샘플링·MSM, 웹 pKa 도구 | Python API + 웹앱 | 고처리량 스크립트 | JCTC 2016, JCIM 2017 |
| **gmx_MMPBSA** | GROMACS 궤적 → 결합 자유에너지 | CLI + GUI | 사후 분석 | JCTC 2021 |
| **MDCrow** | LangChain 40+ 툴 LLM 에이전트(주로 OpenMM) | Python/CLI 에이전트 | **에이전트형 LLM** | *MLST* 2025 |
| **DynaMate** | 멀티에이전트 LLM이 GROMACS 2023+AmberTools 자율 구동, MM/PBSA, 런타임 오류교정 | Python/CLI 에이전트 | **에이전트형 LLM** | arXiv 2512.10034 |
| **JCIM 2024 LLM 워크플로** | LLM이 시뮬 연구 루프 설계·실행 | 프레임워크 | 에이전트형 | **JCIM 2024** (10.1021/acs.jcim.4c01653) |
| **본 프로젝트** | PDB 업로드 → 6단계 빌더 → LLM CLI가 튜토리얼 기반 GROMACS 실행, 라이브 터미널·NGL·XVG | **웹 GUI + 에이전트 + 라이브 터미널** | 에이전트형, 튜토리얼 접지 | (목표: JCIM/SoftwareX) |

### 1.2 진짜 신규성 (출판 가능한 기여)

"LLM이 GROMACS를 구동한다"는 **이미 선점됨** — DynaMate(GROMACS, 단백질-리간드, MM/PBSA, 오류교정), MDCrow(OpenMM), 그리고 JCIM은 2024년 LLM 시뮬 워크플로 논문을 이미 게재했다. 방어 가능한 신규성은 **아무도 동시에 제공하지 않는 조합**이다:

1. **제로설치 브라우저 UI로 전달되는 에이전트 오케스트레이션** — 기존 LLM-MD 에이전트는 전부 로컬 Python/CLI 패키지, 기존 웹서버는 전부 LLM 추론 없는 결정론적 폼. 에이전트 루프를 호스팅 GUI 뒤에 둔 것은 이 프로젝트가 처음.
2. **실행 투명성을 일급 기능으로** — WebSocket+xterm.js가 에이전트가 실제 발행하는 `gmx` 명령을 스트리밍. "LLM 블랙박스" 반박의 자연스러운 근거이자 교육적/재현성 기여.
3. **튜토리얼 접지(RAG형)** — 정규 GROMACS 튜토리얼에 에이전트를 고정. DynaMate의 문헌-코퍼스 접지와 다른, 프로토콜 충실 전략.
4. **모델 무관 백엔드**(Claude/Codex/Gemini 교체) — 내장 교차모델 신뢰성 비교가 가능. 리뷰어가 기대하는 벤치마크.

> **프레이밍 권고:** "MD용 최초 LLM"이 아니라 **"상호작용적·투명한·브라우저 전달 에이전트 하니스"** 로 기여를 정의할 것.

### 1.3 저널 적합성

- **SoftwareX (Elsevier)** — 최적 단기 경로. 공개 GitHub, ≤3000단어 메타페이퍼, 오픈소스 라이선스, 동작 설치. 기존 테스트·CI가 지속가능성 요건을 충족. **가장 낮은 진입장벽.**
- **J. Cheminformatics** — 오픈 웹툴·재현성 중시, SoftwareX보다 신규성/검증 기대 높지만 실험 벤치마크는 불필요.
- **JCIM (목표)** — **달성 가능하나 최고 난도.** 선례(Making it Rain, ProteinPrepare, 2024 LLM 워크플로)는 고무적. 통과하려면 아래 4종 필수:
  1. **벤치마크 스위트**(≥8–12 시스템) + 문헌/실험값 대비 MD 관측량 검증
  2. **교차모델 신뢰성/성공률 표**(Claude vs Codex vs Gemini) + 오류복구 분석
  3. **재현 아티팩트** — 핀 고정 GROMACS/포스필드 버전, 시드, 컨테이너, 아카이브된 예제 런
  4. MDCrow/DynaMate 대비 명시적 포지셔닝
- **NAR Web Server** — 공개·유지되는 서버 배포 시에만. 현재 localhost 하니스는 부적격.

---

## 2. 기능 / 과학적 역량 평가

> `python -m pytest -q` → **53 passed** (1.36s). 단, 전부 파서/검증기/상태의 단위테스트이며 **엔드투엔드 GROMACS 실행·과학적 정확도 검증은 0.**

### 2.1 발견된 과학적 정확성 문제 (심각)

- **중성화 게이트가 死코드.** `judge_neutrality`(`lib/validators.py:38-62`)는 파이프라인에서 호출되지 않음(테스트에서만). `run_step5_genion`(`skills/env_builder/env_builder.py:177-208`)은 `net_charge`를 **0.0으로 하드코딩**(line 204)하고 "Will try to add" 개수만 정규식 스크랩. 즉 이온화 검증 게이트가 실제로는 돌지 않음.
- **에너지 드리프트 검증이 물리적으로 틀림.** `_judge_energy_drift`(`skills/md_runner/md_runner.py:320-326`)는 **퍼텐셜** 에너지를 프레임 수로 나눈 값을 `slope_per_ns`로 넘김. 퍼텐셜 에너지는 보존량이 아니고(NVE의 전체에너지만), 프레임 수 나눗셈은 per-ns가 아니며, 0.5 kJ/mol 임계는 무의미. 실제 적분 불안정을 탐지 불가.
- **`tc-grps = Protein Non-Protein` 하드코딩** (nvt/npt/production.mdp). 비단백질 튜토리얼(Methane/Ethanol 수화, Biphasic)에는 "Protein" 인덱스 그룹이 없어 `grompp` 실패 또는 잘못된 서모스탯 커플링.
- **바로스탯 선택 함정.** 첫 NPT부터 `pcoupl = Parrinello-Rahman` 사용(`lib/mdp_templates/npt.mdp`). 평형 초기엔 Berendsen/C-rescale 권장 — P-R을 평형에서 먼 상태로 시작하면 큰 부피 진동. Berendsen→P-R 단계 없음.
- **밀도 게이트가 물 전용.** `expected_range=(995,1005)` 하드코딩(`md_runner.py:316-317`) — 막/이상(octanol/water)/비수용매 박스에 부적합.
- **`-maxwarn 2`** 를 모든 `grompp`에 부여(`md_runner.py:75`) — 순전하·원자명 불일치 등 검증기가 잡아야 할 경고를 최대 2개 은폐.
- **재현성/프로버넌스 부재.** `gen_vel=yes, gen_seed=-1`(비재현 속도), 시드·`gmx --version`·mdp 해시가 `state.json`에 미기록. 런 재현 불가.

### 2.2 커버리지

- **변형 분석 2종이 스텁.** `_run_membrane_analysis`, `_run_protein_ligand_analysis`가 `{"status":"stub"}` 반환(`skills/illustrator/illustrator.py:221-228`). KALP15/Protein-Ligand(8개 중 2개)는 도메인 분석 산출 0(막두께·면적·질서변수·리간드 RMSD·상호작용맵 없음).
- **자유에너지 스케줄이 조악.** 5개 락스텝 창(`0,0.25,0.5,0.75,1.0`)에서 coul/vdw 동시 변환(`mdp_templates/base.py:17-21`). 소프트코어는 있으나 decharge/vdw 분리 안 됨, 5창은 출판급 수화 자유에너지엔 과소. BAR ΔG 파싱은 취약한 문자열 스크랩(`illustrator.py:210-218`).
- **완전히 빠진 워크플로:** REMD, 메타다이내믹스/강화샘플링, QM/MM, MM-PB/GBSA, constant-pH, 대형/멀티체인 계.

### 2.3 분석 역량

`run_core_analyses`는 RMSD/RMSF/Rg/SASA/에너지, `run_advanced_analyses`는 H-bond/DSSP/PCA. 합리적 코어이나 출판엔:
- **불확실도 정량 전무** — 모든 관측량이 원시 평균/표준편차(`xvg_parser.py:62-73`). 블록평균·자기상관시간·신뢰구간 없음. 오차막대 없는 관측량은 JCIM 리젝 사유.
- DSSP는 `.xpm` 경로만, 2차구조 시계열 정량 없음. PCA는 투영만, 자유에너지 지형 없음.
- 플롯은 matplotlib 기본 단일 시리즈(dpi 120). HTML 리포트는 명시적 플레이스홀더(`illustrator.py:278-287`).

### 2.4 LLM 오케스트레이션 견고성

- **설정 감사가 얕음.** `validate_run_against_config`(`lib/system_config_validator.py:69-101`)는 포스필드 접두·물모델·박스타입 **3개 키만** 검사. mdp 파라미터·이온농도·온도·컷오프·양성자화 상태는 미검증 — LLM이 `dt`/서모스탯/염농도를 몰래 바꿔도 통과.
- **제약 블록은 조언 텍스트일 뿐.** `build_constraint_prompt`가 "MUST FOLLOW"를 주입하나 위 3키 외 프로그램적 강제 없음.
- **환각/오류 처리 조악.** `run_llm_agent`는 PTY 실행 후 종료코드만 기록. LLM이 완료 단계를 조작하거나 잘못된 mdp를 써도 구조적 탐지 없음.
- 결정론적 리트라이 엔진(`run_phase_with_recovery`, `MUTATION_BY_CAUSE`, 동일-재시도 금지)은 **견고**하나, 기본 러너 `_default_phase_runner`가 무조건 PASS 반환("Real validators wired in Task H6", `md_runner.py:168-172`) — 복구는 검증 러너를 명시 선택할 때만 작동하고 그 물리는 §2.1처럼 깨져 있음.

### 2.5 기능 Top 5 격차 (순위·처방)

1. **참조 데이터 대비 정확도 검증 전무** — `collect_metrics.py`는 완료율(ACR)·시간·첫실패단계만 측정, 정확도 아님. → 각 튜토리얼 참조값(ethanol/methane ΔG_hyd, lysozyme Rg/RMSD, DPPC 면적) 커밋 + 편차·허용오차 pass/fail을 Table 1로.
2. **코어 검증 게이트 死/오류** — 중성화 미실행, 드리프트 물리 오류. → `judge_neutrality`를 실제 `gmx` 전하로 연결, 드리프트를 **전체에너지 vs 시간(ns)** 선형회귀로 교체.
3. **관측량 불확실도 부재** — 블록평균+자기상관 표준오차, BAR 통계오차·WHAM 부트스트랩 추가, 모든 요약·플롯에 오차막대.
4. **8개 중 2개 도메인 분석 스텁** — 막(면적·두께·질서변수), 복합체(리간드 RMSD·접촉/H-bond맵, 가능하면 MM-PBSA) 구현.
5. **계-무관 mdp/서모스탯 버그** — `tc-grps`를 실제 조성에서 유도, P-R 앞 Berendsen/C-rescale 단계 추가, 밀도 범위 계별 파라미터화.

---

## 3. 구조 / 아키텍처 평가

> `pytest -q` → **53 passed** (~1.3s). 가장 novel하고 위험한 두 서브시스템(PTY/LLM 러너, run-생성 API)은 테스트가 전혀 닿지 않음.

### 3.1 강점

- **3계층 분리가 최대 자산.** `lib/`(17개 순수 파이썬, 웹 import 없음)는 독립 테스트·재사용 가능. `skills/`가 `lib/` 위에, `web/`가 HTTP/PTY/WS 표면.
- **상태머신이 지적 핵심.** `lib/state.py`는 원자적 쓰기(`mkstemp`+`os.replace`) 정확. Step 0–8 계약, 리트라이 티어 분류, 동일-재시도 금지, 토폴로지 백업 규칙이 `docs/pipeline_contract.md`에 **출판 수준**으로 문서화.
- **보안이 프로토타입 치고 우수.** 경로순회 방어 일관(`_check_run_id`, `api_get_run_file`가 `..`/절대경로 거부·확장자 화이트리스트·resolved 경로 재확인), 아카이브 추출 가드, 업로드 상한(PDB 50MB 등), CORS localhost 제한.
- **PTY 처리 세심.** `pty.openpty` + 데몬 리더스레드 → `call_soon_threadsafe`, ANSI 제거 로그 영속화(재접속 리플레이), 권한 다이얼로그 탐지.

### 3.2 약점

- **`web/server.py`(940줄)가 과부하** — 단일 `create_app()` 클로저에 6개 무관 도메인(런 생명주기·FF설치·프리셋·XVG/PDB분석·리간드·막빌드) ~30개 엔드포인트. `APIRouter` 모듈로 분해 필요. 비즈니스 로직이 핸들러에 인라인(`_install_ff_dir`, 아카이브 추출 등)돼 web/lib 경계 약화.
- **6250줄/255KB 단일 `index.html`가 실질 부채** — 4개 `<script>`, ~105개 JS 함수, 87개 인라인 `onclick`. 빌드·모듈경계·클라이언트 단위테스트 불가. 리뷰어에게 가장 눈에 띄는 약점.
- **명령 실행이 사실상 무제한(설계상).** `auto_approve=true` → `claude --dangerously-skip-permissions`/`codex --approval-mode full-auto`. 하니스 cwd에서 전체 셸 권한 LLM 스폰, 샌드박스(컨테이너/seccomp/제한사용자) 없음. `gemini.py`엔 `# TODO: confirm exact auto-approve flag` — 미검증 플래그가 제출 아티팩트에 실림.
- **Fire-and-forget 태스크:** `asyncio.create_task(...)`(`server.py:482`)가 참조 미보관 → GC 위험·예외 삼킴.
- **`except Exception: pass`** 다수 — 실패 은폐.
- **인증 전무** — localhost 단일사용자엔 허용이나 논문에 위협모델 경계로 명시 필요.

### 3.3 재현성 / 패키징

- 존재: `pyproject.toml`, `requirements.txt`, MIT `LICENSE`, `CITATION.cff`, `.zenodo.json`, `docs/jcim_submission_roadmap.md`. `.gitignore`도 깔끔.
- **버전 핀 없음** — 전부 하한(`fastapi>=0.111`). 락파일 없어 "재현성"은 희망사항.
- **`pyproject.toml`과 `requirements.txt` 불일치** — `requirements.txt`엔 `matplotlib>=3.8`, `propka>=3.5`가 있으나 `pyproject.toml` 의존성엔 누락. 두 설치 경로가 다른 환경 산출 → 실제 재현성 결함.
- **컨테이너 없음** — `Dockerfile`/`docker-compose`/`environment.yml` 전부 부재. 외부 바이너리(`gmx`, `acpype`, `packmol-memgen`, `propka`) + 외부 LLM CLI 의존인데 핀 고정 환경 없어 재현 매우 어려움. **최대 재현성 격차.**
- **CITATION/zenodo 플레이스홀더**(`family-names: Author`, `<org>`) — 아카이브 전 채워야 함.

### 3.4 확장성 / 문서

- **튜토리얼 추가는 저마찰** — `tutorial.manifest.json` 드롭 + `tutorial_index.json` 등록. 선언적 매니페스트/레지스트리 설계는 셀링포인트. 단, 라우팅 키워드가 `tutorial_registry.py:47`에 하드코딩 — 데이터 아닌 코드 수정 필요(부분적 설계 파탄).
- **문서 강점** but: (a) **두 개의 상충하는 ARCHITECTURE.md**(루트=폐기된 TutorialRouter 서술, `docs/`=최신) — 유지보수 위험; (b) **`docs/pipeline_contract.md`가 한국어** + `README.ko.md` — 국제 저널엔 정본 영문 필요.

### 3.5 구조 Top 5 격차 (순위·처방)

1. **컨테이너/핀 고정 환경 없음(재현성 차단)** → GROMACS+Python+보조도구 핀한 `Dockerfile`(또는 Apptainer) + `environment.yml` + 락파일. `requirements.txt`↔`pyproject.toml` 정합(matplotlib/propka 추가).
2. **novel/위험 코어 테스트 0**(run 생성, `/action`, WebSocket, `llm_runner`/PTY) → `TestClient`로 `api_create_run`(직접러너·subprocess 목), continue/abort, 가짜 CLI(`cat`/`echo`) PTY 테스트(EOF·권한탐지·리플레이). 논문 핵심 기여에 리뷰어가 요구할 커버리지.
3. **단일 6250줄 index.html** → 관심사별 ES 모듈 분리(터미널/런목록/설정폼/뷰어), 최소 빌드(esbuild/vite) 또는 `<script type=module>` 분해, 인라인 `onclick` 제거.
4. **server.py 모놀리스 + 무샌드박스 실행** → `APIRouter` 분해, 로직을 `lib/`로, LLM 실행 위협모델 명시 + `auto_approve`를 컨테이너/비특권 사용자 경계 뒤로. `gemini.py` TODO 해결, 태스크 레지스트리 추가.
5. **CI 단일축 + 메타데이터 플레이스홀더** → CI를 Python(3.11/3.12)×OS 매트릭스로, ruff+mypy+커버리지 임계 추가, CITATION/zenodo 실제 값, 두 ARCHITECTURE.md 통합, 영문 pipeline_contract.

---

## 4. UI / UX 평가

> 브라우저 실행 없이 소스 기준 평가. 야심차고 기능 풍부하나 디자인 언어가 **과학 도구보다 데모/대시보드 미학**에 최적화됨.

### 4.1 UX 흐름

- "Select Run Type" 허브(5카드)는 명료.
- **프로덕션 UI에 목/데모 콘텐츠 혼입** — "Virtual Run" + 하드코딩 "Mock AI dialogue"(`index.html:5785`) + 정적 가짜 감사블록("Lysozyme — 4 passed, 0 failed", `5752`). 리뷰어가 실제/플레이스홀더를 구분 못 함 → **신뢰성 위험.**
- **두 개의 다른 단계 모델** — 빌더 6탭 vs 런뷰 8노드 스테퍼. 어휘 상이("Step 4 of 6" vs 8단계 바).
- **실패 시 막다른 길** — 실패는 작은 배지(`badge-failed`)뿐, 실패 요약·재시도 표면 없음. 아티팩트/감사 패널은 `status==='completed'`에만 표시(`4440-4446`) → 실패런은 빈 결과영역+설명 없음.
- WS `exit`에만 상태 갱신, 주기적 폴링 없음 → 깔끔한 종료 프레임 없이 죽으면 "running" 배지 잔존.

### 4.2 정보구조 / 시각디자인

- 디자인 토큰 존재(`:root` 커스텀 속성 + 라이트테마 오버라이드) — 좋은 기반. **그러나 인라인 스타일이 광범위하게 우회**(런카드/모달/XVG 카드 `cssText`, 캔버스 색 하드코딩) → 일관성·테마 무력화.
- **미학이 "사이버/게이밍", 과학 아님** — 네온 글로우, 그라디언트 텍스트, cyber-toggle, 방사형 배경. JCIM/구조생물 독자엔 화려하나 권위 부족. 절제된 고가독 팔레트가 신뢰 형성.
- **CDN Google Fonts 의존**(`8-10`) — NGL/xterm은 오프라인용 번들했으면서 폰트는 네트워크 필요(에어갭 HPC에서 오프라인 스토리 파탄). `JetBrains Mono`는 참조만 되고 미로드.
- 극소 타입스케일(차트 제목 10px, 통계 9px).

### 4.3 피드백 / 상태 전달

- 에러는 `showToast(...,'error')`로 일관.
- **로딩 상태 빈약** — 셀렉트에 "Loading..." 옵션뿐, 스켈레톤/스피너 없음.
- **권한/승인 모델이 비-CLI 사용자에게 최대 문제** — 승인이 xterm 터미널 **안에서** 처리됨(LLM이 Y/N 출력→사용자가 터미널에 타이핑, `term.onData→ws.send`). "Permission Mode" 드롭다운은 있으나 **Approve/Deny 버튼 GUI 다이얼로그 없음.** 셸 모르는 구조생물학자는 터미널 클릭 후 `y` 입력을 알아야 함.
- 터미널이 주 상태표면이나 원시 stdout — "현재 단계/진행%" 증류 없음(MD 진행배지는 step≥6에만).

### 4.4 과학 시각화 품질

- XVG 뷰어의 좋은 디테일: `.xvg`에서 축 라벨 파싱, 시리즈별 min/max/mean/std, 이동평균 슬라이더, 다중시리즈 범례 토글.
- **그러나 플롯이 비출판급·내보내기 불가:**
  - 고정 800×200 캔버스, **`devicePixelRatio` 스케일링 없음** → HiDPI에서 흐릿, 그림으로 사용 불가.
  - **개별 플롯 PNG/SVG/CSV 내보내기 없음** — 전체 런 아카이브만. 리뷰어가 깔끔한 RMSD 그림을 뽑을 수 없음.
  - 축 제목/단위가 캔버스 위 텍스트 한 줄일 뿐, 축 자체에 렌더 안 됨. 틱은 단위 없는 맨 숫자.
  - **라이트테마 렌더 버그** — 그리드/라벨색 `rgba(255,255,255,…)` 하드코딩 → 흰 배경에 흰 축(사라짐).
  - 글로우(`shadowBlur=5`)·그라디언트 채움 — 反과학적, 라인 데이터 왜곡.
- **런 간 비교/오버레이 없음** — MD 방법 비교의 핵심 요구. 갤러리 카드는 비상호작용 스파크라인(클릭 확대 없음).

### 4.5 접근성 / 반응형 / i18n / 온보딩

- **반응형 사실상 없음** — `@media` 쿼리 0개. `body`가 `height:100vh; overflow:hidden` + 고정 250px 사이드바 → 태블릿/모바일 사용 불가.
- **a11y 최소** — 캔버스 플롯에 텍스트대안/`role="img"` 없어 모든 과학 산출이 스크린리더에 비가시. 아이콘 버튼 라벨 없음. 모달 포커스트랩 없음(삭제 모달만 Escape).
- **i18n 부정확** — `<html lang="ko">`인데 UI는 전부 영어(한국어는 개발자 주석뿐). 한국어 스크린리더가 영어를 오발음. `lang="en"`으로 고치거나 UI 현지화 택일.
- **온보딩 사실상 부재** — 환영/투어/빈상태 안내 없음. 파라미터별 `?` 툴팁만.

### 4.6 UI/UX Top 5 격차 (순위·처방)

1. **플롯 비출판급·내보내기 불가**(흐릿·축 단위 없음·PNG/SVG/CSV 없음·라이트테마 비가시) → 캔버스를 `devicePixelRatio` 스케일, 축 제목+단위 렌더, 하드코딩 색을 테마토큰으로, glow/그라디언트 제거, 플롯별 "PNG(300dpi)/SVG/CSV" 버튼(`canvas.toBlob`). (`drawFullChart` `4721-4794`)
2. **실제 GUI 승인 다이얼로그 없음**(터미널 Y/N 타이핑 필요) → 백엔드가 대기 툴콜별 구조화 WS 메시지 방출, "Approve/Deny/Approve all" 버튼 모달 렌더 후 결정 회신. 원시 터미널은 고급뷰로 유지.
3. **반응형 0 + a11y 약함** → ~900px 이하 사이드바를 오버레이 드로어로, 캔버스에 `role="img"`+`aria-label`, 아이콘버튼 라벨, 모든 모달 포커스트랩+Escape, `lang` 수정.
4. **목/데모 콘텐츠가 프로덕션에 혼입** → 모든 목/가상 콘텐츠를 명시적 "Demo mode" 배너 뒤로, 기본 완료-런 경로에서 가짜 감사/채팅 샘플 제거.
5. **실패·장시간 상태 전달 부족 + 온보딩 없음** → `status==='failed'`에 전용 에러카드(마지막 로그+재시도/로그다운로드), 주기적 상태 폴링, 시작가이드 오버레이+빈상태. Google Fonts 로컬 번들로 오프라인 완성, 죽은 `JetBrains Mono` 참조 제거.

---

## 5. 종합 우선순위 로드맵 — bioRxiv 프리프린트 목표

### 5.0 목표 재설정이 바꾸는 것

bioRxiv는 **동료심사 게이트가 없는** 프리프린트 서버다. 스크리닝은 (표절·비과학·이중용도 위험) 기초 심사뿐이며, 본 프로젝트는 자동 통과 수준이다. 따라서 이전 보고서의 "없으면 데스크리젝트(P0)" 프레임은 **더 이상 유효하지 않다.** 대신 세 가지 새 원칙이 우선순위를 지배한다:

1. **프리프린트는 공개·영구·인용 가능한 기록이다** → 하드 게이트는 없어도, **틀리거나(물리 버그) 부정직한(가짜 데이터를 실측처럼 제시) 내용은 절대 실으면 안 된다.** 나중에 저널에 낼 때 그 리뷰어가 프리프린트를 읽으며, 잘못은 영구 박제된다.
2. **버전 관리(v1→v2→v3)가 된다** → 모든 것을 갖추고 낼 필요가 없다. **정직한 최소본을 먼저(v1) 올리고** 강화분을 v2/v3로 얹으면서 그대로 저널 원고로 승격한다.
3. **선점 압박이 실재한다** → 경쟁작 DynaMate(arXiv 2025-12), MDCrow(2025)로 이 분야는 빠르게 채워지는 중. 완벽한 벤치마크를 몇 달 기다리다 우선권을 잃느니, 정직·정확한 v1을 **빨리** 올려 타임스탬프를 확보하는 편이 낫다.

> **핵심 재정렬:** 우선순위 기준이 "리뷰어 게이트 통과"에서 **"정직성·정확성(반드시) → 프리프린트 임팩트(강력히 권장) → 저널 승격 준비(이후)"** 로 이동한다.

### 5.1 티어 A — v1 게시 전 **반드시** (정직성·정확성 방어선)

이것들은 규모는 작지만 **평판·과학적 정직성에 직결**되므로 타협 불가. "공개하면 안 되는 것"을 제거하는 작업이다.

| # | 항목 | 이유(프리프린트 관점) | 출처 | 규모 |
|---|---|---|---|---|
| A1 | **가짜/목 데이터를 실측처럼 보이는 경로 제거·격리** ("Mock AI dialogue", 정적 "4 passed 0 failed" 감사) | 프리프린트 스크린샷/데모에 조작 데이터가 실려선 안 됨 — 최악의 신뢰성 사고 | UI §4.1, §4.6-4 | 小 |
| A2 | **원고 주장을 코드 실제 동작에 일치**시키기 — "per-step validator gate"가 실제로 도는 것만 주장(중성화 게이트는 死코드임을 인지) | 없는 기능을 주장하면 프리프린트가 곧 반증됨 | 기능 §2.1, §2.4 | 小 |
| A3 | **결과를 하나라도 보고한다면** 그 물리 버그부터 수정(에너지드리프트=전체에너지 vs 시간 회귀, `tc-grps` 조성 유도, Berendsen→P-R) | 틀린 물리로 얻은 수치를 프리프린트에 실으면 철회감 | 기능 §2.1, §2.5-2,5 | 中 |
| A4 | **공개 GitHub + Zenodo DOI + 실제 CITATION/저자 메타데이터** | 프리프린트의 "Data/Code availability"에 유효 링크 필수 | 구조 §3.3-3.4 | 小 |
| A5 | **신규성 정직 프레이밍** — "MD용 최초 LLM"(거짓) 아닌 **"투명·브라우저 전달 에이전트 하니스 + 모델무관 백엔드"**, DynaMate/MDCrow 명시 인용·차별 | 선행연구 누락은 프리프린트 신뢰도·후속 저널 모두 훼손 | 웹 §1.2-1.3 | 小 |

### 5.2 티어 B — v1을 **강한 프리프린트로** (게시 전 권장, 임팩트 결정)

프리프린트의 가치는 "인용·주목·우선권"이다. 얇으면 묻히고, 검증표가 하나라도 있으면 급이 달라진다. 시간이 허락하는 만큼 v1에 넣되, 부족하면 v2로 미뤄도 게시 자체는 가능하다.

| # | 항목 | 이유 | 출처 | 규모 |
|---|---|---|---|---|
| B1 | **축소 벤치마크(3~4 시스템)라도 참조값 대비 검증** — 예: ethanol/methane ΔG_hyd, lysozyme RMSD/Rg. 전체 8개가 아니어도 "0개"와는 천지차 | 프리프린트에 실측 검증표 1개 = 임팩트의 핵심 | 기능 §2.5-1 | 中 |
| B2 | **교차모델 신뢰성/성공률 표**(Claude/Codex/Gemini × 시스템, 오류복구율) | 본 프로젝트만의 차별 데이터 — 가장 인용될 그림 | 웹 §1.3, 기능 §2.4 | 中 |
| B3 | **컨테이너 + 핀 고정 환경**(Dockerfile/conda/락파일, req↔pyproject 정합) | "재현하려면 어떻게?"에 답 — 프리프린트 독자가 곧 사용자 | 구조 §3.5-1 | 中 |
| B4 | **출판급 플롯 + 내보내기**(dpi 스케일·축 단위·PNG/SVG/CSV·라이트테마 색버그) | 프리프린트 Figure가 여기서 나옴 | UI §4.6-1 | 中 |
| B5 | **프로버넌스 캡처**(시드 고정, gmx 버전·mdp 해시 → state.json) | "재현 가능" 주장의 물적 근거 | 기능 §2.1 | 小 |

### 5.3 티어 C — v2/프리프린트 개정 & 저널 승격 시

프리프린트 게시 후, 저널(SoftwareX→JCIM) 승격을 노리며 개정 버전에 반영.

| # | 항목 | 출처 |
|---|---|---|
| C1 | 벤치마크를 8개 전 시스템으로 확장 + **불확실도 정량**(블록평균·자기상관·BAR/WHAM 부트스트랩, 오차막대) | 기능 §2.2-2.3, §2.5-3 |
| C2 | **막·복합체 분석 스텁 구현**(면적/두께/질서변수, 리간드 RMSD/접촉맵) | 기능 §2.2 |
| C3 | **핵심 코어 테스트**(run 생성·`/action`·WebSocket·PTY 러너) + CI 매트릭스 + lint/type | 구조 §3.5-2,5 |
| C4 | **GUI 승인 다이얼로그**(구조화 WS + Approve/Deny 버튼) | UI §4.6-2 |
| C5 | server.py `APIRouter` 분해, index.html ES 모듈화, 반응형·a11y·온보딩, LLM 실행 위협모델·샌드박스 | 구조 §3.5-3,4, UI §4.6-3,5 |
| C6 | 자유에너지 창 세분화(decharge/vdw 분리, ≥10창) | 기능 §2.2 |

### 5.4 실행 순서 권고

```
[지금] 티어 A 전체 (1~2주, 소규모·정직성) ──┐
                                          ├─▶ bioRxiv v1 게시 (우선권 확보)
[가능한 만큼] 티어 B1·B2 최소본 ──────────┘
        │
        ▼
[게시 후] 티어 B 잔여 + 티어 C ──▶ bioRxiv v2 (강화) ──▶ SoftwareX/J.Cheminform. 투고
        │
        ▼
[중기] 티어 C 완주 + 전체 벤치마크·불확실도 ──▶ bioRxiv v3 ──▶ JCIM 투고
```

**한 줄 요약:** bioRxiv는 게이트가 없으니 **"완벽"이 아니라 "정직·정확"이 게시 조건**이다. 티어 A(가짜데이터 제거·물리버그·정직한 주장·DOI/인용)만 끝내면 v1 게시가 가능하고, 티어 B의 축소 벤치마크·교차모델 표를 얹을수록 프리프린트의 인용 가치가 오른다. 나머지(티어 C)는 버전 개정으로 얹으며 그대로 저널 원고로 키운다.

---

*보고서 생성: 4개 병렬 서브에이전트(경쟁지형·기능·구조·UI/UX) 평가 종합. §5는 bioRxiv 프리프린트 목표로 재구성(2026-07-08). 인용된 파일/라인은 커밋 `b3b30d2` 기준.*
