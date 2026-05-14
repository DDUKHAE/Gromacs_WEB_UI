# LLM Runtime Tutorial Contract

## Read Order Contract

런타임은 아래 순서를 고정으로 사용한다.

1. `docs/tutorial/TUTORIAL_OVERVIEW.md`
2. `docs/tutorial/tutorial_index.json`
3. 선택 튜토리얼 `tutorial.manifest.json` (있을 경우)
4. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
5. `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
6. 현재 Step에 필요한 tutorial part

## Source-of-Truth Priority

1. Manifest (`tutorial.manifest.json`): runtime truth
2. `tutorial_index.json`: routing/index truth
3. tutorial part markdown: rationale/reference

## Step Contract

- Step 번호 체계는 0-8 고정
- tutorial별 차이는 `pipeline_variant`, `variant_steps`로만 표현
- Step 3/5(topology mutation)는 backup/rollback 강제

## Immediate FAIL Conditions

- `simulation_state.json` 필수 키 누락
- Step 0 hardware profile 누락
- Step 3 또는 Step 5 전 `topol.top` 백업 누락
- retry 시 동일 command string 또는 동일 파라미터 재사용
- retry_history 원인 분류/변경 사항 기록 누락

## Gate Execution

- Step 1-7: `SystemValidator` gate 필수
- Step 8: `TrajectoryAnalyzer` 기반 downsampled 결과로 최종 판정

## Router/Planner Required Outputs

- Router: `selected_tutorial`, `confidence`, `missing_inputs`, `unsupported_reason`, `selected_docs`
- Planner: `workflow`, `state_requirements`, `validator_gates`, `topology_backup_required`, `unsupported_reason`
