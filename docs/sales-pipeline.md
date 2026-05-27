# Sales Pipeline

> B2B 세일즈 직군이 FDE처럼 고객 니즈를 발굴하고 PoC를 시연하며 클로징하는 전 과정을 자동화한다.
> 엔지니어용 `/kickoff → /uiux → /sprint` 파이프라인을 PoC 빌드 단계로 그대로 재활용한다.

## 한눈에 보는 흐름

```
미팅 전        1차 미팅            PoC 제작                          2차 미팅(데모)     클로징/팔로업
─────────    ─────────────       ──────────────────────────       ──────────────    ─────────────
                                                                                  
/account-brief                                                                       
/discovery-prep                                                                       
              세일즈 직접 작성:                                                        
              meeting_notes.md                                                        
              (discovery)                                                              
                                                                                       
              /meeting-capture                                                         
              ↓                                                                         
              docs/prd_draft.md                                                       
              + account_brief 갱신                                                     
                                                                                       
                                  /kickoff [--mode=demo]                              
                                  /uiux                                                
                                  /sprint [--mode=demo]                              
                                  ↓                                                    
                                  prototype/ (PoC)                                    
                                                                                       
                                                                  세일즈 직접 작성:    
                                                                  meeting_notes.md  
                                                                  (demo)            
                                                                                       
                                                                  /proposal         
                                                                  ↓                  
                                                                  docs/proposal.md  
                                                                                       
                                                                                    /followup
                                                                                    ↓
                                                                                    docs/followup.md
                                                                                    + account_brief 갱신
                                                                                    + 이메일 초안
                                                                                    + CRM 업데이트 항목
```

---

## 단계별 상세

### 1. 미팅 전 — 준비

#### `/account-brief`
- **입력**: 고객사 이름 (필수), 선택적으로 URL/접점/가설
- **출력**: `docs/account_brief.md`
- **에이전트**: `account-researcher`
- **시간**: 2–5분 (웹 리서치 포함)
- **목적**: 회사 개요, 최근 12개월 동향, 기술 스택 추정, 의사결정 구조 가설, 페인포인트 가설, 접근 전략

#### `/discovery-prep`
- **입력**: `docs/account_brief.md` (필수)
- **출력**: `docs/discovery_plan.md`
- **에이전트**: `discovery-coach`
- **시간**: 30초–1분
- **목적**: SPIN 질문 세트, MEDDIC 체크리스트, 예상 반론 + 대응, 시간배분 어젠다

---

### 2. 1차 미팅 (Discovery) — 미팅 후 즉시

#### 세일즈 직접 작성: `meeting_notes.md` (discovery)
- **템플릿**: `templates/meeting_notes.md`
- **필드**: 메타, 컨텍스트, 페인포인트, 요구사항, MEDDIC 요소, 반론, 다음 액션, 자유 메모
- **`meeting_type` 필드를 반드시 `discovery`로 설정**

#### `/meeting-capture <meeting_notes_path>`
- **입력**: 미팅 노트 (필수), `docs/account_brief.md` (권장)
- **출력**:
  - `docs/prd_draft.md` (PoC scope로 한정된 PRD 초안)
  - `docs/account_brief.md` 갱신 (미팅 히스토리, 의사결정 구조, 챔피언 상태)
- **에이전트**: `meeting-synthesizer`
- **목적**: 미팅 노트를 엔지니어용 PRD로 변환. 단 ONE primary flow로 좁혀서.

> ⚠️ **중요**: PRD 초안의 "Out of Scope" 섹션을 반드시 확인. 데모 PoC scope를 지키는 핵심 안전장치.

---

### 3. PoC 제작 — 엔지니어용 파이프라인 재활용

```bash
# PRD 초안의 모호한 부분을 세일즈와 확인 후
/kickoff docs/prd_draft.md       # 요구사항/UX 스펙/이슈 분해
/uiux                             # 디자인 시스템 + 프로토타입 베이스
/sprint                           # 이슈 단위 구현 (구현 → 리뷰 → 배포)
```

산출물: `prototype/` 디렉토리 또는 풀스택 PoC.

> 💡 **demo 모드 플래그(미구현)**: 이상적으로는 `/kickoff --mode=demo`, `/sprint --mode=demo`로 프로덕션 게이트(전체 아키텍처, 데이터 모델, 테스트 플랜)를 건너뛰는 게 좋다. 현재는 PRD의 "Out of Scope" 섹션을 통해 scope 규율을 유지한다. 향후 개선 항목.

---

### 4. 2차 미팅 (데모) — 미팅 후 즉시

#### 세일즈 직접 작성: `meeting_notes.md` (demo)
- 동일한 `templates/meeting_notes.md` 템플릿
- **`meeting_type` 필드를 반드시 `demo`로 설정**
- **`데모 피드백` 섹션을 반드시 채울 것** — 제안서 품질이 여기서 갈린다

