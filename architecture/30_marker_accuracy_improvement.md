# 30 --- NPC 대사 @마커 오류율 개선: 3전략 파이프라인

> NPC 대사 발화자 식별(@마커) 오류율을 줄이기 위한 3단계 개선 전략.
> LLM 프롬프트 강화, 서브 LLM 2차 검증, JSON 구조화 출력 모드를 결합하여
> 마커 정확도를 극대화한다.
>
> 작성: 2026-04-13

---

## 1. 배경 및 문제점

### 1.1 ��재 마커 파이프라인 (v1)

```
메인 LLM (산문 출력)
  → nano LLM (발화자 판단, 대사 직전 120자 문맥)
  → regex 5단계 fallback
  → @[표시이름|초상화URL] 변환
```

### 1.2 잔존 오류 패턴

| 오류 유형 | 원인 | 빈도 |
|-----------|------|------|
| 발화자 호칭 누락 | LLM이 대사 직전 발화자 명시 규칙 불이행 | 가끔 |
| 대명사만 사용 | "그가 말했다" → nano가 매칭 실패 | 가끔 |
| @마커 리터럴 출력 | LLM이 @기호를 직접 출력 | 드물게 |
| 교차 대화 혼동 | 여러 NPC 교차 시 발화자 구분 실패 | 가끔 |
| nano 120자 문맥 부족 | 복잡한 장면에서 오매칭 | 가끔 |

---

## 2. 개선 전략

### 2.1 전략 1: 프롬프트 강화 + nano 판단 개선

#### 2.1.1 시스템 프롬프트 NPC 대사 규칙 확장

**변경 파일**: `server/src/llm/prompts/system-prompts.ts`

기존 단순 규칙을 구조화된 3섹션으로 확장:

- **필수 패턴**: `[NPC 호칭 + 조사] + [행동/발화동사] + 마침표 + "대사"` 순서 강제
- **교차 대화 규칙**: 매 대사마다 호칭 반복 예시
- **절대 금지**: 대명사 사용, 대사만 출력, @기호 사용, 문단 첫줄 대사 시작

NARRATIVE_SYSTEM_PROMPT와 PARTY_NARRATIVE_SYSTEM_PROMPT 양쪽 모두 적용.

#### 2.1.2 프롬프트 빌더 NPC 호칭 블록 강화

**변경 파일**: `server/src/llm/prompts/prompt-builder.service.ts`

- NPC 별칭에서 짧은 호칭 자동 추출 (예: "날카로운 눈매의 회계사" → "회계사")
- `[NPC 대사 호칭]` 블록에 짧은 호칭 병기
- 대명사 금지 + 연속 발화 시 짧은 호칭 사용 지시 추가

#### 2.1.3 nano LLM 판단 ���롬프트 정밀화

**변경 파일**: `server/src/llm/llm-worker.service.ts`

nano 시스템 프롬프트에 5단계 우선순위 판단 규칙 추가:

1. 대사 직전 호칭 → NPC_ID
2. 대명사 → 성별 필터링
3. 직업명/역할명 → role 매칭
4. 단서 없음 → 주 NPC
5. 빈 문자열/UNKNOWN 절대 금지

`maxTokens`를 `* 25, 60` → `* 30, 80`으로 증가.

---

### 2.2 전략 2: 서브 LLM 2차 검증 파이프라인

**변경 파일**: `server/src/llm/llm-worker.service.ts`

nano 판단 후, regex fallback 전에 **서브 LLM 2차 검증** 단계 삽입:

```
nano 판단 → 미할당 대사 수집 (≤4개)
  → fallback 모델(GPT-4.1-mini)로 2차 검증
  → 전체 서술 1500자 문맥 전달 (nano 120자 대비 10배+)
  → 검증 결과 assignments에 병합
  → regex fallback (최종 안전망)
```

**조건**:
- nano 성공 시에만 실행 (nano 실패 → 바로 regex)
- 미할당 4개 이하일 때만 (비용/지연 제한)
- 실패해도 기존 흐름 무영향

