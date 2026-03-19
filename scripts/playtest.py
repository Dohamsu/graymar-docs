#!/usr/bin/env python3
"""
플레이테스트 스크립트 — 정본 (scripts/playtest.py)

사용법:
  python3 scripts/playtest.py                    # 기본: 20턴, DESERTER, male
  python3 scripts/playtest.py --turns 30         # 턴 수 변경
  python3 scripts/playtest.py --preset SMUGGLER  # 프리셋 변경
  python3 scripts/playtest.py --output result.json  # 출력 파일 지정

/playtest 커맨드에서 호출됨.
"""

import json, time, uuid, random, sys, argparse, os

# --- CLI 인자 ---
parser = argparse.ArgumentParser(description="Playtest runner")
parser.add_argument("--turns", type=int, default=20, help="최대 턴 수 (default: 20)")
parser.add_argument("--preset", default="DESERTER", help="프리셋 (default: DESERTER)")
parser.add_argument("--gender", default="male", help="성별 (default: male)")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
parser.add_argument("--output", default=None, help="결과 JSON 파일 경로")
parser.add_argument("--loc-turns", type=int, default=4, help="장소당 체류 턴 수 (default: 4)")
args = parser.parse_args()

BASE = args.base
MAX_TURNS = args.turns
EMAIL = f"playtest_{int(time.time())}@test.com"
PASSWORD = "Test1234!!"
NICKNAME = "Tester"

LOCATIONS = ["market", "guard", "harbor", "slums"]
ACTIONS = [
    "주변을 살펴본다", "수상한 곳을 조사한다", "사람들에게 말을 건다",
    "조심스럽게 잠입한다", "거래를 시도한다", "도움을 준다",
    "위협한다", "싸움을 건다", "물건을 훔친다", "설득한다",
    "경비병의 동태를 살핀다", "골목길 벽에 기대어 주변을 관찰한다",
    "소문의 진위를 확인한다", "상인에게 뇌물을 건넨다",
]

try:
    import requests
except ImportError:
    print("requests 패키지가 필요합니다: pip install requests", flush=True)
    sys.exit(1)

session = requests.Session()

def api(method, path, body=None):
    url = f"{BASE}{path}"
    try:
        r = session.request(method, url, json=body, timeout=30)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        print(f"  API error: {e}", flush=True)
        return 0, {}

def poll_llm(run_id, turn_no, max_wait=90):
    """LLM 폴링: GET /turns/:turnNo → llm.status / llm.output"""
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            return llm.get("output") or ""
        if status in ("FAILED", "SKIPPED"):
            return f"[LLM_{status}]"
        time.sleep(3)
    return "[LLM_TIMEOUT]"

# ═══════════════════════════════════════
# 1. Auth
# ═══════════════════════════════════════
print(f"=== 플레이테스트 시작 ({MAX_TURNS}턴, {args.preset}, {args.gender}) ===", flush=True)

status, resp = api("POST", "/auth/register", {"email": EMAIL, "password": PASSWORD, "nickname": NICKNAME})
if status != 201:
    status, resp = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = resp.get("token", "")
if not token:
    print(f"Auth 실패: {resp}", flush=True)
    sys.exit(1)
session.headers["Authorization"] = f"Bearer {token}"
print(f"Auth: {EMAIL}", flush=True)

# ═══════════════════════════════════════
# 2. Create Run
# ═══════════════════════════════════════
status, resp = api("POST", "/runs", {"presetId": args.preset, "gender": args.gender})
if status not in (200, 201) or "run" not in resp:
    print(f"런 생성 실패: {status} {resp}", flush=True)
    sys.exit(1)

run_data = resp
run_id = run_data["run"]["id"]
current_turn = run_data["run"].get("currentTurnNo", 1)
node_type = run_data.get("currentNode", {}).get("nodeType", "")
choices = run_data.get("lastResult", {}).get("choices", [])
init_hp = run_data.get("runState", {}).get("hp", "?")
init_gold = run_data.get("runState", {}).get("gold", "?")
print(f"Run: {run_id}, nodeType: {node_type}, HP: {init_hp}, Gold: {init_gold}", flush=True)

# ═══════════════════════════════════════
# 3. Turn Loop
# ═══════════════════════════════════════
turn_logs = []
loc_idx = 0
loc_turns = 0

