# LLM Context System v1

> 목적: 서버 결과(server_result)로부터 **Fact를 추출**하고, **LLM 입력 컨텍스트(`llm_ctx_v1`)를 구성**하며, **Context Bundle을 안정적으로 빌드**하는 전체 파이프라인을 표준화한다.
>
> 전제: 서버가 SoT(Source of Truth)이며, LLM은 `serverFacts`와 `memory`를 기반으로 **서술만** 생성한다.
>
> 출력: `llm_out_v1` 스키마(JSON)로 반환한다.

---

# Part 1. Fact Extraction (사실 추출)

## 1. Fact Extraction 개요

서버가 확정한 `server_result.events`를 LLM/메모리 시스템에서 사용하기 좋은 **FactEvent / Fact**로 변환하는 규칙을 정의한다.

### 입력 (서버 원본)

- `server_result.events[]`
- `server_result.summary.short`
- (선택) `diff`

### 출력 A: LLM용 FactEvent

- `kind`: 이벤트 유형 (아래 통합 enum 참조)
- `text`: 사실 문장 (수치 과다 노출 금지 권장)
- `data`: 구조화 데이터 (선택)

### 출력 B: Memory 후보 Fact

- `key`, `value`, `importance`, `tags`, `scope 후보(THEME/NODE/STEP)`

> **FactEvent kind enum (정본)**: `BATTLE | DAMAGE | STATUS | LOOT | GOLD | QUEST | NPC | MOVE | SYSTEM | UI`
>
> 필드명은 `kind`로 통일 (schema/server_result_v1.json Event.kind와 동일).
> 이 enum은 JSON Schema(`$defs.FactEvent.properties.kind.enum`)에서 정의되며, 시스템 전체에서 단일 정의를 따른다.
> UI kind(보너스 슬롯 등)는 LLM 컨텍스트 전달 시 필터링 대상이며, flags 기반 toneHint 반영에만 사용한다.

---

## 2. Fact Extraction 원칙

- 사실은 **최소 단위**로 기록한다: "무엇이 발생했는가"만 기록한다.
- 수치 노출은 `text`에서 최소화하고, 필요하면 `data`로 이동한다.
- importance는 규칙 기반으로 산정한다 (결정적, deterministic).

---

## 3. 이벤트 타입별 매핑 규칙

### BATTLE

- **FactEvent**: START/TURN/END를 문장화
- **Memory**: 보스/특수전(BOSS) 또는 노드 결과(WIN/LOSE/FLEE)는 NODE scope로 저장

### DAMAGE

- **FactEvent**: crit/miss/normal 문장화 (kind: DAMAGE)
- **data**: `{ source, target, isCrit, isMiss? }`
- **Memory**: 기본 STEP(0.2~0.4), crit면 tags `CRIT` +0.05~0.1

### STATUS

- **FactEvent**: 상태이상 적용/해제/틱 문장화
- **data**: `{ statusId, op }`
- **Memory**: 장기 영향만 NODE(0.6~0.8)

### LOOT

- **FactEvent**: 전리품 획득 문장화 (희귀 강조)
- **data**: `{ items, hasRare }`
- **Memory**: KEY_ITEM/RARE/QUEST_ITEM은 THEME 또는 NODE(0.85~0.95)

### GOLD

- **FactEvent**: "약간의 돈" 등 정성 표현
- **data**: `{ delta }`
- **Memory**: 기본 저장하지 않음, 큰 변화만 NODE(0.6)

### QUEST

- **FactEvent**: 수락/갱신/완료 문장화
- **data**: `{ questId, op }`
- **Memory**: THEME 우선(0.9~1.0), tags `MAIN_ARC|QUEST|CLUE`

### NPC

- **FactEvent**: 대화 결론/약속/관계 변화 문장화
- **data**: `{ npcId, relationDelta? }`
- **Memory**: 주요 NPC는 NODE 또는 THEME(0.7~0.95)

### MOVE

- **FactEvent**: 지역 이동 문장화
- **data**: `{ from, to }`
- **Memory**: 기본 STEP(0.3), 메인 지점 진입은 NODE(0.7)

### SYSTEM

- 운영 이벤트. 과장 연출 금지.

---

## 4. importance 가이드 (결정적)

