---
name: tutorial-planner
description: >-
  TutorialRouter가 선택한 튜토리얼을 ARCHITECTURE.md Step 0-8 실행 계획으로 변환합니다.
  각 step별 참조 문서와 기대 산출물을 포함한 구조화된 workflow를 반환해야 합니다.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: TutorialPlanner

`TutorialPlanner`는 튜토리얼 문서를 실행 가능한 단계 계획으로 매핑합니다.

## Input Schema

```json
{
  "selected_tutorial": "Lysozyme_in_water",
  "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"
}
```

## Output Schema

```json
{
  "status": "success | error",
  "workflow": [
    {"step": 1, "action": "topology_generation", "doc": "generate_topology/prepare_the_topology.md"},
    {"step": 2, "action": "box_definition", "doc": "define_box_and_solvate/defining_the_unit_cell_and_adding_solvent.md"}
  ]
}
```

## Constraints

1. `ARCHITECTURE.md`의 Step 0-8 계약을 깨지 않는다.
2. 튜토리얼 특화 단계가 있더라도 공통 step 번호 체계를 유지한다.
3. 모든 step 항목에 `doc` 경로와 `action`을 포함한다.
