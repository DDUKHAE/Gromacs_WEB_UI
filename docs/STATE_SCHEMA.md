# `workspace/state.json` Schema (v1.0)

이 문서는 하네스의 단일 진실 소스인 `workspace/state.json`의 canonical schema를 정의한다. `lib/state.py`가 atomic R/W를 보장하며 모든 skill은 이 스키마를 따른다.

## 1. Top-Level Keys

| 키 | 타입 | 설명 |
|---|---|---|
| `schema_version` | string | 현재 `"1.0"`. major 변경 시 bump |
| `workspace_dir` | string | workspace 절대 경로 |
| `current_step` | int | 마지막으로 진입한 step (0–8) |
| `last_completed_stage` | `"env" \| "md" \| "viz" \| null` | skill 완료 marker |
| `tutorial` | object \| null | `{id, variant, manifest_path}` |
| `hardware` | object \| null | `{cpu_count, gpu_ids, ntomp}` |
| `step_outputs` | object | step별 산출 메타 (아래 참조) |
| `retry_history` | array | 실패/재시도 엔트리 |
| `pending_warnings` | array | 사용자 결정 대기 WARNING 페이로드 |
| `topology_backups` | array<string> | `.top.bak` 상대경로 누적 |

## 2. `tutorial` 객체

```json
{
  "id": "Lysozyme_in_water",
  "variant": "protein_aqueous_standard",
  "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"
}
```

`variant`는 `manifest.pipeline_variant`와 일치한다. derived 튜토리얼에서 manifest가 없으면 `null`.

## 3. `hardware` 객체

```json
{
  "cpu_count": 16,
  "gpu_ids": [0, 1],
  "ntomp": 8
}
```

`env-builder.collect_hardware()`가 Step 0에서 채운다. `gpu_ids`는 `nvidia-smi` 부재 시 `[]`.

## 4. `step_outputs` 객체

각 step이 자기 산출을 기록한다. 누락 키는 `lib.state.require_step_keys`가 차단한다.

### `step_1` — pdb2gmx
```json
{
  "forcefield": "charmm36",
  "water_model": "tip3p",
  "top_file": "stage1_env/topol.top",
  "gro_file": "stage1_env/processed.gro"
}
```

### `step_2` — editconf
```json
{
  "box_type": "cubic",
  "box_distance": 1.0,
  "box_gro": "stage1_env/box.gro"
}
```

### `step_3` — solvate
```json
{
  "solv_gro": "stage1_env/solv.gro",
  "n_solvent_molecules": 12345
}
```

### `step_5` — genion
```json
{
  "ion_gro": "stage1_env/ions.gro",
  "n_na": 12,
  "n_cl": 8,
  "net_charge": 0.0
}
```

> Step 4 (ions prep)는 `state.current_step`만 갱신하며 별도 `step_outputs` 키를 만들지 않는다 (산출 `ions.tpr`는 Step 5에서 소비).

### `step_7` — mdrun (per phase)
```json
{
  "em_gro": "stage2_md/em.gro",
  "nvt_gro": "stage2_md/nvt.gro",
  "npt_gro": "stage2_md/npt.gro",
  "production_gro": "stage2_md/production.gro"
}
```

Umbrella/Free-Energy variant는 `production_gro`에 마지막 production phase 산출을 기록한다.

### `step_8` — illustrator
```json
{
  "analysis_summaries": {
    "rmsd":  {"count": 1000, "min": 0.10, "max": 0.30, "mean": 0.21, "std": 0.03,
               "first": 0.10, "last": 0.22},
    "rmsf":  {...},
    "gyrate": {...},
    "sasa":  {...},
    "energy_potential":  {...},
    "energy_temperature": {...},
    "energy_density": {...},
    "energy_pressure": {...},
    "energy_total": {...}
  },
  "advanced_summaries": {
    "hbond": {...},
    "dssp":  {"xpm_path": "stage3_viz/dssp.xpm"},
    "pca":   {"eigenval_summary": {...}, "proj_xvg": "stage3_viz/pca_proj.xvg"}
  },
  "variant_summary": {...},
  "rmsd_stable": true,
  "energy_converged": true,
  "final_report_path": "stage3_viz/report.md"
}
```

## 5. `retry_history` 엔트리

```json
{
  "step": 7,
  "phase": "npt",
  "tier": "retryable" | "warning",
  "cause": "pressure_coupling",
  "remediation": "tau_p 2.0 → 5.0",
  "command": "<full gmx invocation>",
  "parameters": {"tau_p": 5.0},
  "warning_id": "<uuid or null>",
  "timestamp": "2026-05-14T10:00:00Z"
}
```

- `tier="warning"` 엔트리는 RETRYABLE budget을 소비하지 않는다.
- `cause`는 [`simulation_criteria.md`](simulation_criteria.md)와 동일 taxonomy: `unstable_energy`, `pressure_coupling`, `temperature_coupling`, `charge_neutralization`, `topology_mismatch`, `command_error`, `analysis_not_converged`, `missing_input`, `auto_decline_noninteractive`, `user_decline`.

## 6. `pending_warnings` 엔트리

```json
{
  "warning_id": "<uuid>",
  "step": 7,
  "phase": "npt",
  "metric": "density",
  "observed": 985.2,
  "expected_range": [995, 1005],
  "cause": "pressure_coupling",
  "suggested_mutation": {
    "target": "npt.mdp",
    "changes": {"tau_p": "2.0 → 5.0"},
    "rationale": "barostat coupling too tight; relax tau_p"
  }
}
```

`accept_warning_mutation` 또는 `decline_warning_mutation`이 호출되면 해당 엔트리가 제거되고 `retry_history`에 `tier:"warning"` 엔트리가 추가된다.

## 7. `topology_backups`

`.top.bak`의 상대 경로(`stage1_env/topol.top.bak`)를 시간 순으로 append한다. Step 3과 Step 5 진입 시 의무 backup, 실패 시 가장 최근 항목으로 rollback.

## 8. Stage Transition

`last_completed_stage`는 다음 순서로만 전진한다.

```
null → env → md → viz
```

skip이 가능: 외부 도구로 `stage1_env/`를 준비했다면 `last_completed_stage="env"`로 시작해 `md-runner` 직접 호출 가능 ([`independent_entry_guide.md`](independent_entry_guide.md)).

## 9. 호환성 정책

- `schema_version` major 증가는 비호환 변경. 그 외 추가 키는 후방 호환.
- 신규 필드는 모두 기본값(null/[]/{}) 허용하도록 추가.
- skill의 `assert_ready`는 검사 대상 키가 존재할 때만 통과하므로, 필수 산출 키를 변경할 때는 동시 갱신.

## 10. 변경 절차

1. `lib/state.py`의 `initial()` 또는 require* 함수를 수정.
2. 본 문서를 함께 갱신.
3. `tests/unit/test_state.py`의 round-trip 테스트가 새 키를 포함하도록 확장.
4. `pipeline_contract.md`의 step별 contract도 동기화.
