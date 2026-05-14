# Tutorial Tokenization Policy

## Scope

튜토리얼 문서를 LLM 런타임에서 읽을 때 토큰 사용량과 실패율을 동시에 관리하기 위한 정책.

## Corpus Baseline (2026-05-14)

- 전체 tutorial markdown: 45 files
- 튜토리얼별 라인 수:
  - Lysozyme 501
  - KALP15 372
  - Protein_Ligand 334
  - Methane FE 228
  - Umbrella 208
  - Ethanol FE 148
  - Virtual Sites 112
  - Biphasic 85

## Approach Comparison

- A. 전체 통합
  - 장점: 탐색 오버헤드 최소
  - 단점: 라우팅 전 선행 토큰 비용 과대, unrelated context 유입 증가
- B. Part 분할 유지
  - 장점: 필요 부분만 로딩 가능
  - 단점: 라우팅/검색 단계 왕복 증가
- C. 하이브리드 (권장)
  - 장점: 얇은 인덱스 기반 라우팅 + 필요한 part 지연 로딩
  - 단점: 인덱스/가이드 유지보수 필요

## Policy Decision

기본 정책은 C(하이브리드)로 고정한다.

## Fixed Read Order

1. `docs/tutorial/TUTORIAL_OVERVIEW.md`
2. `docs/tutorial/tutorial_index.json`
3. 선택 튜토리얼 `tutorial.manifest.json`(있으면)
4. `docs/tutorial/LLM_TUTORIAL_GUIDE.md`
5. `docs/tutorial/LLM_ESSENTIALS_BY_STEP.md`
6. 선택된 tutorial part 문서 (필요 Step만)

## Load Rules

- 기본: index/guide/essentials 먼저 읽고 Step 관련 part만 로딩
- 예외: 새 도메인 첫 진입, 고위험 variant(umbrella/free energy/membrane)에서는 연속 part 일괄 로딩 허용
- 금지: 대형 결과 파일 직접 로딩 (`.xvg`, trajectory raw). 반드시 parser utility 기반 downsampled JSON 사용

## Operational Metrics

샘플 프롬프트별 측정 항목:

- 읽은 문서 개수
- 총 라인 수
- 라우팅 결정까지 소요 단계 수
- missing input 탐지 시점
