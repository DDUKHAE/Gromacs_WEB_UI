# GROMACS Harness

PDB + 자연어 prompt 입력으로 GROMACS 분자동역학(MD) 파이프라인을 세 capability-aligned skill(`env-builder`, `md-runner`, `illustrator`)로 자율 실행하는 LLM 오케스트레이션 하네스.

## What This Repository Provides

- **3 skill 실행 모델** — 각 skill은 독립 호출 가능하며 파일 기반으로 체이닝됨
  - `skills/env_builder/` — Step 0–5: 하드웨어 프로파일, 튜토리얼 라우팅, topology/box/solvate/ions (CHARMM-GUI workflow를 로컬에서 GROMACS native로 재현)
  - `skills/md_runner/` — Step 6–7: phase별 grompp+mdrun, validator gate, retry/WARNING 처리
  - `skills/illustrator/` — Step 8: RMSD/RMSF/PCA/DSSP/SASA + matplotlib 플롯 + PyMOL/VMD 렌더 + ffmpeg 애니메이션 + markdown 리포트
- **공용 내부 라이브러리** `lib/` — state.py, validators.py, gmx_wrapper.py, xvg_parser.py, tutorial_registry.py, mdp_templates/
- **상태 기반 계약** — `workspace/state.json`이 single source of truth ([`docs/STATE_SCHEMA.md`](docs/STATE_SCHEMA.md))
- **8개 튜토리얼 라우팅** — Lysozyme / KALP15 / Protein-Ligand / Umbrella / Biphasic / FE-Methane / FE-Ethanol / Virtual_Sites
- **회귀 테스트 스크립트** — `scripts/regression/`

## Directory Layout

```
.
├── AGENTS.md                  운영 규칙 + skill 자원 매핑
├── ARCHITECTURE.md            Step 0–8 + 3-skill 매핑
├── CONTRIBUTING.md            기여 가이드
├── LICENSE                    MIT
├── pyproject.toml             pytest 설정
├── lib/                       내부 helper (state, validators, gmx_wrapper, …)
├── skills/                    3개 skill (SKILL.md + 코드 + references/)
├── docs/
│   ├── STATE_SCHEMA.md
│   ├── WARNING_FLOW.md
│   ├── independent_entry_guide.md
│   ├── pipeline_contract.md
│   ├── runbook.md
│   ├── simulation_criteria.md
│   ├── tutorial/              8개 튜토리얼 + 라우팅 가이드
│   └── superpowers/           spec/plan 이력
├── scripts/
│   ├── check_gromacs_env.py
│   └── regression/            튜토리얼별 + 공용 runner
└── tests/{unit,contract,integration}/
```

## Prerequisites

- macOS / Linux shell
- Python 3.11+
- GROMACS (`gmx` on PATH) — `conda-forge::gromacs` 권장
- (선택) `pip install matplotlib` — illustrator 플롯
- (선택) PyMOL 또는 VMD — illustrator 구조 렌더
- (선택) `ffmpeg` — illustrator 트래젝토리 애니메이션

## Quick Start

### Web UI (권장)

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/gromacs-harness.git
cd gromacs-harness

# 2. GROMACS 환경 구성
conda create -n GROMACS -y -c conda-forge gromacs python=3.11
conda activate GROMACS

# 3. 실행 (의존성 자동 설치 후 브라우저 오픈)
python main.py
```

브라우저가 자동으로 `http://localhost:8000` 을 엽니다.

```
python main.py --port 8080          # 포트 변경
python main.py --host 0.0.0.0       # 외부 접속 허용
python main.py --no-browser         # 브라우저 자동 오픈 비활성화
```

### CLI / 개발

```bash
# 환경 확인
python scripts/check_gromacs_env.py
pytest tests -v   # GROMACS 없이도 unit/contract 모두 통과

# 회귀 테스트 (GROMACS 머신)
./scripts/regression/lysozyme.sh        # 1UBQ.pdb 기본 회귀
./scripts/regression/kalp15.sh          # 막 단백질
./scripts/regression/protein_ligand.sh  # 단백질-리간드
# ... umbrella, biphasic, fe_methane, fe_ethanol, virtual_sites
```

## 3-Skill 호출 모델

```
PDB + prompt ──► env-builder ──► md-runner ──► illustrator ──► report.md
                  (Step 0–5)      (Step 6–7)      (Step 8)
                       │             │              │
                       └── workspace/state.json + stage{1,2,3}_*/ ──┘
```

각 skill은 `workspace/state.json` + 디렉터리만 공유한다. 외부 도구(예: CHARMM-GUI 다운로드)에서 받은 산출물로 `md-runner`나 `illustrator`만 단독 실행도 가능 — [`docs/independent_entry_guide.md`](docs/independent_entry_guide.md) 참조.

## Programmatic Use

```python
from pathlib import Path
from skills.env_builder import build_environment
from skills.md_runner import run_simulation
from skills.illustrator import illustrate

ws = Path("runs/my_run").resolve()
build_environment(
    pdb_path=Path("1UBQ.pdb").resolve(),
    prompt="protein in water",
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
| [`docs/simulation_criteria.md`](docs/simulation_criteria.md) | 검증 임계값 (코드와 동기화) |
| [`docs/WARNING_FLOW.md`](docs/WARNING_FLOW.md) | 사용자 결정형 WARNING 분기 |
| [`docs/runbook.md`](docs/runbook.md) | 수동 복구 절차 |
| [`docs/independent_entry_guide.md`](docs/independent_entry_guide.md) | 단독 진입 시나리오 |
| [`docs/tutorial/LLM_TUTORIAL_GUIDE.md`](docs/tutorial/LLM_TUTORIAL_GUIDE.md) | 튜토리얼 라우팅 결정 트리 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 기여 가이드 |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | 설계 spec 이력 |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | 구현 plan 이력 |

## License

MIT — `LICENSE` 참조.

GROMACS 자체는 LGPL-2.1로 별도 배포되며 이 저장소는 GROMACS를 호출만 한다.
