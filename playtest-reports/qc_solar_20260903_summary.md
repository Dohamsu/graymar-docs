# 품질 사이클 — Solar Pro 4 전턴 운영 3회차 (2026-09-03)

교차 중단·Solar 전턴 전환(arch/113 §6) 직후 `/quality-cycle` 3회. 회차마다 팩·페르소나를 바꿨다.
게이트가 잡은 결함은 0건이고, 전부 전문 정독에서 나왔다 (기존 QC 시리즈와 같은 양상).

| 회차 | 런 | 팩·페르소나 | 게이트 | 원문 라벨 | 어체 위반 | 대명사 개시 | 무마커 줄 |
|---|---|---|---|---|---|---|---|
| 1 | c98261b5 | star_sand · chatty · 12턴 | 15/15 | 60% | 4/23 | 16.7% | 7 |
| 2 | 426e5031 | karnholt · coercer · 12턴 | 14/15 (V2 조우) | 55% | 2/9 | 11.6% | 2 (+무명 3) |
| 3 | 45ae4bf2 | graymar · devotee · 12턴 | 14/15 (V9 반복) | 77% | 5/27 | 9.2% | 1 |

비용은 0.24~0.29원/호출(프로모), 서술 호출 p50 3.2~4.4초. 직전 검증 런(44fe6a0b) 라벨 97%는
상한 표본이었고, 3런 평균은 64% — 프로파일이 잡은 무라벨 대사를 **저장본**이 못 받던 구멍이 이번에 드러났다(아래 1-C).

## 1회차 (star_sand · chatty) — 수정 3건

| # | 증상 | 근거 원문 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 1-A | T6 이렌에게 "첫 공통몽의 시점"을 물었는데 비주제 판정 → 빈손 STEER 가드가 "그 주제는 안다"는 자기모순 힌트를 내고, 이렌이 canon과 반대(추락 **뒤**)로 즉흥 답변 | 로그 `[Quest] 대화 계열(TALK) 비주제 — fact 공개 차단` · `[EmptyHanded] turn=6 NPC_SS_IREN` / 프롬프트 "지금 물은 것에는 답할 거리가 없지만 '첫 공통몽의 시점'에 관해서는 아는 바가 있습니다" | fact 키워드 매칭이 토큰(`[가-힣]{2,}`)만 써서 **다어절 키워드가 영원히 안 걸림**. star_sand 49개 중 18개(`첫 공통몽`·`같은 문장`·`두 번째 입구`…)가 사문이었다 | `extractFactQueryKeywords`(토큰+공백 정규화 전문) 신설, fact 조회 5곳 교체. 프로브: 같은 질문 → `matchedByTopic:true, revealMode:direct` |
| 1-B | T15 토바에게 "등불수녀원의 절벽 쪽 수녀라는 이름… 더 묻고 싶습니다?" → **MOVE_LOCATION** 판정, 수녀원으로 순간이동해 수녀 본인이 답변 | `[Intent] … → MOVE_LOCATION (source=RULE)` / 서술 "부둣가 창고의 … 빛이 등불수녀원의 절벽 쪽으로 넘어오자" | `detectLocationBasedMove` 가 장소명 뒤 맨 조사(`쪽`)만으로 이동 판정 → 대화 잠금 가드의 "명시 이동" 예외를 통과 | nano 라벨 승격 경로와 같은 정본 `hasMoveSuffixAfter(requireMoveVerb)` 로 통일(이동 동사 활용형 확장) + 잠금 중 의문형 입력은 명시 이동 불인정(2층). 프로브: 같은 문장 → INVESTIGATE·부두 잔류, "등불수녀원의 절벽으로 간다" → 이동 정상 |
| 1-C | T14 토바 대사 5줄 중 2줄 무마커(초상화·화자 없음). T5 `"…" 그녀가 말한다` 후치 귀속도 무마커 | `[ServerMarker] dialogues=5 matched=3 unmatched=2` (Falling back to regex pipeline) | arch/113 화자 연속 귀속이 **스트림 분류기에만** 있고 저장본 경로(스트리밍 백필 regex)엔 없어 라이브와 저장본이 갈림 | `insertMarkers` 에 `soleSpeakerContinuity` 옵션(프로파일 모델만) — 군중 신호 없으면 직전 화자, 첫 대사는 primary. 스펙 4 |

재확인(기존 트랙): 어체 위반은 하게체 `들어가세`·합쇼 `미끄럽습니다`·하오 GYUSU 침투로 R5v2 맵 범위, 감사기의 말끝 흐림(`…인지.`) 오집계 절반. 대명사 개시어 16.7%(프롬프트로 안 내려감 — 서버 후처리 후보).

## 2회차 (karnholt · coercer) — 수정 1건 + 소유자 판단 1건