| Scope | importance 범위 | 대상 예시 |
|-------|----------------|-----------|
| THEME | 0.85 ~ 1.0 | MAIN_ARC, QUEST, KEY_ITEM, MAJOR_NPC |
| NODE  | 0.6 ~ 0.85 | 보스, 중요한 선택, 관계 변화, 희귀 드랍 |
| STEP  | 0.2 ~ 0.6 | 일반 공격, 회복, 이동 |

**가중치 보정**:

| 태그 | 가중치 | 비고 |
|------|--------|------|
| MAIN_ARC | +0.2 | 메인 스토리 관련 |
| KEY_ITEM | +0.2 | 핵심 아이템 획득 |
| BOSS | +0.15 | 보스 전투 |
| CRIT | +0.05 | 크리티컬 히트 |

> 상한: 1.0

---

## 5. Fact Extraction 구현 체크

- `extractFactEvents(server_result.events)` -> `FactEvent[]`
- `extractMemoryFacts(server_result.events)` -> `Fact[]`
- `promoteFacts(facts)`:
  - THEME: `run_memory.theme_memory` upsert
  - NODE: `node_memory.facts` merge
  - STEP: 최근 N턴 저장

---

# Part 2. LLM Input Context Schema (LLM 입력 컨텍스트 스키마)

## 6. 설계 원칙

- **서버 결과(server_result)가 진실**: 수치/판정/드랍/상태 변화는 서버가 확정한다.
- LLM 입력은 "사실(facts)" 중심으로 전달한다 (장문 로그 전달 금지).
- 메인 스토리 기억은 `memory.theme`(L0)을 통해 **항상 포함**한다.
- 선택지는 서버가 확정한 것만 제공하며, LLM이 새 선택지를 만들지 않도록 한다.
- 입력은 JSON 단일 오브젝트만 허용한다.

---

## 7. 상위 구조 (필수 섹션)

`llm_ctx_v1` 최상위 필드 구성:

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `version` | `string` (const `"llm_ctx_v1"`) | O | 스키마 버전 식별자 |
| `turnNo` | `integer` (min: 0) | O | 현재 턴 번호 |
| `node` | `object { id, type, index }` | O | 현재 노드 정보 |
| `serverFacts` | `ServerFacts` | O | 이번 턴 확정 사실의 집합 (구조화) |
| `memory` | `MemoryBundle` | O | theme/summary/nodeFacts 등 기억 레이어 |
| `recent` | `RecentBundle` | O | 최근 N턴 요약 (짧게) |
| `ui` | `UIBundle` | - | 사용 가능한 액션/표현 힌트 (선택) |
| `choices` | `ChoiceItem[]` (max: 6) | O | 서버가 제공하는 선택지 (없으면 빈 배열) |

---

## 8. JSON Schema (Draft 2020-12) - 정본

