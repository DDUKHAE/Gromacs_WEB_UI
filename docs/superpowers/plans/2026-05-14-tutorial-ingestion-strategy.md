# GROMACS Tutorial Ingestion Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 튜토리얼 문서 집합을 LLM 자율 하네스에 최적화된 읽기 전략으로 재구성하고, 길잡이 문서 + 필수지식 요약 + 문서 구조(통합/분할) 정책 + 런타임 Router/Planner 계약을 확정한다.

**Architecture:** AGENTS.md/ARCHITECTURE.md의 Step 0-8 계약을 기준 축으로 두고, tutorial 문서를 “라우팅(어떤 튜토리얼을 읽을지)”과 “실행(각 Step에서 무엇을 참조할지)”로 분리해 설계한다. 산출물은 운영 문서 3종(Guide, Essentials, Token Policy), 기계 판독 인덱스(`tutorial_index.json`), 런타임 참조 문서(`README_LLM_RUNTIME.md`)로 구성한다. 기존 `TutorialRouter`/`TutorialPlanner` skill 계약이 새 인덱스와 문서 참조 순서를 사용하도록 갱신한다.

**Tech Stack:** Markdown, JSON(manifest/index 참조), rg/find/wc/jq(정적 분석), existing skills(`TutorialRouter`, `TutorialPlanner`)

---

## Current Baseline (2026-05-14)

- 튜토리얼 마크다운 총 파일 수: 45
- 튜토리얼 그룹별 분량(라인):
  - Lysozyme_in_water: 501
  - KALP15_in_DPPC: 372
  - Protein_Ligand_Complex: 334
  - Free_Energy_Calculations_Methane_in_Water: 228
  - Umbrella_Sampling: 208
  - Free_Energy_calculations_Hydration_Free_Energy_of_Ethanol: 148
  - Virtual_Sites: 112
  - Building_Biphasic_Systems: 85
- manifest 보유 튜토리얼: Lysozyme_in_water, KALP15_in_DPPC, Protein_Ligand_Complex
- 기존 런타임 계약:
  - `ARCHITECTURE.md`에는 Tutorial-Guided Autonomy Layer와 Step 0-8 고정 계약이 이미 존재한다.
  - `skills/tutorial-router/SKILL.md`는 현재 `available_manifests` 중심 입력만 정의한다.
  - `skills/tutorial-planner/SKILL.md`는 현재 manifest 기반 Step 매핑만 정의한다.

## Deliverables

1. `docs/tutorial/tutorial_index.json`
- 목적: Router가 manifest 유무와 관계없이 모든 tutorial family를 기계적으로 비교할 수 있는 정규화 인덱스 제공
- 핵심 내용: `id`, `domain`, `system_type`, `difficulty`, `manifest_path`, `derived`, `confidence`, `applicable_steps`, `variant_steps`, `required_inputs`, `prerequisites`, `risk_flags`, `recommended_docs`, `unsupported_autonomy_level`

2. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
- 목적: 입력 목표/시스템 타입별로 LLM이 어떤 튜토리얼부터 읽어야 하는지 결정 규칙 제공
- 핵심 내용: 라우팅 트리, 우선순위, 금지/주의 조건, fallback 경로, manifest 우선 원칙

