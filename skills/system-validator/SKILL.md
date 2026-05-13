---
name: system-validator
description: >-
  각 파이프라인 Step 완료 후 생성된 결과물을 물리적으로 검증하고 다음 단계 진행 여부를
  판단하는 품질 제어(QC) 스킬. 다음 상황에서 반드시 호출한다: 에너지 최소화(minim) 완료 후
  Fmax 수렴 여부를 확인할 때. NVT 완료 후 온도 안정성을 검증할 때. NPT 완료 후 압력/밀도
  수렴을 확인할 때. 본 시뮬레이션(md) 완료 후 에너지 수렴(드리프트 없음)만 갯주이 검증할 때.
  **역할 경계:** RMSD 심층 분석과 보고서 생성은 TrajectoryAnalyzer가 담당. 이 스킬은 PASS/FAIL
  게이트 역할만 수행한다. 에이전트는 이 스킬의 판정(PASS/FAIL/WARNING) 없이 절대로 다음 단계로 진행하지 않는다.
metadata:
  author: GROMACS Harness
  version: 1.0.0
  domain: molecular-dynamics
  pipeline_role: quality-control
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: SystemValidator

각 파이프라인 Step 완료 후 생성된 결과물을 물리적으로 검증하고, 다음 단계로 진행해도 되는지
여부를 판단하는 품질 제어(QC) 스킬이다. **에이전트는 이 스킬의 판정 없이 다음 단계로 넘어가서는 안 된다.**

## Overview

MD 시뮬레이션에서 한 단계의 실패는 이후 모든 단계를 무의미하게 만든다.

- 에너지 최소화(EM)가 수렴하지 않은 채로 NVT를 진행하면 즉시 "Lincs Warning" 또는 구조 붕괴가 발생한다.
- NPT 평형화가 완료되지 않으면 본 시뮬레이션의 압력/밀도가 비정상적으로 나온다.

`SystemValidator`는 `gmx energy` 등의 분석 도구를 내부적으로 호출하여, 정량적 수치가
`references/validation_criteria.md`의 기준값을 만족하는지 확인한다.

## Input Schema

```json
{
  "phase": "<검증할 단계 Phase ID>",
  "files": {
    "tpr": "<.tpr 파일 경로>",
    "edr": "<.edr 파일 경로>",
    "log": "<.log 파일 경로>"
  }
}
```

## Output Schema

```json
{
  "verdict": "PASS | FAIL | WARNING",
  "phase": "<검증한 단계>",
  "metrics": {
    "<측정 항목>": "<측정값>"
  },
  "reason": "<판정 근거 (기준값 대비 측정값 비교)>",
  "recommendation": "<FAIL/WARNING 시 권고 행동>"
}
```

## Workflow

에이전트는 다음 순서로 이 스킬을 실행한다.

1. `phase`에 따른 검증 기준을 `references/validation_criteria.md`에서 로드한다.
2. `gmx energy` (또는 `gmx rms`)를 내부 호출하여 정량적 수치를 추출한다.
3. 추출된 수치를 기준값과 비교하여 `PASS`, `WARNING`, `FAIL` 중 하나로 판정한다.
4. `verdict`가 `FAIL`이면 `recommendation`에 따라 에이전트는 이전 단계(MdpComposer → GmxExecutor)를 재호출한다.
5. `verdict`가 `WARNING`이면 에이전트는 사용자에게 보고 후 계속 진행 여부를 결정한다.

> **역할 경계 (TrajectoryAnalyzer와의 구분):**
> - `SystemValidator` → **PASS/FAIL 게이트** ("다음 단계로 진행해도 되는가?"만 판단)
> - `TrajectoryAnalyzer` → **심층 분석 + 보고서** (RMSD 패턴, 잔기별 RMSF, 통계 요약, 후속 연구 제안)
> `md` Phase에서 `SystemValidator`는 에너지 드리프트 여부만 점검하며, RMSD 실제 분석은 `TrajectoryAnalyzer`가 담당한다.

