# Playtest — 자동 런 테스트 + 선택적 심층 분석 + 수정 + 커밋

자동 플레이테스트를 실행하고, 사용자가 선택한 관점을 중심으로 심층 분석한다.

## 모드

`$ARGUMENTS`를 파싱하여 모드와 옵션을 결정한다:

| 입력 | 모드 | 동작 |
|------|------|------|
| `/playtest` | **분석 모드** | 런 실행 → 분석 리포트 |
| `/playtest 30` | **분석 모드 (30턴)** | 턴 수 지정 |
| `/playtest -fix` | **수정 모드** | 런 실행 → 분석 → 코드 수정 → 서버 재시작 → 재테스트 → 비교 |
| `/playtest 25 -fix` | **수정 모드 (25턴)** | 턴 수 지정 + 수정 |
| `/playtest -fix -commit` | **커밋 모드** | 수정 모드 + 개선 확인 시 git commit & push |

### 인자 파싱 규칙

`$ARGUMENTS`에서 숫자를 추출하면 턴 수로 사용한다. 없으면 기본값 20.

- `/playtest` → 10턴
- `/playtest 30` → 30턴
- `/playtest 15 -fix` → 15턴 + 수정 모드

## 기본 설정

- **턴 수**: 10 (인자로 변경 가능)
- **프리셋**: DESERTER
- **성별**: male
- **장소 순환**: market → guard → harbor → slums

---

## 공통 절차 (모든 모드)

### 1단계: 분석 관점 선택

사용자에게 아래 선택지를 제시한다. **복수 선택 가능** (쉼표 구분).

```
플레이테스트 심층 분석 관점을 선택하세요 (복수 선택 가능, 예: 1,3):

1. 이벤트 서술 품질     — LLM 서술의 문장 품질, 톤 일관성, 반복 표현, 장면 묘사력
2. 맥락 유지 & NPC 성향 — 이전 턴 정보 참조, NPC 이름 공개, 감정축 변화, 태도 일관성
3. 이벤트 다양성        — 이벤트 반복 패턴, EventDirector 정책, ProceduralEvent 품질
4. 메모리 시스템        — storySummary 축적, structuredMemory, finalizeVisit, 토큰 예산
5. 판정 & 밸런스        — ResolveService 판정 분포(S/P/F), 스탯 매핑, 난이도 곡선
6. 장소 전환 & HUB      — MOVE_LOCATION 처리, HUB 복귀, 장소별 체류턴, 탐험 패턴
7. Incident & 시그널    — 사건 진행도(control/pressure), 시그널 피드, 엔딩 조건

선택:
```

사용자의 선택을 기다린다. 선택된 번호를 `FOCUS_AREAS`로 저장한다.

### 2단계: 서버 상태 확인
- `lsof -ti:3000`으로 서버 확인. 없으면 사용자에게 서버 시작 요청.

### 3단계: 플레이테스트 실행 (1차)

**정본 스크립트 `scripts/playtest.py`를 실행한다.** 인라인 스크립트를 새로 작성하지 않는다.

```bash
cd /Users/dohamsu/Workspace/mdfile
python3 scripts/playtest.py --turns {턴수} --preset DESERTER --gender male
```

옵션:
- `--turns N` — 턴 수 변경 (기본 20)
- `--preset X` — DESERTER, SMUGGLER, DOCKWORKER, HERBALIST
- `--output path.json` — 결과 파일 경로 지정
- `--loc-turns N` — 장소당 체류 턴 수 (기본 4)

스크립트 핵심 흐름:
1. 회원가입 → 로그인 (랜덤 이메일)
2. RUN 생성 (프리셋, 성별)
3. HUB: 선택지(accept_quest → 장소 이동)로 LOCATION 진입
4. LOCATION: 다양한 ACTION 입력 순환, CHOICE 자동 처리, 장소 순환
5. LLM 폴링 (최대 90초) + TURN_NO_MISMATCH 자동 복구
6. 전체 턴 로그 + 최종 상태 + 검증 결과를 JSON 저장 (`playtest-reports/`)

**주의: 스크립트를 수정해야 할 경우 `scripts/playtest.py`만 편집한다. 새 스크립트를 생성하지 않는다.**

### 4단계: 기본 분석 리포트 작성 (항상 수행)

JSON 로그를 기반으로 `playtest-reports/` 폴더에 MD 리포트 작성. **아래 항목은 항상 포함**:

