# 49. NPC Resolution Authority v1 — 단일 권한자 + 의도 계층 + 흐름 통합

> **목표**: NPC 화자 결정을 분산된 7개 path에서 단일 `NpcResolverService`로 통합. 명시적 의도/약한 신호를 의도 계층으로 분리하고, 모든 노드 타입(LOCATION/COMBAT/EVENT/REST)이 같은 권한자를 통해 NPC를 결정한다.
> **선행**: architecture/45 (자유 대화) + 46 (Fact·Continuity) + 47 (NPA) + 48 (Discoverability v1).
> **검출 도구**: NPA가 누적 검출한 회귀 사이클 — 미렐라 → 하를런/쥐왕 → 에드릭/미망인 → 마이렐 COMBAT 흐름.
> **작성**: 2026-04-27

---

## 1. 동기 — 누적 회귀가 드러낸 구조적 결함

### 1.1 NPA 회귀 검출 사이클

| 회귀 | 입력 | 잘못 픽한 NPC | 원인 path |
|---|---|---|---|
| 미렐라 점프 | "장부 사건, 부두 쪽 사람들 의심하시오?" | 부두 노동자 (LOC 점프) | IntentParser MOVE_LOCATION |
| 하를런 미등장 | "부두 형제단의 두목에게 다가간다" | 수상한 창고 관리인 | EventMatcher default 이벤트 |
| 쥐왕 미등장 | "지하 조직의 두목에게 다가간다" | 입이 가벼운 술꾼 | textMatchedNpcId 미매칭 |
| ROSA 점프 | "이곳 빈민가 분위기" | 다정한 보육원 여인 | Pass 4 자동추출 |
| GUARD_FELIX 점프 | "젊은 일꾼" | 풋풋한 젊은 경비병 | matchTargetNpc 2자 매칭 |
| DAME_ISOLDE 점프 | "냄새가 나는데" | 향수 냄새가 강한 미망인 | matchTargetNpc 3자 매칭 |
| TOBREN 점프 | "싸움이 있소?" | 토브렌 하위크 | FIGHT actionType 우회 |
| MOON_SEA 점프 | "단 가문의 명예" | 조용한 문서 실무자 | COMBAT 흐름 + LLM 자유 마커 |

각 회귀를 좁은 패치로 차단했지만, **새 path에서 같은 패턴이 반복**. 표면 증상별 대응의 한계.

### 1.2 분산된 NPC 결정 권한 (7개 path)

```
사용자 입력
   ↓
┌──────────────────────┐
│ 1. textMatchedNpcId  │ Pass 1~4 (turns.service.ts:2299)
│ 2. IntentParser      │ matchTargetNpc (intent-parser-v2.ts:1167)
│ 3. IntentV3          │ targetNpcId (intent-v3-builder.ts:127)
│ 4. EventMatcher      │ event.payload.primaryNpcId
│ 5. NanoEventDirector │ PROC 이벤트 NPC
│ 6. conversationLock  │ 5개 파일 분산
│ 7. 후처리 Step F     │ LLM 마커 교정 (llm-worker.ts)
└──────────────────────┘
   ↓
화자 (speakingNpc)
```

각 path는 자기 결정을 우선시키며, 경쟁/순위가 코드 곳곳에 흩어져 있다. 새 패치마다 새 분기 추가 → 복잡성 누적.

### 1.3 구조적 결함 3개 (architecture/47 NPA 보고서 §공통 원인)

| 결함 | 증거 |
|---|---|
| 분산된 권한 | 7개 path, 패치마다 새 분기, 17개 lock 참조 |
| 의도 검증 부재 | "냄새가/젊은/빈민가" 환경 명사 false positive |
| 흐름 분기 컨텍스트 손실 | COMBAT 노드 진입 시 lock/4-mode 무력화 |

→ 표면 패치로는 해결 불가능. **구조 자체의 재설계** 필요.

---

## 2. 핵심 원칙

### 2.1 Single Authority Principle

**모든** NPC 화자 결정은 `NpcResolverService.resolve()`를 통과한다. 다른 path는 결정 자체를 하지 않고, **신호(signal)**만 제공한다.

### 2.2 Intent Hierarchy (의도 계층)

플레이어 호명 신호의 강도를 3등급으로 분리:

