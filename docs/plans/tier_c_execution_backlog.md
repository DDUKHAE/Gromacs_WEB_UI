# Tier B·C 실행 백로그

이 문서는 코드 작업만으로 완료할 수 없는 항목을 실행 순서와 증거 기준으로 정리한다. B1은 C1에 포함해 중복 실행하지 않는다.

## 0. 공통 사전 점검

1. `python scripts/check_gromacs_env.py`에서 `ready_for_pipeline: true`를 확인한다.
2. `gromacs_web` 환경의 `gmx --version`, Python 버전, GPU/CPU 자원을 기록한다.
3. `tutorial_data/` 입력 PDB, force field, water model을 확인한다.
4. 각 런의 `state.json`, 명령 로그, MDP 해시, seed, 재시도 이력을 보존한다.
5. 실패 시 같은 명령을 반복하지 않고 원인과 변경한 파라미터를 `retry_history`에 기록한다.

## 1. B1+C1 통합: 전체 벤치마크·불확실도

B1(3~4개 축소 벤치마크)은 C1(8개 전체)의 부분집합이다. C1을 실행해 B1 요구사항까지 한 번에 충족한다.

1. 8개 튜토리얼을 고정 seed로 환경 구축 → EM/NVT/NPT/production → 분석까지 실행한다.
2. `collect_metrics.py`로 RMSD, Rg, 밀도, 에너지, 수화 자유에너지를 수집한다. XVG는 다운샘플러를 사용한다.
3. `scripts/reference_values.json`에 참조값, 허용오차, DOI를 기록한다.
4. 블록 평균·자기상관시간으로 표준오차를 계산하고, 자유에너지는 BAR, umbrella는 WHAM bootstrap 오차를 계산한다.
5. 8개 Table 1에 계산값±오차, 참조값, 편차, pass/fail, seed, 시간, 재시도 횟수를 포함한다.
6. 최소 1회 재실행해 동일 seed의 결정론적 일치 또는 통계오차 내 일치를 확인한다.

완료 증거: 참조값 JSON/DOI, 8개 Table 1과 오차막대, ethanol/methane 자유에너지 및 단백질 RMSD/Rg 행, provenance와 재실행 로그.

## 2. B2: 교차 LLM 신뢰성

B2는 C1과 겹치지 않으므로 별도 수행한다.

1. Claude·Codex·Gemini CLI 설치·로그인을 확인한다.
2. Gemini auto-approve 플래그를 설치 버전에서 검증하고 근거를 기록한다.
3. 최소 2개 시스템을 3개 모델 각각 N≥3회, 동일 입력·seed·timeout·승인 정책으로 실행한다.
4. 완료 여부, 실패 단계, 재시도·복구, 벽시계 시간, provenance 준수 여부를 수집한다.
5. 시스템×모델 성공률·복구율·평균 시간·표준편차 표를 생성한다. API 오류·CLI 미설치·GROMACS 실패는 분리한다.

완료 증거: Gemini TODO 제거, 2시스템×3모델×3반복 결과, 신뢰성 표와 실패 원인 로그.

## 3. C2: 막·복합체 분석

KALP15/DPPC와 protein–ligand trajectory가 필요하다. trajectory를 생성한 뒤 막의 area-per-lipid·두께·order parameter, 복합체의 ligand RMSD·접촉맵·hydrogen-bond를 계산하고 플롯·단위·오차를 기록한다. `status: stub`가 없어야 하며 실제 수치와 분석 테스트가 필요하다.

## 4. C6: 자유에너지 창 세분화

coulombic decharging과 van der Waals decoupling을 분리하고 각 변환에 최소 10개 lambda 창을 구성한다. 창 overlap과 BAR 수렴을 확인하고 C1 참조값 대비 `ΔG_hyd`와 불확실도를 Table 1에 반영한다. 분리 스케줄, 수렴 증거, 참조 오차범위 내 재실행이 완료 조건이다.

## 5. 통합 검증·기록

1. B1·B2·C1·C2·C6 산출물을 `docs/benchmark/`와 실행 아카이브에 저장한다.
2. 각 런에 command trace, `state.json`, MDP hash, seed, retry history, 환경 버전을 포함한다.
3. `python -m pytest -q`와 `python scripts/check_gromacs_env.py`를 실행한다.
4. `docs/plans/verification_plan.md`의 G2/B 및 G3/C 판정표에 산출물 경로와 명령 출력 요약을 기록한다.
5. GROMACS가 없으면 실행 항목을 완료로 표시하지 않고 차단 원인을 유지한다.