#### A. 기본 정보
- RunID, 프리셋, 턴 수, 최종 상태, 방문 장소, Heat, Day, Incidents

#### B. 턴 흐름 요약 테이블
| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |

#### C. 종합 점수 (10점 만점)
| 항목 | 점수 | 비고 |
- 서사 흐름, NPC 일관성, 맥락 유지, 이벤트 다양성, 메모리 시스템 → 종합

#### D. 개선 권장사항
- Critical / High / Medium / Low 우선순위

### 5단계: 심층 분석 (선택된 FOCUS_AREAS만 수행)

사용자가 선택한 관점별로 아래 심층 분석을 **추가 섹션**으로 리포트에 포함한다.

---

#### [1] 이벤트 서술 품질 심층

LLM이 생성한 narrative 텍스트를 턴별로 분석:

- **문장 품질**: 어색한 표현, 번역체, 문법 오류 검출
- **톤 일관성**: 장소/상황에 맞는 어조 유지 여부 (시장=활기, 뒷골목=긴장)
- **반복 표현**: 동일 문구/구문 패턴의 반복 빈도 (3회 이상 사용된 표현 목록)
- **장면 묘사력**: 감각 묘사(시각/청각/후각)의 존재 여부, 구체성 수준
- **선택지 서술**: LLM 생성 선택지의 구체성, 상황 맥락 반영도
- **서술 길이 분포**: 턴별 narrative 문자수, 평균/최소/최대
- **점수**: 10점 만점 + 개선 필요한 턴 번호 목록

#### [2] 맥락 유지 & NPC 성향 심층

턴 간 정보 연속성과 NPC 시스템을 교차 분석:

- **정보 참조 체인**: 턴 N에서 발견한 정보가 턴 N+k에서 참조되는 경우 목록
- **단절 지점**: 이전 턴 정보가 무시/망각된 턴 식별
- **NPC 이름 공개 타이밍**: encounterCount vs posture threshold 검증
  - FRIENDLY: 1회, CAUTIOUS: 2회, HOSTILE: 3회 기준 충족 여부
- **NPC 감정축 변화**: trust/fear/respect/suspicion/attachment 변화 추적
- **NPC 태도 일관성**: posture 전환이 이벤트/판정과 논리적으로 연결되는지
- **alias→name 전환**: unknownAlias에서 실명으로 전환되는 시점의 자연스러움
- **점수**: 10점 만점 + 문제 NPC/턴 목록

#### [3] 이벤트 다양성 심층

EventDirector 정책과 이벤트 분포를 정량 분석:

- **이벤트 ID 분포**: 고유 이벤트 수 / 총 LOCATION 턴 수
- **연속 반복 검출**: 같은 이벤트가 연속 2턴 이상 나온 경우 (직전 이벤트 hard block 검증)
- **누진 반복 패널티**: 같은 이벤트가 방문 내 2회 이상 등장한 경우
- **ProceduralEvent 비율**: 고정 이벤트 vs 동적 생성 이벤트 비율
- **장소별 이벤트 분포**: 장소마다 몇 종의 이벤트가 매칭되었는지
- **이벤트 타입 분포**: RUMOR, ENCOUNTER, OPPORTUNITY, ATMOSPHERE 등 비율
- **Fallback 발동**: atmosphere fallback이 발동된 횟수
- **점수**: 10점 만점 + 반복/편중 이벤트 목록

#### [4] 메모리 시스템 심층

structuredMemory와 LLM 컨텍스트 파이프라인 검증:

- **storySummary 축적**: finalizeVisit 호출 횟수, 각 방문 기록 내용
- **structuredMemory 상태**: visitLog, npcJournal, npcKnowledge 각 항목 존재 여부
- **[MEMORY]/[THREAD] 태그**: LLM 응답에서 태그가 생성/소비되는 패턴
- **토큰 예산 준수**: L0(theme) 보존 여부, 블록별 예산 배분
- **Mid Summary 생성**: 6턴 초과 시 중간 요약 생성 여부
- **Scene Continuity**: sceneFrame 3단계 억제, locationSessionTurns 관리
- **RUN_ENDED 시 메모리 통합**: 엔딩 발생 시 finalizeVisit 호출 여부
- **점수**: 10점 만점

#### [5] 판정 & 밸런스 심층

ResolveService 판정 결과의 통계적 분석:

