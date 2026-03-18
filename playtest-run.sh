#!/bin/bash
# Context Coherence Reinforcement 통합 런 테스트 (20턴)
set -euo pipefail

BASE="http://localhost:3000/v1"
LOG_FILE="/Users/dohamsu/Workspace/mdfile/playtest-log.json"
RAND_SUFFIX=$RANDOM

echo '{"turns": [' > "$LOG_FILE"

# 1. 회원가입 (토큰 직접 취득)
echo "=== 1. Auth ==="
REG_RESP=$(curl -s -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"ccr_test_${RAND_SUFFIX}@test.com\",\"password\":\"test1234\",\"nickname\":\"CCR테스터\"}")
TOKEN=$(echo "$REG_RESP" | jq -r '.token // empty')
echo "Token: ${TOKEN:0:20}..."

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "Auth failed: $REG_RESP"
  exit 1
fi

AUTH="Authorization: Bearer $TOKEN"

# 2. RUN 생성
echo "=== 2. Create RUN ==="
RUN_RESP=$(curl -s -X POST "$BASE/runs" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"presetId":"DESERTER","gender":"male"}')
RUN_ID=$(echo "$RUN_RESP" | jq -r '.run.id // .runId // empty')
echo "RunID: $RUN_ID"

if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
  echo "Run creation failed (no runId)"
  exit 1
fi

TURN_IDX=1

