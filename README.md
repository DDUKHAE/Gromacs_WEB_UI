# GROMACS Web UI Harness

PDB + 자연어 prompt 입력으로 GROMACS 분자동역학(MD) 파이프라인을 3개의 capability-aligned skill(`env_builder`, `md_runner`, `illustrator`)로 자율 실행하는 LLM 오케스트레이션 하네스 + 웹 UI.

## 주요 기능

- **웹 UI** — PDB 파일 업로드 또는 PDB 코드 입력으로 MD 시뮬레이션 실행 및 결과 시각화
- **3-Skill 파이프라인** — 각 skill은 독립 호출 가능하며 파일 기반으로 체이닝됨
  - `skills/env_builder/` — Step 0–5: 하드웨어 프로파일, 튜토리얼 라우팅, topology/box/solvate/ions
  - `skills/md_runner/` — Step 6–7: phase별 grompp+mdrun, validator gate, retry/WARNING 처리
  - `skills/illustrator/` — Step 8: RMSD/RMSF/PCA/DSSP/SASA + matplotlib 플롯 + 렌더 + markdown 리포트
- **8개 튜토리얼 라우팅** — Lysozyme / KALP15 / Protein-Ligand / Umbrella / Biphasic / FE-Methane / FE-Ethanol / Virtual_Sites
- **테스트 데이터 내장** — `tutorial_data/` — RCSB + mdtutorials.com에서 수집한 표준 입력 파일

## Directory Layout

```
.
├── main.py                    웹 서버 진입점
├── pyproject.toml             pytest 설정
├── lib/                       내부 helper (state, validators, gmx_wrapper, xvg_parser, tutorial_registry, mdp_templates/)
├── skills/
│   ├── env_builder/           Step 0–5 (SKILL.md + env_builder.py + references/)
│   ├── md_runner/             Step 6–7 (SKILL.md + md_runner.py + references/)
│   └── illustrator/           Step 8   (SKILL.md + illustrator.py + references/)
├── web/                       FastAPI 서버 + LLM 어댑터 + 정적 UI
│   ├── server.py
│   ├── runner.py
│   ├── llm_runner.py
│   ├── run_reader.py
│   ├── llm_adapters/          Claude / Gemini / Codex 어댑터
│   └── static/index.html      단일 페이지 UI
├── docs/
│   ├── STATE_SCHEMA.md
│   ├── WARNING_FLOW.md
│   ├── independent_entry_guide.md
│   ├── pipeline_contract.md
│   ├── runbook.md
│   ├── simulation_criteria.md
│   └── tutorial/              8개 튜토리얼 참조 문서
├── scripts/
│   ├── check_gromacs_env.py
│   └── regression/            튜토리얼별 회귀 테스트 스크립트
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── web/
├── tutorial_data/             테스트용 입력 파일 (튜토리얼별 분류)
│   ├── Lysozyme_in_water/     1AKI.pdb
│   ├── Protein_Ligand_Complex/ 3HTB.pdb
│   ├── Umbrella_Sampling/     2BEG.pdb, 2BEG_model1_capped.pdb
│   ├── KALP15_in_DPPC/        KALP-15_princ.pdb
│   ├── Free_Energy_Methane_in_Water/ methane_water.gro, topol.top
│   ├── Free_Energy_Ethanol/   etoh.pdb
│   ├── Building_Biphasic_Systems/ chx.gro, chx.top, chx_10ns.gro
│   └── Virtual_Sites/         co2.pdb
├── AGENTS.md                  LLM 운영 규칙 + skill 자원 매핑
├── ARCHITECTURE.md            Step 0–8 계약, 3-skill 매핑
└── CONTRIBUTING.md            기여 가이드
```

## Prerequisites

| 항목 | 버전 | 비고 |
|---|---|---|
| Python | 3.11+ | |
| GROMACS | 2022+ | `gmx` on PATH, conda-forge::gromacs 권장 |
| matplotlib | 최신 | illustrator 플롯 (선택) |
| PyMOL or VMD | 최신 | 구조 렌더 (선택) |
| ffmpeg | 최신 | 트래젝토리 애니메이션 (선택) |

## Quick Start

### 1. 저장소 클론

```bash
git clone https://github.com/DDUKHAE/Gromacs_WEB_UI.git
cd Gromacs_WEB_UI
```