for turn_i in range(MAX_TURNS):
    idem = str(uuid.uuid4())

    # Refresh state
    _, state = api("GET", f"/runs/{run_id}")
    if not state:
        print(f"  T{turn_i+1}: 상태 조회 실패", flush=True)
        break
    run_status = state.get("run", {}).get("status", "")
    if run_status == "RUN_ENDED":
        print(f"  [RUN_ENDED at turn {turn_i}]", flush=True)
        break

    current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
    node_type = state.get("currentNode", {}).get("nodeType", "")
    choices = state.get("lastResult", {}).get("choices", [])
    hp = state.get("runState", {}).get("hp", "?")

    # Determine input
    if node_type == "HUB":
        loc_name = LOCATIONS[loc_idx % len(LOCATIONS)]
        target = None
        # 1) 장소명 매칭
        for c in choices:
            cid = c.get("id", "")
            if loc_name in cid.lower() or f"loc_{loc_name}" in cid.lower():
                target = c
                break
        # 2) accept_quest
        if not target:
            for c in choices:
                cid = c.get("id", "")
                if "accept" in cid.lower() or "quest" in cid.lower():
                    target = c
                    break
        # 3) go_ / loc_ 아무거나
        if not target:
            for c in choices:
                cid = c.get("id", "")
                if "go_" in cid.lower() or "loc_" in cid.lower():
                    target = c
                    break
        # 4) 첫 번째 선택지 fallback
        if not target and choices:
            target = choices[0]

        if target:
            body = {"input": {"type": "CHOICE", "choiceId": target.get("id", "")}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"CHOICE:{target.get('id', '')}"
        else:
            body = {"input": {"type": "ACTION", "text": "주변을 살펴본다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = "ACTION:observe(no choices)"

    elif node_type == "COMBAT":
        body = {"input": {"type": "ACTION", "text": "정면에서 검을 휘두른다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
        input_desc = "ACTION:combat_attack"

    else:
        # LOCATION turn
        loc_turns += 1
        if loc_turns > args.loc_turns:
            body = {"input": {"type": "ACTION", "text": "다른 장소로 이동한다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = "ACTION:move_location"
            loc_turns = 0
        elif choices and random.random() < 0.25:
            # go_hub은 제외 — 의도치 않은 조기 복귀 방지
            loc_choices = [c for c in choices if c.get("id", "") != "go_hub"]
            if loc_choices:
                c = random.choice(loc_choices)
                body = {"input": {"type": "CHOICE", "choiceId": c.get("id", "")}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
                input_desc = f"CHOICE:{c.get('id', '')}"
            else:
                action = random.choice(ACTIONS)
                body = {"input": {"type": "ACTION", "text": action}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
                input_desc = f"ACTION:{action[:20]}"
        else:
            action = random.choice(ACTIONS)
            body = {"input": {"type": "ACTION", "text": action}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"ACTION:{action[:20]}"

    # Submit turn
    status, resp = api("POST", f"/runs/{run_id}/turns", body)

    # TURN_NO_MISMATCH recovery
    if status == 409:
        expected = resp.get("details", {}).get("expected", current_turn + 1)
        body["expectedNextTurnNo"] = expected
        body["idempotencyKey"] = str(uuid.uuid4())
        status, resp = api("POST", f"/runs/{run_id}/turns", body)

    if status not in (200, 201):
        print(f"  T{turn_i+1}: ERROR {status} - {json.dumps(resp)[:100]}", flush=True)
        _, state = api("GET", f"/runs/{run_id}")
        current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
        continue

    server_result = resp.get("serverResult", {})
    meta = resp.get("meta", {})
    events = server_result.get("events", [])
    resolve = server_result.get("ui", {}).get("resolveOutcome", None)
    node_outcome = meta.get("nodeOutcome", "")
    # eventId: ui.actionContext.eventId (서버가 전달) 또는 이벤트 payload에서 추출
    action_ctx = server_result.get("ui", {}).get("actionContext", {})
    matched_event = action_ctx.get("eventId", "") or next((e.get("payload", {}).get("eventId", "") for e in events if e.get("kind") == "QUEST"), "")

    # Poll LLM
    submitted_turn = resp.get("turnNo", current_turn + 1)
    narrative = poll_llm(run_id, submitted_turn)

    log_entry = {
        "turn": turn_i + 1,
        "turnNo": current_turn,
        "nodeType": node_type,
        "input": input_desc,
        "hp": hp,
        "eventId": matched_event,
        "resolveOutcome": resolve,
        "nodeOutcome": node_outcome,
        "events": [e.get("kind", "") for e in events],
        "narrative": narrative if narrative else "",
    }
    turn_logs.append(log_entry)

    evt_display = matched_event[:25] if matched_event else "-"
    print(f"  T{turn_i+1:02d} [{node_type:8s}] {input_desc[:35]:35s} evt={evt_display:25s} resolve={resolve or '-':8s} HP={hp}", flush=True)

    current_turn += 1

    if node_outcome == "RUN_ENDED":
        print(f"  [RUN_ENDED]", flush=True)
        break

    if node_outcome == "NODE_ENDED":
        loc_turns = 0
        # HUB에서 go_X 선택 시 NODE_ENDED는 loc_idx 증가하지 않음 (장소 이동 자체)
        # LOCATION에서 move_location 시 NODE_ENDED만 loc_idx 증가
        if node_type != "HUB":
            loc_idx += 1

# ═══════════════════════════════════════
# 4. Final State & Verification
# ═══════════════════════════════════════
_, final_state = api("GET", f"/runs/{run_id}")
run_state = final_state.get("runState", {})
npc_states = run_state.get("npcStates", {})
world_state = run_state.get("worldState", {})
memory = final_state.get("memory", {})

print("\n" + "=" * 60, flush=True)
print("플레이테스트 검증 결과", flush=True)
print("=" * 60, flush=True)

# V1: Incidents
incidents = world_state.get("activeIncidents", [])
print(f"\n[V1] Incidents: {len(incidents)}개 활성", flush=True)
for inc in incidents:
    print(f"  - {inc.get('incidentId', '?')} stage={inc.get('stage', '?')} control={inc.get('control', '?')} pressure={inc.get('pressure', '?')}", flush=True)
print(f"  hubHeat: {world_state.get('hubHeat', '?')}", flush=True)

# V2: NPC encounterCount
print(f"\n[V2] NPC encounterCount:", flush=True)
enc_pass = 0
for npc_id, npc in npc_states.items():
    enc = npc.get("encounterCount", 0)
    intro = npc.get("introduced", False)
    posture = npc.get("posture", "None")
    if enc > 0:
        enc_pass += 1
    print(f"  {npc_id}: enc={enc} intro={intro} posture={posture}", flush=True)

# V3: NPC posture
posture_none = [nid for nid, n in npc_states.items() if n.get("posture") is None]
print(f"\n[V3] NPC posture=None: {len(posture_none)}명", flush=True)

# V4: 감정축
print(f"\n[V4] NPC 감정축:", flush=True)
emo_active = 0
for npc_id, npc in npc_states.items():
    emo = npc.get("emotional", {})
    trust = emo.get("trust", 0)
    fear = emo.get("fear", 0)
    if trust != 0 or fear != 0:
        emo_active += 1
        print(f"  {npc_id}: trust={trust} fear={fear}", flush=True)

# V5: structuredMemory
structured = memory.get("structuredMemory", None)
story_summary = memory.get("storySummary", None)
print(f"\n[V5] structuredMemory:", flush=True)
if structured:
    visit_log = structured.get("visitLog", [])
    npc_journal = structured.get("npcJournal", {})
    print(f"  visitLog: {len(visit_log)}건", flush=True)
    print(f"  npcJournal: {len(npc_journal)}건", flush=True)
else:
    print(f"  structuredMemory: None", flush=True)
print(f"  storySummary: {'있음' if story_summary else '없음'}", flush=True)

# V6: resolveOutcome
resolve_count = sum(1 for t in turn_logs if t.get("resolveOutcome"))
print(f"\n[V6] resolveOutcome 포함 턴: {resolve_count}/{len(turn_logs)}", flush=True)

# Summary
print("\n" + "=" * 60, flush=True)
all_checks = {
    "V1_incidents": len(incidents) > 0,
    "V2_encounter": enc_pass >= 2,
    "V3_posture": len(posture_none) == 0,
    "V4_emotion": emo_active > 0,
    "V5_memory": structured is not None and len((structured or {}).get("visitLog", [])) > 0,
    "V6_resolve": resolve_count > 0,
}
passed = sum(1 for v in all_checks.values() if v)
print(f"종합: {passed}/{len(all_checks)} PASS", flush=True)
for k, v in all_checks.items():
    print(f"  {'✅' if v else '❌'} {k}", flush=True)

# ═══════════════════════════════════════
# 5. Save Output
# ═══════════════════════════════════════
output = {
    "meta": {
        "preset": args.preset,
        "gender": args.gender,
        "maxTurns": MAX_TURNS,
        "actualTurns": len(turn_logs),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    },
    "runId": run_id,
    "turns": turn_logs,
    "finalState": {
        "hp": run_state.get("hp"),
        "gold": run_state.get("gold"),
        "npcStates": npc_states,
        "worldState": {
            "hubHeat": world_state.get("hubHeat"),
            "activeIncidents": incidents,
            "day": world_state.get("day"),
            "globalClock": world_state.get("globalClock"),
        },
        "memory": memory,
    },
    "verification": all_checks,
}

output_path = args.output
if not output_path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"playtest-reports/playtest_{ts}.json"

os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
with open(output_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n로그 저장: {output_path}", flush=True)
print(f"=== 플레이테스트 완료 ===", flush=True)
