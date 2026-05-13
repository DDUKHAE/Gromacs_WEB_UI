---
name: protocol-compiler
description: >-
  TutorialPlanner의 workflow를 GmxExecutor 호출에 직접 사용할 수 있는 명령 스펙으로 컴파일합니다.
  토폴로지 변경 step(solvate, genion)에 대해 backup/rollback 정책 플래그를 반드시 포함해야 합니다.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: ProtocolCompiler

`ProtocolCompiler`는 계획 단계 JSON을 실행 명령 스펙으로 변환합니다.

## Input Schema

```json
{
  "workflow": [{"step": 3, "action": "solvation"}],
  "state": {"top_file": "topol.top", "gro_file": "protein_box.gro"}
}
```

## Output Schema

```json
{
  "status": "success | error",
  "commands": [
    {
      "step": 3,
      "command": "solvate",
      "args": {"-cp": "protein_box.gro", "-cs": "spc216.gro", "-p": "topol.top", "-o": "protein_solv.gro"},
      "requires_backup": true,
      "topology_mutates": true
    }
  ]
}
```

## Constraints

1. 동일 재시도에서는 같은 command string을 금지한다.
2. `requires_backup: true`인 step은 실행 전 `topol.top` 백업을 강제한다.
3. 출력 스펙은 `GmxExecutor` 입력 스키마와 정합해야 한다.