- **판정 분포**: SUCCESS / PARTIAL / FAIL 비율 (기대: 약 30/40/30)
- **ActionType별 분포**: INVESTIGATE, PERSUADE, SNEAK 등 어떤 행동이 많았는지
- **ActionType→스탯 매핑 검증**: FIGHT→ATK, SNEAK→EVA 등 올바른 스탯 사용 여부
- **dice + statBonus + baseMod 분해**: 각 요소가 판정에 미치는 영향 비율
- **난이도 곡선**: 턴 진행에 따른 판정 성공률 변화
- **SUPPORT/BLOCK 정책 영향**: matchPolicy가 판정에 미치는 실제 효과
- **프리셋별 강점 활용**: 선택한 프리셋의 높은 스탯이 유리한 판정으로 이어지는지
- **점수**: 10점 만점

#### [6] 장소 전환 & HUB 심층

장소 이동 패턴과 HUB 시스템 검증:

- **장소 순회 패턴**: 방문 순서, 각 장소 체류 턴 수
- **MOVE_LOCATION 처리**: "다른 장소로 이동" 입력 → NODE_ENDED → HUB 복귀 검증
- **extractTargetLocation 성공률**: 특정 장소명 지정 vs 불명확 이동
- **HUB 선택지 구성**: 장소 선택지가 올바르게 생성되는지
- **finalizeVisit 타이밍**: 장소 떠날 때 storySummary 저장 확인
- **actionHistory 리셋**: 장소 이동 시 히스토리 초기화 여부
- **체류 패턴**: 장소당 평균 체류 턴, 최소/최대
- **점수**: 10점 만점

#### [7] Incident & 시그널 심층

Narrative Engine v1의 사건 시스템과 시그널 피드 분석:

- **활성 Incident**: 어떤 사건이 spawn되었는지, 종류/시점
- **control/pressure 변화**: 턴별 이중 축 추이 그래프 (텍스트)
- **Incident 생명주기**: ACTIVE → CONTAINED/ESCALATED/EXPIRED 전이 여부
- **시그널 생성**: 채널별(RUMOR/SECURITY/NPC_BEHAVIOR/ECONOMY/VISUAL) 분포
- **시그널 severity 분포**: 1~5 단계별 빈도
- **엔딩 조건 근접도**: ALL_RESOLVED/DEADLINE/PLAYER_CHOICE 중 어느 쪽에 가까운지
- **최소 턴 가드**: 15턴 미만에서 ALL_RESOLVED 차단 여부
- **점수**: 10점 만점

### 6단계: 결과 요약 (분석 모드는 여기서 종료)

리포트 파일 경로, 종합 점수, 선택된 심층 분석 결과의 핵심 발견을 간결히 보고.

**분석 모드(`/playtest`)는 여기서 종료.**

---

## -fix 모드 추가 절차

`-fix` 플래그가 있을 때만 아래를 계속 수행한다.

### 7단계: 수정 계획 수립

리포트의 **개선 권장사항**과 **선택된 심층 분석 결과**를 기반으로 수정 계획을 작성한다.

수정 계획 원칙:
- **선택한 FOCUS_AREAS와 직접 관련된 이슈만** 수정 대상으로 삼는다
- Critical → High → Medium 순서로 의존성을 고려하여 정렬
- 각 수정에 대해: 대상 파일, 수정 내용, 예상 영향을 명시
- Low 우선순위는 수정하지 않는다

수정 계획을 사용자에게 보여주고 **승인을 요청**한다:

```
수정 계획:
1. [Critical] {파일}: {수정 내용}
2. [High] {파일}: {수정 내용}
...

진행할까요? (y/n)
```

사용자 승인 후 진행.

### 8단계: 코드 수정

승인된 수정 계획에 따라 코드를 수정한다.

