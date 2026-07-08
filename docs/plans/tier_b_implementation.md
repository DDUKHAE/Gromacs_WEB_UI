# 티어 B 구현 계획서 — v1을 강한 프리프린트로

> **목표:** 프리프린트의 인용 가치·주목도를 결정하는 항목. 게시 전 넣으면 좋고, 부족하면 v2로 미뤄도 게시 자체는 가능.
> **원칙:** 검증표 하나, 재현 경로 하나가 "묻히는 프리프린트"와 "인용되는 프리프린트"를 가른다.
> **선행 참조:** `docs/journal_readiness_evaluation.md` §5.2 / 선행 조건: **티어 A 완료**
> **기준 커밋:** `b3b30d2`

## 에이전트 실행 규칙

1. **B1은 A3(물리 버그 수정) 완료 후 착수** — 틀린 물리로 만든 벤치마크는 무의미.
2. B1·B2·B3·B4·B5는 상호 독립 → 병렬 가능. 단 B1·B2는 벤치마크 실행 인프라를 공유하므로 `scripts/` 충돌 주의.
3. 벤치마크는 실제 GROMACS 실행이 필요 → 계산 자원·시간 확보. 소형 계 위주로 설계.
4. 완료 시 실제 산출물(표·플롯·DOI·컨테이너 빌드 로그)로 증명.

---

## B1 — 축소 벤치마크 (참조값 대비 정확도 검증)

**목표:** 3~4개 시스템에 대해 MD 관측량을 **문헌/실험 참조값과 비교**하는 표를 생성. "0개 검증"과 결정적 차이.

**근거:** 현재 `scripts/collect_metrics.py:29-51`은 완료율(ACR)·시간·첫실패단계만 측정 — 정확도가 아님. 참조 대비 검증이 프리프린트 임팩트의 핵심. — 평가 기능 §2.5-1

**권장 시스템 & 참조값(우선 3~4개):**
| 시스템 | 관측량 | 참조값 | 허용오차(예시) |
|---|---|---|---|
| Free Energy Ethanol (수화) | ΔG_hyd | 실험 ≈ −20.5 kJ/mol | ±핀 고정 후 통계오차 내 |
| Free Energy Methane (수화) | ΔG_hyd | 실험 ≈ +8.4 kJ/mol | 동상 |
| Lysozyme in Water | RMSD 평탄역, Rg | 문헌 범위 | 정성+정량 |
| (선택) KALP15/DPPC | 면적/지질, 두께 | 문헌 | C2 스텁 구현 후 |

> 정확한 참조값·인용은 착수 시 문헌으로 재확인·기록할 것.

**대상 파일:** `scripts/collect_metrics.py`(확장), `scripts/run_benchmark.py`, (신규) `scripts/reference_values.json`, (신규) `scripts/compute_reference_deviation.py`, 결과 표 산출물(`docs/benchmark/table1.md` 또는 `.csv`).

**단계:**
1. `scripts/reference_values.json` 생성 — 시스템별 참조값·출처 DOI·허용오차.
2. 각 시스템을 파이프라인으로 실행(핀 고정 시드·환경, B3·B5 선행 권장).
3. `collect_metrics.py`에 **관측량 추출 + 참조 대비 편차 + pass/fail** 로직 추가(FE는 BAR ΔG, 단백질은 RMSD/Rg).
4. Table 1 생성: 시스템 | 관측량 | 계산값±오차 | 참조값 | 편차 | pass/fail | (겸 ACR·시간).
5. 재실행 재현성 확인(최소 2회, 시드 고정 시 결정론적 or 통계오차 내 일치).

**완료 조건(Acceptance):**
- `scripts/reference_values.json` 존재 + 출처 DOI 포함.
- Table 1 산출물 존재, ≥3 시스템, 각 행에 참조 대비 편차·pass/fail.
- 적어도 하나의 FE ΔG가 참조 오차범위 내로 재현되거나, 벗어난다면 원인이 문서화됨.

**규모:** 中~大 (계산 시간 지배적)

---

## B2 — 교차모델 신뢰성/성공률 표

**목표:** Claude/Codex/Gemini 각각으로 동일 시스템 집합을 구동, **성공률·오류복구·소요**를 표로. 본 프로젝트만의 차별 데이터.

**근거:** 모델무관 백엔드는 핵심 차별점이며, DynaMate도 5개 LLM 교차 벤치를 제시 — 리뷰어 기대치. — 평가 웹 §1.3, 기능 §2.4

