# Skill: MdpComposer

LLM이 `.mdp` (Molecular Dynamics Parameters) 파일을 직접 텍스트로 작성하면 문법 오류(Typo)나 비물리적 파라미터 조합이 발생할 수 있습니다. `MdpComposer`는 검증된 표준 템플릿을 기반으로 파라미터 파일을 안전하게 생성하는 스킬입니다.

---

## 1. 지원하는 시뮬레이션 단계 (Phases)

| Phase ID | 목적 | 기반 템플릿 |
|---|---|---|
| `ions` | 이온화 준비용 더미 run | 최소 설정, nsteps=0 |
| `minim` | 에너지 최소화 (Steepest Descent) | 스텝 제한, 수렴 기준 포함 |
| `nvt` | NVT 평형화 (온도 제어) | V-rescale 서모스탯, 위치 구속 포함 |
| `npt` | NPT 평형화 (압력 제어) | Parrinello-Rahman 바로스탯 추가 |
| `md` | 본 시뮬레이션 (Production MD) | 위치 구속 제거, 최대 성능 설정 |

---

## 2. 입력 스키마 (Input Schema)

```json
{
  "phase": "<Phase ID>",
  "overrides": {
    "<mdp 파라미터 키>": "<값>"
  }
}
```

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `phase` | string | ✅ | 생성할 시뮬레이션 단계 ID |
| `overrides` | object | ❌ | 기본 템플릿에서 변경할 파라미터만 명시 (나머지는 기본값 사용) |

---

## 3. 반환 스키마 (Output Schema)

```json
{
  "status": "success | error",
  "output_file": "<생성된 .mdp 파일 경로>",
  "final_params": { "<전체 파라미터 내용>" }
}
```

---

## 4. 기본 템플릿 내용 (Default Templates)

### Phase: `minim` (에너지 최소화)
```ini
; Energy Minimization Parameters
integrator      = steep     ; Steepest descent 최소화 알고리즘
emtol           = 1000.0    ; 수렴 기준: 최대 힘이 1000 kJ/mol/nm 이하
emstep          = 0.01      ; 초기 스텝 크기
nsteps          = 50000     ; 최대 스텝 수

; 비결합 상호작용 설정
nstlist         = 1
cutoff-scheme   = Verlet
ns_type         = grid
coulombtype     = PME
rcoulomb        = 1.0
rvdw            = 1.0
pbc             = xyz
```

### Phase: `nvt` (NVT 평형화, 100ps)
```ini
; NVT Equilibration Parameters
integrator      = md
nsteps          = 50000     ; 100ps (2fs * 50000)
dt              = 0.002     ; 스텝 크기 2fs

; 출력 설정
nstxout         = 500
nstvout         = 500
nstenergy       = 500
nstlog          = 500

; 비결합 상호작용
cutoff-scheme   = Verlet
nstlist         = 10
rcoulomb        = 1.0
rvdw            = 1.0
coulombtype     = PME

; 온도 제어 (V-rescale)
tcoupl          = V-rescale
tc-grps         = Protein Non-Protein
tau_t           = 0.1  0.1
ref_t           = 300  300

; 압력 제어 없음
pcoupl          = no

; 위치 구속 (단백질 중원자)
define          = -DPOSRES
gen_vel         = yes
gen_temp        = 300
gen_seed        = -1
```

### Phase: `npt` (NPT 평형화, 100ps)
```ini
; NPT Equilibration Parameters (NVT 설정 계승 + 압력 제어 추가)
integrator      = md
nsteps          = 50000
dt              = 0.002

; 온도 제어 (V-rescale)
tcoupl          = V-rescale
tc-grps         = Protein Non-Protein
tau_t           = 0.1  0.1
ref_t           = 300  300

; 압력 제어 (Parrinello-Rahman)
pcoupl          = Parrinello-Rahman
pcoupltype      = isotropic
tau_p           = 2.0
ref_p           = 1.0
compressibility = 4.5e-5

; 위치 구속 유지
define          = -DPOSRES
gen_vel         = no
```

### Phase: `md` (본 시뮬레이션)
```ini
; Production MD Parameters
integrator      = md
nsteps          = 5000000   ; 10ns (2fs * 5000000) — overrides로 조정 가능
dt              = 0.002

; 출력 빈도
nstxout         = 0
nstvout         = 0
nstfout         = 0
nstxout-compressed = 5000   ; .xtc에 10ps마다 기록
nstenergy       = 5000
nstlog          = 5000

; 온도/압력 제어 (NVT와 동일)
tcoupl          = V-rescale
tc-grps         = Protein Non-Protein
tau_t           = 0.1  0.1
ref_t           = 300  300
pcoupl          = Parrinello-Rahman
pcoupltype      = isotropic
tau_p           = 2.0
ref_p           = 1.0
compressibility = 4.5e-5

; 위치 구속 없음 (Production)
define          =
gen_vel         = no
```

---

## 5. 호출 예시

### 10ns 시뮬레이션으로 변경하여 md.mdp 생성
```json
{
  "skill": "MdpComposer",
  "params": {
    "phase": "md",
    "overrides": {
      "nsteps": "5000000",
      "ref_t": "310  310"
    }
  }
}
```
> `nsteps=5000000`, `dt=0.002`이면 10ns. 온도를 310K(체온)로 변경한 예시입니다.