| 등급 | 패턴 | 행동 |
|---|---|---|
| **STRONG** | "X에게/X와/X을(를)" + 실명/별칭 전체 | NPC 강제 변경 (lock 무시) |
| **MEDIUM** | 명시 roleKeywords ("두목/형제단/회계사") + 같은 location | lock 부재 시 매칭 |
| **WEAK** | 별칭 부분 키워드 / 자동 추출 | lock 활성 시 무시 (lock 우선) |

이 계층이 회귀 사이클의 모든 케이스를 깨끗이 분류:
- "냄새가" = WEAK → lock 우선 (Edric 유지)
- "두목" = MEDIUM → 같은 location의 매칭 NPC
- "미렐라" = STRONG → 명시 호명, 어디에 있든 매칭

### 2.3 Cross-Node Continuity (흐름 통합)

LOCATION/COMBAT/EVENT/REST 모든 노드 타입이 같은 NpcResolverService 인스턴스를 사용. lock 컨텍스트가 노드 전환 시에도 보존.

---

## 3. NpcResolverService API

### 3.1 입력/출력

```ts
export interface NpcResolutionContext {
  /** 사용자 입력 원문 */
  rawInput: string;
  /** IntentParserV2 결과 (actionType 등) */
  intent: ParsedIntentV2;
  /** 현재 location id */
  currentLocationId: string;
  /** 현재 시간대 */
  timePhase: TimePhaseV2;
  /** 직전 N턴 actionHistory (lock 검색용) */
  actionHistory: Array<Record<string, unknown>>;
  /** EventMatcher가 매칭한 이벤트 (있으면) */
  candidateEvent?: { eventId: string; payload: { primaryNpcId?: string } };
  /** 노드 타입 — LOCATION/COMBAT/EVENT/REST */
  nodeType: 'LOCATION' | 'COMBAT' | 'EVENT' | 'REST' | 'HUB';
  /** 입력 종류 */
  inputType: 'ACTION' | 'CHOICE';
  /** runState (worldState.npcLocations 등 동적 위치 활용) */
  runState: RunState;
}

export interface NpcResolution {
  /** 결정된 화자 NPC id (null이면 비-NPC 흐름) */
  npcId: string | null;
  /** 결정 근거 — audit trail */
  source: NpcResolutionSource;
  /** 신뢰도 0~1 */
  confidence: number;
  /** 다음 후보 (디버깅용) */
  alternatives: Array<{ npcId: string; source: NpcResolutionSource; reason: string }>;
  /** lock 적용 여부 */
  lockApplied: boolean;
  /** 위치 안내 hint (NPC가 다른 location일 때) */
  whereaboutsHint?: NpcWhereaboutsHint;
}

export type NpcResolutionSource =
  | 'STRONG_EXPLICIT_NAME'      // 실명/별칭 전체 매칭
  | 'STRONG_PARTICLE'            // "X에게" 패턴
  | 'MEDIUM_ROLE_KEYWORD'        // 명시 roleKeywords
  | 'WEAK_ALIAS_PARTIAL'         // 별칭 부분 키워드 (lock 부재 시만)
  | 'CONVERSATION_LOCK'          // 직전 SOCIAL NPC 잠금
  | 'EVENT_PRIMARY'              // EventMatcher 이벤트 NPC
  | 'PROC_DIRECTOR'              // NanoEventDirector PROC NPC
  | 'NO_NPC';                    // NPC 없는 턴 (시스템/이동 등)
```

### 3.2 결정 알고리즘

