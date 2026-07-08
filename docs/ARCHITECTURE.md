# Molecular Dynamics Simulation Architecture: GROMACS Harness

이 문서는 LLM 에이전트(`AGENTS.md` 참조)가 GROMACS를 자율적으로 운용하기 위한 **파이프라인 지도**입니다.
단백질-수용액 시스템을 기준으로, 각 Step의 명령어/입력/출력/상태 변화를 정의하며 에이전트는 이 문서를 나침반 삼아 단계를 진행합니다.

> **참고 (2026-05-14 이후 현재 구조):** 아래 `GmxExecutor`/`SystemValidator`/`MdpComposer`/
> `TrajectoryAnalyzer`는 설계 당시의 개념적 스킬 이름이며, `skills/gmx-executor/SKILL.md`·
> `skills/system-validator/SKILL.md` 같은 개별 디렉터리는 현재 코드에 존재하지 않습니다.
> 실제로는 3-스킬 구조로 통합되어 있습니다: `skills/env_builder/`(Step 0–5),
> `skills/md_runner/`(Step 6–7, 검증 게이트 `lib/validators.py` 직접 호출),
> `skills/illustrator/`(Step 8). 최신 스킬 매핑은 루트 `ARCHITECTURE.md` §7과
> `skills/SKILLS_OVERVIEW.md`를 참조. 아래 Step 0–8 명령어/입출력 매핑 자체(섹션 3)는
> 여전히 유효합니다 — 바뀐 것은 이를 호출하는 스킬 계층의 이름과 구조입니다.

> **하네스 연동 규칙 (개념 원안, 위 참고 참조):** 각 Step 실행 시 `GmxExecutor` 역할(현재
> `lib/gmx_wrapper.py`)을 호출하고, Step 완료 후 `SystemValidator` 역할(현재
> `lib/validators.py`)로 결과를 검증해야 합니다.

## 1. 시스템 워크플로우 개요 (System Workflow)

본 아키텍처의 핵심 목표는 **CHARMM-GUI 웹 서비스가 제공하는 시스템 자동화 구축 기능을 순수 GROMACS 자체 명령어 라인 코드만으로 완벽하게 구현(Replicate)**하는 데 있습니다.

CHARMM-GUI가 수행하는 복잡한 시스템 준비 과정(포스 필드 적용, 시뮬레이션 박스 생성, 솔베이션, 이온 추가 등)은 본질적으로 GROMACS 내장 도구(`gmx` 명령어)들이 제공하는 기능들과 일치합니다. 따라서 외부 웹 툴에 의존하지 않고, GROMACS 명령어들의 파이프라인을 구축하여 CHARMM-GUI와 동일한 결과물(`.gro`, `.top`, `.mdp`)을 자동으로 만들어내는 것이 이 시스템의 개요입니다.

### 핵심 시스템 구축 파이프라인 (GROMACS Native Automation)

PDB 파일 입력부터 시뮬레이션 준비 완료까지의 단계를 GROMACS 명령어로 다음과 같이 매핑하여 구현합니다:

1. **Topology Generation (`gmx pdb2gmx`):**
   - 역할: 입력된 PDB 구조를 GROMACS 구조 파일(`.gro`)과 물리화학적 특성이 담긴 토폴로지 파일(`.top`)로 변환하고 포스 필드를 적용합니다.
2. **Box Definition (`gmx editconf`):**
   - 역할: 시뮬레이션이 진행될 가상의 3차원 공간(Box)의 형태와 단백질 주변 여백의 크기를 정의합니다.
3. **Solvation (`gmx solvate`):**
   - 역할: 정의된 시뮬레이션 상자 내의 빈 공간에 용매(물 분자)를 자동으로 채워 넣습니다.
4. **Ionization (`gmx grompp` & `gmx genion`):**
   - 역할: 시스템 전체 전하가 0(Neutral)이 되도록 물 분자 일부를 적절한 수의 이온(Na+, Cl- 등)으로 치환합니다.
5. **Execution Preparation:**
   - 역할: CHARMM-GUI가 생성해 주는 것과 같이, 에너지 최소화(Minimization) 및 평형화(Equilibration)를 위한 최적화된 `.mdp` 파일 세트를 제공하여 시뮬레이션을 준비합니다.

이러한 GROMACS 명령어 체인이 기존 CHARMM-GUI의 "System Builder" 프로세스를 완벽히 대체하여, 독립적이고 코드로 제어 가능한 시뮬레이션 준비 인프라를 구축합니다.

---

