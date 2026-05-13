# Simulation Quality Criteria (Simulation Criteria)

이 문서는 시뮬레이션의 각 단계가 성공적으로 완료되었는지 판단하는 물리적/기술적 검증 기준을 정의합니다. `SystemValidator` 및 `TrajectoryAnalyzer` 스킬은 이 기준을 사용하여 PASS/WARNING/FAIL 여부를 결정합니다.

## 1. 단계별 검증 기준 (Step-wise Validation)

### Step 1: Topology Generation
- **PASS:** `.gro` 및 `topol.top` 파일 생성 완료. GROMACS 로그에 "Fatal error" 없음.
- **FAIL:** 파일 생성 실패 또는 "Invalid force field" 관련 에러 발생.

### Step 2: Box Definition
- **PASS:** 단백질 원자와 상자 경계 사이의 거리가 설정값(기본 1.0nm) 이상 유지.
- **FAIL:** 상자 크기가 단백질 크기보다 작음.

### Step 3: Solvation
- **PASS:** `topol.top`의 `[ molecules ]` 섹션에 `SOL` 항목이 추가됨. 물 분자 간의 비정상적인 겹침 없음.
- **FAIL:** 물 분자가 추가되지 않거나 토폴로지 파일 업데이트 실패.

### Step 5: Ionization
- **PASS:** 시스템의 Net Charge가 0.000e+00 (또는 소수점 오차 범위 내) 도달.
- **FAIL:** Net Charge가 남아있어 시스템이 중성이 아님.

### Step 7: Energy Minimization (EM)
- **PASS:** Maximum Force ($F_{max}$) < $1000$ kJ/mol/nm (또는 `.mdp` 설정값).
- **WARNING:** $F_{max}$가 $1000$ ~ $2000$ 사이이나 수렴 추세일 때.
- **FAIL:** 에너지가 발산(Diverged)하거나 $F_{max}$가 줄어들지 않음.

### Step 7: Equilibration (NVT/NPT)
- **Temperature (NVT):** 평균 온도가 목표 온도(T)의 $\pm 5K$ 이내 유지.
- **Pressure (NPT):** 평균 압력이 목표 압력(P)의 $\pm 100$ bar 이내 유지 (변동폭이 크므로 평균값이 중요).
- **Density:** 해당 용매(물 등)의 이론적 밀도에 수렴.

## 2. 최종 분석 검증 기준 (Step 8: Analysis)

| 항목 | 검증 기준 (Threshold) | 판단 |
|---|---|---|
| **RMSD** | 시뮬레이션 후반부(마지막 20%)에서 Plateau(평탄화) 형성 | PASS |
| **RMSD** | 지속적으로 상승하며 수렴 기미가 없음 | WARNING |
| **Potential Energy** | 시뮬레이션 전체에 걸쳐 감소하거나 안정적으로 유지 | PASS |
| **Temperature Drift** | 전체 구간에서 온도의 기울기(Slope)가 통계적으로 0에 가까움 | PASS |

## 3. 자율 복구 정책 (Recovery Policy)

- **WARNING 발생 시:** 에이전트는 로그에 경고 내용을 기록하고 다음 단계를 진행하되, `simulation_state.json`에 `warning_flag: true`를 마킹합니다.
- **FAIL 발생 시:** `AGENTS.md`의 "무한 루프 방지" 규칙에 따라 파라미터를 수정하여 최대 3회 재시도합니다.
- **중단(Termination):** 3회 재시도 후에도 FAIL이 지속되거나, 물리적으로 복구 불가능한 시스템 에러(예: Topology mismatch) 발생 시 사용자에게 즉시 보고하고 작업을 중단합니다.
