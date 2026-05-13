# MDP 파라미터 레퍼런스 및 모범 사례

`MdpComposer` 스킬이 `.mdp` 파일을 생성하거나 수정할 때 참조하는 파라미터별 상세 설명 및 권장값 문서입니다.

---

## 1. 통합자 (Integrator) 설정

| 파라미터 | 권장값 | 설명 |
|---|---|---|
| `integrator` | `steep` (EM) / `md` (나머지) | 에너지 최소화는 `steep` (Steepest Descent), MD 계열은 `md` (leapfrog) |
| `nsteps` | 페이즈별 상이 | 총 시뮬레이션 스텝 수. 시간 = nsteps × dt |
| `dt` | `0.002` | 타임스텝 (단위: ps). 수소 결합 제약 시 최대 2fs. LINCS 에러 시 0.001로 축소 |

---

## 2. 비결합 상호작용 (Non-bonded Interactions)

| 파라미터 | 권장값 | 설명 |
|---|---|---|
| `cutoff-scheme` | `Verlet` | 현대 GROMACS의 표준. `Group` 방식은 구식 |
| `nstlist` | `10` (MD) / `1` (EM) | 이웃 목록 갱신 주기. Verlet 방식에서는 자동 조정됨 |
| `ns_type` | `grid` | 격자 기반 이웃 탐색 |
| `rcoulomb` | `1.0` | 쿨롱 상호작용 컷오프 (단위: nm) |
| `rvdw` | `1.0` | 반데르발스 상호작용 컷오프 (단위: nm) |
| `coulombtype` | `PME` | 장거리 정전기 계산. 수용액 시스템 표준 |
| `fourierspacing` | `0.16` | PME 격자 간격. 작을수록 정확, 느림 |
| `pbc` | `xyz` | 주기적 경계 조건 (3차원 모두 적용) |

---

## 3. 온도 제어 (Temperature Coupling / Thermostat)

| 파라미터 | 권장값 | 설명 |
|---|---|---|
| `tcoupl` | `V-rescale` | Velocity Rescaling. NVT/NPT 표준. `nose-hoover`보다 안정적 |
| `tc-grps` | `Protein Non-Protein` | 온도 제어 그룹. 단백질과 용매(물+이온)를 분리 제어 |
| `tau_t` | `0.1  0.1` | 각 그룹의 온도 완화 시간 (단위: ps). 기본값 0.1 |
| `ref_t` | `300  300` | 각 그룹의 목표 온도 (단위: K). 일반적으로 300K |

> **체온 시뮬레이션:** `ref_t = 310  310`으로 변경

---

## 4. 압력 제어 (Pressure Coupling / Barostat)

| 파라미터 | 권장값 | 설명 |
|---|---|---|
| `pcoupl` | `no` (NVT) / `Parrinello-Rahman` (NPT, MD) | Berendsen 대신 Parrinello-Rahman 권장 (열역학적 앙상블 정확) |
| `pcoupltype` | `isotropic` | 등방성 압력 제어. 막 시스템은 `semiisotropic` 사용 |
| `tau_p` | `2.0` | 압력 완화 시간 (단위: ps). 너무 작으면 압력 발산 위험 |
| `ref_p` | `1.0` | 목표 압력 (단위: bar). 표준 대기압 |
| `compressibility` | `4.5e-5` | 물의 등온 압축률 (단위: bar⁻¹). 수용액 표준값 |

---

## 5. 위치 구속 (Position Restraints)

| 파라미터 | NVT/NPT | Production MD | 설명 |
|---|---|---|---|
| `define` | `-DPOSRES` | *(빈값)* | 위치 구속 플래그. EM/평형화 시 단백질 중원자를 고정 |

> **위치 구속 작동 원리:** `define = -DPOSRES`를 설정하면 `topol.top`에 포함된 `posre.itp` 파일이 활성화되어 단백질의 중원자(Cα 등)에 힘 상수 1000 kJ/mol/nm²의 제약이 걸립니다.

---

## 6. 속도 초기화 (Velocity Generation)

| 파라미터 | 첫 평형화(NVT) | 이후 단계 | 설명 |
|---|---|---|---|
| `gen_vel` | `yes` | `no` | NVT 시작 시에만 초기 속도 생성. 이후 단계는 이전 단계에서 이어받음 |
| `gen_temp` | `300` | *(해당 없음)* | 속도 생성에 사용할 온도 (Boltzmann 분포) |
| `gen_seed` | `-1` | *(해당 없음)* | 난수 시드. -1이면 자동 생성 (재현성 불필요 시) |

---

## 7. 출력 빈도 (Output Frequency)

| 파라미터 | 평형화 권장값 | MD 권장값 | 설명 |
|---|---|---|---|
| `nstxout-compressed` | `500` | `5000` | `.xtc` 궤적 파일에 저장하는 주기 (스텝). 5000 × 0.002ps = 10ps마다 |
| `nstenergy` | `500` | `5000` | `.edr` 에너지 파일 저장 주기 |
| `nstlog` | `500` | `5000` | `.log` 파일 저장 주기 |
| `nstxout` | `0` | `0` | 무압축 `.trr` 파일 저장 주기. 용량 크므로 0(저장 안 함) 권장 |

---

## 8. 파라미터 조합 모범 사례 요약

| 시나리오 | 권장 조합 |
|---|---|
| 단기 테스트 (1ns) | `dt=0.002`, `nsteps=500000`, TIP3P, CHARMM36m |
| 표준 연구 (10ns) | `dt=0.002`, `nsteps=5000000`, TIP3P, CHARMM36m |
| 장기 시뮬레이션 (100ns+) | GPU 가속 필요, `dt=0.002`, `nsteps=50000000` |
| 체온 환경 | `ref_t=310`, 나머지 동일 |
| 막 단백질 | CHARMM36m, `pcoupltype=semiisotropic`, CHARMM-GUI 지질 파라미터 추가 |