### 2. GROMACS 환경 구성

```bash
conda create -n GROMACS -y -c conda-forge gromacs python=3.11
conda activate GROMACS
pip install fastapi uvicorn anthropic
```

### 3. API 키 설정 (LLM 연동 시)

```bash
export ANTHROPIC_API_KEY="your-key"   # Claude
# export GEMINI_API_KEY="your-key"    # Gemini (선택)
```

### 4. 웹 서버 실행

```bash
python main.py
```

브라우저가 자동으로 `http://localhost:8000` 을 엽니다.

```bash
python main.py --port 8080          # 포트 변경
python main.py --host 0.0.0.0       # 외부 접속 허용
python main.py --no-browser         # 브라우저 자동 오픈 비활성화
```

### 5. 환경 확인

```bash
python scripts/check_gromacs_env.py
```

## 테스트

### 단위/계약 테스트 (GROMACS 불필요)

```bash
pytest tests/unit tests/contract -v
```

### 웹 API 테스트

```bash
pytest tests/web -v
```

### 통합 테스트 (GROMACS 필요)

```bash
pytest tests/integration -v
```

### 튜토리얼 데이터를 활용한 테스트

`tutorial_data/` 디렉터리의 파일을 웹 UI에 업로드하거나 회귀 스크립트로 실행하는 방법은 [`docs/TESTING_WITH_TUTORIAL_DATA.md`](docs/TESTING_WITH_TUTORIAL_DATA.md)를 참조하세요.

## 3-Skill 파이프라인 구조

```
PDB + prompt ──► env_builder ──► md_runner ──► illustrator ──► report.md
                  (Step 0–5)      (Step 6–7)      (Step 8)
                       │              │               │
                       └──── workspace/state.json + stage{1,2,3}_*/ ────┘
```

각 skill은 `workspace/state.json` + 디렉터리만 공유한다. 외부 도구(예: CHARMM-GUI)에서 받은 산출물로 `md_runner`나 `illustrator`만 단독 실행도 가능 — [`docs/independent_entry_guide.md`](docs/independent_entry_guide.md) 참조.

## Programmatic Use

```python
from pathlib import Path
from skills.env_builder import build_environment
from skills.md_runner import run_simulation
from skills.illustrator import illustrate

ws = Path("runs/my_run").resolve()
build_environment(
    pdb_path=Path("tutorial_data/Lysozyme_in_water/1AKI.pdb").resolve(),
    prompt="protein in water, CHARMM36 force field",
    workspace_dir=ws,
    prerequisites={},
    interactive=False,
)
run_simulation(workspace_dir=ws, interactive=False)
illustrate(workspace_dir=ws, animation={"enabled": False})
# 결과: ws/stage3_viz/report.md
```

## Documentation

| 문서 | 용도 |
|---|---|
| [`AGENTS.md`](AGENTS.md) | LLM 운영 규칙 + skill 자원 매핑 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Step 0–8 계약, 3-skill 매핑 |
| [`docs/STATE_SCHEMA.md`](docs/STATE_SCHEMA.md) | `workspace/state.json` 정식 스키마 |
| [`docs/pipeline_contract.md`](docs/pipeline_contract.md) | Step별 입출력/안전 계약 |
| [`docs/simulation_criteria.md`](docs/simulation_criteria.md) | 검증 임계값 |
| [`docs/WARNING_FLOW.md`](docs/WARNING_FLOW.md) | 사용자 결정형 WARNING 분기 |
| [`docs/runbook.md`](docs/runbook.md) | 수동 복구 절차 |
| [`docs/independent_entry_guide.md`](docs/independent_entry_guide.md) | 단독 진입 시나리오 |
| [`docs/TESTING_WITH_TUTORIAL_DATA.md`](docs/TESTING_WITH_TUTORIAL_DATA.md) | 튜토리얼 데이터 테스트 가이드 |
| [`docs/tutorial/LLM_TUTORIAL_GUIDE.md`](docs/tutorial/LLM_TUTORIAL_GUIDE.md) | 튜토리얼 라우팅 결정 트리 |

## License

MIT — `LICENSE` 참조.

GROMACS 자체는 LGPL-2.1로 별도 배포되며 이 저장소는 GROMACS를 호출만 한다.