#### `/proposal <demo_meeting_notes_path>`
- **입력**:
  - demo 미팅 노트 (필수)
  - `docs/account_brief.md` (권장)
  - `docs/prd_draft.md` (PoC가 약속한 것)
  - `prototype/` (실제 PoC 산출물)
  - 이전 모든 `meeting_notes_*.md` (페인포인트 누적)
- **출력**: `docs/proposal.md`
- **에이전트**: `proposal-writer`
- **목적**: Executive Summary, 페인 재진술, 요구사항 ↔ PoC 시연 매핑, ROI, 가격, 리스크/완화, 다음 단계

---

### 5. 팔로업

#### `/followup <meeting_notes_path>`
- **입력**: 미팅 노트 (어떤 유형이든), `docs/account_brief.md` (필수)
- **출력**:
  - `docs/followup.md` (이메일 초안, 내부 액션, CRM 업데이트, 챔피언 상태, 워치리스트)
  - `docs/account_brief.md` 갱신 (실제로 파일을 편집)
- **에이전트**: `champion-mapper`
- **목적**: 미팅 후 24시간 내 보낼 이메일, 내부 액션 리스트, CRM 업데이트 항목, 챔피언 상태 추적

---

## 산출물 한눈에

| 파일 | 생성 | 갱신 | 용도 |
|---|---|---|---|
| `docs/account_brief.md` | `/account-brief` | `/meeting-capture`, `/followup` (atomic Write) | 누적 계정 인텔리전스. **Active Context**(상단)만 보고 미팅 들어갈 수 있어야 함 |
| `docs/discovery_plan.md` | `/discovery-prep` | `/discovery-prep` (update) | 미팅 30분 전 훑기. **SPIN 질문 최대 6개** |
| `meeting_notes_*.md` | **세일즈 작성** | — | 모든 미팅의 단일 진실 소스 |
| `docs/prd_draft.md` | `/meeting-capture` | `/meeting-capture` | PoC 빌드 입력. **PoC Deliverables**(일회성) vs **Productionalizable Features**(실 제품 기능) 분리 |
| `prototype/` | `/sprint` | `/sprint` | 실제 PoC 산출물 |
| `docs/poc_results.md` | **세일즈 + 엔지니어** (템플릿 복사 후 작성) | — | **`/proposal`의 필수 입력.** 모든 PoC 메트릭의 단일 진실 소스 |
| `docs/proposal.md` | `/proposal` | `/proposal` (update) | 클로징용 제안서. 모든 메트릭은 `poc_results.md` 출처 |
| `docs/followup.md` | `/followup` | `/followup` (update) | 미팅 후 액션 |
| `docs/sales_lessons.md` | `/followup` (누적) | `/followup` | 어카운트 간 패턴. `/discovery-prep`과 `/meeting-capture`가 읽음. **walk-up 발견 가능** |
| `docs/sales_email_persona.md` | **세일즈 작성** (선택) | — | 세일즈별 이메일 톤. `/followup`이 있으면 따름. **walk-up 발견 가능** |

---

## Multi-Account 레포 구조

세일즈 1명이 여러 B2B 고객을 추적할 때 권장 구조:

```
sales-ops/                              ← 세일즈 팀 단일 레포 (.git)
├── .claude/                            ← sales pack 1회 설치
├── docs/                               ← 어카운트 무관 공통 파일
│   ├── sales_lessons.md                (cross-account)
│   └── sales_email_persona.md          (세일즈 본인)
├── accounts/
│   ├── kt-millie/docs/...              (어카운트별 산출물)
│   ├── tossbank/docs/...
│   └── kakao-enterprise/docs/...
└── archive/                            (종료된 deal)
```

세일즈는 작업 시 어카운트 디렉토리로 이동 후 스킬 실행:

```bash
cd accounts/kt-millie/
/account-brief           # → accounts/kt-millie/docs/account_brief.md 생성
/discovery-prep          # → 자동으로 docs/ 발견 + 공유 lessons walk-up
```

### Walk-up 메커니즘

스킬은 `sales_lessons.md`와 `sales_email_persona.md`를 찾을 때 **현재 디렉토리부터 위로 올라가며 `docs/<file>` 탐색**:

```bash
bash scripts/find_shared.sh sales_lessons.md
# accounts/kt-millie/docs/sales_lessons.md 없음 → 한 레벨 위
# accounts/docs/sales_lessons.md 없음 → 한 레벨 위
# sales-ops/docs/sales_lessons.md 발견 → 절대 경로 반환
```