수정 대상 범위:
- `server/src/` — 서버 로직 (turns.service.ts, engine/hub/*, llm/* 등)
- `client/src/` — 클라이언트 (필요 시)
- `content/graymar_v1/` — 콘텐츠 데이터 (필요 시)

수정 시 반드시 준수:
- 수정 전 해당 파일을 Read로 확인
- CLAUDE.md의 Critical Design Invariants 위반 금지
- 기존 기능 회귀 방지 (수정 범위 최소화)

### 9단계: 서버 재시작

기존 NestJS 프로세스 트리를 **전체 정리**한 뒤 재시작한다.
`lsof`로 포트만 죽이면 부모/자식 프로세스가 좀비로 남으므로, 프로세스 이름 기반으로 정리한다.

```bash
# 1) graymar 관련 nest/pnpm 프로세스 트리 전체 정리
pkill -f 'graymar/server.*nest.js start --watch' 2>/dev/null
pkill -f 'graymar/server.*pnpm start:dev' 2>/dev/null
# 2) 혹시 남은 포트 점유 프로세스 정리
sleep 1
lsof -ti:3000 | xargs kill -9 2>/dev/null
# 3) 재시작
cd server && pnpm start:dev &
```

서버가 정상 기동될 때까지 대기 (최대 30초).

### 10단계: 재테스트 (2차 플레이테스트)

1차와 **동일한 조건**으로 플레이테스트를 다시 실행한다.
JSON 로그를 별도 파일로 저장 (파일명에 `_after` 접미사).

### 11단계: 비교 분석

1차와 2차 결과를 비교하여 개선 여부를 판정한다.

비교 항목:
- **종합 점수 변화**: 1차 vs 2차 (항목별)
- **선택한 FOCUS_AREAS 점수 변화**: 심층 분석 점수 비교
- **수정한 이슈별 해결 여부**: 각 수정 항목이 실제로 개선되었는지
- **회귀 검출**: 수정하지 않은 항목에서 점수가 떨어진 경우

비교 결과를 리포트에 추가:

```markdown
## 수정 전후 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 종합 | X.X | Y.Y | +Z.Z |
| ... | ... | ... | ... |

### 수정 항목별 검증
- [✅/❌] {수정 내용}: {결과}
```

### 12단계: 수정 결과 보고

사용자에게 보고:
- 1차 → 2차 종합 점수 변화
- 개선된 항목 / 미개선 항목 / 회귀 항목
- 수정된 파일 목록

**-fix 모드(`/playtest -fix`)는 여기서 종료.**

---

## -fix -commit 모드 추가 절차

`-fix -commit` 플래그가 모두 있을 때만 아래를 계속 수행한다.

### 13단계: 커밋 가능 여부 판단

아래 **모든 조건**을 충족해야 커밋을 진행한다:

- [ ] 2차 종합 점수가 1차보다 **0.3점 이상** 향상
- [ ] 선택한 FOCUS_AREAS 중 **과반수**에서 점수 향상
- [ ] **회귀 항목 없음** (수정하지 않은 항목에서 1점 이상 하락 없음)

조건 미충족 시:
```
커밋 조건 미충족:
- 종합 점수: X.X → Y.Y (개선 Z.Z, 기준 0.3 미달)
- 회귀 항목: {목록}

커밋을 건너뛰고 종료합니다.
```

### 14단계: 관련 문서 싱크

코드 수정에 따라 설계 문서를 업데이트한다:

- `guides/03_hub_engine_guide.md` — HUB 엔진 변경 시
- `guides/04_llm_memory_guide.md` — LLM/메모리 변경 시
- `guides/05_runstate_constants.md` — RunState 구조 변경 시
- `architecture/*.md` — 아키텍처 수준 변경 시
- `CLAUDE.md` — 불변식/enum/phase 변경 시

### 15단계: Git 커밋 & 푸시

변경된 파일을 리포지토리별로 분리하여 커밋/푸시한다.

#### 서버 (graymar-server)
```bash
cd server
git add {수정된 파일들}
git commit -m "{커밋 메시지}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin main
```

#### 클라이언트 (graymar-client) — 수정이 있을 때만
```bash
cd client
git add {수정된 파일들}
git commit -m "{커밋 메시지}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin main
```

#### 문서 (graymar-docs) — 설계문서/리포트 변경 시
```bash
# docs repo (mdfile 루트)
git add {수정된 파일들}
git commit -m "{커밋 메시지}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin main
```

커밋 메시지 형식:
- 서버: `fix: {FOCUS_AREA} 개선 — {핵심 변경 1줄 요약}`
- 클라이언트: `fix: {핵심 변경 요약}`
- 문서: `docs: playtest {날짜} 결과 반영 — {변경 요약}`

### 16단계: 최종 보고

```
## Playtest -fix -commit 완료

### 점수 변화
| 항목 | 1차 | 2차 | 변화 |

### 커밋 결과
- 서버: {commit hash} — {메시지}
- 클라이언트: {commit hash} — {메시지} (해당 시)
- 문서: {commit hash} — {메시지} (해당 시)

### 수정 요약
- {수정 항목 1}: ✅ 개선 확인
- {수정 항목 2}: ✅ 개선 확인
```
