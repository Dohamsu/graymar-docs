# Database Schema v1

## 핵심 테이블

users
player_profiles
hub_states
run_sessions
node_instances
battle_states
turns
run_memories
node_memories
recent_summaries
ai_turn_logs

---

## 중요 제약

UNIQUE (run_id, turn_no)
UNIQUE (run_id, idempotency_key)
UNIQUE (run_id, node_index)

---

## run_sessions 필수 필드

- id (PK)
- user_id (FK)
- status (RUN_ACTIVE / RUN_ENDED / RUN_ABORTED)
- run_type (CAPITAL / PROVINCE / BORDER)
- act_level (1~6)
- chapter_index
- current_node_index
- current_turn_no
- seed (RNG 시드)
- started_at
- updated_at

---

## battle_state 필수 저장

> OpenAPI 정본: `OpenAPI 3.1.yaml` → `BattleState` 스키마

- phase (START / TURN / END)
- player_state (hp, stamina, status[])
- enemies_state[] (id, hp, status[], personality, distance, angle)
- rng_state
- last_resolved_turn_no

### distance/angle 규칙 (다수 적 전투)

- distance/angle은 **enemies_state 각 항목에만 존재** (per-enemy 정본)
- player_state에는 distance/angle을 저장하지 않는다
- 단일 적 전투에서도 동일 규칙 적용 (enemies_state[0]에 저장)
- server_result_v1의 MetaDiff.position.distance/angle은 단일 적 편의용 복사본이며, enemies[].distance/angle이 정본

---

## turns 필수 저장

- raw_input
- parsed_intent
- action_plan
- server_result
- llm_output
- llm_status

---

## turns 파이프라인 필드 (input_processing_pipeline 연동)

- parsed_by (RULE / LLM / MERGED)
- confidence (float, 파싱 신뢰도)
- policy_result (ALLOW / TRANSFORM / PARTIAL / DENY)
- transformed_intent (jsonb, 변환 후 intent)

---

## turns LLM Worker 필드 (llm_worker 연동)

- llm_attempts (int, 재시도 횟수)
- llm_locked_at (timestamptz, 워커 락 시간)
- llm_lock_owner (text, worker_id)
- llm_model_used (text, 사용된 모델)
- llm_completed_at (timestamptz, 서술 생성 완료 시간)

---

## hub_states 필수 필드

- id (PK)
- user_id (FK)
- active_events (jsonb[])
- npc_relations (jsonb: { npcId → { relation_score, trust_level, hidden_flags } })
- faction_reputation (jsonb: { factionId → score (-100 ~ +100) })
- unlocked_locations (text[])
- rumor_pool (jsonb[])
- available_runs (jsonb[])
- political_tension_level (1~5: STABLE / UNSTABLE / FRACTURED / PRE_WAR / CIVIL_WAR)
- growth_points (int, 미사용 GP)
- updated_at

> hub_states는 run_sessions와 별도 저장. RUN 종료 시 hub_states 업데이트.

---

## player_profiles 필수 필드

- id (PK)
- user_id (FK)
- permanent_stats (jsonb: MaxHP, MaxStamina, ATK, DEF, ACC, EVA, CRIT, CRIT_DMG, RESIST, SPEED)
- unlocked_traits (text[])
- magic_access_flags (text[])
- story_progress (jsonb: act_level, clue_points, revealed_truths 등)
- created_at
- updated_at

