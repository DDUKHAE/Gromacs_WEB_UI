---
name: gmx-executor
description: >-
  GROMACS gmx 명령어를 안전하게 실행하고 결과를 정형화된 JSON으로 반환하는 핵심 실행 스킬.
  다음 상황에서 이 스킬을 호출한다: pdb2gmx, editconf, solvate, grompp, genion, mdrun 등
  gmx 모듈을 실행해야 할 때. 대화형 프롬프트(interactive prompt)가 필요한 명령어
  (예: genion의 그룹 선택)를 자동 처리해야 할 때. 실행 결과에서 Fatal Error를 파싱하고
  output_files 목록을 추출해야 할 때.
metadata:
  author: GROMACS Harness
  version: 1.0.0
  domain: molecular-dynamics
  pipeline_role: executor
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: GmxExecutor

GROMACS `gmx` 명령어를 안전하게 실행하고, 대화형(Interactive) 입력을 자동 처리하며,
결과를 LLM이 파싱하기 좋은 형태로 정형화하여 반환하는 핵심 실행 스킬이다.

## Overview

터미널에서 `gmx` 명령어를 직접 실행하면 세 가지 문제가 발생한다.

1. **대화형 프롬프트(Interactive Prompt):** `gmx genion`은 이온으로 치환할 그룹을 사용자에게 직접 물어본다. 에이전트는 이 단계에서 멈춘다.
2. **장황한 로그:** 수백 줄의 stdout 출력을 그대로 전달하면 컨텍스트 윈도우를 낭비한다.
3. **에러 파싱 어려움:** GROMACS의 Fatal Error 메시지는 로그 하단에 파묻혀 있어 별도 파싱이 필요하다.

`GmxExecutor`는 이 모든 문제를 해결하는 중간 계층(Wrapper)이다.

## 2. 입력 스키마 (Input Schema)

```json
{
  "command": "<gmx 모듈 이름>",
  "args": {
    "<플래그>": "<값>"
  },
  "interactive_responses": ["<응답1>", "<응답2>"],
  "backup_topology": true,
  "retry_count": 0,
  "timeout_seconds": 3600,
  "cwd": "<작업 디렉터리 절대 경로>"
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `command` | string | ✅ | gmx 모듈 이름 (예: `pdb2gmx`, `editconf`, `mdrun`) |
| `args` | object | ✅ | 명령어 플래그와 값의 딕셔너리 |
| `interactive_responses` | array | ❌ | 대화형 프롬프트에 순서대로 전달할 응답 목록 |
| `backup_topology` | boolean | ❌ | `true` 설정 시 명령어 실행 전 `topol.top` 파일을 `topol.top.bak_<timestamp>`로 백업함 (파괴적 명령어 시 필수) |
| `retry_count` | integer | ❌ | 무한 루프 방지용 카운터. 에이전트가 재시도할 때마다 1씩 증가시켜 전달해야 함. 3 이상 시 자동 에러 반환. |
| `timeout_seconds` | integer | ❌ | 명령어 최대 실행 시간 (기본: 3600초. `mdrun`은 수 시간 소요 시 86400등 사용) |
| `cwd` | string | ❌ | 명령어 실행 작업 디렉터리 (분자 동역학 시뮬레이션 데이터 디렉터리) |

## Output Schema

```json
{
  "status": "success | error | timeout",
  "output_files": ["<생성된 파일 목록>"],
  "summary": "<핵심 로그 요약 (최대 5줄)>",
  "fatal_error": "<에러 메시지 (status가 error인 경우)>",
  "elapsed_seconds": "<실제 실행 시간 (초)>"
}
```

## Workflow

에이전트는 다음 순서로 이 스킬을 실행한다.

1. `cwd`가 지정된 경우 해당 디렉터리로 작업 경로를 설정한다.
2. `args` 딕셔너리를 조합하여 완전한 명령어 문자열을 구성한다.
3. `interactive_responses`가 존재하는 경우 `echo -e "응답1\n응답2" | gmx ...` 형태의 파이프라인으로 자동 우회한다.
4. 명령어 실행 전, 모든 입력 파일의 존재 여부를 사전 검증한다. 파일이 없으면 즉시 `error`를 반환한다.
5. `timeout_seconds` 경과 시 `status: timeout`을 반환한다. `mdrun` 실패로 처리하지 않고 에이전트에게 에스커레이션한다.
6. 실행 후 `stdout/stderr`에서 `Fatal error:` 키워드를 탐지하여 에러 메시지만 추출한다.
7. 정상 종료 시 생성된 파일 목록을 스캔하여 `output_files`에 담아 반환한다.

## Usage Examples

### Step 1: pdb2gmx (토폴로지 생성)

```json
{
  "skill": "GmxExecutor",
  "params": {
    "command": "pdb2gmx",
    "args": {
      "-f": "protein.pdb",
      "-o": "protein_processed.gro",
      "-p": "topol.top",
      "-ff": "charmm36m-ut",
      "-water": "tip3p",
      "-ignh": ""
    },
    "interactive_responses": []
  }
}
```

> `-ignh` 플래그는 수소 원자를 자동으로 처리한다. 포스필드 선택은 [`references/force_field_guide.md`](./references/force_field_guide.md)를 참조.

### Step 5: genion (이온화)

```json
{
  "skill": "GmxExecutor",
  "params": {
    "command": "genion",
    "args": {
      "-s": "ions.tpr",
      "-o": "protein_solv_ions.gro",
      "-p": "topol.top",
      "-pname": "NA",
      "-nname": "CL",
      "-neutral": ""
    },
    "interactive_responses": ["SOL"]
  }
}
```

> `"SOL"` 응답은 물(Solvent) 그룹을 이온으로 치환하도록 자동 선택한다.

### Step 7: mdrun (시뮬레이션 실행)

```json
{
  "skill": "GmxExecutor",
  "params": {
    "command": "mdrun",
    "args": {
      "-v": "",
      "-deffnm": "md_production",
      "-ntmpi": "1",
      "-ntomp": "4"
    },
    "interactive_responses": [],
    "timeout_seconds": 86400,
    "cwd": "/absolute/path/to/simulation/dir"
  }
}
```

> `timeout_seconds: 86400` = 24시간. GPU 사용 시 `-ntmpi 1 -ntomp 4 -gpu_id 0` 조합 권장.

## Guidelines & Constraints

- 에러 발생 시 `references/error_troubleshooting.md`를 먼저 검색하고 자율적으로 재시도한다 (최대 3회).
- `fatal_error` 필드에 에러 원인이 기록된 경우, 에이전트는 `MdpComposer` 또는 `SystemValidator`와 연계하여 파라미터를 수정한 후 재호출한다.
- `-ntmpi`, `-ntomp` 값은 실행 환경의 CPU/GPU 코어 수에 맞게 조정한다.
- `cwd`는 시뮬레이션 데이터 디렉터리의 **절대 경로**를 사용한다.
- `timeout_seconds` 기본값: 일반 명령어는 `3600`(1시간), `mdrun`은 시뮬레이션 시간에 따라 `86400`(24시간) 이상으로 설정한다.
- `status: timeout` 반환 시 에이전트는 `-cpi md.cpt` 촬렉포인트 재시작 옵션을 고려한다.
