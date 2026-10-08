# Evolution Audit — 표면적 전수 분류 (2026-10-08)

> **Status**: evidence snapshot for SPEC-055 (kept-surface criterion). Classifications reflect the
> surface as of 2026-10-08; later audits may revise them with the same evidence discipline.

> 질문: "프론티어 모델이 좋아질수록 이 하네스가 중요할까?"
> 답: 가치는 사라지지 않고 **이동**한다. 이 문서는 kit의 전체 표면적(skill 23, agent 32, script 37, hook 10)을
> 그 이동 방향 기준으로 세 버킷에 분류하고, 전환 로드맵을 제안한다.

## 버킷 정의

| 버킷 | 정의 | 모델이 좋아지면 |
|---|---|---|
| **A — 감가상각 빠름** | 모델에게 HOW를 가르치는 레이어: 단계별 기법, 사고 스캐폴딩, 크래프트 튜토리얼, 네이티브 능력과 중복되는 프롬프트 | 가치 하락 → 축소·삭제·런타임 위임 |
| **B — 계약으로 전환** | 가치가 WHAT(아티팩트 스키마, 불변식, 포스트컨디션)에 있는데 현재 HOW 산문에 싸여 있는 것 | HOW를 벗기면 가치 유지 → 계약만 남기고 압축 |
| **C — 검증 코어** | 신뢰 인프라: refute-first 감사자, 결정론적 게이트, provenance, 상태 기계, 훅 기반 강제 | 가치 **상승** → 투자 |

분류 원칙: 버킷은 "지금 모습"이 아니라 "가치의 소재"를 기준으로 한다. 한 파일 안에 A층과 B층이
섞여 있으면 지배적 성격으로 분류하고 분리 액션을 명시한다.

---

## 핵심 구조적 발견 6가지

### 1. 검증 코어는 이미 존재하고, 이미 kit의 최대 자산이다
scripts/ 37개 중 17개가 검증·provenance·synthesis 레이어다 — validator/gate 12개(`verify_checkpoint.py`
1,872줄 포함 ~7,000줄), provenance 3개, 결정론적 synthesizer 2개. 여기에 refute-first 감사자 2개
(research-auditor, synthesizer-auditor: 분리 컨텍스트, verbatim-quote 검증, blocking JSON 판정),
provenance 태그 규율(`[CONFIRMED]`/`[INFERRED]` + file:line)을 가진 포렌식 에이전트 5개, 모델 밖에서
강제되는 hook 가드 3종(secret/dangerous-command/freeze)이 있다. **전환은 신규 구축이 아니라 무게중심
재배치다.**

### 2. 역설: 산문이 가장 무거운 곳에 검증이 가장 약하다
`checkpoint.sh`(→`verify_checkpoint.py`)를 실제 호출하는 skill은 23개 중 8개뿐이다. 산문이 가장 긴
5개 skill(uiux 568줄, mobile-uiux 590줄, desktop-uiux 648줄, kickoff 203줄, scan 190줄)은 **스크립트
체크포인트가 0개**다 — "CHECKPOINT — MANDATORY" 블록이 전부 모델 자기단언이다. 검증이 가장 필요한
곳(가장 긴 자유생성)에서 검증이 가장 약한 구조.

### 3. 검증 로직이 감가상각 레이어 안에 갇혀 있다
falsifiable한 게이트들(literal_quote verbatim 검사, Signature Move 전 화면 존재 검사, AI Tell 스윕,
testgen의 hollow-test 술어)이 전부 **모델-실행 grep 지시**로 skill 산문 안에 있다. 이들은 이미
결정론적으로 검사 가능한 술어다 — 스크립트로 옮기면 A 버킷 산문이 C 버킷 자산으로 바뀐다.

### 4. 위임 관용구는 증명됐지만 3곳에만 적용됐다
`has_skill.py` probe → 런타임 위임(`/deep-research`, `/code-review`, `/security-review`) → 결정론적
synthesizer → 분리-컨텍스트 merge-auditor → degraded fallback. SPEC-019 스스로 "재사용 가능한 kit
관용구로 투자 가치가 있다"고 명시했고 다음 후보(테스트 실행)까지 flag해 뒀지만, 적용은 review /
brainstorm / bizanalysis 3개 skill에 멈춰 있다.

