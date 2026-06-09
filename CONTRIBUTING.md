# Contributing to GROMACS Harness

이 저장소에 코드/문서를 추가하기 위한 간단한 가이드입니다.

## 1. 개발 환경

```bash
git clone https://github.com/DDUKHAE/GROMACS_Harness
cd GROMACS_Harness

# Conda 환경 (권장)
conda create -n GROMACS -y -c conda-forge gromacs python=3.11
conda activate GROMACS
pip install pytest matplotlib

# 환경 확인
python scripts/check_gromacs_env.py
pytest tests -v
```

GROMACS가 없어도 unit/contract 테스트는 모두 실행된다(integration은 자동 skip).

## 2. 코드 레이아웃

- `lib/` — skill이 import하는 내부 모듈. 새로운 user-facing capability가 아니라면 여기에 추가.
- `skills/{env_builder,md_runner,illustrator}/` — 세 skill. 신규 skill 추가는 spec 변경이 선행되어야 함.
- `tests/{unit,contract,integration}/` — 단위·계약·통합 테스트. 모든 PR은 새 코드에 대한 unit 또는 contract 테스트를 동반해야 함.
- `docs/` — 운영/계약 문서.
- `docs/tutorial/` — 튜토리얼 원문 + manifest + 인덱스.

## 3. 자주 하는 변경 절차

### 3.1 새 검증 임계값 추가
1. `lib/validators.py`에 상수와 `judge_<metric>` 함수 추가.
2. `tests/unit/test_validators.py`에 PASS/WARNING/RETRYABLE 경계값 케이스 작성.
3. `docs/simulation_criteria.md` §1–3에 임계값과 권장 mutation 추가.
4. md-runner의 `_validate_phase`에 호출 분기 추가 (필요 시).

### 3.2 새 튜토리얼 키워드 라우팅
1. `lib/tutorial_registry.py`의 `KEYWORDS` dict에 키워드 추가.
2. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`의 decision tree 갱신.
3. `tests/unit/test_tutorial_registry.py`에 새 키워드용 라우팅 테스트 추가.

### 3.3 새 derived tutorial 자동화 활성화
1. `docs/tutorial/<tutorial_id>/tutorial.manifest.json` 작성 — 기존 manifest 형식 참조 (`pipeline_variant`, `architecture_steps`, `documents`, `defaults`).
2. `lib/tutorial_registry.py`의 manifest 로딩이 자동 인식.
3. md-runner의 `PHASE_SEQUENCES`에 variant가 없으면 추가.
4. illustrator의 `VARIANT_DISPATCH`에 variant별 분석이 필요하면 등록.
5. `scripts/regression/<id>.sh` 회귀 스크립트 추가.

### 3.4 새 분석 레시피
1. `skills/illustrator/illustrator.py`에 `_<analysis>` private 함수와 `run_*_analyses` 분기 추가.
2. `skills/illustrator/references/analysis_recipes.md`의 카탈로그 표 갱신.
3. `tests/unit/test_illustrator_*` 또는 integration test에 케이스 추가.

### 3.5 `state.json` 스키마 변경
1. `lib/state.py`의 `initial()`을 갱신, 새 키 기본값 설정.
2. `docs/STATE_SCHEMA.md` 동기화.
3. `docs/pipeline_contract.md`의 Step contract도 함께 갱신.
4. 후방호환 우려 시 `schema_version` major bump 검토.
5. `tests/unit/test_state.py`의 round-trip 테스트가 새 키를 포함하도록 확장.

## 4. 테스트 정책

- **TDD 권장**: 실패 테스트 → 구현 → 통과 순.
- **단위 테스트**: 모든 신규 함수는 unit 또는 contract 테스트 필수.
- **모의(mock)**: GROMACS 호출은 `unittest.mock.patch("subprocess.run")`으로 모의. 통합 테스트만 실제 gmx 실행.
- **회귀**: `scripts/regression/` 스크립트는 GROMACS 머신에서 PR 머지 전 최소 1회 실행 권장.

## 5. 커밋 컨벤션

Conventional Commits 사용:

- `feat(area): ...` — 신규 기능
- `fix(area): ...` — 버그 수정
- `docs: ...` 또는 `docs(area): ...` — 문서 변경
- `test: ...` — 테스트만 변경
- `refactor: ...` — 동작 변경 없는 리팩토링
- `chore: ...` — 빌드/설정/cleanup

area 예: `lib`, `env-builder`, `md-runner`, `illustrator`, `tutorial`, `regression`.

작은 단위로 자주 commit. 한 commit = 한 논리 단위.

## 6. PR 체크리스트

- [ ] `pytest tests -v` 전체 통과 (integration은 skip 허용).
- [ ] 새 기능에 대한 unit 또는 contract 테스트 추가.
- [ ] 관련 docs 갱신 (`STATE_SCHEMA.md`, `simulation_criteria.md`, `pipeline_contract.md`, skill의 `references/`).
- [ ] state schema 또는 외부 인터페이스 변경 시 `schema_version` 검토.
- [ ] PR description에 "왜 이렇게 변경했는가"를 한 단락 이내로 명시.

## 7. 자주 묻는 질문

**Q. GROMACS가 없는데 어떻게 검증하나?**
A. unit + contract 테스트만 돌려도 코드 정합성은 검증된다. integration은 GROMACS 머신에서 별도 수행. `scripts/check_gromacs_env.py`로 환경 확인.

**Q. 새로운 skill을 추가해도 되나?**
A. 가능. 단, `docs/superpowers/specs/` 아래에 design spec을 먼저 작성하고 합의 후 진행. 3-skill 원칙(`env-builder`, `md-runner`, `illustrator`)을 깨는 변경은 brainstorming 단계 필수.

**Q. 외부 도구(PyMOL/VMD/ffmpeg) 의존을 추가해도 되나?**
A. illustrator 내부에서만 허용. `select_renderer()` 패턴처럼 graceful degradation을 반드시 갖춰 미설치 환경에서도 다른 산출은 보존되어야 한다.

**Q. 백업 정책을 바꿔도 되나?**
A. Step 3/5의 `topol.top.bak`은 안전 계약이므로 변경 시 `AGENTS.md` mandatory rules 갱신 + 사용자 공지 필요.
