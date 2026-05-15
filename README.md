# GROMACS Harness

Prompt + PDB input 기반으로 GROMACS 분자동역학 파이프라인을 3가지 핵심 스킬(env_builder, md_runner, illustrator)로 자율 실행하기 위한 LLM 오케스트레이션 하네스입니다.

## What This Repository Provides

- 3-skill 기반 실행 모델:
  - `skills/env_builder`: 시스템 설정 및 환경 구축
  - `skills/md_runner`: 분자동역학 시뮬레이션 실행
  - `skills/illustrator`: 결과 시각화 및 보고
- 상태 기반 계약/아키텍처:
  - `AGENTS.md`
  - `ARCHITECTURE.md`
  - `docs/pipeline_contract.md`
- 회귀 테스트 스크립트: `scripts/regression/`

## Directory Layout

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── scripts/
│   ├── check_gromacs_env.py
│   └── regression/
│       ├── run_tutorial.sh
│       ├── lysozyme.sh
│       ├── kalp15.sh
│       ├── protein_ligand.sh
│       ├── umbrella.sh
│       ├── biphasic.sh
│       ├── fe_methane.sh
│       ├── fe_ethanol.sh
│       └── virtual_sites.sh
├── skills/
│   ├── env_builder/
│   ├── md_runner/
│   └── illustrator/
├── lib/
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

3. 회귀 테스트 실행

```bash
# Lysozyme 기본 회귀 테스트
./scripts/regression/lysozyme.sh

# 모든 회귀 스크립트 실행 가능
./scripts/regression/kalp15.sh
./scripts/regression/protein_ligand.sh
./scripts/regression/umbrella.sh
./scripts/regression/biphasic.sh
./scripts/regression/fe_methane.sh
./scripts/regression/fe_ethanol.sh
./scripts/regression/virtual_sites.sh
```

## 3-Skill Execution Model

사용자는 3개 핵심 스킬을 직렬로 호출:

1. **env_builder**: PDB + 프롬프트 → 시스템 구축 (Stage 0-1)
2. **md_runner**: 환경 → 시뮬레이션 실행 (Stage 2)
3. **illustrator**: 결과 → 시각화 보고서 (Stage 3)

각 스킬의 입출력 계약은 `skills/<name>/SKILL.md`에 명시됩니다.

## Current Notes

- 실행은 기본적으로 run 격리 디렉터리(`runs/<tutorial_id>_<timestamp>`)에서 수행되어 런 간 파일 오염을 줄입니다.
- 각 회귀 스크립트는 `scripts/regression/run_tutorial.sh`를 호출하여 3개 스킬 체인을 실행합니다.
- 실제 물리적 타당성은 입력 시스템/force field/파라미터 품질에 의존합니다.

## Documentation

- 실행 정책/역할: `AGENTS.md`
- 아키텍처 개요: `ARCHITECTURE.md`
- 상태/단계 계약: `docs/pipeline_contract.md`

## License Guidance

이 저장소는 GROMACS 자체 코드를 포함하지 않고, GROMACS를 호출하는 하네스/오케스트레이션 레이어입니다.

- 일반적으로는 하네스 코드에 대해 `MIT` 또는 `Apache-2.0`을 선택해도 무방합니다.
- GROMACS와 라이선스 정합성을 우선한다면 `LGPL-2.1-or-later`도 선택 가능합니다.

권장:
- 외부 기여/재사용을 넓게 받으려면 `MIT`
- GROMACS 생태계와 톤을 맞추려면 `LGPL-2.1-or-later`

최종 선택 후 루트에 `LICENSE` 파일을 추가하세요.