```ts
class NpcResolverService {
  resolve(ctx: NpcResolutionContext): NpcResolution {
    const allNpcs = this.content.getAllNpcs();
    const inputLower = ctx.rawInput.toLowerCase();
    const audit: Alternative[] = [];

    // ── Step 1: STRONG 신호 (lock 무시) ──
    // 실명 또는 별칭 전체 매칭
    for (const npc of allNpcs) {
      if (npc.name && inputLower.includes(npc.name.toLowerCase())) {
        return this.finalize(npc.npcId, 'STRONG_EXPLICIT_NAME', 1.0, ctx);
      }
      if (npc.unknownAlias && inputLower.includes(npc.unknownAlias.toLowerCase())) {
        return this.finalize(npc.npcId, 'STRONG_EXPLICIT_NAME', 0.95, ctx);
      }
    }
    // "X에게" 패턴 + 실명/별칭/role 부분
    const particleMatch = this.matchParticle(ctx.rawInput, allNpcs);
    if (particleMatch) {
      return this.finalize(particleMatch.npcId, 'STRONG_PARTICLE', 0.9, ctx);
    }

    // ── Step 2: 잠금 NPC 검색 (MEDIUM/WEAK 후보 평가 전 미리 계산) ──
    const lockNpcId = this.findConversationLock(ctx);

    // ── Step 3: MEDIUM 신호 (명시 roleKeywords) ──
    const roleMatched = this.matchRoleKeywords(inputLower, allNpcs, ctx.currentLocationId, ctx.timePhase);
    if (roleMatched.length > 0) {
      // 같은 location NPC 우선
      const localFirst = roleMatched.find(n => this.isAtLocation(n, ctx.currentLocationId, ctx.timePhase));
      if (localFirst) {
        return this.finalize(localFirst.npcId, 'MEDIUM_ROLE_KEYWORD', 0.8, ctx);
      }
      // 다른 location NPC면 위치 안내 hint + lock 우선 (lock 활성 시)
      if (lockNpcId) {
        return this.finalize(lockNpcId, 'CONVERSATION_LOCK', 0.7, ctx, {
          whereaboutsHint: this.buildWhereaboutsHint(roleMatched[0], ctx),
        });
      }
      return this.finalize(roleMatched[0].npcId, 'MEDIUM_ROLE_KEYWORD', 0.6, ctx, {
        whereaboutsHint: this.buildWhereaboutsHint(roleMatched[0], ctx),
      });
    }

    // ── Step 4: WEAK 신호 (별칭 부분 키워드) — lock 활성 시 무시 ──
    if (!lockNpcId) {
      const weakMatch = this.matchAliasPartial(inputLower, allNpcs, ctx.currentLocationId);
      if (weakMatch) {
        return this.finalize(weakMatch.npcId, 'WEAK_ALIAS_PARTIAL', 0.5, ctx);
      }
    }

    // ── Step 5: lock NPC 활성 + 약한 신호 부재 → lock 적용 ──
    if (lockNpcId) {
      return this.finalize(lockNpcId, 'CONVERSATION_LOCK', 0.7, ctx);
    }

    // ── Step 6: EventMatcher NPC (lock도 신호도 없을 때) ──
    if (ctx.candidateEvent?.payload.primaryNpcId) {
      return this.finalize(
        ctx.candidateEvent.payload.primaryNpcId,
        'EVENT_PRIMARY',
        0.6,
        ctx,
      );
    }

    // ── Step 7: NPC 없음 ──
    return { npcId: null, source: 'NO_NPC', confidence: 1.0, alternatives: [], lockApplied: false };
  }
}
```

### 3.3 STRONG 호명 패턴 — "X에게/X와/X을"

```ts
private matchParticle(input: string, npcs: NpcDefinition[]): { npcId: string } | null {
  // "에게/께/와/하고/한테" 등 호명 조사
  const particle = input.match(/(.+?)(에게|께|와|하고|한테)\s/);
  if (!particle) return null;
  const target = particle[1].trim().toLowerCase();
  // 실명/별칭/명시 roleKeywords와 매칭
  for (const npc of npcs) {
    if (npc.name && target.includes(npc.name.toLowerCase())) return { npcId: npc.npcId };
    if (npc.unknownAlias && target.includes(npc.unknownAlias.toLowerCase())) return { npcId: npc.npcId };
    const rkws = npc.roleKeywords ?? [];
    if (rkws.some(k => target.includes(k))) return { npcId: npc.npcId };
  }
  return null;
}
```

"부두 형제단의 두목에게 다가간다" → particle = "부두 형제단의 두목" → roleKeywords "두목" 매칭 → STRONG_PARTICLE.

### 3.4 lock 검색 통합

