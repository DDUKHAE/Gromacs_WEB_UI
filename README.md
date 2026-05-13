# GROMACS Harness

Prompt + PDB input 기반으로 GROMACS 분자동역학 파이프라인(Step 0-8)을 자율 실행하기 위한 LLM 오케스트레이션 하네스입니다.

## What This Repository Provides

- `run_autonomy.py` 중심의 실행 오케스트레이터
- 단계별 스킬 모듈:
  - `skills/state-manager`
  - `skills/gmx-executor`
  - `skills/mdp-composer`
  - `skills/system-validator`
  - `skills/trajectory-analyzer`
- 상태 파일 기반 컨텍스트 유지: `simulation_state.json`
- 문서 기반 계약/아키텍처:
  - `AGENTS.md`
  - `ARCHITECTURE.md`
  - `docs/pipeline_contract.md`

## Directory Layout

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── run_autonomy.py
├── simulation_state.json
├── scripts/
│   └── check_gromacs_env.py
├── skills/
│   ├── gmx-executor/
│   ├── mdp-composer/
│   ├── state-manager/
│   ├── system-validator/
│   ├── trajectory-analyzer/
│   ├── protocol-compiler/
│   ├── tutorial-planner/
│   └── tutorial-router/
└── docs/
```

## Prerequisites

- macOS/Linux shell
- Conda (권장)
- GROMACS (conda-forge 패키지 사용 가능)

## Quick Start

1. Conda env 생성 및 설치

```bash
conda create -n GROMACS -y -c conda-forge gromacs
```

2. 환경 확인

```bash
conda run -n GROMACS gmx --version
conda run -n GROMACS python3 scripts/check_gromacs_env.py
```

3. Dry run (`execute=false`)

```bash
conda run -n GROMACS python3 run_autonomy.py '{
  "cwd": "/absolute/path/to/GROMACS_Harness",
  "prompt": "lysozyme in water",
  "pdb_path": "/absolute/path/to/input.pdb",
  "execute": false
}'
```

4. Full pipeline run (`execute=true`)

```bash
conda run -n GROMACS python3 run_autonomy.py '{
  "cwd": "/absolute/path/to/GROMACS_Harness",
  "prompt": "lysozyme in water",
  "pdb_path": "/absolute/path/to/input.pdb",
  "execute": true
}'
```

## Autonomy Model

- 사용자 입력 최소 단위: `prompt`, `pdb_path`
- 나머지 Step 0-8은 오케스트레이터/스킬이 처리
- 상태 추적: `simulation_state.json`
- 실패 처리:
  - 최대 3회 재시도
  - 동일 지문 재시도 방지
  - topology 변경 단계 백업/복구

## Current Notes

- 바이너리 일관성을 위해 런타임에서 `gmx_bin`을 전달합니다.
- 대용량 `.xvg`는 직접 판독 대신 downsampling 분석 경로를 사용합니다.
- 실제 물리적 타당성은 입력 시스템/force field/파라미터 품질에 의존합니다.

## Documentation

- 실행 정책/역할: `AGENTS.md`
- 아키텍처 개요: `ARCHITECTURE.md`
- 상태/단계 계약: `docs/pipeline_contract.md`