# 3. 턴 제출 함수
submit_turn() {
  local INPUT_TYPE=$1
  local INPUT_TEXT=$2
  local CHOICE_ID=${3:-}
  local IDEM_KEY="ccr_${RUN_ID}_${TURN_IDX}_$(date +%s%N)"

  local BODY
  if [ "$INPUT_TYPE" = "ACTION" ]; then
    BODY="{\"input\":{\"type\":\"ACTION\",\"text\":\"$INPUT_TEXT\"},\"expectedNextTurnNo\":$TURN_IDX,\"idempotencyKey\":\"$IDEM_KEY\"}"
  else
    BODY="{\"input\":{\"type\":\"CHOICE\",\"choiceId\":\"$CHOICE_ID\"},\"expectedNextTurnNo\":$TURN_IDX,\"idempotencyKey\":\"$IDEM_KEY\"}"
  fi

  local RESP=$(curl -s -X POST "$BASE/runs/$RUN_ID/turns" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d "$BODY")

  local TURN_NO=$(echo "$RESP" | jq -r '.turnNo // 0')
  local RESOLVE=$(echo "$RESP" | jq -r '.serverResult.ui.resolveOutcome // "N/A"')
  local LLM_STATUS=$(echo "$RESP" | jq -r '.llm.status // "N/A"')
  local NODE_OUTCOME=$(echo "$RESP" | jq -r '.meta.nodeOutcome // "N/A"')
  local ACCEPTED=$(echo "$RESP" | jq -r '.accepted // false')

  if [ "$ACCEPTED" != "true" ]; then
    echo "  Turn $TURN_IDX REJECTED: $(echo $RESP | jq -r '.message // .error // "unknown"' 2>/dev/null)"
    TURN_IDX=$((TURN_IDX + 1))
    return
  fi

  echo "  Turn $TURN_NO: resolve=$RESOLVE llm=$LLM_STATUS outcome=$NODE_OUTCOME"

  # LLM 폴링 (최대 60초)
  local NARRATIVE=""
  local LLM_CHOICES="[]"
  if [ "$LLM_STATUS" = "PENDING" ] || [ "$LLM_STATUS" = "RUNNING" ]; then
    for i in $(seq 1 30); do
      sleep 2
      local POLL=$(curl -s "$BASE/runs/$RUN_ID/turns/$TURN_NO" -H "$AUTH")
      local POLL_STATUS=$(echo "$POLL" | jq -r '.llm.status // empty')
      if [ "$POLL_STATUS" = "DONE" ]; then
        NARRATIVE=$(echo "$POLL" | jq -r '.llm.narrative // empty')
        LLM_CHOICES=$(echo "$POLL" | jq -c '.llm.choices // []')
        LLM_STATUS="DONE"
        break
      elif [ "$POLL_STATUS" = "FAILED" ]; then
        LLM_STATUS="FAILED"
        break
      fi
    done
  fi

  local CHOICES=$(echo "$RESP" | jq -c '.serverResult.choices // []')
  local EVENTS=$(echo "$RESP" | jq -c '.serverResult.events // []')
  local SUMMARY=$(echo "$RESP" | jq -r '.serverResult.summary.short // empty')

  if [ $TURN_IDX -gt 0 ]; then
    echo "," >> "$LOG_FILE"
  fi

  local ESC_NARR=$(python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" <<< "$NARRATIVE" 2>/dev/null || echo '""')
  local ESC_SUM=$(python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" <<< "$SUMMARY" 2>/dev/null || echo '""')
  local ESC_INPUT=$(python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" <<< "$INPUT_TEXT" 2>/dev/null || echo '""')

  cat >> "$LOG_FILE" << JSONEOF
{
  "turnNo": $TURN_NO,
  "inputType": "$INPUT_TYPE",
  "inputText": $ESC_INPUT,
  "choiceId": "$CHOICE_ID",
  "resolveOutcome": "$RESOLVE",
  "llmStatus": "$LLM_STATUS",
  "narrative": $ESC_NARR,
  "summary": $ESC_SUM,
  "choices": $CHOICES,
  "llmChoices": $LLM_CHOICES,
  "events": $EVENTS,
  "nodeOutcome": "$NODE_OUTCOME"
}
JSONEOF

  TURN_IDX=$((TURN_IDX + 1))

  # RUN_ENDED 체크
  if [ "$NODE_OUTCOME" = "RUN_ENDED" ]; then
    echo "  *** RUN ENDED at turn $TURN_NO ***"
    return 1
  fi
  return 0
}

# === 턴 시퀀스 (20턴) ===
echo "=== 3. 턴 시퀀스 시작 ==="

# 프롤로그 (턴 0) — HUB 도착
submit_turn "ACTION" "주변을 둘러본다" || true

# 턴 1: 시장 거리로 이동
submit_turn "ACTION" "시장 거리로 가자" || true

# 턴 2-5: 시장 거리 (NPC 연속성 + Knowledge 테스트)
submit_turn "ACTION" "상인에게 말을 건다" || true
submit_turn "ACTION" "그 상인에게 밀수에 대해 더 캔다" || true
submit_turn "ACTION" "장부를 보여달라고 설득한다" || true
submit_turn "ACTION" "주변 사람들에게 소문을 묻는다" || true

# 턴 6-9: 항만 부두 이동 + 탐색
submit_turn "ACTION" "항만 부두로 이동한다" || true
submit_turn "ACTION" "부두에서 수상한 활동을 관찰한다" || true
submit_turn "ACTION" "부두 노동자에게 밀수 경로를 묻는다" || true
submit_turn "ACTION" "선원에게 위협하며 정보를 캔다" || true

# 턴 10-12: 경비대 지구
submit_turn "ACTION" "경비대 지구로 이동한다" || true
submit_turn "ACTION" "경비대 주변을 조사한다" || true
submit_turn "ACTION" "경비병에게 최근 사건을 묻는다" || true

# 턴 13-15: 빈민가
submit_turn "ACTION" "빈민가로 이동한다" || true
submit_turn "ACTION" "어두운 골목을 몰래 조사한다" || true
submit_turn "ACTION" "노숙자에게 뒷골목 소문을 묻는다" || true

# 턴 16-18: 시장 재방문 (Phase 4 검증)
submit_turn "ACTION" "시장 거리로 돌아간다" || true
submit_turn "ACTION" "이전에 만난 상인을 다시 찾는다" || true
submit_turn "ACTION" "상인에게 장부 건을 다시 물어본다" || true

# 턴 19-20: 마무리
submit_turn "ACTION" "주변을 더 살핀다" || true
submit_turn "ACTION" "거점으로 돌아간다" || true

echo "" >> "$LOG_FILE"
echo "]," >> "$LOG_FILE"

# RUN 상태 조회
echo ""
echo "=== 4. RUN 상태 ==="
RUN_STATE=$(curl -s "$BASE/runs/$RUN_ID" -H "$AUTH")
echo "Status: $(echo $RUN_STATE | jq -r '.status // empty')"
echo "HP: $(echo $RUN_STATE | jq -r '.runState.hp // empty')"
echo "Gold: $(echo $RUN_STATE | jq -r '.runState.gold // empty')"

# actionHistory 마지막 5개 (primaryNpcId 필드 확인)
echo ""
echo "=== 5. actionHistory (마지막 5개) ==="
echo "$RUN_STATE" | jq '.runState.actionHistory[-5:]' 2>/dev/null || echo "(parse failed)"

# structuredMemory 확인
echo ""
echo "=== 6. structuredMemory 스냅샷 ==="

# DB에서 직접 조회하기보다 RUN State에서 정보 추출
WORLD_STATE=$(echo "$RUN_STATE" | jq -c '.runState.worldState' 2>/dev/null || echo "{}")
echo "WorldState heat=$(echo $WORLD_STATE | jq '.hubHeat // 0'), safety=$(echo $WORLD_STATE | jq -r '.hubSafety // "N/A"')"

# RUN State를 JSON에 추가
echo "\"runState\": {" >> "$LOG_FILE"
echo "  \"status\": \"$(echo $RUN_STATE | jq -r '.status // empty')\"," >> "$LOG_FILE"
echo "  \"hp\": $(echo $RUN_STATE | jq '.runState.hp // 0')," >> "$LOG_FILE"
echo "  \"gold\": $(echo $RUN_STATE | jq '.runState.gold // 0')," >> "$LOG_FILE"
echo "  \"actionHistory\": $(echo $RUN_STATE | jq -c '.runState.actionHistory // []')," >> "$LOG_FILE"
echo "  \"worldState\": $WORLD_STATE" >> "$LOG_FILE"
echo "}}" >> "$LOG_FILE"

echo ""
echo "=== 완료 ==="
echo "로그 파일: $LOG_FILE"
echo "RunID: $RUN_ID"