```ts
private findConversationLock(ctx: NpcResolutionContext): string | null {
  // 비-SOCIAL 행동(MOVE_LOCATION/FIGHT/STEAL) + 명시 의도 부재 시 다운그레이드 (architecture/46/48)
  const SOCIAL = new Set(['TALK', 'PERSUADE', 'BRIBE', 'THREATEN', 'HELP', 'INVESTIGATE', 'OBSERVE', 'TRADE']);
  const downgraded = this.shouldDowngradeToSocial(ctx);
  const lookupAction = downgraded ? 'INVESTIGATE' : ctx.intent.actionType;
  if (!SOCIAL.has(lookupAction)) return null;
  // 직전 SOCIAL NPC 검색 (4턴 윈도우)
  for (let i = ctx.actionHistory.length - 1; i >= Math.max(0, ctx.actionHistory.length - 4); i--) {
    const prev = ctx.actionHistory[i];
    const prevNpc = prev.primaryNpcId as string | undefined;
    const prevAction = prev.actionType as string | undefined;
    if (!prevNpc) continue;
    if (SOCIAL.has(prevAction ?? '')) return prevNpc;
    break;
  }
  return null;
}
```

---

## 4. 모든 노드 타입 통합

### 4.1 현재 — 노드별 다른 path

| 노드 | NPC 결정 위치 |
|---|---|
| LOCATION | turns.service.ts handleLocationTurn (textMatch + lock + EventMatcher + IntentV3) |
| COMBAT | turns.service.ts handleCombatTurn (이벤트 NPC만, lock 미적용) |
| EVENT | event-director nano (자유 NPC 선택) |
| REST | NPC 결정 자체 없음 |

→ COMBAT/EVENT에서 lock 무력화.

### 4.2 변경 — 모든 노드가 NpcResolverService 통과

```ts
// turns.service.ts 모든 분기
const resolution = this.npcResolver.resolve({
  rawInput,
  intent,
  currentLocationId: locationId,
  timePhase: ws.phaseV2,
  actionHistory,
  candidateEvent: event,
  nodeType: currentNode.nodeType,
  inputType: body.input.type,
  runState,
});

// 결정 NPC를 모든 후속 처리에 전파
const speakingNpcId = resolution.npcId;
// LLM context 빌드 시 lock + 결정 근거 전달
const llmContext = await this.contextBuilder.build({
  ..., 
  npcResolution: resolution,
});
```

### 4.3 LLM 후처리 (Step F) — lock 인식

```ts
// llm-worker.service.ts Step F
// LLM 출력의 첫 @마커가 resolution.npcId와 다르면 강제 교정
// resolution.confidence ≥ 0.7면 마커 교체, 미만이면 LLM 자유 허용 + 후속 lock 갱신
```

COMBAT 중에도 resolution.npcId가 LLM 마커 검증의 기준점이 됨.

---

## 5. 콘텐츠 정합성 빌드 검증

### 5.1 ContentValidatorService 신규

빌드 또는 ContentLoader.onModuleInit 시점에 실행:

```ts
class ContentValidatorService {
  validate(): ValidationResult[] {
    const results: ValidationResult[] = [];
    for (const npc of this.content.getAllNpcs()) {
      // 1. speechRegister vs speechStyle 일치
      const styleRegister = this.inferRegisterFromStyle(npc.personality?.speechStyle);
      if (styleRegister && styleRegister !== npc.personality?.speechRegister) {
        results.push({
          severity: 'WARNING',
          rule: 'REGISTER_STYLE_MISMATCH',
          message: `${npc.npcId}: register=${npc.personality?.speechRegister} but style suggests ${styleRegister}`,
        });
      }
      // 2. CORE NPC roleKeywords 누락
      if (npc.tier === 'CORE' && !npc.roleKeywords) {
        results.push({
          severity: 'WARNING',
          rule: 'CORE_NO_ROLE_KEYWORDS',
          message: `${npc.npcId}: CORE NPC without explicit roleKeywords`,
        });
      }
      // 3. unknownAlias 부분 단어가 일반 형용사 (자주 매칭 false positive)
      const RISKY_FRAGMENTS = ['젊은', '늙은', '냄새가', '강한', '약한', '큰', '작은'];
      const fragments = (npc.unknownAlias ?? '').split(/\s+/);
      for (const f of fragments) {
        if (RISKY_FRAGMENTS.includes(f)) {
          results.push({
            severity: 'INFO',
            rule: 'ALIAS_RISKY_FRAGMENT',
            message: `${npc.npcId} alias "${npc.unknownAlias}" contains generic fragment "${f}"`,
          });
        }
      }
    }
    return results;
  }

  private inferRegisterFromStyle(style?: string): string | null {
    if (!style) return null;
    if (/~소|~하오|~이오|~구려|~구먼/.test(style)) return 'HAOCHE';
    if (/~습니다|~입니다|~십시오/.test(style)) return 'HAPSYO';
    if (/~해요|~예요|~네요/.test(style)) return 'HAEYO';
    if (/~다네|~라네|~한다/.test(style)) return 'HAECHE';
    return null;
  }
}
```

