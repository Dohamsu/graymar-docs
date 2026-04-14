# 31 — 메모리 시스템 v4: 구조화 사실 추출 + nano 요약 주입

> 기존 [MEMORY] 태그 기반 자유 텍스트 저장을 폐기하고,
> nano LLM 구조화 추출 + DB 정규화 + nano 요약 주입으로 재설계.
>
> 작성: 2026-04-14

---

## 1. 현재 시스템 (v3) 문제점

| 문제 | 원인 | 영향 |
|------|------|------|
| 동일 디테일 중복 저장 | text 완전 일치만 체크 | "붉은색 가죽 끈" 4건 누적 |
| NPC 귀속 불명확 | 자유 텍스트에 NPC 이름이 섞여 있을 뿐 | 다른 NPC 기억이 잘못 주입 |
| LLM 자율 분류 | category 판단을 메인 LLM에 위임 | 일관성 없는 분류 |
| 주입 시 과다 | raw 텍스트 17~20개 전부 주입 | 토큰 낭비 + 반복 강화 |
| 자기강화 루프 | 기억 → 서술 반복 → 또 기억 | 표현 고착화 |

---

## 2. v4 아키텍처 개요

```
메인 LLM 서술 출력 (산문/JSON)
       ↓
[Phase 1] nano LLM 구조화 추출
  입력: 서술 텍스트 + NPC 목록
  출력: FactEntry[] (JSON)
       ↓
[Phase 2] 서버 DB 정규화 저장
  npc_facts / location_facts / plot_facts 테이블
  UPSERT (같은 entity + key → 최신 value로 교체)
       ↓
[Phase 3] 다음 턴 프롬프트 조립 시
  관련 entity의 facts를 DB에서 조회
       ↓
[Phase 4] nano LLM 요약 주입
  facts 목록 → 1~2문장 자연어 요약
  프롬프트에 삽입
```

---

## 3. Phase 1: nano 구조화 추출

### 3.1 타이밍

메인 LLM 서술 완료 후, llm-worker.service.ts에서 비동기 호출.
기존 [MEMORY] 태그 파싱을 대체.

### 3.2 nano 프롬프트

```
시스템: 당신은 텍스트 RPG 서술에서 사실을 추출하는 파서입니다.
아래 서술에서 기억할 만한 사실을 JSON 배열로 추출하세요.

규칙:
- 각 사실은 하나의 구체적 정보 (복합 금지)
- entity: NPC ID 또는 장소 ID 또는 "PLOT"
- factType: APPEARANCE | BEHAVIOR | KNOWLEDGE | RELATIONSHIP | LOCATION_DETAIL | PLOT_CLUE
- key: 사실의 식별 키 (같은 key면 업데이트) 예: "손목_장신구", "말투_특징"
- value: 구체적 내용 (30자 이내)
- importance: 0.5~1.0

등장 NPC 목록: {npcList}

출력 (JSON만):
[
  { "entity": "NPC_EDRIC_VEIL", "factType": "APPEARANCE", "key": "안경", "value": "신경질적으로 밀어 올리는 습관", "importance": 0.7 },
  { "entity": "LOC_MARKET", "factType": "LOCATION_DETAIL", "key": "분수대_앞", "value": "악사가 풍자 노래를 부르고 있다", "importance": 0.5 }
]
```

### 3.3 입력

```typescript
interface NanoFactExtractionInput {
  narrative: string;          // 메인 LLM 서술 (조립 후)
  npcList: string[];          // 이번 턴 등장 NPC ID + alias
  locationId: string;         // 현재 장소
  turnNo: number;
}
```

### 3.4 출력

```typescript
interface FactEntry {
  entity: string;             // NPC_ID | LOC_ID | "PLOT"
  factType: FactType;
  key: string;                // 사실 식별 키 (같은 entity+key → UPSERT)
  value: string;              // 구체적 내용 (30자)
  importance: number;         // 0.5~1.0
  turnNo: number;             // 발견 턴
  source: 'LLM_EXTRACT';     // 출처
}

type FactType =
  | 'APPEARANCE'       // 외모: 옷차림, 흉터, 체형
  | 'BEHAVIOR'         // 행동: 습관, 버릇, 말투 특징
  | 'KNOWLEDGE'        // 정보: NPC가 알려준 단서, 비밀
  | 'RELATIONSHIP'     // 관계: NPC 간 관계, 플레이어와의 관계 변화
  | 'LOCATION_DETAIL'  // 장소: 환경 변화, 발견한 물건
  | 'PLOT_CLUE';       // 줄거리: 퀘스트 진행 관련 단서
```

