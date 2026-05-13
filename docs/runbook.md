# Operational Runbook: Manual Intervention Guide

본 문서는 하네스(Harness) 시스템이 자율 복구(3회 재시도)에 실패하거나, 에이전트가 처리할 수 없는 심각한 오류가 발생했을 때 사용자가 수행해야 할 수동 점검 및 복구 절차를 안내합니다.

## 1. 자율 복구 실패 시 점검 항목

### 1.1 로그 분석 (Log Analysis)
- `simulation_state.json`에서 `last_status`가 `error`인 경우, `summary` 필드에 기록된 마지막 GROMACS 로그를 확인하십시오.
- `working_dir` 내의 `.log` 파일(예: `minim.log`, `nvt.log`)을 열어 `Fatal error` 키워드로 검색합니다.

### 1.2 토폴로지 불일치 (Topology Mismatch)
- **증상:** `gmx grompp` 중 "number of coordinates in gro file does not match topology" 에러 발생.
- **원인:** `solvate`나 `genion` 단계에서 `topol.top` 파일은 업데이트되었으나 `.gro` 파일 쓰기에 실패했거나 그 반대의 경우.
- **해결:**
  1. `simulation_state.json`의 `topology_backup` 경로를 확인하여 백업 파일을 `topol.top`으로 복사합니다.
  2. 에이전트에게 직전 단계(Step 3 또는 5)부터 다시 실행하도록 지시합니다.

### 1.3 온도/압력 발산 (Temperature/Pressure Instability)
- **증상:** `SystemValidator`가 `FAIL`을 반환하며 온도나 압력이 비정상적으로 높음.
- **해결:**
  1. `.mdp` 파일의 `tau_t` 또는 `tau_p` 값을 확인합니다 (일반적으로 0.1~2.0).
  2. 시스템에 겹치는 원자가 있는지 `gmx check -c`로 확인합니다.
  3. 필요시 `emstep`을 줄여 에너지 최소화를 더 정밀하게 수행합니다.

## 2. 수동 복구 절차 (Manual Recovery Workflow)

1. **상태 동기화:** 수동으로 명령어를 실행하여 파일을 생성했다면, `StateManager`를 사용하여 `simulation_state.json`의 `latest_gro` 및 `current_step`을 수동으로 업데이트하십시오.
2. **에이전트 재개:** 상태가 업데이트된 후 에이전트에게 "현재 상태를 기반으로 다음 단계부터 진행하라"고 명령합니다.

## 3. 중단 기준 (Stop Criteria)

다음 상황에서는 하네스 운용을 즉시 중단하고 시스템 구성을 재검토해야 합니다:
- 하드웨어 OOM (Out of Memory) 지속 발생.
- 사용 중인 포스 필드와 PDB 파일의 원자 명칭이 근본적으로 불일치할 때.
- 파일 시스템 권한 문제로 인해 백업 생성이 불가능할 때.
