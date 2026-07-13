# GROMACS Web UI

PDB 파일 업로드 한 번으로 GROMACS 분자동역학(MD) 시뮬레이션을 브라우저에서 완전 제어하는 웹 하네스.  
LLM(Claude / Codex / Gemini)이 입력 데이터와 튜토리얼 문서를 기반으로 각 Step을 순서대로 따라가며 실행하거나, 직접 단계별 제어도 지원합니다.

---

## Features

### MD 시뮬레이션 파이프라인

```mermaid
flowchart LR
    A([PDB 파일]) --> B

    subgraph B["시스템 준비 (Step 0–5)"]
        B1[Topology 생성] --> B2[박스 정의]
        B2 --> B3[용매화]
        B3 --> B4[이온 배치]
    end

    B --> C

    subgraph C["MD 시뮬레이션 (Step 6–7)"]
        C1[Energy minimization] --> C2[NVT 평형화]
        C2 --> C3[NPT 평형화]
        C3 --> C4[Production MD 실행]
    end

    C --> D

    subgraph D["트래젝토리 분석 (Step 8)"]
        D1[RMSD / RMSF / PCA]
        D2[DSSP / SASA]
        D3[XVG 플롯 갤러리]
    end
```

### 실행 모드

- **직접 제어** — 각 Stage 완료 후 사용자가 **Continue** / **Abort** 로 진행 여부 결정
- **LLM 튜토리얼 실행** — LLM 에이전트가 입력 데이터와 튜토리얼 문서를 기반으로 각 Step을 순서대로 따라가며 실행하고, 도구 승인 요청 발생 시 Y/N 팝업으로 처리
- **System Builder** — 런 시작 전 MD 시스템 파라미터를 설정하는 6단계 마법사. 설정을 프리셋으로 저장·재사용하고, LLM 프롬프트에 강제 제약으로 주입

### System Builder

```
Step 1 → Step 2 → Step 3 → Step 4 → [Step 5]  → Step 6
PDB       Force    박스      이온     시뮬레이션  검토 &
업로드    Field             설정     (Expert)    시작
```