이 스키마가 모든 필드 제약의 **정본(canonical source)**이다. 예산 정책 등 다른 곳에서 언급되는 수치 제약은 이 스키마를 따른다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/llm_input_context_v1.schema.json",
  "title": "LLM Input Context v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "turnNo", "node", "serverFacts", "memory", "recent", "choices"],
  "properties": {
    "version": { "type": "string", "const": "llm_ctx_v1" },
    "turnNo": { "type": "integer", "minimum": 0 },
    "node": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "type", "index"],
      "properties": {
        "id": { "type": "string", "minLength": 1, "maxLength": 80 },
        "type": { "type": "string", "enum": ["COMBAT", "EVENT", "REST", "SHOP", "EXIT"] },
        "index": { "type": "integer", "minimum": 0 }
      }
    },
    "serverFacts": { "$ref": "#/$defs/ServerFacts" },
    "memory": { "$ref": "#/$defs/MemoryBundle" },
    "recent": { "$ref": "#/$defs/RecentBundle" },
    "ui": { "$ref": "#/$defs/UIBundle" },
    "choices": {
      "type": "array",
      "maxItems": 6,
      "items": { "$ref": "#/$defs/ChoiceItem" }
    }
  },
  "$defs": {
    "ServerFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": ["summary", "events"],
      "properties": {
        "summary": {
          "type": "object",
          "additionalProperties": false,
          "required": ["short"],
          "properties": {
            "short": { "type": "string", "minLength": 1, "maxLength": 180 }
          }
        },
        "events": {
          "type": "array",
          "maxItems": 20,
          "items": { "$ref": "#/$defs/FactEvent" }
        },
        "flags": {
          "type": "object",
          "additionalProperties": { "type": ["boolean", "string", "number"] }
        }
      }
    },
    "FactEvent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "text"],
      "properties": {
        "kind": {
          "type": "string",
          "enum": ["BATTLE", "DAMAGE", "STATUS", "LOOT", "GOLD", "QUEST", "NPC", "MOVE", "SYSTEM", "UI"],
          "description": "server_result_v1 Event.kind와 동일 enum. UI kind는 LLM 전달 시 필터링 대상."
        },
        "text": { "type": "string", "minLength": 1, "maxLength": 200 },
        "data": { "type": "object", "additionalProperties": true }
      }
    },
    "MemoryBundle": {
      "type": "object",
      "additionalProperties": false,
      "required": ["theme", "storySummary", "nodeFacts"],
      "properties": {
        "theme": {
          "type": "array",
          "maxItems": 12,
          "items": { "$ref": "#/$defs/ThemeItem" }
        },
        "storySummary": { "type": "string", "minLength": 0, "maxLength": 2000 },
        "nodeFacts": {
          "type": "array",
          "maxItems": 20,
          "items": { "$ref": "#/$defs/NodeFact" }
        }
      }
    },
    "ThemeItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "text", "priority", "tags"],
      "properties": {
        "id": { "type": "string", "minLength": 1, "maxLength": 80 },
        "text": { "type": "string", "minLength": 1, "maxLength": 220 },
        "priority": { "type": "integer", "minimum": 0, "maximum": 1000 },
        "tags": {
          "type": "array",
          "maxItems": 6,
          "items": { "type": "string", "minLength": 1, "maxLength": 24 }
        },
        "expiresAt": { "type": ["string", "null"], "format": "date-time" }
      }
    },
    "NodeFact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["key", "value", "importance", "tags"],
      "properties": {
        "key": { "type": "string", "minLength": 1, "maxLength": 80 },
        "value": { "type": "string", "minLength": 1, "maxLength": 220 },
        "importance": { "type": "number", "minimum": 0, "maximum": 1 },
        "tags": {
          "type": "array",
          "maxItems": 6,
          "items": { "type": "string", "minLength": 1, "maxLength": 24 }
        }
      }
    },
    "RecentBundle": {
      "type": "object",
      "additionalProperties": false,
      "required": ["shortSummaries"],
      "properties": {
        "shortSummaries": {
          "type": "array",
          "maxItems": 8,
          "items": { "type": "string", "minLength": 1, "maxLength": 180 }
        }
      }
    },
    "UIBundle": {
      "type": "object",
      "additionalProperties": false,
      "required": ["availableActions"],
      "properties": {
        "availableActions": {
          "type": "array",
          "maxItems": 10,
          "items": { "type": "string", "minLength": 1, "maxLength": 30 }
        },
        "toneHint": {
          "type": "string",
          "enum": ["neutral", "tense", "calm", "mysterious", "triumph", "danger"]
        }
      }
    },
    "ChoiceItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "label", "action"],
      "properties": {
        "id": { "type": "string", "minLength": 1, "maxLength": 32 },
        "label": { "type": "string", "minLength": 1, "maxLength": 40 },
        "hint": { "type": "string", "minLength": 0, "maxLength": 80 },
        "action": {
          "type": "object",
          "additionalProperties": false,
          "required": ["type", "payload"],
          "properties": {
            "type": { "type": "string", "enum": ["ACTION", "CHOICE", "SYSTEM"] },
            "payload": { "type": "object" }
          }
        }
      }
    }
  }
}
```

---

## 9. 예시 payload

```json
{
  "version": "llm_ctx_v1",
  "turnNo": 12,
  "node": { "id": "node_3", "type": "COMBAT", "index": 3 },
  "serverFacts": {
    "summary": { "short": "슬라임에게 피해를 주었다." },
    "events": [
      { "kind": "BATTLE", "text": "전투가 계속된다.", "data": { "phase": "TURN" } },
      { "kind": "DAMAGE", "text": "공격이 적중했다.", "data": { "source": "PLAYER", "target": "ENEMY", "isCrit": false } }
    ]
  },
  "memory": {
    "theme": [
      { "id": "main_arc_red_door", "text": "폐광의 붉은 문을 열기 위한 열쇠를 찾아야 한다.", "priority": 100, "tags": ["MAIN_ARC", "QUEST"], "expiresAt": null }
    ],
    "storySummary": "마을에서 촌장은 붉은 문에 대한 경고와 단서를 남겼다.",
    "nodeFacts": [
      { "key": "clue.red_door", "value": "열쇠는 늑대 두목과 연관", "importance": 0.9, "tags": ["CLUE", "QUEST"] }
    ]
  },
  "recent": { "shortSummaries": ["촌장에게서 붉은 문 이야기를 들었다.", "사냥터로 이동했다."] },
  "ui": { "availableActions": ["ATTACK", "DEFEND", "USE_ITEM", "REST", "FLEE"], "toneHint": "tense" },
  "choices": []
}
```

---

# Part 3. Context Bundle Builder (컨텍스트 번들 빌더)

## 10. Bundle 포함 순서 (고정)

Context Bundle을 조립할 때 아래 순서를 반드시 따른다. 상위 레이어일수록 우선순위가 높다.

| 순서 | 레이어 | 소스 | 필수 여부 |
|------|--------|------|-----------|
| 1 | L0 theme | `run_memory.theme_memory` | **필수** (절대 탈락 금지) |
| 2 | L1 storySummary | `run_memory.story_summary` | 필수 |
| 3 | L2 nodeFacts | `node_memory.facts` (현재 노드 우선) | 필수 |
| 4 | L3 recent | 최근 N턴 short summaries | 필수 |
| 5 | serverFacts | `summary` + `events` | 필수 |
| 6 | choices / ui | `availableActions`, 선택지 | 조건부 |

---

## 11. 예산 정책 및 축소 규칙

### 예산 한도 (JSON Schema 정본 기준)

아래 수치는 섹션 8의 JSON Schema에 정의된 `maxItems`/`maxLength` 제약과 일치한다.

| 항목 | 최대 개수 | 항목당 최대 길이 |
|------|-----------|-----------------|
| theme | 12개 | 220자 |
| storySummary | 1개 | 2000자 (운용 권장: 1500자) |
| nodeFacts | 20개 | 220자 |
| recent (shortSummaries) | 8개 | 180자 |
| events | 20개 | 200자 |

> storySummary는 스키마상 최대 2000자이나, 운용 시 1500자 이내로 유지하는 것을 권장한다.

### 축소 규칙 (예산 초과 시 우선순위)

예산 초과 시 아래 순서대로 축소한다. 번호가 낮을수록 먼저 축소 대상이 된다.

1. **recent** 축소: 8 -> 5 -> 3개
2. **nodeFacts** 제거: importance가 낮은 것부터 제거
3. **storySummary** 재압축: 서버 요약기를 통해 재압축
4. **events** 축소: 중요도 기반으로 20 -> 12 -> 8개
5. **theme는 절대 제거 금지**: 필요하면 문장 자체를 더 짧게 정제할 수는 있으나 항목을 삭제하지 않는다

---

## 12. 캐시 전략

- **키 형식**: `ctx:{runId}:{turnNo}`
- **무효화 조건**:
  - `run_memory.updated_at` 변경
  - `node_memory.updated_at` 변경 (현재/직전 노드)
  - storySummary 재압축 발생
  - choices/availableActions 변경 (EVENT/SHOP 노드)

---

## 13. Context Bundle Builder 의사코드

```
buildContextBundle(runId, turnNo, node, serverResult):
  runMem = loadRunMemory(runId)
  nodeNow = loadNodeMemory(node.id)
  nodePrev = loadPrevNodeMemory(runId, node.index - 1)
  recent = loadRecentShortSummaries(runId, turnNo, N=8)

  factEvents = extractFactEvents(serverResult.events)  // UI kind 제외

  ctx = {
    version: "llm_ctx_v1",
    turnNo,
    node: { id: node.id, type: node.type, index: node.index },
    serverFacts: { summary: { short: serverResult.summary.short }, events: factEvents },
    memory: {
      theme: topK(runMem.theme_memory, 12, priority desc),
      storySummary: runMem.story_summary,
      nodeFacts: mergeNodeFacts(nodeNow, nodePrev, limit=20)
    },
    recent: { shortSummaries: recent },
    ui: { availableActions: resolveAvailableActions(node, serverResult) },
    choices: resolveChoices(node, serverResult)
  }

  ctx = trimToBudget(ctx)       // 섹션 11의 축소 규칙 적용
  cacheSet("ctx:{runId}:{turnNo}", ctx)  // 섹션 12의 캐시 전략 적용
  return ctx
```

---