**대상 파일:** `web/llm_adapters/{claude,codex,gemini}.py`(플래그 확인), `scripts/run_benchmark.py`(모델 루프), (신규) `scripts/reliability_matrix.py`, 산출 표.

**측정 지표:** 시스템×모델 셀별 — 자율완료 여부, 실패 단계, 리트라이 횟수·복구 성공, 벽시계 시간, (가능하면) config 준수(감사 통과).

**단계:**
1. `web/llm_adapters/gemini.py`의 `# TODO: confirm exact auto-approve flag`를 실제 검증된 플래그로 확정(미검증 플래그가 벤치에 섞이면 안 됨).
2. `scripts/run_benchmark.py`를 (시스템 × 모델) 격자로 반복하도록 확장, 각 런의 지표를 수집.
3. N회 반복으로 성공률·표준편차 산출(LLM 비결정성 정량화).
4. 표 생성: 시스템 | 모델 | 성공률(n/N) | 평균 리트라이 | 복구율 | 평균 시간.

**완료 조건(Acceptance):**
- gemini 어댑터 TODO 해소(플래그 근거 주석).
- ≥2 시스템 × 3 모델 × (N≥3) 반복의 성공률 표 산출.
- LLM 비결정성이 성공률·표준편차로 정량화됨.

**규모:** 中~大 (계산 시간)

---

## B3 — conda 환경 고정 (컨테이너 미사용)

> **결정(2026-07-08):** Docker는 사용하지 않는다. GROMACS가 conda-forge로만 안정 배포되므로 **conda 가상환경을 만들고 그 실환경을 export해 락으로 고정**하는 방식을 채택. 실제 구동 중인 `gromacs_web` 환경(GROMACS 2026.0 + Python 3.13.13)의 스냅샷이므로 이론적 빌드보다 재현성이 강하다.

**목표:** 재현 가능한 실행 환경을 conda 스펙 + 락파일로 고정.

**근거:** `environment.yml`/락파일 전무, 의존성 전부 하한. `requirements.txt`(matplotlib, propka) ↔ `pyproject.toml`(둘 다 누락) 불일치 → 두 설치 경로가 다른 환경 산출. — 평가 구조 §3.3, §3.5-1

**대상 파일:** (신규) `environment.yml`(스펙), (신규) `environment.lock.yml`(`conda env export --no-builds`), (신규) `environment.lock.txt`(`conda list --explicit`, linux-64), (신규) `requirements.lock`(pip 레이어), `requirements.txt`, `pyproject.toml`, `README.md`. **Dockerfile은 만들지 않는다.**

**단계:**
1. `requirements.txt` ↔ `pyproject.toml` 정합 — `matplotlib`, `propka`를 pyproject 의존성에 추가, 버전 정책 통일.
2. `environment.yml`(스펙) 생성 — conda-forge `gromacs=2026.0`, `python=3.13`, pip 서브블록에 파이썬 의존성.
3. 실환경에서 락 export:
   - `conda env export -n gromacs_web --no-builds | grep -v '^prefix:' > environment.lock.yml`
   - `conda list -n gromacs_web --explicit > environment.lock.txt`
4. pip 레이어 락(`uv pip compile` 또는 `pip freeze`) → `requirements.lock`.
5. README에 3단계 재현 경로(스펙/버전락/정확락) + 락 재생성 명령 + 비-LLM(`web/runner.py`) 경로 명시(LLM CLI는 conda/pip 미설치·로그인 필요).

**완료 조건(Acceptance):**
- `environment.yml`·`environment.lock.yml`·`environment.lock.txt`·`requirements.lock` 존재, YAML/파싱 정상, 미-gitignore.
- 락이 실환경(GROMACS 2026.0 + Python 3.13) 반영.
- `requirements.txt`·`pyproject.toml` 의존성 정합(matplotlib·propka 양쪽 존재).
- (최종 확인, 실환경 필요) 클린 머신에서 `conda env create -f environment.lock.yml` → `pytest -q` 통과 + `check_gromacs_env.py`가 gmx 탐지.

**규모:** 中

---

## B4 — 출판급 플롯 + 내보내기

**목표:** 프리프린트 Figure로 쓸 수 있는 선명·라벨링·내보내기 가능한 플롯.

