---
name: trajectory-analyzer
description: >-
  본 시뮬레이션(md) 완료 후 궤적 파일(.xtc, .edr)을 분석하여 구조 안정성(RMSD, RMSF),
  에너지 수렴, 회전 반경(Gyration) 데이터를 생성하는 분석 스킬.
  다음 상황에서 호출한다: gmx rms, gmx rmsf, gmx gyrate, gmx energy 명령어를 통해
  시뮬레이션 품질 분석 데이터(.xvg)를 생성해야 할 때. SystemValidator가 PASS 판정을 내린
  후 최종 분석 결과물을 정리하고 사용자에게 요약 보고서를 제출해야 할 때.
  단백질 구조의 안정성(RMSD plateau), 잔기별 유연성(RMSF), 전체 크기 변화(Gyration)를
  정량적으로 분석해야 할 때.
metadata:
  author: GROMACS Harness
  version: 1.0.0
  domain: molecular-dynamics
  pipeline_role: analyzer
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: TrajectoryAnalyzer

본 시뮬레이션 완료 후 궤적 파일(`.xtc`)과 에너지 파일(`.edr`)을 분석하여
구조 안정성 및 시뮬레이션 품질 지표를 계산하고, 사용자에게 요약 보고서를 제공하는 분석 스킬이다.

## Overview

GROMACS `mdrun`이 완료되면 `.xtc` (궤적), `.edr` (에너지), `.log` (로그) 파일이 생성된다.
이 파일들을 그대로 두면 시뮬레이션의 물리적 타당성을 알 수 없다.
`TrajectoryAnalyzer`는 표준 분석 도구(`gmx rms`, `gmx rmsf`, `gmx gyrate`, `gmx energy`)를
체계적으로 호출하여 핵심 지표를 추출하고, 이를 `SystemValidator`에 전달하거나 최종 보고서를 작성한다.

## Input Schema

```json
{
  "phase": "<분석할 단계 Phase ID (통상 'md')>",
  "files": {
    "tpr": "<.tpr 파일 경로>",
    "xtc": "<.xtc 궤적 파일 경로>",
    "edr": "<.edr 에너지 파일 경로>"
  },
  "analyses": ["rmsd", "rmsf", "gyrate", "energy"]
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `phase` | string | ✅ | 분석할 시뮬레이션 단계 |
| `files` | object | ✅ | 분석에 필요한 파일 경로 |
| `analyses` | array | ❌ | 수행할 분석 항목 (기본: 전체) |

## 3. 반환 스키마 (Output Schema)

```json
{
  "status": "success | error",
  "reports": {
    "rmsd_plateau_reached": true,
    "rmsd_final_avg": 2.3,
    "rmsf_core_max": 1.2,
    "energy_drift_detected": false
  },
  "downsampled_data": {
    "rmsd": [{"t": 0, "val": 0.1}, {"t": 100, "val": 1.5}, "...(최대 100개 포인트로 축약)"],
    "energy": ["...(축약된 배열)"]
  },
  "generated_files": ["rmsd.xvg", "rmsf.xvg", "gyrate.xvg"]
}
```

> **⚠️ 대용량 데이터 처리 규칙 (XVG Downsampling):**
> `.xvg` 파일은 수만 줄에 달하므로 에이전트가 파일 내용을 직접 읽어서는 안 됩니다.
> 스킬 내장 파서가 `.xvg`를 읽어들인 뒤, 최대 100개의 데이터 포인트로 다운샘플링하고, 선형 회귀 기울기 및 핵심 통계값(`reports`)만을 추출하여 JSON으로 반환해야 합니다.

## Workflow

에이전트는 다음 순서로 이 스킬을 실행한다.

1. `analyses` 배열의 각 항목에 대해 `GmxExecutor`를 순차 호출한다 (대화형 프롬프트는 `echo "3 3" |` 등으로 파이프라인 우회).
2. 생성된 `.xvg` 파일을 파이썬 파서를 통해 로드하고 헤더를 제거한다.
3. 시계열 데이터를 100개 이하의 포인트로 다운샘플링(Downsampling)한다.
4. 통계값(평균, 최대, plateau 여부)을 계산하여 `reports` 딕셔너리에 정리한다.
5. 최종 분석 결과물(JSON)을 반환하여 에이전트가 Markdown 요약 보고서를 작성할 수 있게 돕는다.

## Analysis Details

### 1. RMSD (Root Mean Square Deviation)

```bash
gmx rms -s {tpr} -f {xtc} -o rmsd.xvg -tu ns
```

- **해석:** 시뮬레이션 시간에 따른 초기 구조 대비 변위
- **PASS 기준:** 시뮬레이션 후반부 (마지막 50%)에서 안정적인 plateau (< 3Å)
- **선택 그룹:** `4` (Backbone)

### 2. RMSF (Root Mean Square Fluctuation)

```bash
gmx rmsf -s {tpr} -f {xtc} -o rmsf.xvg -res
```

- **해석:** 잔기(Residue)별 평균 유연성
- **활용:** 활성 부위(Active Site) 유연성, 루프(Loop) 영역 확인

### 3. Radius of Gyration

```bash
gmx gyrate -s {tpr} -f {xtc} -o gyrate.xvg
```

- **해석:** 단백질 전체 크기의 시간적 변화
- **PASS 기준:** 시뮬레이션 후반부에서 안정적인 수렴

### 4. Energy Analysis

```bash
gmx energy -f {edr} -o energy.xvg
```

- **선택 항목:** `Potential`, `Total Energy`, `Temperature`, `Pressure`, `Density`
- **PASS 기준:** 각 항목이 드리프트 없이 수렴

## Usage Examples

### 본 시뮬레이션 전체 분석

```json
{
  "skill": "TrajectoryAnalyzer",
  "params": {
    "phase": "md",
    "files": {
      "tpr": "md_production.tpr",
      "xtc": "md_production.xtc",
      "edr": "md_production.edr"
    },
    "analyses": ["rmsd", "rmsf", "gyrate", "energy"]
  }
}
```

### RMSD만 빠르게 확인

```json
{
  "skill": "TrajectoryAnalyzer",
  "params": {
    "phase": "md",
    "files": {
      "tpr": "md_production.tpr",
      "xtc": "md_production.xtc",
      "edr": "md_production.edr"
    },
    "analyses": ["rmsd"]
  }
}
```

## Guidelines & Constraints

- 이 스킬은 반드시 `SystemValidator`가 `PASS`를 반환한 후에만 호출한다.
- `.xvg` 파일 파싱 시 `@` 및 `#`으로 시작하는 헤더 라인은 무시한다.
- `report` 마크다운에는 수치 요약, 물리적 해석, 후속 연구 제안을 포함한다.
- 분석 결과가 `FAIL` 기준을 충족하면 `SystemValidator`에 결과를 전달하고 재시뮬레이션 여부를 결정한다.