### 5.2 빌드 시 출력

```
[ContentValidator] 3 WARNING + 5 INFO
  ⚠️ NPC_RONEN: register=HAPSYO but style suggests HAOCHE
  ⚠️ NPC_INFO_BROKER: CORE NPC without explicit roleKeywords
  ℹ️ NPC_GUARD_FELIX alias "풋풋한 젊은 경비병" contains generic fragment "젊은"
```

---

## 6. 데이터 모델 변경

### 6.1 LlmContext 확장

```ts
export interface LlmContext {
  // ... 기존 필드
  /** architecture/49 — NPC 결정 근거 (LLM 마커 검증용) */
  npcResolution: {
    npcId: string | null;
    source: NpcResolutionSource;
    confidence: number;
    lockApplied: boolean;
  } | null;
}
```

### 6.2 actionContext (serverResult.ui)

```ts
actionContext: {
  // ... 기존 필드
  npcResolutionSource?: NpcResolutionSource;  // 디버깅 + NPA
  npcResolutionConfidence?: number;
  lockApplied?: boolean;
}
```

NPA가 이 필드들을 capture하여 결정 근거의 일관성 검증 가능.

### 6.3 actionHistory entry

```ts
{
  turnNo,
  actionType,
  primaryNpcId,
  resolutionSource,  // 새 필드 — lock 검색의 신뢰도 평가용
  // ...
}
```

---

## 7. 마이그레이션 — 7개 path → 단일 service

### Phase 1 (~3h) — NpcResolverService 신규 + 기존 path 호출 위치 통합
- [ ] `engine/hub/npc-resolver.service.ts` 신규 (resolve + helpers)
- [ ] HubModule 등록
- [ ] turns.service.ts handleLocationTurn에서 NpcResolverService 호출
- [ ] 기존 textMatchedNpcId/conversationLockedNpcId/eventPrimaryNpc 분기 제거 (resolution 결과로 대체)
- [ ] 단위 테스트: 기존 NPA 시나리오 회귀 검출 0 확인

### Phase 2 (~2h) — 약한 매칭 비활성화 + STRONG 강화
- [ ] intent-parser-v2.service.ts matchTargetNpc 제거 또는 격하 (resolveContext signal 전달만)
- [ ] turns.service.ts Pass 3 (별칭 부분 매칭) 제거
- [ ] STRONG_PARTICLE ("X에게/와/께") 패턴 강화

### Phase 3 (~2h) — COMBAT/EVENT/REST 통합
- [ ] handleCombatTurn에서 NpcResolverService 호출 (lock-aware)
- [ ] llm-worker Step F에서 resolution.npcId 활용
- [ ] 기존 후처리 분기 정리

### Phase 4 (~2h) — ContentValidatorService
- [ ] `content/content-validator.service.ts` 신규
- [ ] ContentLoader onModuleInit에 validation 추가
- [ ] CORE NPC roleKeywords 자동 보완 (alias 안전 부분 + role 핵심 명사)

### Phase 5 (~3h) — NPA 통합 검증
- [ ] 5+3 = 8 시나리오 ERROR 0 검증
- [ ] 새 actionContext 필드를 NPA reporter에 노출
- [ ] resolution audit trail 출력

### Phase 6 — 커밋·푸시
- [ ] graymar-server (npc-resolver/content-validator + 통합)
- [ ] graymar-docs (architecture/49 + 콘텐츠 정정)

총 ~12h. 단계별 NPA 검증 → 회귀 0 유지.

---

## 8. 위험 및 완화

