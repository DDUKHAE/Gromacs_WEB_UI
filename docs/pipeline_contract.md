# Pipeline Contract: Input/Output & State Transitions

이 문서는 GROMACS 하네스 파이프라인의 각 단계 간의 데이터 계약(Contract)을 정의합니다. 모든 스킬과 에이전트는 이 계약을 준수해야 합니다.

## 1. 전역 상태 계약 (Global State)

`simulation_state.json`은 모든 단계의 Single Source of Truth입니다.

필수 공통 키:
- `current_step` (Integer)
- `last_status` (String)
- `working_dir` (String)
- `retry_history` (Object)
- `top_file` (String)
- `latest_gro` (String|null)
- `forcefield` (String)
- `water_model` (String)

권장 운영 키:
- `hardware_specs` (Object)
- `last_command_fingerprint` (String|null)
- `topology_backup` (String|null)

## 2. 단계별 입출력 계약 (Step-wise Contract)

### Step 1: Topology Generation
- Input: `{target}.pdb`
- Output: `{target}_processed.gro`, `topol.top`, `posre.itp`
- State Update: `top_file`, `latest_gro`.

### Step 2: Box Definition
- Output: `{target}_box.gro`
- State Update: `box_type`, `box_distance`, `box_gro`, `latest_gro`.

### Step 3: Solvation
- Input: `latest_gro`, `top_file`
- Output: `{target}_solv.gro`
- Side Effect: `topol.top`의 `[ molecules ]` 수정
- State Update: `solv_gro`, `n_solvent_molecules`, `latest_gro`.

### Step 5: Ionization
- Input: `ions.tpr`, `top_file`
- Output: `{target}_solv_ions.gro`
- Side Effect: `topol.top` 수정
- State Update: `ion_gro`, `n_na`, `n_cl`, `net_charge`, `latest_gro`.

### Step 7: Simulation (EM/NVT/NPT/MD)
- Input: `current_phase.tpr`
- Output: `current_phase.gro`, `current_phase.edr`, `current_phase.xtc`
- Validation: `SystemValidator` verdict 확인
- State Update: `em_gro`, `nvt_gro`, `npt_gro`, `production_gro`, `latest_gro`.

### Step 8: Analysis
- Requirement: 대용량 `.xvg` 원본 직접 판독 대신 다운샘플 결과 사용
- State Update: `rmsd_stable`, `energy_converged`, `final_report_path`.

## 3. 에러 처리 계약 (Error Handling)

- `status: "error"` 발생 시 `retry_history`에 시도 횟수, 상태, 요약을 기록.
- 동일 `command_fingerprint` 재시도는 거부.
- 동일 명령 문자열/파라미터로 무한 반복 금지.
- 단계 내 최대 재시도는 총 3회.