### 3.5 비용/속도

- nano (gpt-4.1-nano): 입력 ~300토큰, 출력 ~150토큰
- 비용: ~$0.00008/회 (~0.12원)
- 속도: ~0.3초
- 메인 LLM 서술과 병렬 처리 가능 (서술 저장 후 비동기)

---

## 4. Phase 2: DB 정규화 저장

### 4.1 테이블 스키마

```sql
CREATE TABLE entity_facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES run_sessions(id),
  entity TEXT NOT NULL,            -- NPC_EDRIC_VEIL | LOC_MARKET | PLOT
  fact_type TEXT NOT NULL,         -- APPEARANCE | BEHAVIOR | ...
  key TEXT NOT NULL,               -- 사실 식별 키
  value TEXT NOT NULL,             -- 구체적 내용 (30자)
  importance NUMERIC(3,2) DEFAULT 0.7,
  discovered_at_turn INT NOT NULL, -- 최초 발견 턴
  updated_at_turn INT NOT NULL,    -- 마지막 업데이트 턴
  source TEXT DEFAULT 'LLM_EXTRACT',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  UNIQUE(run_id, entity, key)      -- 같은 런 + entity + key → UPSERT
);

CREATE INDEX idx_entity_facts_entity ON entity_facts(run_id, entity);
CREATE INDEX idx_entity_facts_type ON entity_facts(run_id, fact_type);
```

### 4.2 UPSERT 로직

```typescript
async saveExtractedFacts(runId: string, facts: FactEntry[]): Promise<void> {
  for (const fact of facts) {
    await db.insert(entityFacts)
      .values({
        runId,
        entity: fact.entity,
        factType: fact.factType,
        key: fact.key,
        value: fact.value,
        importance: fact.importance,
        discoveredAtTurn: fact.turnNo,
        updatedAtTurn: fact.turnNo,
        source: fact.source,
      })
      .onConflictDoUpdate({
        target: [entityFacts.runId, entityFacts.entity, entityFacts.key],
        set: {
          value: fact.value,            // 최신 value로 교체
          importance: fact.importance,
          updatedAtTurn: fact.turnNo,
          updatedAt: new Date(),
        },
      });
  }
}
```

### 4.3 UPSERT의 효과

T2: { entity: "NPC_RONEN", key: "손목_장신구", value: "길드 문양 가죽 끈" } → INSERT
T4: { entity: "NPC_MAIREL", key: "손목_장신구", value: "붉은색 가죽 끈" } → INSERT (다른 NPC)
T6: { entity: "NPC_EDRIC_VEIL", key: "손목_장신구", value: "붉은색 가죽 끈" } → INSERT (다른 NPC)
T9: { entity: "NPC_RONEN", key: "손목_장신구", value: "길드 문양 붉은 가죽 끈" } → UPDATE (같은 NPC+key → value 갱신)

→ NPC당 key 1개만 유지. 같은 NPC의 같은 특징이 여러 번 저장되지 않음.

---

## 5. Phase 3: 관련 사실 조회

### 5.1 조회 시점

context-builder.service.ts에서 프롬프트 조립 시.

### 5.2 조회 로직

```typescript
async getRelevantFacts(
  runId: string,
  relevantNpcIds: string[],
  locationId: string,
): Promise<FactEntry[]> {
  return db.select()
    .from(entityFacts)
    .where(
      and(
        eq(entityFacts.runId, runId),
        or(
          inArray(entityFacts.entity, relevantNpcIds),  // 관련 NPC
          eq(entityFacts.entity, locationId),            // 현재 장소
          eq(entityFacts.entity, 'PLOT'),                // 줄거리 단서
        ),
      ),
    )
    .orderBy(desc(entityFacts.importance), desc(entityFacts.updatedAtTurn))
    .limit(15);  // 최대 15개
}
```

---

## 6. Phase 4: nano 요약 주입

### 6.1 필요성

15개 사실을 raw로 주입하면 여전히 토큰 낭비.
nano가 관련 사실을 NPC별로 1~2문장 요약.

### 6.2 nano 프롬프트

```
아래 사실 목록을 NPC별로 1~2문장 요약하세요. 서술자가 참고할 핵심만.

사실:
- NPC_EDRIC_VEIL/APPEARANCE/안경: 신경질적으로 밀어 올리는 습관
- NPC_EDRIC_VEIL/BEHAVIOR/긴장: 말을 더듬고 손끝이 떨림
- NPC_EDRIC_VEIL/KNOWLEDGE/장부: 3번 창고에 관련 문서가 있다고 함
- LOC_MARKET/LOCATION_DETAIL/분수대: 악사가 풍자 노래 중

출력:
[날카로운 눈매의 회계사] 안경을 자주 밀어 올리며 긴장 시 말을 더듬는다. 3번 창고에 관련 문서가 있다고 알려줬다.
[시장] 분수대 앞에서 악사가 풍자 노래를 부르고 있다.
```

