# Simulation Quality Criteria

이 문서는 `lib/validators.py`가 사용하는 정량 기준을 정리한다. 검증 함수는 `Judgment(tier, metric, ...)`을 반환하며 tier는 `pass | warning | retryable | fatal`이다. 임계값은 `lib/validators.py`의 모듈 상수로 정의되어 있으며 변경 시 본 문서도 함께 갱신해야 한다.

## 1. Step 5 — Ionization 중성도

함수: `judge_neutrality(net_charge)`

| `|net_charge|` | tier | 처리 |
|---|---|---|
| `< 1e-6` | pass | 다음 step |
| `≤ 0.1` (`NEUTRALITY_WARNING_TOL`) | warning | 제안: genion `-conc` 0.15 → 0.20 |
| `≤ 0.5` (`NEUTRALITY_FATAL_TOL`) | retryable | 자동 mutation 재시도 |
| `> 0.5` | fatal | 즉시 중단 |

## 2. Step 7 — Phase별 물리 검증

phase별로 `gmx energy`가 추출한 평균값을 기준 판정한다.

### 2.1 Temperature (NVT)
함수: `judge_temperature(observed, target)`

| `|observed − target|` (K) | tier | 제안 mutation |
|---|---|---|
| `≤ 3` (`TEMP_WARNING_K`) | pass | — |
| `≤ 10` (`TEMP_RETRYABLE_K`) | warning | `nvt.mdp` `tau_t` 0.1 → 0.5 |
| `> 10` | retryable | 자동 mutation 후 재시도 |

### 2.2 Density (NPT)
함수: `judge_density(observed, expected_range)`

표준 물 시스템 기본 범위: `(995, 1005)` kg/m³. 평균 중심값 대비 편차로 평가한다.

| `dev = |observed − center| / center` | tier | 제안 mutation |
|---|---|---|
| `dev = 0` (in range) | pass | — |
| `dev ≤ 0.02` (`DENSITY_WARNING_FRAC`) | warning | `npt.mdp` `tau_p` 2.0 → 3.0 |
| `0.02 < dev ≤ 0.10` (`DENSITY_RETRYABLE_FRAC`) | warning | `tau_p` 2.0 → 5.0 |
| `dev > 0.10` | retryable | 자동 mutation 후 재시도 |

### 2.3 Energy drift (Production)
함수: `judge_energy_drift(slope_per_ns)` (단위 kJ/mol per ns)

| `|slope|` | tier | 제안 mutation |
|---|---|---|
| `≤ 0.5` (`ENERGY_DRIFT_WARNING`) | pass | — |
| `≤ 5.0` (`ENERGY_DRIFT_RETRY`) | warning | `production.mdp` `dt` 0.002 → 0.001 |
| `> 5.0` | retryable | 자동 mutation 후 재시도 |

### 2.4 RMSD plateau (Production)
함수: `judge_rmsd_plateau(rmsd_series: list[float])`

`tail = rmsd_series[len/2:]`의 spread(max−min)로 판정.

| 조건 | tier | 제안 mutation |
|---|---|---|
| `len < 4` | warning | 데이터 부족 — 샘플링 연장 |
| `tail_spread ≤ 0.05` nm (`RMSD_PLATEAU_MAX_RANGE`) | pass | — |
| `tail_spread > 0.05` nm | warning | `production.mdp` `nsteps` +50% |

## 3. Step 8 — Analysis 보고 기준

`lib/validators.py`는 RMSD plateau 이외의 Step 8 metric에 대한 자동 판정을 제공하지 않는다. illustrator는 다음을 추출해 `report.md`에 게재한다.

| 지표 | 권장 해석 |
|---|---|
| RMSD backbone tail-half spread | `≤ 0.05 nm` 평탄 |
| Potential energy slope | 단조 감소 또는 안정 |
| Temperature drift | 평균 ± 표준편차가 target ± 3K |
| Density drift | 평균이 expected_range 내 |
| H-bond count | 시뮬 후반 변동 < 20% |

위 지표가 모두 충족되면 `step_8.rmsd_stable=True`, `step_8.energy_converged=True`로 기록된다.

## 4. Recovery Policy 요약

- **PASS**: 다음 단계로 즉시 진행.
- **WARNING**: `pending_warnings[]`에 페이로드 추가, skill은 `warning_pending_decision` 반환. 사용자/LLM이 `accept_warning_mutation` 또는 `decline_warning_mutation`으로 재호출. 자세한 흐름은 [`WARNING_FLOW.md`](WARNING_FLOW.md).
- **RETRYABLE**: 무인 mutation 재시도(최대 3회). 각 시도는 (command, parameters) 변경 의무.
- **FATAL**: 즉시 중단, `last_status="fatal"`, 원인을 `retry_history`에 기록.

## 5. 임계값 변경 절차

1. `lib/validators.py`의 상수를 수정한다.
2. 본 문서(섹션 1–3)의 임계값과 mutation 권장사항을 동기화한다.
3. `tests/unit/test_validators.py`의 경계값 케이스를 갱신한다.
4. 변경 사유를 PR description에 명시한다 (관련 incident, 새 시스템 클래스 추가 등).