## 2. 데이터 흐름 및 핵심 파일 구조 (Data Flow & Core Files)

시뮬레이션 시스템은 아래의 핵심 파일들이 서로 유기적으로 상호작용하며 작동합니다.

### 2.1 입력 및 시스템 정의 파일
*   **`.pdb` (Protein Data Bank):** 초기 단백질의 3차원 원자 좌표 파일입니다.
*   **`.top` (Topology):** 시스템의 물리적/화학적 규칙을 정의합니다. 원자 간의 결합, 각도, 전하량 및 사용할 포스 필드(Force Field) 정보가 담겨 있으며, 시스템에 물이나 이온이 추가될 때마다 실시간으로 업데이트됩니다.
*   **`.mdp` (Molecular Dynamics Parameters):** 시뮬레이션 '어떻게' 할 것인지에 대한 설정 파일입니다. (예: 온도, 압력, 스텝 크기, 시뮬레이션 시간 등)
*   **`.gro` (GROMACS Coordinates):** GROMACS 표준 좌표 파일로, 매 단계가 끝날 때마다 새로운 상태의 `.gro` 파일이 출력되어 다음 단계의 입력으로 사용됩니다.

### 2.2 실행 파일
*   **`.tpr` (Portable Binary Run Input):** `gmx grompp` 명령어를 통해 `.gro`(구조), `.top`(규칙), `.mdp`(설정) 세 가지 파일이 하나로 결합된 **실행 전용 바이너리 파일**입니다. `gmx mdrun` 엔진은 오직 이 `.tpr` 파일만을 읽어 연산을 수행합니다.

### 2.3 출력 파일 (Output)
`gmx mdrun` 엔진이 연산을 마치면 다음과 같은 결과 파일들이 생성됩니다.
*   **`.xtc` / `.trr` (Trajectory):** 시간에 따른 원자들의 움직임(궤적)이 기록된 파일입니다. (시각화 및 분석의 핵심)
*   **`.edr` (Energy):** 시간에 따른 시스템의 에너지 변화(온도, 압력, 퍼텐셜 에너지 등)가 기록됩니다.
*   **`.log` (Log):** 시뮬레이션 진행 과정의 텍스트 로그 파일입니다.

---

## 3. 실행 파이프라인 명세 (LLM-Readable Execution Pipeline)

본 섹션은 LLM 에이전트가 GROMACS 시스템의 실행 흐름을 명확히 파싱하고 이해할 수 있도록 구조화된 YAML 형식으로 워크플로우를 정의합니다. 에이전트는 아래의 스키마를 참조하여 각 단계의 명령어, 필수 입력값, 생성되는 출력값 및 시스템 상태 변화(Side-effect)를 추적해야 합니다.