마법사가 생성한 `system_config.json`은 LLM 프롬프트에 "반드시 따라야 할 제약"으로 주입되지만, 이는 프롬프트 상의 지시일 뿐 프로그램적으로 강제되지는 않습니다. Force field, Water model, Box 형태·크기, 이온 종류·농도를 기본 파라미터로 설정하며, Expert 모드에서는 온도, 압력, 시뮬레이션 시간, Thermostat, Barostat까지 제어할 수 있습니다. 설정을 프리셋으로 저장해 다음 런에서 바로 불러올 수 있으며, 런 완료 후 `/api/runs/{id}/audit` 엔드포인트(`lib/system_config_validator.py`)는 이 중 **3개 파라미터**(force field 접두사, water model, box type)만 `state.json` 기록값과 비교해 pass/fail을 보고합니다. mdp 파라미터(온도·압력·dt·thermostat/barostat 선택), 이온 농도, 양성자화 상태는 감사되지 않으며, 이 3개 항목 밖에서 LLM이 지시를 이탈해도 이를 막는 구조적 장치는 없습니다. [Limitations](#limitations-한계) 참고.

### 지원 LLM

Claude Code, OpenAI Codex CLI, Gemini CLI를 지원합니다. 각 LLM은 PTY 프로세스로 실행되며, WebSocket + xterm.js 터미널을 통해 출력이 브라우저에 실시간 스트리밍됩니다.

---

## 지원 튜토리얼

| 튜토리얼                           | 시스템                                 |
| ---------------------------------- | -------------------------------------- |
| Lysozyme in Water                  | 수용액 중 구형 단백질                  |
| KALP15 in DPPC                     | 지질 이중층 내 막관통 펩타이드         |
| Protein-Ligand Complex             | 단백질-소분자 결합 시스템              |
| Umbrella Sampling                  | 평균력 포텐셜(PMF) / 자유에너지 샘플링 |
| Building Biphasic Systems          | 소수성/수성 이상계 계면                |
| Free Energy of Hydration (Methane) | 연금술적 자유에너지 섭동               |
| Free Energy of Hydration (Ethanol) | 연금술적 자유에너지 섭동 (CGenFF)      |
| Virtual Sites                      | 가상 상호작용 사이트를 통한 강체 구속  |

---

## Installation

### 필수 항목

| 항목               | 필요한 기능                                                                                               |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| Python 3.13        | 웹 서버 런타임 (FastAPI + uvicorn)                                                                        |
| GROMACS 2026.0     | 파이프라인 전 단계 — Topology / 용매화 / 평형화 / Production run / 분석                                   |
| `requirements.txt` | REST API · WebSocket 서버 + 트래젝토리 분석 플롯 (`fastapi`, `uvicorn`, `python-multipart`, `matplotlib`) |

### 선택 항목

| 항목            | 필요한 기능                       |
| --------------- | --------------------------------- |
| PyMOL           | 단백질 구조 시각화                |
| VMD             | 단백질 구조 / 트래젝토리 시각화   |
| ffmpeg          | 트래젝토리 애니메이션 렌더링      |
| Claude Code CLI | LLM 튜토리얼 실행 — Claude        |
| Codex CLI       | LLM 튜토리얼 실행 — OpenAI Codex  |
| Gemini CLI      | LLM 튜토리얼 실행 — Google Gemini |

---

### Linux

```bash
# 1. Miniforge 설치 (conda가 없는 경우)
#    설치 스크립트 다운로드 후 실행: https://github.com/conda-forge/miniforge

# 2. conda 환경 생성 (Python 3.13 + GROMACS)
conda create -n gromacs_web -c conda-forge gromacs python=3.13 -y
conda activate gromacs_web

# 3. 저장소 클론 및 Python 의존성 설치
git clone https://github.com/DDUKHAE/Gromacs_WEB_UI.git
cd Gromacs_WEB_UI
pip install -r requirements.txt

# 4. 설치 확인
gmx --version
python scripts/check_gromacs_env.py   # GROMACS + 선택 도구 전체 진단 (JSON 출력)

# ── 선택 항목 ────────────────────────────────────────────────────────────
# ffmpeg (트래젝토리 애니메이션)
sudo apt install ffmpeg

# PyMOL (구조 시각화 — 오픈소스 빌드)
conda install -c conda-forge pymol-open-source
# VMD (구조/트래젝토리 시각화): https://www.ks.uiuc.edu/Research/vmd/

# LLM CLI (튜토리얼 실행 모드) — Node.js 필요
npm install -g @anthropic-ai/claude-code    # Claude Code
npm install -g @openai/codex                # Codex CLI  (https://github.com/openai/codex)
npm install -g @google/gemini-cli           # Gemini CLI (https://github.com/google-gemini/gemini-cli)
# ─────────────────────────────────────────────────────────────────────────

# 5. 서버 실행 → 브라우저 자동 오픈 (http://localhost:8000)
python main.py
```

---

### macOS

```bash
# 1. Miniforge 설치 (conda가 없는 경우)
#    설치 스크립트 다운로드 후 실행: https://github.com/conda-forge/miniforge

# 2. conda 환경 생성 (Python 3.13 + GROMACS)
conda create -n gromacs_web -c conda-forge gromacs python=3.13 -y
conda activate gromacs_web

# 3. 저장소 클론 및 Python 의존성 설치
git clone https://github.com/DDUKHAE/Gromacs_WEB_UI.git
cd Gromacs_WEB_UI
pip install -r requirements.txt

# 4. 설치 확인
gmx --version
python scripts/check_gromacs_env.py

# ── 선택 항목 ────────────────────────────────────────────────────────────
# ffmpeg (트래젝토리 애니메이션)
brew install ffmpeg

# PyMOL (구조 시각화 — 오픈소스 빌드)
conda install -c conda-forge pymol-open-source
# VMD (구조/트래젝토리 시각화): https://www.ks.uiuc.edu/Research/vmd/

# LLM CLI (튜토리얼 실행 모드) — Node.js 필요
npm install -g @anthropic-ai/claude-code    # Claude Code
npm install -g @openai/codex                # Codex CLI  (https://github.com/openai/codex)
npm install -g @google/gemini-cli           # Gemini CLI (https://github.com/google-gemini/gemini-cli)
# ─────────────────────────────────────────────────────────────────────────

# 5. 서버 실행 → 브라우저 자동 오픈 (http://localhost:8000)
python main.py
```

---

### Windows

WSL2 (Ubuntu) 설치를 권장합니다. WSL 터미널을 열고 Linux 방법을 따릅니다.

네이티브 Windows에서 실행하려면 [Miniforge Windows 인스톨러](https://github.com/conda-forge/miniforge)를 설치한 뒤 Anaconda Prompt에서 아래 명령을 실행합니다.

```bash
# 1. conda 환경 생성 (Python 3.13 + GROMACS)
conda create -n gromacs_web -c conda-forge gromacs python=3.13 -y
conda activate gromacs_web

# 2. 저장소 클론 및 Python 의존성 설치
git clone https://github.com/DDUKHAE/Gromacs_WEB_UI.git
cd Gromacs_WEB_UI
pip install -r requirements.txt

# 3. 설치 확인
gmx --version
python scripts/check_gromacs_env.py

# ── 선택 항목 ────────────────────────────────────────────────────────────
# ffmpeg (트래젝토리 애니메이션): https://ffmpeg.org/download.html 에서 다운로드 후 PATH 추가

# PyMOL (구조 시각화 — 오픈소스 빌드)
conda install -c conda-forge pymol-open-source
# VMD (구조/트래젝토리 시각화): https://www.ks.uiuc.edu/Research/vmd/

# LLM CLI (튜토리얼 실행 모드) — Node.js 필요
npm install -g @anthropic-ai/claude-code    # Claude Code
npm install -g @openai/codex                # Codex CLI  (https://github.com/openai/codex)
npm install -g @google/gemini-cli           # Gemini CLI (https://github.com/google-gemini/gemini-cli)
# ─────────────────────────────────────────────────────────────────────────

# 4. 서버 실행 → 브라우저 자동 오픈 (http://localhost:8000)
python main.py
```

서버 실행 옵션:

```bash
python main.py --port 8080   # 포트 변경
python main.py --listen      # 0.0.0.0 바인딩 (같은 네트워크의 다른 기기에서 접속)
python main.py --no-browser  # 브라우저 자동 오픈 비활성화
```

---

## Force Field 안내

각 튜토리얼은 원본(mdtutorials.com) 기준의 force field를 그대로 사용합니다.

### GROMACS에 기본 포함된 Force Field

`conda-forge::gromacs` 설치 시 아래 force field가 `$GMXLIB`에 자동 포함됩니다.

| Force Field      | 해당 튜토리얼                                         |
| ---------------- | ----------------------------------------------------- |
| `oplsaa`         | Lysozyme (대체), Free Energy (Methane), Virtual Sites |
| `gromos53a6`     | Umbrella Sampling, KALP15 in DPPC                     |
| `gromos43a1`     | Building Biphasic Systems                             |
| `amber99sb-ildn` | —                                                     |
| `charmm27`       | —                                                     |

### 별도 설치 필요: CHARMM36

CHARMM36은 GROMACS 패키지에 포함되지 않으며, 아래 튜토리얼에서 요구합니다.

| 튜토리얼                   | 이유                                         |
| -------------------------- | -------------------------------------------- |
| **Lysozyme in Water**      | Justin Lemkul 최신 튜토리얼 기준 force field |
| **Protein-Ligand Complex** | CGenFF 소분자 파라미터와의 일관성 유지       |
| **Free Energy (Ethanol)**  | CHARMM General Force Field (CGenFF) 사용     |

MacKerell 연구실 공식 배포 페이지에서 "CHARMM36 force field for GROMACS" 항목을 다운로드하세요:  
https://mackerell.umaryland.edu/charmm_ff.shtml

---

## 사용 방법

### 새 시뮬레이션 시작 (System Builder 마법사)

1. **New Run** 클릭 → 6단계 System Builder 마법사 열림
2. **Step 1** — PDB 파일 업로드 (드래그&드롭 또는 클릭). **Expert Mode** 토글 시 Step 5 (시뮬레이션 파라미터) 활성화
3. **Step 2** — Force field / Water model 선택
4. **Step 3** — Box 형태와 Edge distance 설정
5. **Step 4** — Salt 종류 및 이온 농도 설정
6. **Step 5** *(Expert 전용)* — 온도, 압력, 시뮬레이션 시간, Thermostat, Barostat 설정
7. **Step 6** — 전체 설정 검토, 프리셋 저장(선택), LLM 선택 후 **Start** 클릭

### LLM 튜토리얼 실행 모드

- LLM 에이전트가 입력 데이터와 튜토리얼 문서를 기반으로 각 Step을 순서대로 따라가며 실행
- 도구 승인 요청 발생 시 Permission 다이얼로그 자동 팝업 → Y/N 응답
- 내장 xterm.js 터미널에서 에이전트 출력 실시간 확인

### 직접 제어 모드

- `env-builder` 완료 후 **Continue** → `md-runner` 시작
- `md-runner` 완료 후 **Continue** → `illustrator` 시작
- 언제든 **Abort** 로 파이프라인 중단 가능

### 결과 확인

파이프라인 완료 후 **Results Gallery** 패널에서 XVG 출력 파일로부터 파싱된 RMSD, RMSF, 에너지 플롯 확인

---

## 디렉터리 구조

```
.
├── main.py                    서버 진입점 (uvicorn 래퍼)
├── pyproject.toml             Python 패키지 설정
├── requirements.txt           Python 의존성
├── AGENTS.md                  LLM 운영 규칙 + skill 자원 매핑
├── ARCHITECTURE.md            Step 0–8 계약, 3-skill 매핑
│
├── web/                       FastAPI 웹 서버
│   ├── server.py              REST API + WebSocket 엔드포인트
│   ├── llm_runner.py          PTY 기반 LLM 프로세스 관리
│   ├── runner.py              직접 실행 subprocess 래퍼
│   ├── run_reader.py          실행 상태 파일 파서
│   ├── llm_adapters/          Claude / Codex / Gemini CLI 어댑터
│   └── static/
│       ├── index.html         단일 페이지 프론트엔드 (vanilla JS)
│       ├── xterm.js           터미널 에뮬레이터
│       └── xterm-addon-fit.js 터미널 자동 크기 조정 애드온
│
├── skills/                    3단계 파이프라인 스킬
│   ├── env_builder/           Step 0–5: topology / box / solvate / ions
│   ├── md_runner/             Step 6–7: grompp + mdrun, retry 처리
│   └── illustrator/           Step 8: RMSD/RMSF/PCA + 플롯 + 리포트
│
├── lib/                       내부 공용 라이브러리
│   ├── system_config.py       System Builder — 설정 검증 + LLM 제약 프롬프트 생성
│   ├── system_config_validator.py  런 완료 후 감사: Builder 설정 vs LLM 실제 사용값 비교
│   ├── xvg_parser.py          XVG 파일 파서 (분석 갤러리 백엔드)
│   ├── state.py               workspace/state.json 입출력
│   ├── validators.py          Step별 검증 게이트
│   ├── gmx_wrapper.py         GROMACS 명령 래퍼
│   ├── tutorial_registry.py   튜토리얼 라우팅 로직
│   └── mdp_templates/         MDP 파라미터 템플릿
│
├── presets/                   저장된 System Builder 프리셋 (사용자 생성, gitignore)
├── tutorial_data/             8개 튜토리얼 표준 입력 파일 (PDB/GRO/TOP)
│
├── scripts/
│   ├── check_gromacs_env.py   의존성 진단 — GROMACS + 선택 도구 (JSON 출력)
│   └── regression/            튜토리얼별 회귀 테스트 스크립트
│
└── docs/
    ├── STATE_SCHEMA.md        workspace/state.json 공식 스키마
    ├── pipeline_contract.md   Step별 입출력/안전 계약
    ├── WARNING_FLOW.md        사용자 결정형 WARNING 분기 로직
    ├── runbook.md             수동 복구 절차
    └── tutorial/
        ├── tutorial_index.json         전체 매니페스트 레지스트리
        └── <튜토리얼>/tutorial.manifest.json  튜토리얼별 매니페스트 + 단계 문서
```

---

## Tutorial Manifest 시스템

각 튜토리얼은 **매니페스트**(`tutorial.manifest.json`)로 정의됩니다. 매니페스트는 force field 기본값, 시뮬레이션 박스 파라미터, 활성 파이프라인 단계, Step별 문서 참조를 선언하는 라우팅 계약입니다.

```jsonc
{
  "id": "Lysozyme_in_water",
  "pipeline_variant": "protein_aqueous_standard",
  "required_inputs": ["protein_pdb"],
  "defaults": { "forcefield": "charmm36", "water_model": "tip3p", "box_type": "cubic" },
  "architecture_steps": [0, 1, 2, 3, 4, 5, 6, 7, 8],
  "documents": { "step_1": "generate_topology/prepare_the_topology.md", ... },
  "validation_profile": "standard_protein_water"
}
```

기본 8개 매니페스트는 저장소에 포함되어 별도 설치가 필요 없습니다. 모든 매니페스트는 `docs/tutorial/tutorial_index.json` 레지스트리에 등록되며, `lib/tutorial_registry.py`가 이를 읽어 입력 PDB/프롬프트에 맞는 튜토리얼로 라우팅합니다.

### 새 매니페스트 등록 방법

```bash
# 1. 튜토리얼 디렉터리 + 매니페스트 파일 생성
#    기존 매니페스트를 docs/tutorial/<NewTutorial>/tutorial.manifest.json 으로 복사해 수정

# 2. Step별 가이드 문서 배치 (manifest의 "documents" 경로와 일치해야 함)
#    예: docs/tutorial/<NewTutorial>/generate_topology/...md

# 3. docs/tutorial/tutorial_index.json 의 "entries" 배열에 항목 추가
#    { "id": "...", "manifest_path": "...", "required_inputs": [...], ... }

# 4. (선택) lib/tutorial_registry.py 의 KEYWORDS 딕셔너리에 키워드 라우팅 추가

# 5. 등록 확인
python -c "from lib.tutorial_registry import load_manifest; print(load_manifest('<NewTutorial>'))"
```

> `tutorial_index.json`에 등록되지 않은 매니페스트는 하네스가 인식하지 못합니다. 레지스트리 등록이 곧 "설치"입니다.

---

## 문서

| 문서                                                                         | 용도                               |
| ---------------------------------------------------------------------------- | ---------------------------------- |
| [`AGENTS.md`](AGENTS.md)                                                     | LLM 운영 규칙 + skill 자원 매핑    |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)                                         | Step 0–8 계약, 3-skill 매핑        |
| [`docs/STATE_SCHEMA.md`](docs/STATE_SCHEMA.md)                               | `workspace/state.json` 공식 스키마 |
| [`docs/pipeline_contract.md`](docs/pipeline_contract.md)                     | Step별 입출력/안전 계약            |
| [`docs/WARNING_FLOW.md`](docs/WARNING_FLOW.md)                               | 사용자 결정형 WARNING 분기 로직    |
| [`docs/runbook.md`](docs/runbook.md)                                         | 수동 복구 절차                     |
| [`docs/tutorial/LLM_TUTORIAL_GUIDE.md`](docs/tutorial/LLM_TUTORIAL_GUIDE.md) | 튜토리얼 라우팅 결정 트리          |
| [`TESTING_WITH_TUTORIAL_DATA.md`](TESTING_WITH_TUTORIAL_DATA.md)             | 튜토리얼 데이터 회귀 테스트 가이드 |

---

## Limitations (한계)

이 절은 이 코드베이스의 자동 검증이 실제로 무엇을 커버하고 무엇을 커버하지 않는지 정확히 명시합니다. 이 README의 다른 곳에 이보다 더 강하게 들리는 표현이 있다면, 범위가 다르다는 뜻이 아니라 문구가 부정확한 것으로 간주해 주세요.

- **Config audit는 3개 파라미터만 검사하며 "런 전체"를 검증하지 않습니다.** `lib/system_config_validator.py::validate_run_against_config`는 force field 접두사, water model, box type만 `state.json`과 비교합니다. mdp 파라미터(온도·압력·`dt`·thermostat/barostat 선택·cutoff), 이온 농도, 양성자화 상태는 검사하지 않습니다 — LLM 에이전트가 이 값들을 몰래 바꿔도 감사는 3개 항목에서만 pass를 보고합니다. `lib/system_config.py`가 생성하는 제약 프롬프트("MUST FOLLOW")는 어디까지나 LLM 지시문에 삽입되는 조언 텍스트이며, 위 3개 항목 감사 외에는 프로그램적 강제가 없습니다.
- **LLM의 프로토콜 이탈 전반에 대한 구조적 방어는 없습니다.** `run_llm_agent`(`web/llm_runner.py`)는 PTY 출력과 종료코드만 기록하며, 에이전트가 튜토리얼이 의도한 명령을 실제로 실행했는지, 의도한 mdp 값을 썼는지, "완료" 상태를 조작하지 않았는지는 검증하지 않습니다. 실제로 실행되는 물리 검증은 `lib/validators.py`의 단계별 게이트(중성화·밀도·에너지 드리프트·RMSD 평탄화)뿐이며, 이 게이트들이 측정하지 않는 것은 검증되지 않습니다.
- **에너지 드리프트 게이트는 거칠고 시스템 크기로 정규화되지 않습니다.** `_judge_energy_drift`(`skills/md_runner/md_runner.py`)는 **전체(total)** 에너지의 시뮬레이션 시간(ns) 대비 선형회귀 기울기를 계산합니다(이전의 "퍼텐셜 에너지 ÷ 프레임 수" 버그는 수정됨). pass/warning/retryable 임계값(`lib/validators.py`의 `ENERGY_DRIFT_WARNING`/`ENERGY_DRIFT_RETRY`)은 고정된 절대 kJ/mol/ns 값이며 원자 수로 정규화되지 않습니다 — 같은 원자당 안정성이라도 큰 용매화 시스템은 작은 시스템보다 절대 에너지 변동이 크게 나타납니다. 이 게이트는 정밀 진단이 아니라 명백한 적분 불안정을 걸러내는 거친 필터입니다.
- **밀도 게이트는 단일 벌크 밀도가 물리적으로 의미 있는 계에만 적용됩니다.** 막(membrane), biphasic 등 단일상 수용성 벌크가 아닌 계에서는 게이트가 건너뛰어집니다(`skills/md_runner/md_runner.py`의 `_density_expected_range`, `density_gate_not_applicable_for_system_type`로 pass 처리).
- **런 재현성/프로버넌스 기록이 없습니다.** `nvt.mdp`는 `gen_seed = -1`(비재현 초기 속도)을 사용하며, `state.json`에는 `gmx` 바이너리 버전, mdp 파일 해시, 실제 사용된 시드가 기록되지 않습니다. 동일 튜토리얼의 두 런이 동일하거나 통계적으로 동등함이 보장되거나 검증되지 않습니다. 이 프로버넌스 기록은 계획 중이나 아직 구현되지 않았습니다.
- **분석 결과에 불확실도 정량화가 없습니다.** RMSD/RMSF/Rg/SASA/에너지 요약(`lib/xvg_parser.py`)은 궤적에 대한 원시 평균/표준편차이며, 블록 평균·자기상관 시간 추정·신뢰구간이 없습니다.
- **막/단백질-리간드 분석 2종은 스텁입니다.** `_run_membrane_analysis`, `_run_protein_ligand_analysis`(`skills/illustrator/illustrator.py`)는 `{"status": "stub"}`만 반환합니다 — 해당 튜토리얼 변형에 대한 이중층 두께/면적당지질/order parameter 또는 리간드 RMSD/접촉맵 출력이 아직 없습니다.

---

## License

MIT — [`LICENSE`](LICENSE) 참조.

GROMACS 자체는 LGPL-2.1로 별도 배포되며, 이 저장소는 GROMACS를 외부 바이너리로 호출만 합니다.