## Validation Criteria by Phase

> 상세 기준값은 [`references/validation_criteria.md`](./references/validation_criteria.md)를 참조한다.

### Phase: `minim` (에너지 최소화)

| 검증 항목 | 내부 명령어 | PASS 조건 | FAIL 시 권고 |
|---|---|---|---|
| 최대 힘(Fmax) | `gmx energy -f em.edr` | `Fmax < 1000 kJ/mol/nm` | nsteps 증가 또는 emstep 감소 후 재실행 |
| 퍼텐셜 에너지 | `gmx energy -f em.edr` | 충분히 큰 음수이며 단조 감소 추세 | pdb2gmx 단계 재확인 (원자 충돌 가능성) |

### Phase: `nvt` (NVT 평형화)

| 검증 항목 | 내부 명령어 | PASS 조건 | FAIL 시 권고 |
|---|---|---|---|
| 온도(Temperature) | `gmx energy (Temperature)` | `ref_t ± 5K` 이내에서 안정적 수렴 | tau_t를 0.1 → 0.05로 줄이고 재실행 |

> WARNING 조건: 온도가 요동(oscillation)하나 평균은 목표치에 근접한 경우.

### Phase: `npt` (NPT 평형화)

| 검증 항목 | PASS 조건 | FAIL 시 권고 |
|---|---|---|
| 압력(Pressure) | `ref_p ± 100 bar` 이내 (평균값 기준) | tau_p 조정 또는 NPT 시간 연장 |
| 밀도(Density) | 물 기반 시스템: `950~1050 kg/m³` | tau_p 조정 또는 NPT 시간 연장 |

### Phase: `md` (본 시뮬레이션) — 에너지 수렴 GATE

| 검증 항목 | 내부 명령어 | PASS 조건 |
|---|---|---|
| 에너지 보존 | `gmx energy (Total Energy)` | drift 없이 수렴 |

> **RMSD 분석은 이 스킬에서 수행하지 않는다.** 심층 구조 안정성 분석(RMSD plateau, RMSF, Gyration)은
> `TrajectoryAnalyzer` 스킬이 전담한다. `SystemValidator`는 에너지 드리프트 여부만 확인하는
> 단순 GATE 역할에 집중한다.

## Usage Examples

### NVT 완료 후 검증

```json
{
  "skill": "SystemValidator",
  "params": {
    "phase": "nvt",
    "files": {
      "tpr": "nvt.tpr",
      "edr": "nvt.edr",
      "log": "nvt.log"
    }
  }
}
```

### 예상 반환 (PASS)

```json
{
  "verdict": "PASS",
  "phase": "nvt",
  "metrics": {
    "temperature_avg": "299.8 K",
    "temperature_std": "2.1 K"
  },
  "reason": "평균 온도 299.8K이 목표 온도 300K ± 5K 기준을 만족합니다.",
  "recommendation": "NPT 평형화 단계로 진행하세요."
}
```

### 예상 반환 (FAIL)

```json
{
  "verdict": "FAIL",
  "phase": "minim",
  "metrics": {
    "fmax": "15234.2 kJ/mol/nm"
  },
  "reason": "최대 힘(Fmax) 15234.2 kJ/mol/nm이 기준값 1000 kJ/mol/nm을 초과합니다.",
  "recommendation": "nsteps를 50000 → 100000으로 늘리거나 emstep을 0.01 → 0.001로 줄인 후 에너지 최소화를 재실행하세요."
}
```

## Guidelines & Constraints

- `verdict`가 `FAIL`인 경우, 에이전트는 자동으로 재시도하되 최대 3회를 초과하면 사용자에게 에스컬레이션한다.
- `verdict`가 `WARNING`인 경우, 에이전트는 경고 내용을 사용자에게 보고한 후 진행한다.
- 검증 없이 다음 Step으로 진행하는 것은 절대 금지이다.