### 5. README가 아직 옛 서사를 판다
README의 아키텍처 스토리는 "파이프라인 + 전문 에이전트 로스터"다. `/deep-research`, `/code-review`,
`/security-review`, 위임 관용구가 한 번도 등장하지 않는다. kit이 실제로 진화해 온 방향(SPEC-017/018/019:
플랫폼 위임 + 검증)이 공식 정체성에 반영되지 않았다.

### 6. 자기채점 보일러플레이트가 32개 중 ~22개 에이전트에 있다
Self-Review + High/Med/Low confidence rating 블록. SPEC-010이 이미 "self-grading sycophancy"를 결함으로
기록했고, business-analyst는 스스로 "Self-Review는 load-bearing gate가 아니다"라고 선언한다. 실질
게이트는 분리-컨텍스트 감사자와 스크립트다 — 보일러플레이트는 토큰 비용만 내는 의식(ritual)에 가깝다.

---

## Skill 분류 (23)

| Skill | 줄수 | 버킷 | 근거 · 액션 |
|---|---|---|---|
| careful | 22 | **C** | PreToolUse hook 강제, 모델 지시 0줄. 유지 |
| freeze | 38 | **C** | Edit/Write 경계 hook 강제. 유지 |
| guard | 41 | **C** | 위 둘의 합성. 유지 |
| review | 240 | **C** | 위임 관용구 flagship: probe→위임→synthesize→audit, checkpoint 12개. 202행의 메타룰("문서 가드를 가르치는 lesson을 기록하지 마라")은 이 감사의 논지를 스스로 선취. 유지·투자 |
| spec | 150 | **B** (모범) | 전 조항이 `validate_spec.py`가 독립 검사하는 계약(Options≥2, 측정가능 comparator, 명시적 Decision). **다른 skill이 수렴해야 할 목표 형태** |
| ship | 165 | **B** (모범) | 검증가능 포스트컨디션 체인 + 멱등 머지 probe + blocking checkpoint 4개. 이미 계약형 |
| sprint | 258 | **B**+C | IRON LAW + 7-상태 FSM + 의사결정의 스크립트 위임(`sprint_queue.py` — "수동으로 큐를 계산하지 마라"). 구조적 강제라는 C 철학의 구현. 유지 |
| implement | 453 | **B** | WHAT 척추 강함(spec gate, RED-before-GREEN, checkpoint 11개, Figma 5종 검증). A 잔재: Decision Ladder 6단계 사고 지시, 인라인 figma-converter 프롬프트 50줄 → 벗겨내기 |
| scan | 190 | **B** | kit 최강의 인식론 계약(전 주장 CONFIRMED/INFERRED + Evidence 필드 + --audit 출력 불변식). prose checkpoint → 스크립트화 필요 |
| kickoff | 203 | **B** | 오케스트레이션 계약(에이전트별 아티팩트 소유권, 교차문서 정합성). prose checkpoint 5개 → 스크립트화 필요 |
| prd | 84 | **B** | 아티팩트 계약(9섹션/TODO 마커, 검증가능 AC) 중심, 이미 가벼움. 유지 |
| issue | 161 | **B** | 문서-갱신 트리거 매트릭스 + append-only 불변식 + 읽기전용 경계. 유지 |
| bizanalysis | 93 | **B** | SPEC-018 위임 + claim-provenance 불변식 + no-data 리터럴 + `## Limits` 정직성. 유지 |
| brainstorm | 82 | **B** | 동일 패턴, 인식론 계층화(연구-게이트 섹션 vs 저자 의견 섹션) 명시. 유지 |
| figma2proto | 191 | **B** | "Figma가 source of truth, 묘사하되 창작 금지" 불변식. 검증은 스크립트에 있음. 유지 |
| devops | 97 | **B** | checkpoint 계약 유지, `## Guidelines`(일반 모범사례)는 A → 축소 |
| migrate | 104 | **B** | 롤백-선행·단계별-green 불변식 유지. persona block(ISSUE-034 잔재) 삭제 |
| refactor | 121 | **B** | "테스트가 바뀌면 리팩토링이 아니다" 불변식은 날카로움. 패턴 카탈로그는 A → 삭제 |
| testgen | 176 | **B** | hollow-test 술어는 검사가능 → **스크립트로 승격(C)**. 파일명 휴리스틱·출력 템플릿은 A |
| diagnose | 163 | **B** | regression-test 불변식 + blocking test checkpoint 유지. step 5.5(사고 스캐폴딩 6항목)와 persona block은 순수 A → 삭제 |
| uiux | 568 | **A→B** | 최대 수축 대상. 유지할 것: Phase 5A 분리-컨텍스트 pilot gate("생성자-심판 동일체는 실패한다"는 근거 명시), literal_quote/Signature Move/2–3 cues 등 falsifiable 게이트(→스크립트 승격). 벗길 것: CSS 역학 ~15줄, 금지어휘 프로토콜, 질문 스크립트, 크래프트 튜토리얼 |
| mobile-uiux | 590 | **A→B** | 동일 + Expo 설정 핀(경험적 지식 — 모델이 따라잡는 즉시 감가). Anti-AI-Slop ~65줄 × 3개 skill 중복 |
| desktop-uiux | 648 | **A→B** | 동일. 레포 최장 파일이 스크립트 체크포인트 0개 |

