# LLM Essentials by Step

## Step Matrix

| Step | Core Command | Required Inputs | Required State Keys | Gate | Fail Pattern |
|---|---|---|---|---|---|
| 0 | `gmx hardware`/`nvidia-smi` | none | `current_step`, `working_dir` | hardware profile 저장 | hardware profile 누락 |
| 1 | `gmx pdb2gmx` | `protein_pdb`, forcefield choice | `forcefield`, `water_model`, `top_file`, `gro_file` | topology 생성 확인 | topology mismatch |
| 2 | `gmx editconf` | processed `.gro` | `box_type`, `box_distance`, `box_gro` | box geometry 범위 확인 | invalid box margin |
| 3 | `gmx solvate` | `box_gro`, `topol.top` | `solv_gro`, solvent count | solvation count 확인 | topology backup 누락 |
| 4 | `gmx grompp` (ions prep) | `ions.mdp`, solvated `.gro`, `topol.top` | `current_step`, retry metadata | tpr 생성 확인 | grompp warning unresolved |
| 5 | `gmx genion` | `ions.tpr`, `topol.top` | `ion_gro`, `n_na`, `n_cl`, `net_charge` | 중성화 검증 | charge neutralization fail |
| 6 | `gmx grompp` (min/nvt/npt/md) | phase `.mdp`, previous `.gro`, `topol.top` | per-phase prep metadata | tpr 생성 + coupling 설정 확인 | temperature/pressure coupling issue |
| 7 | `gmx mdrun` | `{phase}.tpr` | `em_gro`, `nvt_gro`, `npt_gro`, `production_gro` | `SystemValidator` gate | unstable energy |
| 8 | `gmx energy/rms/rmsf/gyrate` via analyzer | `md.xtc`, `md.edr`, `md.tpr` | `rmsd_stable`, `energy_converged`, `final_report_path` | `TrajectoryAnalyzer` 요약 통과 | analysis_not_converged |

## Mandatory Execution Notes

- Step 3, 5 전: `topol.top.bak` 생성 필수.
- Step 3, 5 재시도 시: 백업으로 rollback 후 재실행 필수.
- state 키 누락, backup 누락, Step 0 hardware profile 누락은 `WARNING`이 아니라 즉시 `FAIL`.

## Validator/Analyzer Timing

- `SystemValidator`: Step 1-7 종료 직후 매 step 호출
- `TrajectoryAnalyzer`: Step 8에서 `.xvg` 직접 읽기 대신 downsampled JSON 반환 사용

## Retry Taxonomy for `simulation_state.json.retry_history`

- `command_error`
- `grompp_warning`
- `topology_mismatch`
- `charge_neutralization`
- `unstable_energy`
- `temperature_coupling`
- `pressure_coupling`
- `analysis_not_converged`
- `missing_input`
- `unsupported_variant`

## Mutation Rules by Taxonomy

- `command_error`: CLI flag 변경 (`-maxwarn`, `-ntomp`, I/O 파일명 분리)
- `grompp_warning`: `.mdp` coupling/constraints 값 조정
- `topology_mismatch`: include 순서/분자수 재검증 후 topology 재생성
- `charge_neutralization`: `genion` 이온 농도/선택 그룹 변경
- `unstable_energy`: `nsteps` 축소 + dt 완화 + 초기 restraint 강화
- `temperature_coupling`: `tau_t`, coupling group 조정
- `pressure_coupling`: `tau_p`, compressibility, barostat 설정 조정
- `analysis_not_converged`: production 길이 증가 또는 equilibration 재수행
- `missing_input`: 입력 파일/메타 확보 후 재계획
- `unsupported_variant`: 자동 실행 중지, manual prerequisite 요구