| 위험 | 완화 |
|---|---|
| 모든 노드 타입 통합 시 거대한 회귀 (LOCATION 외에 작동했던 path 망가짐) | Phase 1~3 단계별, 각 단계 NPA 검증 |
| STRONG 패턴이 부족해 명시적 호명 누락 | Phase 2에 다양한 패턴 단위 테스트 |
| 콘텐츠 검증이 너무 엄격해 빌드 실패 | WARNING/INFO 분리, ERROR는 정말 명백한 경우만 |
| resolveContext 너무 무거워 성능 저하 | NpcResolver는 stateless + cache, 매 턴 1회 호출 |
| 기존 7개 path 제거 시 다른 코드의 직접 의존 | 마이그레이션 단계별 grep + 단위 테스트 |

---

## 9. 검증 메트릭 (NPA로)

| 지표 | 베이스라인 (현재) | 목표 |
|---|---|---|
| 8 시나리오 ERROR 합계 | 5 (chat-edric/mairel + 추후 회귀) | 0 |
| 평균 종합 점수 | 3.13 | 4.0+ (★★★★) |
| TONE_DRIFT | 41~58% | <30% (LLM 변동성 한계) |
| NPC 결정 시간 | <1ms (분산) | <2ms (통합 단일 service) |
| Resolution 통과율 | N/A | 100% (모든 노드 타입) |

---

## 10. Open Questions

### Q1. 콘텐츠 정합성 검증 ERROR 처리

빌드 ERROR로 hard-fail 시 기존 콘텐츠 입력 오류로 서버 시작 자체 실패. WARNING만 사용하고 별도 audit 명령 (`pnpm content:check`) 추가가 안전.

### Q2. STRONG 호명에 다른 location NPC 포함?

"하를런에게 묻는다"인데 하를런이 다른 location → 강제 변경할지, 위치 안내 hint만 줄지. 추천: 위치 안내 (architecture/48 Layer 4 통합).

### Q3. PROC_DIRECTOR (NanoEventDirector NPC) 우선순위

현재 NanoEventDirector는 매 턴 동적으로 NPC 픽. resolveContext에 candidate로 전달하고 lock 활성 시 무시. lock 부재 시만 채택. (Option B 통합)

### Q4. CHOICE 입력의 NPC 결정

CHOICE는 지금 textMatch 미적용. NpcResolverService도 CHOICE면 실명/role 매칭 skip하고 EventMatcher 결과 또는 lock만 사용. inputType=CHOICE 분기 명시.

### Q5. 단위 테스트 커버리지

resolution 알고리즘 단위 테스트 권장 50건+ (각 source별 8~10건). 회귀 사이클 8건은 우선 테스트 케이스.

---

## 11. 관련 문서

- `architecture/45_npc_free_dialogue.md` — daily_topics 기반 잡담 (resolveContext.signal 통합 가능)
- `architecture/46_fact_pool_continuity.md` — Fact 분리 + lock + fact awareness (resolveContext 통합 대상)
- `architecture/47_dialogue_quality_audit.md` — NPA (검증 도구)
- `architecture/48_npc_discoverability_v1.md` — role 매칭 + 위치 lookup (Layer 1·2가 resolveContext의 MEDIUM/whereabouts에 통합)
- `server/src/turns/turns.service.ts:2299` — 기존 textMatchedNpcId Pass 1~4 (마이그레이션 대상)
- `server/src/engine/hub/intent-parser-v2.service.ts:1167` — matchTargetNpc (마이그레이션 대상)
- `server/src/engine/hub/event-matcher.service.ts` — EventMatcher (signal 제공자로 격하)
- `server/src/llm/llm-worker.service.ts` — Step F 후처리 (resolution 활용)
- CLAUDE.md Critical Design Invariant #26 (대화 잠금) — 본 문서에서 강화

---

## 12. 결론

NPA가 누적 검출한 회귀 8건은 **단일 root cause**(분산된 NPC 결정 권한)의 다양한 발현. 좁은 패치는 새 path에서 같은 패턴을 반복하므로 **구조적 통합**이 필요하다.

NpcResolverService는 7개 path를 단일 권한자로 흡수하고, 의도 계층(STRONG/MEDIUM/WEAK)으로 신호를 분리하며, 모든 노드 타입에서 일관된 lock-aware 결정을 보장한다. 콘텐츠 정합성 빌드 검증으로 콘텐츠 입력 오류(현재 7건)도 사전 차단.

총 작업 ~12h, 6 Phase 단계별 NPA 검증으로 회귀 0 유지.