**로그**: `[SubLlmVerify] turn=N unassigned=M resolved=K`

---

### 2.3 전략 3: Structured JSON Output 모드

환경변수 `LLM_JSON_MODE=true`로 활성화 (기본 off, 전투 턴 제외).

#### 2.3.1 타입 확장

**변경 파일**: `server/src/llm/types/llm-provider.types.ts`

```typescript
export interface LlmProviderRequest {
  // ... 기존 필드 ...
  responseFormat?: 'text' | 'json_object';
}
```

#### 2.3.2 OpenAI Provider

**변경 파일**: `server/src/llm/providers/openai.provider.ts`

`responseFormat === 'json_object'`일 때 `response_format: { type: 'json_object' }` 전달.

#### 2.3.3 JSON 출력 스키마

**변경 파일**: `server/src/llm/prompts/system-prompts.ts`

새 상수 `NARRATIVE_JSON_FORMAT_INSTRUCTION` 추가:

```json
{
  "segments": [
    { "type": "narration", "text": "서술 문장" },
    { "type": "dialogue", "speaker_id": "NPC_ID", "speaker_alias": "호칭", "text": "대사" }
  ],
  "choices": [...],
  "memories": [...],
  "thread": "장면 요약"
}
```

#### 2.3.4 파이프라인 분기

**변경 파일**: `server/src/llm/llm-worker.service.ts`

```
JSON 모드 ON → LLM 호출 (responseFormat: json_object)
  → JSON 파싱 성공 → assembleFromJson() → 서술 + @마커 직접 조립
                      → nano/regex 후처리 전체 스킵
  → JSON 파싱 실패 → 기존 산문 파이프라인으로 fallback
```

헬퍼 메서드:
- `parseJsonNarrative()`: JSON 추출 + segments 검증
- `assembleFromJson()`: segments → 산문 + @마커 조립

---

## 3. 파이프라인 전체 흐름도

```
NanoDirector 전처리
  ↓
메인 LLM 서술 생성 ──── [JSON 모드] ──→ JSON 파서 → assembleFromJson() → 마커 완성
  │                                         (실패 시 아래로)
  ↓ (산문 모드)
[전략1] 강화된 프롬프트 (호칭 예시 + 금지 패턴)
  ↓
[전략1] 개선된 nano 판단 (5단계 규칙)
  ↓
[전략2] 미할당 대사 ≤4개? → 서브 LLM 2차 검증 (GPT-4.1-mini, 1500자 문맥)
  ↓
regex 5단계 fallback (최종 안전망)
  ↓
@[표시이름|초상화URL] 변환 + sanitize
```

---

## 4. 변경 파일 요약

| 파일 | 전략 | 변경 내용 |
|------|------|----------|
| `server/src/llm/prompts/system-prompts.ts` | 1, 3 | NPC 대사 규칙 확장 + JSON 포맷 상수 |
| `server/src/llm/prompts/prompt-builder.service.ts` | 1, 3 | 호칭 블록 강화 + useJsonMode 분기 |
| `server/src/llm/llm-worker.service.ts` | 1, 2, 3 | nano 프롬프트 개선 + 서브 LLM 2차 검증 + JSON 모드 전체 |
| `server/src/llm/types/llm-provider.types.ts` | 3 | responseFormat 필드 |
| `server/src/llm/providers/openai.provider.ts` | 3 | response_format 전달 |

---

## 5. 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_JSON_MODE` | `false` | JSON 구조화 출력 모드 (true/false) |

---

## 6. 검증 방법

1. `pnpm build` — 빌드 성공 확인
2. **전략 1+2** (기본): 서버 재시작 후 플레이테스트로 마커 정확도 비교
3. **전략 3** (`LLM_JSON_MODE=true`): JSON 파싱 성공률 + 마커 정확도 확인
4. 로그 모니터링:
   - `[NanoSpeakerBatch]` assigned/total 비율
   - `[SubLlmVerify]` 2차 검증 해소 비율
   - `[JsonMode]` JSON 파싱 성공/실패