### 6.3 비용

- 입력 ~200토큰, 출력 ~100토큰
- ~0.08원/회, ~0.2초
- 턴당 1회 호출 (Phase 1과 합치면 총 2회 nano 호출)

### 6.4 프롬프트 주입 형태 (개선 전후)

**Before (v3):**
```
[인물] 로넨은 오른손 손목에 길드의 문장이 새겨진 가죽 끈을 두르고 있다. 손끝이 떨리는 것은 두려움이 아니라 피로에서 비롯된 것처럼 보인다.
[인물] 붉은색 튜닉을 입은 남자는 오른손 손목에 길드 문양이 새겨진 붉은색 가죽 끈을 두르고 있다.
[인물] 경비 책임자는 오른손 손목에 붉은색 가죽 끈을 두르고 있으며...
[인물] 회계사는 오른손 손목에 붉은색 가죽 끈을 두르고 있다...
⚠️ 위 사실들을 서술에 적극 활용하세요.
```
(~400자, "붉은색" 4회 반복)

**After (v4):**
```
[기억 요약]
회계사: 안경을 자주 밀어 올리며 긴장 시 더듬는다. 3번 창고 문서 정보를 알려줬다.
경비 책임자: 오른손 흉터가 있다. 야간 순찰을 강화하겠다고 했다.
시장: 분수대 앞 악사가 풍자 노래 중.
이 정보는 참고용입니다. 같은 표현을 반복하지 말고 새로운 관찰로 발전시키세요.
```
(~200자, 중복 0, 구체적)

---

## 7. 마이그레이션 전략

### 7.1 하위 호환

- 기존 `run_memories.structuredMemory.llmExtracted`는 유지 (읽기 전용)
- 새 `entity_facts` 테이블 병행 운영
- context-builder에서 `entity_facts` 우선 사용, 없으면 `llmExtracted` fallback

### 7.2 단계별 전환

**Phase A**: entity_facts 테이블 생성 + nano 추출 파이프라인 구현
**Phase B**: context-builder에서 entity_facts 기반 주입으로 전환
**Phase C**: nano 요약 주입 추가
**Phase D**: 기존 [MEMORY] 태그 생성 지시 제거 (시스템 프롬프트에서 삭제)
**Phase E**: llmExtracted 마이그레이션 완료 후 deprecated

---

## 8. 성능 영향

| 항목 | v3 | v4 |
|------|-----|-----|
| 메모리 생성 | 메인 LLM이 태그 출력 (0원) | nano 1회 (~0.12원) |
| 메모리 저장 | JSONB 배열 append | UPSERT (인덱스 활용) |
| 메모리 주입 | raw 텍스트 ~400자 | 요약 ~200자 + nano 1회 (~0.08원) |
| 중복 | text 완전 일치만 | entity+key UPSERT (완전 방지) |
| 턴당 추가 비용 | 0원 | ~0.20원 (nano 2회) |
| 턴당 토큰 절감 | 0 | ~200토큰 (주입 압축) |
| 자기강화 루프 | 있음 | 없음 (요약이 매번 재생성) |

---

## 9. factType별 key 가이드라인

### APPEARANCE (외모)
- key: 체형, 옷차림, 흉터, 얼굴, 머리카락, 장신구, 손
- 예: { key: "옷차림", value: "낡은 갈색 튜닉" }

### BEHAVIOR (행동/습관)
- key: 말투, 습관, 긴장반응, 걸음걸이
- 예: { key: "긴장반응", value: "안경테를 밀어 올리고 말을 더듬는다" }

### KNOWLEDGE (정보)
- key: 장부_위치, 밀수_경로, 비밀_정보
- 예: { key: "장부_위치", value: "3번 창고에 관련 문서가 있다" }

### RELATIONSHIP (관계)
- key: 플레이어_태도, NPC간_관계
- 예: { key: "플레이어_태도", value: "경계하지만 협조적" }

### LOCATION_DETAIL (장소)
- key: 환경변화, 발견물, 분위기
- 예: { key: "분수대", value: "악사가 풍자 노래를 부르고 있다" }

### PLOT_CLUE (줄거리)
- key: 단서명
- 예: { key: "창고_흔적", value: "3번 창고 뒷문에 최근 출입 흔적" }
