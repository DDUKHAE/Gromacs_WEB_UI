# LLM Documentation Validation Checklist

## 1. Runnable Without Clarifying Questions

- [ ] Required inputs가 tutorial별로 정의되어 있다.
- [ ] missing inputs 판정 규칙이 있다.
- [ ] fallback route가 문서화되어 있다.
- [ ] selected docs 계산 규칙이 있다.
- [ ] Step 0-8 매핑 규칙이 있다.
- [ ] state key requirements가 있다.
- [ ] topology backup/rollback 정책이 있다.
- [ ] retry mutation 정책이 있다.

## 2. Contract Consistency

- [ ] `AGENTS.md` mandatory rules와 충돌 없음
- [ ] `ARCHITECTURE.md` Step 0-8 고정 계약과 충돌 없음
- [ ] `skills/tutorial-router/SKILL.md` 입력/출력 계약 일치
- [ ] `skills/tutorial-planner/SKILL.md` 입력/출력 계약 일치
- [ ] FAIL 조건 문구가 runtime 문서들과 일치

## 3. Token Efficiency Evaluation

고정 샘플 프롬프트:

1. Protein-water PDB 자동 시뮬레이션
2. Protein-ligand complex 자동 시뮬레이션
3. Umbrella/free-energy 고급 워크플로우

각 샘플에 대해 기록:

- [ ] 읽은 문서 수
- [ ] 총 라인 수
- [ ] 라우팅 결정까지 읽은 문서 수
- [ ] missing input 탐지 시점

## 4. Command Checks

```bash
jq empty docs/tutorial/tutorial_index.json

rg -n "Immediate FAIL|FAIL|topol.top" docs/tutorial/README_LLM_RUNTIME.md docs/tutorial/LLM_ESSENTIALS_BY_STEP.md ARCHITECTURE.md

test -f docs/tutorial/tutorial_index.json
test -f docs/tutorial/LLM_TUTORIAL_GUIDE.md
test -f docs/tutorial/LLM_ESSENTIALS_BY_STEP.md
test -f docs/tutorial/TUTORIAL_TOKENIZATION_POLICY.md
test -f docs/tutorial/README_LLM_RUNTIME.md
test -f docs/tutorial/LLM_DOC_VALIDATION_CHECKLIST.md
```