**근거:** 프론트 캔버스 플롯이 고정 800×200·`devicePixelRatio` 미적용→흐릿, 축 단위 미표기, PNG/SVG/CSV 내보내기 없음, 라이트테마에서 축색 하드코딩 `rgba(255,255,255,…)`로 사라짐, glow/그라디언트가 데이터 왜곡. 백엔드 matplotlib은 dpi 120 기본. — 평가 UI §4.4, §4.6-1; 기능 §2.3

**대상 파일:**
- 프론트: `web/static/index.html` — `drawFullChart`(`:4721-4794`), `renderXvgResultModal`(`:4796-4898`), 하드코딩 색(`:4740, 4748, 4758`).
- 백엔드: `skills/illustrator/illustrator.py` — `plot_xvg`(`:397-412`, dpi 120), `scripts/_pubstyle.py`(존재 — 활용/확장).

**단계:**
1. 캔버스를 `window.devicePixelRatio`로 스케일(`canvas.width = cssW*dpr; ctx.scale(dpr,dpr)`).
2. 축 제목+단위를 `xaxis_label`/`yaxis_label`에서 축에 렌더, 틱에 단위 부여.
3. 하드코딩 `rgba(255,255,255,…)`를 테마 토큰(`getComputedStyle`로 `--text-secondary`/`--border-color`)으로 교체 → 라이트테마 정상.
4. `shadowBlur`/그라디언트 채움 제거(깔끔한 스트로크).
5. 플롯별 **Export PNG(≥300dpi)/SVG/CSV** 버튼(`canvas.toBlob` 또는 SVG 재렌더). CSV는 원 시계열.
6. 백엔드 matplotlib 플롯을 `_pubstyle.py` 적용 + dpi≥300, 축 단위·범례 정비.

**완료 조건(Acceptance):**
- HiDPI에서 선명(dpr 스케일 코드 존재).
- 라이트테마에서 축·그리드 가시(색 토큰화 확인).
- 각 플롯에 PNG/SVG/CSV 내보내기 동작(수동 확인 + 코드 존재).
- 백엔드 산출 PNG가 dpi≥300, 축 단위·라벨 포함.

**규모:** 中

---

## B5 — 프로버넌스 캡처 (재현성 물적 근거)

**목표:** 각 런의 재현에 필요한 메타데이터를 `state.json`에 기록.

**근거:** 시드 비결정(`gen_vel=yes, gen_seed=-1`), `gmx --version`·mdp 해시 미기록 → 런 재현 불가, 방법 섹션용 프로버넌스 부재. — 평가 기능 §2.1

**대상 파일:** `lib/mdp_templates/nvt.mdp`(및 관련 mdp), `lib/state.py`, `skills/md_runner/md_runner.py`, `skills/env_builder/env_builder.py`, `docs/STATE_SCHEMA.md`.

**단계:**
1. 벤치마크/재현 모드에서 `gen_seed`를 **고정값**으로 설정(또는 실행별 시드를 기록). 프로덕션 기본과 재현 모드를 구분.
2. 런 시작 시 `gmx --version`, 포스필드 버전, 각 mdp의 해시(sha256), OS/환경을 `state.json` provenance 블록에 기록.
3. `docs/STATE_SCHEMA.md`에 provenance 스키마 추가.
4. 사용된 mdp·명령 트레이스를 런 아카이브에 포함(이미 runner.log 존재 — 보강).

**완료 조건(Acceptance):**
- 완료된 런의 `state.json`에 `gmx_version`·`mdp_hashes`·`seed`(또는 기록) 필드 존재.
- 동일 시드·환경 재실행이 결정론적 or 통계오차 내 일치(B1과 연계 확인).
- `docs/STATE_SCHEMA.md`에 provenance 문서화.

**규모:** 小~中

---

## 티어 B 완료 게이트 (강한 v1)

- [ ] B1: ≥3 시스템 참조 대비 Table 1
- [ ] B2: ≥2 시스템 × 3 모델 신뢰성 표 + gemini 플래그 확정
- [ ] B3: 빌드되는 컨테이너 + 의존성 정합 + 컨테이너 내 테스트 통과
- [ ] B4: dpi 스케일·축 단위·내보내기·라이트테마 수정
- [ ] B5: state.json provenance + 재현 확인

> B1·B2가 부족하면 **티어 A만으로 v1 게시 후 B를 v2에 반영** 가능(§5.4 실행 순서).
> 검증 절차는 `docs/plans/verification_plan.md` §B 참조.