3. `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
- 목적: tutorial 원문 전체가 아니라 Step 0-8 실행에 필요한 최소 필수 지식만 압축
- 핵심 내용: Step별 필수 명령/파라미터/검증 기준/실패 대응 포인트, validator/analyzer 호출 시점, retry taxonomy

4. `docs/tutorial/TUTORIAL_TOKENIZATION_POLICY.md`
- 목적: 튜토리얼 “통합 1문서 vs part 분할”의 토큰 효율 정책 확정
- 핵심 내용: 비용 모델, 선택 기준, 하이브리드 전략(인덱스+파트 본문), 예외적 통합 로딩 조건

5. `docs/tutorial/README_LLM_RUNTIME.md`
- 목적: 런타임에서 Router/Planner/Executor가 tutorial 문서를 어떤 순서와 조건으로 참조하는지 명시
- 핵심 내용: 참조 순서, Step 0-8 불변 계약, state/topology FAIL 조건

6. `docs/tutorial/LLM_DOC_VALIDATION_CHECKLIST.md`
- 목적: 생성 문서와 런타임 계약이 AGENTS.md/ARCHITECTURE.md/skills와 충돌하지 않는지 검증
- 핵심 내용: 질문 없이 실행 가능성, 계약 충돌 체크, 토큰 절약 샘플 측정

7. Updated contracts
- `docs/tutorial/TUTORIAL_OVERVIEW.md`: 사람이 읽는 개요에 index/guide/runtime 문서 위치 추가
- `ARCHITECTURE.md`: 기존 Tutorial-Guided Autonomy Layer를 새 문서 3종과 FAIL 조건 중심으로 강화
- `skills/tutorial-router/SKILL.md`: `tutorial_index.json` 입력과 derived/fallback 정책 반영
- `skills/tutorial-planner/SKILL.md`: Guide/Essentials/Token Policy 참조 순서와 필수 출력 필드 반영

## Required JSON Schema for `tutorial_index.json`

Each tutorial entry must use this shape:

```json
{
  "id": "Lysozyme_in_water",
  "domain": "standard_md",
  "system_type": ["protein", "aqueous"],
  "difficulty": "basic",
  "manifest_path": "docs/tutorial/Lysozyme_in_water/tutorial.manifest.json",
  "derived": false,
  "confidence": "high",
  "applicable_steps": [0, 1, 2, 3, 4, 5, 6, 7, 8],
  "variant_steps": [],
  "required_inputs": ["protein_pdb"],
  "prerequisites": ["valid_protein_coordinates"],
  "risk_flags": ["topology_mutation_steps_3_5"],
  "recommended_docs": {
    "minimal": ["tutorial.manifest.json", "generate_topology/prepare_the_topology.md"],
    "deep": ["analysis/analysis.md"]
  },
  "unsupported_autonomy_level": "none"
}
```

Allowed values:

- `confidence`: `high`, `medium`, `low`
- `unsupported_autonomy_level`: `none`, `partial`, `manual_prerequisite_required`, `research_only`
- `domain`: `standard_md`, `membrane_md`, `protein_ligand_md`, `free_energy`, `umbrella_sampling`, `biphasic_system`, `topology_modeling`

## Task 1: 튜토리얼 라우팅용 메타데이터 정규화

**Files:**
- Modify: `docs/tutorial/TUTORIAL_OVERVIEW.md`
- Create: `docs/tutorial/tutorial_index.json`
- Modify: `skills/tutorial-router/SKILL.md`

- [ ] Step 1: `find docs/tutorial -type f -name '*.md' | wc -l`와 tutorial별 `wc -l`로 Current Baseline을 재확인한다.
- [ ] Step 2: 각 튜토리얼의 목적/시스템 타입/난이도/Step 매핑 가능 범위를 `TUTORIAL_OVERVIEW.md`, manifest, part 제목에서 추출한다.
- [ ] Step 3: `tutorial_index.json`에 Required JSON Schema 형태로 8개 튜토리얼을 모두 등록한다.
- [ ] Step 4: manifest 없는 튜토리얼은 `derived=true`, `confidence=medium|low`, `manifest_path=null`로 표시한다.
- [ ] Step 5: Step 0-8에 단순 매핑하기 어려운 튜토리얼은 `variant_steps`와 `unsupported_autonomy_level`을 명시한다.
- [ ] Step 6: `skills/tutorial-router/SKILL.md`의 Input Schema에 `tutorial_index_path`와 `available_manifests`를 함께 받도록 갱신한다.
- [ ] Step 7: `skills/tutorial-router/SKILL.md`에 manifest가 없는 tutorial은 즉시 FAIL이 아니라 `derived` fallback 후보로 분류하되, `unsupported_autonomy_level`이 `manual_prerequisite_required` 이상이면 missing input/unsupported reason을 반환하도록 명시한다.
- [ ] Step 8: `jq empty docs/tutorial/tutorial_index.json`로 JSON 문법을 검증한다.
- [ ] Step 9: Router 최소 필드(`id`, `domain`, `applicable_steps`, `prerequisites`, `risk_flags`, `recommended_docs`)가 모든 entry에 존재하는지 `jq`로 검증한다.

## Task 2: 길잡이 문서(읽기 방향) 작성

**Files:**
- Create: `docs/tutorial/LLM_TUTORIAL_GUIDE.md`

- [ ] Step 1: 목적 기반 분기 규칙을 정의한다. 예: 단백질-물, 막단백질, 단백질-리간드, 자유에너지, 우산표집, biphasic, virtual sites.
- [ ] Step 2: 라우팅 우선순위를 명시한다: explicit user goal > required input availability > manifest presence > system type heuristic > Lysozyme fallback.
- [ ] Step 3: AGENTS.md Mandatory Rules(상태추적, topol 백업, hardware awareness, 재시도 정책, downsampling)를 읽기 순서 규칙에 연결한다.
- [ ] Step 4: “최소 읽기 경로”와 “심화 읽기 경로”를 분리한다.
- [ ] Step 5: `tutorial.manifest.json` 우선 원칙과 manifest 부재 시 fallback 절차를 명시한다: `tutorial_index.json` -> `TUTORIAL_OVERVIEW.md` -> `recommended_docs.minimal` -> 필요한 part.
- [ ] Step 6: 금지/주의 조건을 작성한다: ligand topology 누락, membrane prerequisite 누락, free-energy lambda 계획 부재, topology 수동 편집 필요, Step 0-8 자동 실행 불가 도메인.
- [ ] Step 7: Router가 반환해야 하는 `confidence`, `missing_inputs`, `unsupported_reason`, `selected_docs` 의미를 문서화한다.

## Task 3: Step별 필수 내용 압축 문서 작성

**Files:**
- Create: `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`

- [ ] Step 1: Step 0-8 각각에 대해 필수 입력/출력/state keys/실패패턴/검증기준을 테이블화한다.
- [ ] Step 2: tutorial 원문에서 반복되는 배경 설명은 제거하고 실행 결정에 필요한 명령, 파라미터, 파일명 패턴만 남긴다.
- [ ] Step 3: `SystemValidator` 호출 시점을 Step 1-7 gate로, `TrajectoryAnalyzer` 호출 시점을 Step 8로 명시한다.
- [ ] Step 4: Step 3(`solvate`)와 Step 5(`genion`) 이전 `topol.top` 백업과 retry 시 rollback을 필수 조건으로 적는다.
- [ ] Step 5: `simulation_state.json.retry_history`에 기록할 taxonomy를 포함한다: `command_error`, `grompp_warning`, `topology_mismatch`, `charge_neutralization`, `unstable_energy`, `temperature_coupling`, `pressure_coupling`, `analysis_not_converged`, `missing_input`, `unsupported_variant`.
- [ ] Step 6: retry가 동일 command string/동일 파라미터로 반복되지 않도록 각 taxonomy별 parameter mutation 예시를 추가한다.
- [ ] Step 7: state 키 누락 또는 topology backup 누락은 `WARNING`이 아니라 즉시 `FAIL`임을 명시한다.

## Task 4: 통합 vs 분할 토큰 정책 수립

**Files:**
- Create: `docs/tutorial/TUTORIAL_TOKENIZATION_POLICY.md`

- [ ] Step 1: 3가지 접근을 비교한다: A 전체 통합, B part 분할 유지, C 하이브리드.
- [ ] Step 2: 현재 코퍼스 분량(총 45개 md, 튜토리얼별 라인 수)을 기반으로 정성/정량 비용을 기술한다.
- [ ] Step 3: 권장안으로 C(하이브리드)를 기본 채택한다.
- [ ] Step 4: 운영 규칙을 정의한다: 기본은 index/guide 먼저 읽기, 필요 시 Step 관련 part만 지연 로딩, 예외는 새로운 도메인 첫 진입 시 해당 튜토리얼 통합본 또는 연속 part 일괄 로딩 허용.
- [ ] Step 5: Router/Planner가 문서를 읽는 순서를 고정한다: `TUTORIAL_OVERVIEW.md` -> `tutorial_index.json` -> manifest -> `LLM_TUTORIAL_GUIDE.md` -> `LLM_ESSENTIALS_BY_STEP.md` -> 필요한 tutorial part.
- [ ] Step 6: 대형 `.xvg`, trajectory, generated output 파일은 토큰 정책 대상이 아니며 항상 `TrajectoryAnalyzer` 등 parser utility를 통해 downsampled JSON만 읽도록 명시한다.

## Task 5: 문서 간 런타임 계약 강화

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `skills/tutorial-planner/SKILL.md`
- Create: `docs/tutorial/README_LLM_RUNTIME.md`

- [ ] Step 1: `ARCHITECTURE.md`의 기존 Tutorial-Guided Autonomy Layer를 유지하되, 새 문서 3종과 `tutorial_index.json`의 역할을 추가한다.
- [ ] Step 2: `README_LLM_RUNTIME.md`에 참조 순서를 명시한다: `TUTORIAL_OVERVIEW.md` -> `tutorial_index.json` -> manifest -> `LLM_TUTORIAL_GUIDE.md` -> `LLM_ESSENTIALS_BY_STEP.md` -> 필요한 tutorial part.
- [ ] Step 3: Step 0-8 고정 번호 체계를 유지한 채 tutorial variant만 바뀌는 계약을 문서화한다.
- [ ] Step 4: `skills/tutorial-planner/SKILL.md`의 Input Schema에 `tutorial_index_path`, `guide_path`, `essentials_path`, `token_policy_path`를 선택 입력으로 추가한다.
- [ ] Step 5: `skills/tutorial-planner/SKILL.md`의 Output Schema에 `selected_docs`, `state_requirements`, `validator_gates`, `topology_backup_required`, `unsupported_reason`을 추가한다.
- [ ] Step 6: state 키 누락, topology backup 누락, Step 0 hardware profile 누락, retry mutation 누락 시 즉시 `FAIL` 처리 규칙을 `ARCHITECTURE.md`, `README_LLM_RUNTIME.md`, `skills/tutorial-planner/SKILL.md`에 일관되게 반영한다.
- [ ] Step 7: manifest가 runtime truth이고, `tutorial_index.json`은 routing/index truth이며, tutorial markdown은 rationale/reference라는 우선순위를 명시한다.

## Task 6: 검증 체크리스트 및 수용 기준

**Files:**
- Create: `docs/tutorial/LLM_DOC_VALIDATION_CHECKLIST.md`

- [ ] Step 1: “질문 없이 실행 가능성” 체크 항목을 만든다: required inputs, missing inputs, fallback route, selected docs, Step 0-8 mapping, state keys, backup policy, retry mutation.
- [ ] Step 2: 각 문서가 AGENTS.md/ARCHITECTURE.md/skills와 충돌하지 않는지 교차검증 항목을 만든다.
- [ ] Step 3: 토큰 절약 효과 검증을 위해 샘플 프롬프트 3종에서 읽은 문서 수/라인 수를 비교하도록 정의한다.
- [ ] Step 4: 샘플 프롬프트를 고정한다: protein-water PDB, protein-ligand complex, umbrella/free-energy advanced request.
- [ ] Step 5: `jq empty docs/tutorial/tutorial_index.json`와 `rg` 기반 필수 문구 검증 명령을 체크리스트에 포함한다.
- [ ] Step 6: Done Criteria 전체 산출물이 존재하는지 검증하는 `test -f` 명령 목록을 포함한다.

## Recommendation on Format

- 단일 통합 문서 1개로 모든 tutorial을 합치는 방식은 라우팅 이전의 선행 토큰 비용이 커서 비효율적이다.
- 현재처럼 part 분할만 유지하면 탐색 오버헤드가 커질 수 있다.
- 권장 방식은 하이브리드다.
- 얇은 인덱스/가이드 문서로 라우팅한다.
- 실행 단계에서 필요한 part만 지연 로딩한다.
- 필요할 때만 튜토리얼 단위 통합본 또는 연속 part를 사용한다.
- manifest가 있는 튜토리얼은 manifest를 runtime truth로 사용한다.
- manifest가 없는 튜토리얼은 `tutorial_index.json`의 `derived`, `confidence`, `unsupported_autonomy_level`로 안전하게 제한한다.

## Execution Order

1. Task 1: index와 Router 계약을 먼저 만든다.
2. Task 2: 사람이 읽는 routing guide를 작성한다.
3. Task 3: Step 0-8 essentials를 작성한다.
4. Task 4: tokenization policy를 작성한다.
5. Task 5: Architecture/Planner/runtime README 계약을 강화한다.
6. Task 6: validation checklist와 수용 기준을 작성한다.

## Risks

- tutorial 간 용어/파라미터 명명 불일치
- manifest 부재 튜토리얼의 메타 추론 오류
- 자유에너지/umbrella/virtual-sites처럼 Step 0-8과 1:1 대응되지 않는 variant 누락
- 필수 요약 과정에서 예외 케이스 누락
- Router/Planner skill 계약이 새 문서와 동기화되지 않아 문서만 있고 런타임이 사용하지 않는 상태 발생
- state key 누락 또는 topology backup 누락을 warning으로 처리하는 계약 불일치

## Risk Controls

- manifest 없는 entry는 반드시 `derived=true`와 `confidence`를 표기한다.
- 자동 실행이 위험한 tutorial은 `unsupported_autonomy_level`을 `partial` 이상으로 둔다.
- Router/Planner SKILL.md를 같은 변경 세트에서 수정한다.
- `ARCHITECTURE.md`, `README_LLM_RUNTIME.md`, Planner constraints의 FAIL 조건을 동일 문구로 맞춘다.
- `jq`와 `rg` 검증을 체크리스트에 포함한다.

## Done Criteria

- `docs/tutorial/tutorial_index.json`이 생성되고 `jq empty`를 통과한다.
- `docs/tutorial/LLM_TUTORIAL_GUIDE.md`가 생성된다.
- `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`가 생성된다.
- `docs/tutorial/TUTORIAL_TOKENIZATION_POLICY.md`가 생성된다.
- `docs/tutorial/README_LLM_RUNTIME.md`가 생성된다.
- `docs/tutorial/LLM_DOC_VALIDATION_CHECKLIST.md`가 생성된다.
- `docs/tutorial/TUTORIAL_OVERVIEW.md`가 새 index/guide/runtime 문서를 안내한다.
- `ARCHITECTURE.md`의 Tutorial-Guided Autonomy Layer가 새 문서 참조 순서와 FAIL 조건을 포함한다.
- `skills/tutorial-router/SKILL.md`가 `tutorial_index.json`과 derived/fallback 정책을 입력 계약으로 반영한다.
- `skills/tutorial-planner/SKILL.md`가 Guide/Essentials/Token Policy 참조와 `selected_docs`, `state_requirements`, `validator_gates`, `topology_backup_required`, `unsupported_reason` 출력 계약을 포함한다.
- 라우팅 규칙이 Step 0-8 및 AGENTS mandatory rule과 직접 연결된다.
- 통합/분할 정책이 명시적 규칙으로 문서화되어 재사용 가능하다.
- state 키 누락/토폴로지 백업 누락/retry mutation 누락은 즉시 `FAIL`로 문서화된다.