| # | 증상 | 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 2-A | 술집 4턴 화자가 `@[무명 인물]` 사내, 이후 **술집 안주인 오슬라가 주조소에 등장**해 3턴 대화. V2 조우 게이트 실패(enc 0) | `[NpcResolver] npcId=null source=NO_NPC` ×6 · `[LockSeed] turn=13 actionHistory primaryNpcId 보충: NPC_KH_INNKEEP` · `npcLocations` 공백 | **karnholt 저작 NPC 6명 전원 `schedule` 부재**(graymar·star_sand 는 전원 보유). `audit_content` 가 AUTONOMOUS 팩은 "PlotDirector 가 등장을 만든다"고 INFO 처리했으나, 30일 실측 NO_NPC 턴 **46.5%**(graymar 11%·star_sand 14%)이고 이 런은 비트 채택 0 | **미수정 — 소유자 판단 요청**. 이전 결정(감사 INFO)이 명시적이라 콘텐츠를 임의로 바꾸지 않았다. 권고: 6명 schedule 저작(안주인=술집 상시, 감독관=감독청/주조소, 조각공=주조소, 밀수두목=검은 시장/초소, 길드장=갱도/숙소촌, 의뢰인=숙소촌/술집) + 감사 규칙을 WARN 으로 |
| 2-B | 플롯 시드가 "광부 **메린**의 실종"·"메린의 아내" — 메린은 실종 광부의 **아내**(의뢰인) | plotSeed.truth.what / keyFacts FACT_4 / 비트 프리미스 | 콘텐츠에 실종자 이름이 없어 nano 가 코어 NPC 이름을 다른 인물에 재사용. 검증기(`validatePlotSeedCore`)에 이름 규칙 없음 | 규칙 2b `findReusedCoreNameCore`(`X의 아내/남편/실종`, `실종된 X` 패턴 → 재롤) + 시스템 프롬프트 1줄. 스펙 2 |

재확인: 골드 서술("주머니가 무거워지는 감각") 은 THREATEN PARTIAL 골드 이벤트와 정합. nano 라벨 파손("…눌러 붙인다를 관찰한다") 은 arch/105 P1 라벨 트랙. 시드 생성이 T4 까지 늦어 초반 비트 스킵(`plotSeed 부재로 선계산 스킵`) — 기존 관측.

## 3회차 (graymar · devotee) — 수정 2건

| # | 증상 | 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 3-A | T15 마이렐이 T13·T14 대사 두 줄을 **글자 그대로** 다시 말함 (V9 반복 실패의 실체) | 프롬프트 `[야간 경비 책임자의 직전 발언 — 이어받을 맥락]` 이 두 줄을 원문 인용 + "그대로 반복하지 마세요" | 인용된 구체 문장을 저모델이 복제(불변식 50). 인용은 연속성에 필요해 입력에서 못 뺌. 재탕 센서(5.12.5)는 계측 전용 | `dialogue-repeat.core` — 최근 3턴 대사와 정규화 15자+ 완전 일치하는 **마커 대사 줄**만 통째 제거(문장 내부 절삭 없음, 전부 재탕이면 첫 줄 보존). `[DialogueRepeatDrop]` 로그. 스펙 3 |
| 3-B | T6 콜론 라벨 3줄 + 무라벨 1줄 혼재 → 무라벨 줄 무마커 | `[ServerMarker:ColonFormat] converted=3 unmatched=…` | 콜론 형식 경로는 변환 후 즉시 반환해 1-C 의 연속 귀속을 타지 않음 | `attachBareQuoteLinesCore` — 콜론 변환 뒤 남은 줄 머리 무라벨 대사를 직전 화자(없으면 primary)로. 스펙 2 |

재확인: `그대`·`냄새` 어휘 반복(V9 계측), "단정한 장교"(토브렌 별칭)를 마이렐에 오용 1회, 첫 조우에 "다시 만나는구려" 1회 — 반복·별칭 트랙.

## 검증

- 서버 스펙 2,564 passed(신규 +16) · `pnpm build` · 재기동 · 스모크 PASS (3회 반복).
- 재현 프로브(scratchpad `probe_qc1.py`): 1-A direct 공개 · 1-B 잠금 유지·명시 이동 정상.
- 1-C/3-A/3-B 는 LLM 출력 의존이라 단위 스펙 + 확인 런(`run_20260903_qc_solar_verify.json`)의 무마커 줄·`[DialogueRepeatDrop]` 발화로 본다.

## 미커밋 파일 (커밋은 요청 시)

server: `common/text-utils.ts`(+spec) · `engine/hub/{intent-parser-v2.service,nano-move-choice.core,plot-seed-validator,quest-progression.service}.ts`(+spec 3) · `llm/{llm-worker.service,npc-dialogue-marker.service,speaker-continuity.core,plot-seed-generator.service,context-builder.service,dialogue-repeat.core}.ts`(+spec 2) · `turns/{location-turn,location-result}.service.ts`
root: 이 보고서, `run_20260903_qc_solar{1,2,3,_verify}.json`

## 잔여 (기존 트랙 귀속, 미수정)

- 어체 드리프트: R5v2 맵 확장 후보(HAOCHE `겠지→겠소`, HAECHE `구려→구먼`, 하게체 `~세`), 감사기 말끝 흐림 오집계.
- 대명사 개시어 7~17% — 프롬프트 한계, 서버 후처리 후보.
- karnholt 스케줄(2-A) 소유자 결정 대기.

## 확인 런 (graymar · chatty · 8턴, run 00c8a09b)

수정 후 저장본 기준: 무마커 줄 0(1회차 7 → 0)·마커 커버리지 100%·`[DialogueRepeatDrop] turn=7` 1회 발화(레닉 T6 대사 "충성심이란 건 제일 마지막에 팔리는 물건…"을 T7 이 그대로 복창 → 제거, 나머지 서술 무손상). 게이트 실패 2건은 짧은 술집 런의 표본 문제(V2 CORE 조우 0 — 배경 NPC 레닉과만 대화 / V9 `탁자` 어휘 반복 계측)로 이번 수정과 무관.