**집계**: C 4 · B 16 · A→B 전환 긴급 3 (uiux 트리플릿, 합 1,806줄).

## Agent 분류 (32)

### C — 검증 코어 (6) → 투자
| Agent | 근거 |
|---|---|
| research-auditor | refute-first, 분리 컨텍스트, verbatim quote + 주변 맥락 검증, blocking JSON, 관용 자기검사("관대한 심판이라면 통과시켰을까"), 정직한 Limits |
| synthesizer-auditor | 동일 설계. 실패 지점("LLM 추출 단계에서 claim이 조용히 drop/paraphrase/scope-shift된다")을 정확히 조준 |
| design-scanner | 생성 에이전트가 아닌데 생성 영역에 있는 포렌식: 단일 실패 모드 명시, file:line 없으면 CONFIRMED 불가, 거부 판정(`insufficient`) 보유. **A 버킷 생성자들이 수렴해야 할 자세** |
| design-auditor | 시스템/구현 스코프 분할의 절반, 읽기전용, 의도적 결정 대조로 false-positive 통제 |
| ui-reviewer | 분할의 나머지 절반 + native memory 학습 루프(ISSUE-033) 소유 |
| reviewer | **minimality 축 + `[record]` finding class만 C.** code/security 차원은 degraded fallback — 런타임 커버리지 검증 후 단계적 폐기 경로에 있음 |

### B — 계약으로 전환 (15) → invariant만 남기고 압축
| Agent | 남길 계약 | 벗길 HOW |
|---|---|---|
| developer | RED 검증 게이트, Discovered Findings 테이블(team-lead가 파싱), blast-radius 체크 | 14단계 TDD 튜토리얼, 코딩 표준 산문 |
| planner | 13필드 스키마, append-only 번호 영속성, flock 동시쓰기, 수동-설정 의존성 분리 규칙 | 사이징 루브릭 산문 |
| qa-designer | `verify_gates.py`가 regex 파싱하는 config 블록(기계 계약) | 11단계 전략 워크플로, 도구 이름 나열 |
| team-lead | FSM + checkpoint 강제 프로토콜 + 사용자-영향 게이트(5c) + 안전 상한들 | 단계별 핸들러 산문 일부 |
| figma-converter | MISSING_ASSETS 거부 프로토콜, "모든 CSS 값은 design_data.json에서", 렌더 PNG = truth | 좌표 수학·그라디언트 레시피 튜토리얼(413줄 → 모델이 흡수할수록 감가) |
| issue-writer | 변이-권한 매트릭스(append-only, design_philosophy 읽기전용) | — (이미 계약 중심) |
| codebase-scanner | scan_context 스키마, not-found/not-checked 구분 | 파일명 탐지 단계 나열 |
| scan-analyst / scan-architect / scan-data-modeler / scan-planner / scan-qa-designer | CONFIRMED/INFERRED + Evidence 계약, "감사이지 재설계가 아니다" 경계 | 읽기 기법 단계 — 네이티브 탐색이 대체 |
| requirement-analyst | 수치 NFR 강제, 침묵→Out-of-Scope 기본값 | 7단계 워크플로 |
| ux-designer | 5-상태 전수 커버리지, /uiux와의 경계 | 8단계 워크플로 |
| data-modeler | 인덱스↔접근패턴 추적성 불변식 | 9단계 워크플로 |