```yaml
Pipeline_Steps:
  - Step: 0
    Action: "Pre-flight Hardware Check & State Init"
    Command: "gmx hardware / nvidia-smi"
    Inputs:
      - None
    Outputs:
      - State_File: "simulation_state.json"
    State_Change: "시스템의 가용 CPU 코어와 GPU 상태를 파악하고, StateManager를 호출하여 현재 작업 디렉토리에 시뮬레이션 상태 추적 파일을 초기화함. 이 정보는 이후 mdrun 최적화에 사용됨."

  - Step: 1
    Action: "Topology Generation"
    Command: "gmx pdb2gmx"
    Inputs:
      - Coordinate: "{target}.pdb"
    Outputs:
      - Coordinate: "{target}_processed.gro"
      - Topology: "topol.top"
    State_Change: "단백질 구조에 지정된 Force Field를 적용하고 초기 토폴로지 파일을 생성함."

  - Step: 2
    Action: "Box Definition"
    Command: "gmx editconf"
    Inputs:
      - Coordinate: "{target}_processed.gro"
    Outputs:
      - Coordinate: "{target}_box.gro"
    State_Change: "단백질 주변의 여백(distance)과 가상의 시뮬레이션 상자(box type) 크기를 구조 파일에 기록함."

  - Step: 3
    Action: "Solvation"
    Command: "gmx solvate"
    Inputs:
      - Coordinate: "{target}_box.gro"
      - Topology: "topol.top"
    Outputs:
      - Coordinate: "{target}_solv.gro"
    State_Change: "상자 내부를 물 분자로 채움. (Side-effect: topol.top 파일의 [ molecules ] 섹션에 용매 분자(SOL) 개수가 자동 추가됨.)"

  - Step: 4
    Action: "Ionization Preparation"
    Command: "gmx grompp"
    Inputs:
      - Coordinate: "{target}_solv.gro"
      - Topology: "topol.top"
      - Parameters: "ions.mdp"
    Outputs:
      - Run_Input: "ions.tpr"
    State_Change: "이온 추가를 위한 임시 시스템 상태를 바이너리 파일(.tpr)로 컴파일함."

  - Step: 5
    Action: "Ionization"
    Command: "gmx genion"
    Inputs:
      - Run_Input: "ions.tpr"
      - Topology: "topol.top"
    Outputs:
      - Coordinate: "{target}_solv_ions.gro"
    State_Change: "시스템의 Net Charge를 0으로 맞추기 위해 일부 물 분자를 이온(NA, CL 등)으로 치환함. (Side-effect: topol.top 파일에서 SOL 개수가 감소하고 이온 개수가 기록됨.)"

  - Step: 6
    Action: "Execution Preparation (Loop for minim, nvt, npt, md)"
    Command: "gmx grompp"
    Inputs:
      - Coordinate: "{previous_step}.gro"
      - Topology: "topol.top"
      - Parameters: "{current_phase}.mdp"
    Outputs:
      - Run_Input: "{current_phase}.tpr"
    State_Change: "에너지 최소화 또는 평형화/본 시뮬레이션의 파라미터(.mdp)를 적용하여 최종 실행 파일을 생성함."

  - Step: 7
    Action: "Simulation Execution"
    Command: "gmx mdrun"
    Inputs:
      - Run_Input: "{current_phase}.tpr"
    Outputs:
      - Coordinate: "{current_phase}.gro"
      - Trajectory: "{current_phase}.xtc", "{current_phase}.trr"
      - Energy: "{current_phase}.edr"
      - Log: "{current_phase}.log"
    State_Change: "MD 엔진을 구동하여 물리적 연산을 수행. 생성된 .gro 파일은 다음 시뮬레이션 단계(Step 6)의 입력값으로 순환됨."

  - Step: 8
    Action: "Trajectory Analysis"
    Command: "gmx energy / gmx rms / gmx rmsf / gmx gyrate"
    Inputs:
      - Trajectory: "{production_phase}.xtc"
      - Energy: "{production_phase}.edr"
      - Run_Input: "{production_phase}.tpr"
    Outputs:
      - Energy_Data: "energy.xvg"
      - RMSD_Data: "rmsd.xvg"
      - RMSF_Data: "rmsf.xvg"
      - Gyration_Data: "gyrate.xvg"
    State_Change: "시뮬레이션 결과물(.xtc, .edr)을 분석하여 시스템 안정성(RMSD), 유연성(RMSF), 에너지 수렴 여부를 검증. docs/simulation_criteria.md의 기준값과 비교하여 시뮬레이션 품질을 최종 판정함."
```

---

## 4. 하네스 연동 요약 (Harness Integration Summary)

> 아래 표의 `GmxExecutor`/`StateManager`/`MdpComposer`/`SystemValidator`/`TrajectoryAnalyzer`는
> 개념적 역할 이름입니다. 현재 코드에서 Step 0–5는 `skills/env_builder/`, Step 6–7은
> `skills/md_runner/`, Step 8은 `skills/illustrator/`가 이 역할들을 `lib/gmx_wrapper.py`,
> `lib/state.py`, `lib/mdp_templates/`, `lib/validators.py`, `lib/xvg_parser.py`를 직접
> 호출해 수행합니다. 참조 Doc 열의 파일명들도 현재 문서 트리와 다를 수 있습니다(§2 참조).

| Step | Action | 사용 Skill (개념적 역할) | 참조 Doc |
|---|---|---|---|
| 0 | Pre-flight | `GmxExecutor` + `StateManager` | - |
| 1 | Topology Generation | `GmxExecutor` + `StateManager` | `force_field_guide.md` |
| 2 | Box Definition | `GmxExecutor` + `StateManager` | - |
| 3 | Solvation | `GmxExecutor` + `StateManager` | - |
| 4 | Ionization Prep | `GmxExecutor` + `MdpComposer` | `mdp_parameter_reference.md` |
| 5 | Ionization | `GmxExecutor` + `StateManager` | `error_troubleshooting.md` |
| 6 | Execution Prep | `GmxExecutor` + `MdpComposer` | `mdp_parameter_reference.md` |
| 7 | Simulation Run | `GmxExecutor` + `SystemValidator` + `StateManager`| `validation_criteria.md` |
| 8 | Analysis | `GmxExecutor` + `TrajectoryAnalyzer` | `xvg_analysis_guide.md` |
