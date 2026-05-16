# Pipeline Contract: Input/Output & State Transitions

이 문서는 GROMACS 하네스 파이프라인의 단계 간 데이터 계약을 정의한다. 세 skill(`env-builder`, `md-runner`, `illustrator`)과 내부 `lib/` 모듈은 모두 이 계약을 따른다.

전체 스키마 상세는 [`STATE_SCHEMA.md`](STATE_SCHEMA.md)를 참조한다.

## 1. 전역 상태 계약

`workspace/state.json`이 모든 단계의 single source of truth다. atomic R/W는 `lib/state.py`가 제공한다.

필수 최상위 키:

- `schema_version` (현재 `"1.0"`)
- `workspace_dir` (절대 경로)
- `current_step` (0–8 정수)
- `last_completed_stage` (`"env" | "md" | "viz" | null`)
- `tutorial` (`{id, variant, manifest_path}` 또는 null)
- `hardware` (`{cpu_count, gpu_ids, ntomp}` 또는 null)
- `step_outputs` (Step 1–8 산출물 메타)
- `retry_history` (실패/재시도 기록 배열, `tier`는 `retryable | warning`)
- `pending_warnings` (사용자 결정 대기 중 WARNING 페이로드)
- `topology_backups` (`.top.bak` 상대경로 리스트)

## 2. Stage ↔ Step 매핑

| stage label | skill | step 범위 |
|---|---|---|
| `env` | `env-builder` | 0–5 |
| `md` | `md-runner` | 6–7 |
| `viz` | `illustrator` | 8 |

`last_completed_stage`는 skill 완료 시 `env → md → viz` 순으로 전진한다. 어느 stage에서든 단독 진입이 가능하다(독립 호출 계약, [`independent_entry_guide.md`](independent_entry_guide.md) 참조).

## 3. Step별 입출력 계약

각 Step의 결과는 `state.json.step_outputs.step_N`에 기록된다.

### Step 0 — Hardware profile (`env-builder.collect_hardware`)
- 입력: 없음
- 출력: `state.hardware = {cpu_count, gpu_ids, ntomp}`

### Step 1 — Topology generation (`pdb2gmx`)
- 입력: `inputs/input.pdb`
- 출력 파일: `stage1_env/processed.gro`, `stage1_env/topol.top`, `stage1_env/posre.itp`
- 상태: `step_outputs.step_1 = {forcefield, water_model, top_file, gro_file}`

### Step 2 — Box definition (`editconf`)
- 입력: Step 1 산출
- 출력: `stage1_env/box.gro`
- 상태: `step_outputs.step_2 = {box_type, box_distance, box_gro}`

### Step 3 — Solvation (`solvate`)
- 사전 조건: `stage1_env/topol.top.bak` 생성 후 진행
- 입력: Step 2 산출, `topol.top`
- 출력: `stage1_env/solv.gro`
- 부수 효과: `topol.top` `[ molecules ]` 섹션에 `SOL` 추가
- 상태: `step_outputs.step_3 = {solv_gro, n_solvent_molecules}`, `topology_backups`에 `.bak` 경로 append
- 실패 시: 백업으로 rollback

### Step 4 — Ions prep (`grompp -f ions.mdp`)
- 입력: `lib/mdp_templates`로 렌더링된 `ions.mdp`
- 출력: `stage1_env/ions.tpr`
- 상태: `current_step = 4` (별도 키 없음)

### Step 5 — Ionization (`genion`)
- 사전 조건: `topol.top` 백업 갱신
- 입력: `ions.tpr`, `topol.top`
- 출력: `stage1_env/ions.gro`
- 상태: `step_outputs.step_5 = {ion_gro, n_na, n_cl, net_charge}`, `last_completed_stage = "env"`

### Step 6 — Phase prep (`grompp`, per phase)
- 입력: phase별 `.mdp` (`em`, `nvt`, `npt`, `production`, `umbrella`, `free_energy`)
- 출력: `stage2_md/{phase}.tpr`
- 상태: `current_step = 6` (per-phase metadata는 `retry_history`로 추적)

### Step 7 — Run (`mdrun`, per phase)
- 입력: `stage2_md/{phase}.tpr`
- 출력: `stage2_md/{phase}.{gro,xtc,edr,trr,log,cpt}`
- 검증: phase별 validator gate (`lib/validators.py`)
- 상태: `step_outputs.step_7 = {em_gro, nvt_gro, npt_gro, production_gro}`, `last_completed_stage = "md"`

### Step 8 — Analysis & Illustration
- 입력: Step 7 trajectory + edr
- 출력: `stage3_viz/{*.xvg, *.png, frame_*.png, trajectory.mp4, report.md, report.html}`
- 상태: `step_outputs.step_8 = {analysis_summaries, advanced_summaries, variant_summary, final_report_path}`, `last_completed_stage = "viz"`
- 규칙: LLM은 원본 `.xvg`/`.xtc`를 직접 읽지 않는다. 모든 통계는 `lib/xvg_parser`로 downsample된 JSON으로 받는다.

## 4. 에러 처리 계약

판정 등급은 `lib/validators.Judgment.tier`로 표현된다.

| tier | 의미 | 처리 |
|---|---|---|
| `pass` | 정상 진행 | 다음 phase/step |
| `warning` | 권장 범위 이탈, 사용자 결정 필요 | `pending_decision` 반환 → `accept_warning_mutation` 또는 `decline_warning_mutation` 재호출 ([`WARNING_FLOW.md`](WARNING_FLOW.md)) |
| `retryable` | 즉시 mutation 후 재시도 | 최대 3회, mutation 강제, 동일 cmd/parameter 재사용 금지 |
| `fatal` | 즉시 중단 | 사용자에게 사유 보고 |

`retry_history[]` 엔트리 필수 필드:

```json
{
  "step": 7,
  "phase": "npt",
  "tier": "retryable",
  "cause": "pressure_coupling",
  "remediation": "tau_p 2.0 → 5.0",
  "command": "<gmx invocation>",
  "parameters": {"tau_p": 5.0},
  "warning_id": "<uuid or null>",
  "timestamp": "..."
}
```

`lib/validators.assert_unique_attempt`가 동일 `command`+`parameters` 재시도를 차단한다. `lib/validators.retryable_budget_remaining`이 (step, phase)당 `retryable` 누적을 추적한다. WARNING tier 재시도는 budget을 소비하지 않는다.

## 5. 안전 계약 (Mandatory)

1. **Topology 백업**: Step 3, Step 5 진입 직전 `topol.top.bak` 생성 — 누락 시 즉시 FATAL.
2. **Hardware profile**: Step 6 진입 전 `state.hardware` 누락 시 FATAL (`md-runner.assert_ready`).
3. **Identical-retry 금지**: `retry_history`와 동일한 `(command, parameters)` 조합 재호출 시 `RetryContractError`.
4. **대용량 파일 보호**: `.xvg`/`.xtc`/`.trr` 직접 read 금지. `lib/xvg_parser` 또는 `illustrator` 분석 출력만 사용.
5. **Stage marker 정합**: 각 skill의 `assert_ready`는 `last_completed_stage`가 기대값과 일치하는지 확인.
