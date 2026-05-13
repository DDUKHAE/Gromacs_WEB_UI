---
name: mdp-composer
description: >-
  검증된 표준 템플릿을 기반으로 GROMACS .mdp (Molecular Dynamics Parameters) 파일을
  안전하게 생성하는 스킬. 다음 상황에서 호출한다: 에너지 최소화(minim), NVT 평형화(nvt),
  NPT 평형화(npt), 본 시뮬레이션(md) 단계를 위한 .mdp 파일이 필요할 때.
  기본 템플릿에서 온도, 압력, nsteps 등 특정 파라미터만 재정의(override)해야 할 때.
  LLM이 .mdp 파일을 직접 작성하여 발생하는 문법 오류 또는 비물리적 파라미터 조합을 방지해야 할 때.
metadata:
  author: GROMACS Harness
  version: 1.0.0
  domain: molecular-dynamics
  pipeline_role: parameter-generator
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: MdpComposer

LLM이 `.mdp` (Molecular Dynamics Parameters) 파일을 직접 텍스트로 작성하면 문법 오류(Typo)나
비물리적 파라미터 조합이 발생할 수 있다. `MdpComposer`는 검증된 표준 템플릿을 기반으로
파라미터 파일을 안전하게 생성하는 스킬이다.

## Overview

이 스킬은 시뮬레이션 단계(Phase)에 대응하는 검증된 `.mdp` 템플릿을 보유하고 있다.
에이전트는 `phase`와 선택적 `overrides`만 지정하면 되며, 나머지 파라미터는
템플릿 기본값이 자동 적용된다.

## Supported Phases

| Phase ID | 목적 | 기반 템플릿 |
|---|---|---|
| `ions` | 이온화 준비용 더미 run | 최소 설정, nsteps=0 |
| `minim` | 에너지 최소화 (Steepest Descent) | 스텝 제한, 수렴 기준 포함 |
| `nvt` | NVT 평형화 (온도 제어) | V-rescale 서모스탯, 위치 구속 포함 |
| `npt` | NPT 평형화 (압력 제어) | Parrinello-Rahman 바로스탯 추가 |
| `md` | 본 시뮬레이션 (Production MD) | 위치 구속 제거, 최대 성능 설정 |

## Input Schema

```json
{
  "phase": "<Phase ID>",
  "overrides": {
    "<mdp 파라미터 키>": "<값>"
  }
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `phase` | string | ✅ | 생성할 시뮬레이션 단계 ID |
| `overrides` | object | ❌ | 기본 템플릿에서 변경할 파라미터만 명시 (나머지는 기본값 사용) |

## Output Schema

```json
{
  "status": "success | error",
  "output_file": "<생성된 .mdp 파일 경로>",
  "final_params": { "<전체 파라미터 내용>" }
}
```

## Default Templates

자세한 기본 템플릿 내용은 [`references/mdp_templates.md`](./references/mdp_templates.md)를 참조한다.

### Phase: `minim` (에너지 최소화) — 핵심 파라미터

```ini
integrator  = steep
emtol       = 1000.0    ; 수렴 기준: Fmax < 1000 kJ/mol/nm
emstep      = 0.01
nsteps      = 50000
coulombtype = PME
cutoff-scheme = Verlet
pbc         = xyz
```

### Phase: `nvt` (NVT 평형화, 100ps) — 핵심 파라미터

```ini
integrator  = md
nsteps      = 50000     ; 100ps (2fs × 50000)
dt          = 0.002
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
ref_t       = 300  300
pcoupl      = no
define      = -DPOSRES
gen_vel     = yes
```

### Phase: `npt` (NPT 평형화, 100ps) — 핵심 파라미터

```ini
integrator  = md
nsteps      = 50000
tcoupl      = V-rescale
ref_t       = 300  300
pcoupl      = Parrinello-Rahman
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
define      = -DPOSRES
gen_vel     = no
```

### Phase: `md` (본 시뮬레이션) — 핵심 파라미터

```ini
integrator  = md
nsteps      = 5000000   ; 10ns (2fs × 5000000) — overrides로 조정 가능
dt          = 0.002
nstxout-compressed = 5000   ; .xtc에 10ps마다 기록
tcoupl      = V-rescale
pcoupl      = Parrinello-Rahman
define      =            ; 위치 구속 없음
gen_vel     = no
```

## Usage Examples

### Step 4: ions.mdp 생성 (이온화 준비)

```json
{
  "skill": "MdpComposer",
  "params": {
    "phase": "ions",
    "overrides": {}
  }
}
```

> `nsteps=0`으로 실제 시뮬레이션은 수행하지 않고, `grompp`에서 `.tpr` 파일 생성 후 `genion`에 전달하는 용도.

### 10ns 시뮬레이션, 체온(310K)으로 md.mdp 생성

```json
{
  "skill": "MdpComposer",
  "params": {
    "phase": "md",
    "overrides": {
      "nsteps": "5000000",
      "ref_t": "310  310"
    }
  }
}
```

> `nsteps=5000000`, `dt=0.002`이면 10ns. 온도를 310K(체온)로 변경한 예시.

### NVT 시간 연장 (500ps)

```json
{
  "skill": "MdpComposer",
  "params": {
    "phase": "nvt",
    "overrides": {
      "nsteps": "250000"
    }
  }
}
```

## Guidelines & Constraints

- `overrides`에 명시하지 않은 파라미터는 반드시 기본 템플릿 값을 사용한다. 임의의 값을 삽입하지 않는다.
- `references/mdp_parameter_reference.md`에 없는 파라미터 키를 `overrides`에 추가하기 전에 에이전트는 먼저 해당 문서를 조회하여 유효성을 확인해야 한다.
- 생성된 `.mdp` 파일은 `GmxExecutor`의 `grompp` 호출 시 `-f` 인자로 즉시 사용된다.
