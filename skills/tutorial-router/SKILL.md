---
name: tutorial-router
description: >-
  입력 PDB 파일 특성과 사용자 프롬프트를 바탕으로 적절한 GROMACS 튜토리얼 계열을 선택합니다.
  Step 0 실행 직후 호출하여 실행할 파이프라인 variant를 결정하고, 누락 입력을 보고해야 합니다.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: TutorialRouter

`TutorialRouter`는 런타임에서 어떤 튜토리얼 프로토콜을 따를지 결정하는 분기 스킬입니다.

## Input Schema

```json
{
  "prompt": "사용자 목표",
  "pdb_path": "/abs/path/input.pdb",
  "available_manifests": ["docs/tutorial/Lysozyme_in_water/tutorial.manifest.json"]
}
```

## Output Schema

```json
{
  "status": "success | error",
  "selected_tutorial": "Lysozyme_in_water",
  "pipeline_variant": "protein_aqueous_standard",
  "confidence": 0.9,
  "required_inputs": ["protein_pdb"],
  "missing_inputs": []
}
```

## Routing Rules (Phase 1)

1. 기본값은 `Lysozyme_in_water`로 라우팅한다.
2. 프롬프트에 `ligand`, `complex`가 있으면 `Protein_Ligand_Complex` 후보를 우선 검토한다.
3. 프롬프트에 `membrane`, `dppc`가 있으면 `KALP15_in_DPPC` 후보를 우선 검토한다.
4. 선택된 튜토리얼 manifest가 없으면 `status: error`로 반환한다.
