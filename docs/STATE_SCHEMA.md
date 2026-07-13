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
| `provenance` | object | 재현성 메타데이터 (`gmx_version`, mdp 해시, 시드 등) — 아래 §3.1 참조 |

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

## 3.1 `provenance` 객체 (Task B5)

각 런의 재현에 필요한 메타데이터. `lib.state.initial()`이 빈 骨格을 만들고,
`env-builder`/`md-runner`가 실행 중 채운다. 필드가 채워지지 않을 이유(예:
`gmx` 미설치)가 있으면 크래시 대신 `null`을 남긴다 — provenance 캡처는 절대
파이프라인을 실패시키지 않는다.

```json
{
  "gmx_version": "2023.3",
  "platform": "Linux-5.4.0-144-generic-x86_64-with-glibc2.35",
  "force_field": "charmm36",
  "mdp_hashes": {
    "ions": "3f8b1c...(sha256 hex, 64 chars)",
    "em":   "a1c9de...",
    "nvt":  "902fbe...",
    "npt":  "77aa10...",
    "production": "c4d001..."
  },
  "seed": {
    "nvt": 20240101
  }
}
```

| 키 | 타입 | 설명 |
|---|---|---|
| `gmx_version` | string \| null | `gmx --version`의 `GROMACS version:` 라인 파싱 결과 (`lib.gmx_wrapper.get_version`). `gmx` 바이너리 부재/응답없음 시 `null` — 크래시하지 않음 |
| `platform` | string \| null | `platform.platform()` 산출 OS/아키텍처 문자열 |
| `force_field` | string \| null | Step 1(`pdb2gmx`)에 실제 사용된 포스필드 이름 (`lib.state.record_force_field`) |
| `mdp_hashes` | object<string, string> | 렌더링된 `.mdp` 파일의 sha256 hex digest, phase(`ions`/`em`/`nvt`/`npt`/`production`/`umbrella`/`free_energy`)로 키잉 (`lib.state.record_mdp_hash`). 동일 입력(overrides) → 동일 해시 → 결정론적 재현성 증거 |
| `seed` | object<string, int> | 실제 렌더링된 mdp에서 사용된 `gen_seed` 값, phase로 키잉 (`lib.state.record_seed`). 현재는 `nvt`만 `gen_vel`을 사용하므로 채워짐 |

**시드 처리 / 재현 모드:** 프로덕션 기본값은 `gen_seed = -1`(GROMACS가 매번
새 난수 시드 사용 — 통계적으로 독립적인 반복실행에는 정확하지만 비트단위
재현은 불가). 호출자가 `lib.mdp_templates.base.render("nvt", {"reproducible_mode": True}, ...)`
로 렌더링하면 고정 시드 `lib.mdp_templates.base.REPRODUCIBLE_SEED`(`20240101`)가
기록되고 mdp에 박힌다. 명시적으로 `gen_seed=<int>`를 넘기면 `reproducible_mode`
보다 우선한다. 어느 경로든 실제 사용된 값이 `provenance.seed`에 남는다.

**감사 추적:** mdp·명령 트레이스는 이미 `stage2_md/<phase>_progress.log`
(mdrun 실시간 로그) + `step_outputs.step_7.grompp_warnings`(억제된 grompp
WARNING)로 남는다. `provenance.mdp_hashes`는 이를 대체하지 않고, "어떤 mdp
내용이 실제로 grompp에 들어갔는지"를 해시로 고정해 보강한다.

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
