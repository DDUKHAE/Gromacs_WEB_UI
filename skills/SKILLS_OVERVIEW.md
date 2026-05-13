# Skills Overview — GROMACS 하네스 도구 모음

이 문서는 LLM 에이전트가 호출할 수 있는 모든 스킬(Agent Skill)의 목록, 호출 시점, 입출력 규약을 정의합니다.
각 스킬은 Claude Code / GPT Agent Skills 표준 형식(`SKILL.md` + YAML frontmatter)을 따릅니다.

---

## 스킬 디렉터리 구조

```
skills/
├── SKILLS_OVERVIEW.md              ← 현재 파일: 전체 스킬 목록 및 호출 규칙
│
├── gmx-executor/                   ← gmx 명령어 실행 래퍼
│   └── SKILL.md
│
├── mdp-composer/                   ← .mdp 파라미터 파일 생성기
│   ├── SKILL.md
│   └── references/
│       └── mdp_templates.md        ← 완전한 기본 템플릿 모음
│
├── system-validator/               ← 단계별 물리적 품질 검증
│   ├── SKILL.md
│   └── references/
│       └── validation_criteria.md  ← 정량적 검증 기준값
│
├── trajectory-analyzer/            ← 궤적 분석 및 최종 보고
│   └── SKILL.md
│
├── tutorial-router/                ← 입력 기반 튜토리얼 선택
│   └── SKILL.md
│
├── tutorial-planner/               ← 튜토리얼을 Step 0-8로 계획화
│   └── SKILL.md
│
└── protocol-compiler/              ← 계획을 실행 명령 스펙으로 변환
    └── SKILL.md
```

---

## 스킬 목록

| 스킬 ID | 폴더 | 역할 | 파이프라인 위치 |
|---|---|---|---|
| `GmxExecutor` | `gmx-executor/` | gmx 명령어를 안전하게 실행하고 결과를 정형화하여 반환 | 모든 Step |
| `MdpComposer` | `mdp-composer/` | 시뮬레이션 단계에 맞는 .mdp 파라미터 파일을 생성 | Step 4, 6 |
| `SystemValidator` | `system-validator/` | 각 단계 결과물의 물리적 유효성을 검사하고 진행 여부 판단 | 각 Step 완료 후 |
| `TrajectoryAnalyzer` | `trajectory-analyzer/` | 궤적/에너지 파일 분석 후 RMSD·RMSF·Gyration 데이터 및 보고서 생성 | Step 8 (최종 분석) |
| `TutorialRouter` | `tutorial-router/` | 입력 PDB/프롬프트 기반 튜토리얼 선택 및 누락 입력 보고 | Step 0 이후 |
| `TutorialPlanner` | `tutorial-planner/` | 선택된 튜토리얼을 Step 0-8 workflow로 매핑 | Step 0 이후 |
| `ProtocolCompiler` | `protocol-compiler/` | workflow를 `GmxExecutor` 호환 명령 스펙으로 컴파일 | Step 실행 직전 |

---

## Agent Skill 표준 형식

각 스킬은 다음 표준을 따릅니다 (Claude Code / GPT Agent Skills 호환).

```yaml
# SKILL.md 상단 YAML frontmatter
---
name: skill-name          # 1–64자, 소문자 + 하이픈 (폴더명과 일치)
description: >-           # 에이전트가 시작 시 읽는 유일한 부분 — 트리거 조건 포함
  "언제 이 스킬을 호출하는지" 명확하게 기술
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---
```

**Progressive Disclosure 원칙:**
- 에이전트는 시작 시 `description`만 로드 → 관련성이 있을 때만 전체 `SKILL.md` 로드
- 상세 문서는 `references/` 서브디렉터리에 분리 (500줄 초과 시)

---

## 스킬 호출 규약 (Calling Convention)

에이전트는 스킬을 호출할 때 아래 JSON 형식으로 인자를 전달합니다.

```json
{
  "skill": "<스킬 ID>",
  "params": {
    "<파라미터 키>": "<파라미터 값>"
  }
}
```

### 예시: GmxExecutor 호출
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
      "-water": "tip3p"
    },
    "interactive_responses": []
  }
}
```

---

## 파이프라인별 스킬 호출 흐름

```
Step 1–3: GmxExecutor (pdb2gmx → editconf → solvate)
          └─ 각 Step 후 → SystemValidator

Step 4–5: MdpComposer (ions.mdp 생성)
          └─ GmxExecutor (grompp → genion)

Step 6–7: MdpComposer (minim/nvt/npt/md .mdp 생성) [루프]
          └─ GmxExecutor (grompp → mdrun)
          └─ SystemValidator (에너지/온도/압력 GATE 판정)

Step 8:   SystemValidator (md 에너지 드리프트 GATE)
          └─ [PASS 후] TrajectoryAnalyzer (RMSD, RMSF, Gyration, Energy 심층 분석 + 보고서)
```

---

## 스킬 역할 경계 (SystemValidator vs TrajectoryAnalyzer)

| 크라이테리아 | SystemValidator | TrajectoryAnalyzer |
|---|---|---|
| **언제 호출?** | 각 Phase 완료 즉시 (블로킹) | md Phase PASS 이후 (비동기) |
| **목적** | “다음 단계 진행 가능?” GATE | “시뮬레이션 품질은 어떻습니까?” 심층 분석 |
| **md Phase RMSD** | ❌ 수행 안 함 | ✅ RMSD plateau, RMSF, Gyration 모두 수행 |
| **출력** | `PASS/FAIL/WARNING` 판정 JSON | `.xvg` 파일 + 마크다운 보고서 |

---

## 버전 관리 정책 (Versioning Policy)

모든 `SKILL.md`는 `metadata.version` 필드를 사용하며 **Semantic Versioning** (매이저.마이너.패치)을 따른다.

| 변경 유형 | 버전 업 | 예시 |
|---|---|---|
| 파이프라인 통합 보이지 않는 창본 수정 (typo 등) | 패치 (`x.x.1`) | 주석, 예시 문장 수정 |
| 파라미터 추가/수정 (하위 호환성 유지) | 마이너 (`x.1.0`) | `timeout_seconds` 파라미터 추가 |
| 특성 삭제, 스키마 파겴적 변경 | 매이저 (`2.0.0`) | Input Schema 구조 변경 |

**파일 변경 시 `version` 필드를 반드시 업데이트**한다. `SKILLS_OVERVIEW.md`의 스킬 목록 테이블에도 현재 버전을 단에 표기한다.

---

## 에러 시 스킬 호출 우선순위

1. `GmxExecutor` 실행 중 에러 발생
2. `gmx-executor/references/error_troubleshooting.md` 검색 → 해결책 확인
3. 해결책이 파라미터 수정인 경우 → `MdpComposer` 재호출
4. 해결책이 재실행인 경우 → `GmxExecutor` 재호출 (최대 3회)
5. 3회 이후에도 실패 시 → 사용자에게 에러 보고 (에스컬레이션)
