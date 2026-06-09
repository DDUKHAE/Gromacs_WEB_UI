# Independent-Entry Guide

세 skill(`env-builder`, `md-runner`, `illustrator`)은 풀-파이프라인 체인뿐 아니라 **각자 단독 진입**도 지원한다. 외부 도구(CHARMM-GUI 다운로드, 사전 평형화된 시스템, 과거 trajectory)에서 받은 산출물을 임의의 stage에서 합류시킬 수 있다.

진입 계약은 `assert_ready()`가 검사하며 `lib.state.StateContractError`가 누락을 차단한다.

## 1. 시나리오별 진입 지점

| 가지고 있는 것 | 진입 skill | 추가 작업 |
|---|---|---|
| PDB만 | `env-builder` (build_environment) | 없음 (정상 풀 진입) |
| 사전 솔베이션·이온화된 `stage1_env/` | `md-runner` (run_simulation) | `state.json` 최소 구성 + 파일 배치 |
| 사전 실행된 trajectory `stage2_md/{tpr,xtc,edr}` | `illustrator` (illustrate) | `state.json` 최소 구성 + 파일 배치 |

## 2. md-runner 단독 진입 — CHARMM-GUI 시나리오

CHARMM-GUI에서 받은 GROMACS 출력물 또는 다른 도구로 평형화한 시스템을 받아 MD만 자동 실행한다.

### 2.1 워크스페이스 준비

```bash
WS="$PWD/runs/external_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$WS/stage1_env" "$WS/stage2_md" "$WS/stage3_viz"
```

다음 파일을 `stage1_env/`에 배치:

| 파일 | 설명 |
|---|---|
| `processed.gro` | 단백질(+리간드/막) 좌표 |
| `topol.top` | 최종 topology (`[ molecules ]`에 SOL, NA, CL 모두 반영) |
| `topol.top.bak` | 안전을 위해 동일 내용 백업 |
| `ions.gro` | 용매·이온이 포함된 완전 시스템 |
| `box.gro` | (선택) editconf 직후 산출 — md-runner는 사용 안 함 |
| `solv.gro` | (선택) solvate 직후 산출 — md-runner는 사용 안 함 |
| `index.ndx` | (선택) 사용자 정의 group |

`processed.gro`, `topol.top`, `ions.gro` 세 개가 필수다.

### 2.2 최소 `state.json`

```python
from pathlib import Path
from lib import state

ws = Path("runs/external_2026-05-15_120000")
s = state.initial(ws)
s["last_completed_stage"] = "env"
s["hardware"] = {"cpu_count": 16, "gpu_ids": [0], "ntomp": 8}
s["tutorial"] = {
    "id": "Lysozyme_in_water",
    "variant": "protein_aqueous_standard",
    "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json",
}
s["step_outputs"]["step_1"] = {
    "forcefield": "charmm36", "water_model": "tip3p",
    "top_file": "stage1_env/topol.top",
    "gro_file": "stage1_env/processed.gro",
}
s["step_outputs"]["step_2"] = {
    "box_type": "cubic", "box_distance": 1.0,
    "box_gro": "stage1_env/box.gro",
}
s["step_outputs"]["step_3"] = {
    "solv_gro": "stage1_env/solv.gro",
    "n_solvent_molecules": 12345,
}
s["step_outputs"]["step_5"] = {
    "ion_gro": "stage1_env/ions.gro",
    "n_na": 12, "n_cl": 8, "net_charge": 0.0,
}
s["topology_backups"] = ["stage1_env/topol.top.bak"]
state.write(ws, s)
```

### 2.3 md-runner 호출

```python
from skills.md_runner import run_simulation
result = run_simulation(workspace_dir=ws, interactive=False)
# {"status": "complete"} on success
```

`assert_ready`가 검사하는 항목:

- `last_completed_stage == "env"`
- `step_outputs`에 `step_1`, `step_2`, `step_3`, `step_5` 모두 존재
- `stage1_env/`에 `processed.gro`, `topol.top`, `ions.gro` 존재
- `state.hardware` 비어있지 않음

위 중 하나라도 누락이면 `StateContractError`가 발생한다.

### 2.4 변형(variant) 라우팅 보정

CHARMM-GUI가 막/리간드 시스템을 만든 경우 `tutorial.variant`를 정확히 설정한다:

- 막: `"membrane_md_standard"` (id `KALP15_in_DPPC`)
- 단백질-리간드: `"protein_ligand_complex"` (id `Protein_Ligand_Complex`)

variant가 phase sequence를 결정하므로 미설정 시 `protein_aqueous_standard`로 fallback 된다.

## 3. illustrator 단독 진입 — 기존 trajectory 분석

이미 실행된 trajectory(`md.xtc`/`md.tpr`/`md.edr`)를 분석한다.

### 3.1 파일 배치

```
workspace/
├── stage2_md/
│   ├── production.tpr
│   ├── production.xtc
│   └── production.edr
└── stage3_viz/   (자동 생성)
```

다른 이름(예: `md.xtc`)이면 `production.*`로 rename하거나 `state.step_outputs.step_7.production_gro`의 stem을 그 이름에 맞게 설정.

### 3.2 최소 `state.json`

```python
s = state.initial(ws)
s["last_completed_stage"] = "md"
s["tutorial"] = {"id": "Lysozyme_in_water",
                  "variant": "protein_aqueous_standard",
                  "manifest_path": ""}
s["step_outputs"]["step_7"] = {
    "production_gro": "stage2_md/production.gro",
}
state.write(ws, s)
```

### 3.3 illustrator 호출

```python
from skills.illustrator import illustrate
result = illustrate(
    workspace_dir=ws,
    analyses=["rmsd", "rmsf", "gyrate", "energy"],
    render_frames=[0, "last"],
    animation={"enabled": False},  # PyMOL/ffmpeg 없으면 비활성
    report_html=False,
)
# result == {"report_path": ".../report.md", ...}
```

## 4. 결정 트리

```
입력이 무엇인가?
├── PDB + 자연어 prompt  → env-builder.build_environment
├── 사전 준비된 stage1_env/  → md-runner.run_simulation
└── 사전 준비된 stage2_md/  → illustrator.illustrate
```

세 단계 모두 file-based 계약으로 분리되어 있어 도중에 끊고 다시 합류해도 무해하다.

## 5. 흔한 오류

| 증상 | 원인 | 해결 |
|---|---|---|
| `StateContractError: last_completed_stage must be 'env'` | stage marker 미설정 | `s["last_completed_stage"] = "env"` |
| `StateContractError: missing required step keys: ['step_3']` | step_outputs에 키 누락 | 빈 dict라도 `s["step_outputs"]["step_3"] = {...}` 추가 |
| `StateContractError: missing stage1 file: ions.gro` | 파일이 stage1_env/ 외부에 있음 | symlink 또는 복사로 정확한 위치에 배치 |
| `StateContractError: hardware profile missing` | `s["hardware"]` null | `collect_hardware`를 별도 호출하거나 수동 dict 설정 |
| `assert_ready` 통과했지만 grompp가 분자 수 불일치로 실패 | `topol.top`과 `ions.gro` 분자 수 불일치 | 두 파일이 동일 source 출력인지 확인 |

## 6. 회귀 검증

독립 진입 계약은 다음 테스트가 검증한다 — 환경 구성 시 반드시 통과해야 한다.

```bash
pytest tests/contract/test_state_handoff.py -v
```

3개 케이스: md-runner 단독 진입, illustrator 단독 진입, 풀-체인 stage marker 전이.