### A — 감가상각 빠름 (11) → 축소·해체·위임
| Agent | 처분 제안 |
|---|---|
| architect | plan mode와 거의 전면 중복. 11섹션 스키마 + "기각한 대안을 옹호해 보라" 규칙만 계약으로 남기고 위임 검토 |
| brainstormer, business-analyst | 대화 진행은 네이티브. 위임 라우팅과 불변식은 이미 skill 계약에 있음 → 에이전트를 skill로 흡수·해체 후보 |
| devops | 일반 모범사례 — 네이티브가 이미 적용. 체크리스트만 skill로 |
| documenter | 네이티브 문서작성과 중복. "명령어 실존 검증" 규칙만 남김 |
| copywriter | 쓰기는 네이티브. 화면×상태 인벤토리 계약만 남김 |
| a11y-auditor | WCAG 지식은 네이티브에 내장. 수치 임계값을 데이터/검사 스크립트로, 산문 삭제 |
| test-generator | hollow-test 금지를 **스크립트 validator로 승격**, don't-touch-source 규칙만 계약으로 |
| uiux-developer (193), mobile-uiux-developer (241), desktop-uiux-developer (300) | 크래프트 튜토리얼(duration band, Expo 핀, 성능 규칙)이 본체 — 가장 빨리 감가. 유지 가치는 anti-slop 트리오(기본값 금지·Brief overrides 장부·자기유사성 검사)와 교차문서 정합성 계약뿐 → fragments.py SSOT로 추출, 에이전트는 수축 |

**집계**: C 6 · B 15 · A 11.

## Scripts & Hooks (분류 완료 상태)

- **C (17)**: validator/gate 12 + provenance 3 + 결정론적 synthesizer 2. 이미 코어. `verify_checkpoint.py`가 최대 단일 자산
- **B (2)**: `figma_fetch.py`, `generate_figma_css.py` — 외부 통합, 계약 명확
- **Plumbing (18)**: SPEC-017이 이미 플랫폼 위임 중(설치 레이어 폐기 경로). 방향 일치
- **Hooks**: 전부 C (secret_guard, dangerous_command_guard, autotest, telemetry, 방어적 fail-open 설계)
- **정리 후보 flag**: `debt_harvest.py`(호출자 없음), `trace_query.py`, `contributor_report.py` — 참조 없는 orphan. 유지한다면 명시적 소유자(hook/CI) 지정

---

## 로드맵 (우선순위순)

1. **정체성 전환 SPEC** — "파이프라인 + 에이전트 로스터" → "**verification & delegation control plane**"으로
   README 재서술. 위임 관용구(probe→위임→synthesize→audit→degrade)를 공식 아키텍처로 승격. 이 감사의
   분류를 kept-agent/kept-skill 기준으로 명문화 (ISSUE-034 기준의 후속).
2. **검증 비대칭 해소** — kickoff/scan/uiux×3에 `verify_checkpoint.py` phase 추가(엔진은 이미 있음).
   모델-실행 스윕 4종(literal_quote, Signature Move 존재, AI Tell, hollow-test)을 결정론적 validator로 이전.
3. **HOW 수축** — uiux 트리플릿 skill 1,806줄 + agent 734줄이 최대 단일 대상(fragments.py 확장으로 중복
   제거 선행). persona block 4개(prd/diagnose/refactor/migrate), confidence-rating 보일러플레이트 ~22개
   삭제(SPEC-010 근거). implement의 인라인 프롬프트·사고 지시 제거.
4. **위임 확장** — 다음 후보: 테스트 실행(SPEC-019가 이미 flag), architect→plan mode, a11y→런타임 리뷰
   차원. 각각 관용구 5단계를 그대로 적용.
5. **중복 통합** — scan-*/greenfield 5쌍을 evidence-mode 플래그 단일 에이전트로 통합 검토(출력 계약은
   이미 "downstream 호환"으로 동일하게 설계되어 있어 비용 낮음).
6. **A-bucket 에이전트 해체** — brainstormer/business-analyst/devops/documenter/copywriter의 불변식을
   호출 skill 계약으로 흡수하고 에이전트 파일 삭제.

## 한 줄 결론

kit의 미래 가치는 "모델을 잘 시키는 법"(A, ~40% 표면적)이 아니라 "모델이 한 일을 믿을 수 있게 만드는
법"(C, 이미 구축됨)에 있다. 전환 비용의 대부분은 신규 개발이 아니라 **삭제와 승격**이다 — 산문을 벗기고,
그 안에 갇힌 검사가능 술어를 스크립트로 꺼내는 일.
