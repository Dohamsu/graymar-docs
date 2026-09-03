# 113. 모델 프로파일 — Solar Pro 4 전용 대사·화자 귀속 시스템

- 작성: 2026-09-03 (arch/25 부록 J-5·J-6 의 후속, 소유자 지시 "솔라 한정 별도 대사·마커 시스템")
- 브랜치: server `feat/solar-dialogue-profile` (브랜치 정책: 미검증 대공사는 feat/*)
- 상태: 📐 설계 → 구현 → 실런 검증 후 병합 판단

## 0. 결론

Solar Pro 4 는 P0 규칙 중 **라벨(B)·화폐(K)·대명사 개시어**만 못 지키고 나머지는 Gemma 이상으로 따른다(J-6).
그중 라벨은 "모델 문법을 바꾸는" 방식(V2 와이어 마커)이 역효과였고, "규칙 재강조"(V1) + "서버 귀속 규칙"의 조합이 답이다.
그래서 이 문서는 **모델 프로파일**이라는 얇은 층을 하나 만든다 — 프롬프트 접두/접미와 화자 귀속 옵션을 **모델 슬러그로 선택**하는 구조.
Solar 가 첫 프로파일이고, Gemma·Luna 는 프로파일 없음(현행 동작 그대로, 골든 스냅샷 불변).

## 1. 문제 정의 (실측)

| 축 | Solar Pro 4 | 현행(Gemma) | 출처 |
|---|---:|---:|---|
| 원문 라벨 준수 | 57% (40×2) → V1 재강조 80.4% | 100% | J-5·J-6 |
| 실패 형태 | 줄머리 무라벨 큰따옴표 · 한 줄 두 대사 · 군중 조각 · 지문 뒤 같은 줄 대사 | — | J-6 |
| 무라벨 잔존 18건의 정체 (V1) | 군중 8 · 단일 화자 턴 5 · 별칭 언급 1 · 모호 4 | — | J-6 |
| 한 턴 화자 >2 | 1/80 | 4/40 | J-6 |

**현행 스트리밍 귀속(StreamClassifier.identifySpeaker)** 은 마커 → 이름·호칭 60자 창 → 발화동사 패턴 → 대명사(직전 화자) →
primary(단, 이미 화자가 한 번 정해진 뒤(`markerSeen`)면 무명) 순이다. 이 규칙은 Gemma 의 "라벨은 다 달고, 무라벨은 배경"이라는
행동에 맞춰져 있다(arch/68 부록 K 서버판). Solar 처럼 **한 화자의 대사가 전부 무라벨**이면 첫 대사만 주 화자로 붙고 **둘째부터
무명 인물**이 된다 — 같은 사람이 말하는데 초상화가 실루엣으로 바뀐다. 이것이 Solar 에서 사용자에게 보이는 실제 피해다.

## 2. 설계

### 2.1 모델 프로파일 (`llm/model-prompt-profile.core.ts`)

```ts
type ModelPromptProfile = {
  id: 'solar';
  systemPrefix: string;   // 시스템 프롬프트 최상단에 — 라벨 규칙 재강조 (예시 문장 없음, 불변식 42)
  userSuffix: string;     // 유저 메시지 말미 — 출력 전 자기 점검
  dialogueAttribution: { soleSpeakerContinuity: true };  // 2.2
};
resolveModelPromptProfile(model: string): ModelPromptProfile | null
applyPromptProfileCore(messages, profile): LlmMessage[]   // 첫 system 앞·마지막 user 뒤. 원본 불변
```

- 선택 규칙: `LLM_PROMPT_PROFILE_MAP`(`모델=프로파일;…`, `LLM_PROVIDER_ONLY_MAP` 과 같은 문법)이 있으면 그것, 없으면
  슬러그에 `solar` 가 포함되면 `solar`. 그 외 null → **아무것도 하지 않는다**.
- 프롬프트 빌더는 손대지 않는다. 워커가 `buildNarrativePrompt` 결과에 프로파일을 덧씌운다 → 골든 스냅샷 17건 불변.
- 문구는 J-6 V1 그대로(재생 40건 57→80.4% 실증). 예시 문장을 넣지 않는다.

### 2.2 화자 연속 귀속 (`llm/speaker-continuity.core.ts`)

`identifySpeaker` 4단계(무명 폴백) 직전에 프로파일 옵션이 켜져 있을 때만 끼어드는 순수 규칙:

```
decideSoleSpeakerContinuityCore({ before, markerSeen, lastMatchedNpcId, primaryNpcId, candidateCount })
  → { npcId } | null
```
- 조건: `markerSeen` 이고(둘째 이후 무라벨 대사) `lastMatchedNpcId` 가 있고, **`before`(따옴표 앞 60자)에 군중·타인 신호가 없을 때**
  → lastMatchedNpcId 로 귀속. 군중 신호 = 수군·말 조각·행인·누군가·사람들·목소리가·웅성·한 사람이·다른 이가·주고받·외치·속삭이는 소리.
- 조건 불충족이면 null → 기존 무명 처리. 첫 대사(markerSeen 전)는 기존 primary 폴백이 이미 처리하므로 손대지 않는다.
- 왜 안전한가: Solar 는 한 턴 화자 ≤2 를 잘 지키고(위반 1/80), 잠금 턴은 단일 화자다. 오귀속 위험이 남는 유일한 자리는
  "군중 조각을 큰따옴표로"인데 그건 군중 신호 가드가 받는다(J-6 잔존 18건 중 군중 8 이 전부 이 신호를 가졌다).
- Gemma·Luna 에는 적용하지 않는다(옵션 off) — 부록 K 의 "무라벨=배경" 계약을 그대로 둔다.

### 2.3 워커 배선 (`llm-worker.service.ts`)

1. **모델 교차 결정을 프롬프트 빌드 앞으로** 옮긴다(현재는 뒤). 결정 로직·슬롯(`turnNo % 10`)은 불변 — `model-alternation.spec` 이 고정.
2. `narrativeModel = alternateModel ?? lightConfig?.model ?? config.model` 로 프로파일을 해석해 `messages` 에 덧씌운다.
3. `StreamClassifierService` 생성 시 `{ soleSpeakerContinuity }` 옵션을 넘긴다. 비스트리밍 백필 경로(A-2 regex)는 변경 없음.

### 2.4 비목표

- 화폐(K)·대명사 개시어는 이번 범위 밖(기존 후처리·arch/78 축). 계측만 한다.
- 라벨 문법 변경(V2) 안 함. 2-Stage 대사 분리(arch/32)·JSON 모드 무관.
- Gemma·Luna 경로의 어떤 동작도 바꾸지 않는다 — 스냅샷·기존 스펙이 게이트.

## 3. 검증

1. 스펙: 프로파일 해석(슬러그·env 맵·null)·덧씌우기(첫 system/마지막 user, 원본 불변)·연속 귀속(단일 화자 연속 · 군중 신호 → null
   · markerSeen 전 무동작 · lastMatched 없음 → null).
2. 전체 스위트 + 골든 스냅샷 17 불변 + 스모크.
3. 실런 15턴 × 2 (브랜치 빌드, `LLM_ALTERNATE_MODEL=upstage/solar-pro4` 교차, 종료 후 env 원복·main 재빌드):
   - 원문 라벨(`ai_turn_logs.raw_completion`) — 목표 ≥ 80%(V1 재생과 동급)
   - **저장본 무명 인물 대사 수** — J-5 실런 대비 감소(연속 귀속 효과의 직접 지표)
   - 어체 위반(`llm_speech_audit`) — J-5 16.7% 대비
   - 지연 p50(벤치와 겹치지 않는 시간) — Gemma 대비 배율
   - 게이트 15종, NpcMismatch·MarkerCollision 로그 0
4. 병합 판단은 소유자: 라벨·무명·어체 세 지표가 J-5 보다 개선되고 회귀 0 이면 병합, 채택(교차 슬롯 투입)은 별도 결정.
