# Skill: GmxExecutor

GROMACS `gmx` 명령어를 안전하게 실행하고, 대화형(Interactive) 입력을 자동 처리하며, 결과를 LLM이 파싱하기 좋은 형태로 정형화하여 반환하는 핵심 실행 스킬입니다.

---

## 1. 역할 및 존재 이유

터미널에서 `gmx` 명령어를 직접 실행하면 다음과 같은 문제들이 발생합니다:

- **대화형 프롬프트(Interactive Prompt):** `gmx genion`은 이온으로 치환할 그룹을 사용자에게 직접 물어봅니다. LLM은 이 단계에서 멈춰버립니다.
- **장황한 로그:** 수백 줄의 stdout 출력을 그대로 LLM에 전달하면 컨텍스트 윈도우를 낭비합니다.
- **에러 파싱 어려움:** GROMACS의 Fatal Error 메시지는 로그 하단에 파묻혀 있어 별도 파싱이 필요합니다.

`GmxExecutor`는 이 모든 문제를 해결하는 중간 계층입니다.

---

## 2. 입력 스키마 (Input Schema)

```json
{
  "command": "<gmx 모듈 이름>",
  "args": {
    "<플래그>": "<값>"
  },
  "interactive_responses": ["<응답1>", "<응답2>"]
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `command` | string | ✅ | gmx 모듈 이름 (예: `pdb2gmx`, `editconf`, `mdrun`) |
| `args` | object | ✅ | 명령어 플래그와 값의 딕셔너리 |
| `interactive_responses` | array | ❌ | 대화형 프롬프트에 순서대로 전달할 응답 목록 |

---

## 3. 반환 스키마 (Output Schema)

```json
{
  "status": "success | error",
  "output_files": ["<생성된 파일 목록>"],
  "summary": "<핵심 로그 요약 (최대 5줄)>",
  "fatal_error": "<에러 메시지 (status가 error인 경우)>"
}
```

---

## 4. 내부 동작 방식

1. `args` 딕셔너리를 조합하여 완전한 명령어 문자열을 구성합니다.
2. `interactive_responses`가 존재하는 경우 `echo -e "응답1\n응답2" | gmx ...` 형태의 파이프라인으로 자동 우회합니다.
3. 명령어 실행 전, 모든 입력 파일의 존재 여부를 사전 검증합니다. 파일이 없으면 즉시 `error`를 반환합니다.
4. 실행 후 `stdout/stderr`에서 `Fatal error:` 키워드를 탐지하여 에러 메시지만 추출합니다.
5. 정상 종료 시 생성된 파일 목록을 스캔하여 `output_files`에 담아 반환합니다.

---

## 5. 주요 명령어별 호출 예시

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
> `-ignh` 플래그는 수소 원자를 자동으로 처리합니다. 포스필드 선택은 `docs/force_field_guide.md`를 참조하세요.

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
> `"SOL"` 응답은 물(Solvent) 그룹을 이온으로 치환하도록 자동으로 선택합니다.

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
    "interactive_responses": []
  }
}
```