- **`.git` 디렉토리 또는 filesystem root에서 중단** (레포 경계 존중)
- 찾으면 해당 파일을 입력으로 사용, 못 찾으면 그냥 그 입력 없이 진행
- `scripts/find_shared.sh`는 kit의 utility (수정 불필요)

이 메커니즘 덕분에 sales pack은 **단일 어카운트 레포**와 **multi-account 레포** 둘 다에서 작동.

---

## 핵심 설계 원칙

### 1. 미팅 노트는 세일즈가 직접 작성
- Transcription 도구에 의존하지 않음 (한국어 화자 분리 품질 이슈 회피)
- 세일즈가 노이즈를 걸러 신호만 전달
- 미팅 분위기/직감 같은 비언어 정보를 직접 보강

### 2. `meeting_type` 필드가 분기 로직의 핵심
- `discovery` → `/meeting-capture`가 PRD 초안 생성
- `demo` → `/proposal`이 클로징 제안서 생성
- `closing` → 양쪽 다 가능 (계약 단계 미팅)

### 3. PoC는 demo-grade scope, PoC Deliverables ≠ Productionalizable Features
- ONE primary flow만
- **PoC Deliverables**: 데모 미팅에서만 보여주는 일회성 산출물 (비교 패키지, 평가 리포트 등). 본 제품에 안 들어감.
- **Productionalizable Features**: 본 계약 시 실제 제품이 될 기능
- "Out of Scope"를 길고 구체적으로 명시 (10+ 항목)

### 4. 지식은 `account_brief.md`에 누적, **Active Context가 최상단**
- 미팅마다 atomic Write로 단일 파일 갱신 (Edit 여러 번 X)
- **Active Context** 섹션 1페이지만 보고 미팅 준비 가능
- 세부는 하단, 미팅 히스토리는 누적

### 5. PoC 메트릭은 `poc_results.md` 단일 진실 소스
- 세일즈 + 엔지니어가 PoC 시연 직후 함께 작성
- `/proposal`이 모든 메트릭(권당 단가, 처리 시간, ROI 가정)을 여기서 인용
- 없으면 `/proposal` 실행 거부 — 검증 불가능한 주장 방지

### 6. 어카운트 간 학습은 `sales_lessons.md`
- 매 `/followup`이 일반화 가능 패턴 추출 시도
- 3+ 사례 누적 시에만 정식 lesson으로 promote
- 다른 어카운트 `/discovery-prep`과 `/meeting-capture`가 시작 시 참조

### 7. Discovery 질문은 6개 hard cap
- 60분 미팅에 9–10개는 interrogation
- 6개 × 5분 = 30분, 나머지 30분은 대화/반론/가치 제안

### 8. 모든 스킬은 update 모드 지원
- 출력 파일이 이미 존재하면 갱신 모드로 진입
- 처음부터 다시 만들지 않고 변경분만 통합

---

## 빠른 시작 (Quickstart)

처음 사용하는 세일즈의 1주차 흐름:

```bash
# 월요일: 첫 미팅 잡힘. 화요일 미팅 준비
/account-brief                      # "토스 페이먼츠"
# → docs/account_brief.md 생성. 5분 훑기.

/discovery-prep                     # 자동으로 account_brief 사용
# → docs/discovery_plan.md 생성. 미팅 30분 전 훑기.

# 화요일: 미팅 진행. 미팅 노트는 머리속/노트북에 메모.

# 화요일 저녁: 노트 정리
cp templates/meeting_notes.md docs/meeting_notes_001.md
# meeting_type: discovery 로 설정하고 채우기.

/meeting-capture docs/meeting_notes_001.md
# → docs/prd_draft.md 생성. 모호한 부분 확인.

# 수–목요일: PoC 빌드
/kickoff docs/prd_draft.md
/uiux
/sprint
# → prototype/ 생성.

# 금요일 오전: 데모 미팅 직전, PoC 측정 결과 작성
cp templates/poc_results.md docs/poc_results.md
# 세일즈 + 엔지니어가 함께 채움 — 처리 시간, 단가, 평가 점수, 시연 가능 항목

# 금요일: 데모 미팅 진행.

# 금요일 저녁
cp templates/meeting_notes.md docs/meeting_notes_002.md
# meeting_type: demo 로 설정하고 demo_feedback 섹션 꼭 채우기.

/proposal docs/meeting_notes_002.md
# → docs/proposal.md 생성. 모든 메트릭은 poc_results.md에서 인용됨.

/followup docs/meeting_notes_002.md
# → docs/followup.md 생성. 이메일 초안을 24시간 내 발송.
```

---

## 더 읽을거리

- [`execution-model.md`](execution-model.md) — 스킬·에이전트 런타임 메커니즘
- [`README.md`](README.md) — kit-generated 파일 일람
