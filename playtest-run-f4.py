#!/usr/bin/env python3
"""Fixplan4 검증용 플레이테스트 — 20턴, DESERTER, male"""

import json, time, uuid, random, sys, requests

BASE = "http://localhost:3000/v1"
EMAIL = f"test_f4_{int(time.time())}@test.com"
PASSWORD = "Test1234!!"
NICKNAME = "F4Tester"
MAX_TURNS = 20
LOCATIONS = ["market", "guard", "harbor", "slums"]
ACTIONS = [
    "주변을 살펴본다", "수상한 곳을 조사한다", "사람들에게 말을 건다",
    "조심스럽게 잠입한다", "거래를 시도한다", "도움을 준다",
    "위협한다", "싸움을 건다", "물건을 훔친다", "설득한다",
    "쉰다", "다른 장소로 이동한다"
]

session = requests.Session()

def api(method, path, body=None):
    url = f"{BASE}{path}"
    r = session.request(method, url, json=body, timeout=30)
    return r.status_code, r.json() if r.text else {}

def poll_llm(run_id, turn_no, max_wait=90):
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
        status = data.get("llmStatus", "")
        if status == "DONE":
            return data.get("llmOutput", "")[:500]
        if status == "FAILED":
            return "[LLM_FAILED]"
        time.sleep(3)
    return "[LLM_TIMEOUT]"

# --- Auth ---
status, resp = api("POST", "/auth/register", {"email": EMAIL, "password": PASSWORD, "nickname": NICKNAME})
if status != 201:
    status, resp = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = resp.get("token", "")
session.headers["Authorization"] = f"Bearer {token}"
print(f"Auth: {EMAIL}")

# --- Create Run ---
status, resp = api("POST", "/runs", {"presetId": "DESERTER", "gender": "male"})
run_data = resp
run_id = run_data["run"]["id"]
current_turn = run_data["run"].get("currentTurnNo", 1)
node_type = run_data.get("currentNode", {}).get("nodeType", "")
choices = run_data.get("lastResult", {}).get("choices", [])
print(f"Run: {run_id}, nodeType: {node_type}")

# --- State tracking ---
turn_logs = []
loc_idx = 0
loc_turns = 0

for turn_i in range(MAX_TURNS):
    idem = str(uuid.uuid4())

    # Refresh state
    _, state = api("GET", f"/runs/{run_id}")
    run_status = state.get("run", {}).get("status", "")
    if run_status == "RUN_ENDED":
        print(f"  [RUN_ENDED at turn {turn_i}]")
        break

    current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
    node_type = state.get("currentNode", {}).get("nodeType", "")
    choices = state.get("lastResult", {}).get("choices", [])

    # Determine input
    if node_type == "HUB":
        # Find location choice
        loc_name = LOCATIONS[loc_idx % len(LOCATIONS)]
        target = None
        for c in choices:
            cid = c.get("id", "")
            if loc_name in cid.lower() or f"loc_{loc_name}" in cid.lower():
                target = c
                break
        if not target:
            # Try accept_quest first, then any go_ choice
            for c in choices:
                cid = c.get("id", "")
                if "accept" in cid.lower() or "quest" in cid.lower():
                    target = c
                    break
            if not target:
                for c in choices:
                    cid = c.get("id", "")
                    if "go_" in cid.lower() or "loc_" in cid.lower():
                        target = c
                        break
            if not target and choices:
                target = choices[0]

        if target:
            body = {"input": {"type": "CHOICE", "choiceId": target.get("id", "")}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"CHOICE:{target.get('id','')}"
        else:
            body = {"input": {"type": "ACTION", "text": "주변을 살펴본다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = "ACTION:observe(no choices)"
    else:
        # LOCATION turn
        loc_turns += 1
        if loc_turns > 4:
            # Rotate location
            body = {"input": {"type": "ACTION", "text": "다른 장소로 이동한다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = "ACTION:move_location"
            loc_turns = 0
            loc_idx += 1
        elif choices and random.random() < 0.25:
            c = random.choice(choices)
            body = {"input": {"type": "CHOICE", "choiceId": c.get("id","")}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"CHOICE:{c.get('id','')}"
        else:
            action = random.choice(ACTIONS[:10])  # exclude move/rest more often
            body = {"input": {"type": "ACTION", "text": action}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"ACTION:{action[:20]}"

    # Submit turn
    status, resp = api("POST", f"/runs/{run_id}/turns", body)

    if status == 409:
        expected = resp.get("details", {}).get("expected", current_turn + 1)
        body["expectedNextTurnNo"] = expected
        body["idempotencyKey"] = str(uuid.uuid4())
        status, resp = api("POST", f"/runs/{run_id}/turns", body)

    if status not in (200, 201):
        print(f"  T{turn_i+1}: ERROR {status} - {json.dumps(resp)[:100]}")
        # Refresh and retry
        _, state = api("GET", f"/runs/{run_id}")
        current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
        continue

    server_result = resp.get("serverResult", {})
    events = server_result.get("events", [])
    resolve = server_result.get("ui", {}).get("resolveOutcome", None)
    node_outcome = server_result.get("nodeOutcome", "")
    matched_event = server_result.get("matchedEventId", "")

    # Poll LLM
    narrative = poll_llm(run_id, current_turn + 1 if status == 201 else current_turn)

    log_entry = {
        "turn": turn_i + 1,
        "turnNo": current_turn,
        "nodeType": node_type,
        "input": input_desc,
        "eventId": matched_event,
        "resolveOutcome": resolve,
        "nodeOutcome": node_outcome,
        "events": [e.get("kind","") for e in events],
        "narrative": narrative[:300] if narrative else "",
    }
    turn_logs.append(log_entry)

    print(f"  T{turn_i+1} [{node_type}] {input_desc[:30]:30s} evt={matched_event[:25] if matched_event else '-':25s} resolve={resolve or '-'}")

    current_turn += 1

    if node_outcome == "RUN_ENDED":
        print(f"  [RUN_ENDED]")
        break

    if node_outcome == "NODE_ENDED":
        loc_turns = 0

# --- Final state ---
_, final_state = api("GET", f"/runs/{run_id}")
run_state = final_state.get("runState", {})
npc_states = run_state.get("npcStates", {})
world_state = run_state.get("worldState", {})
memory = final_state.get("memory", {})

# --- Fixplan4 Verification ---
print("\n" + "="*60)
print("FIXPLAN4 검증 결과")
print("="*60)

# F1: Incidents
incidents = world_state.get("activeIncidents", [])
print(f"\n[F1] Incidents: {len(incidents)}개 활성")
for inc in incidents:
    print(f"  - {inc.get('incidentId','?')} stage={inc.get('stage','?')} control={inc.get('control','?')} pressure={inc.get('pressure','?')}")
print(f"  hubHeat: {world_state.get('hubHeat', '?')}")
print(f"  → {'✅ PASS' if len(incidents) > 0 else '❌ FAIL'}")

# F2: NPC encounterCount
print(f"\n[F2] NPC encounterCount:")
enc_pass = 0
for npc_id, npc in npc_states.items():
    enc = npc.get("encounterCount", 0)
    intro = npc.get("introduced", False)
    posture = npc.get("posture", "None")
    if enc > 0:
        enc_pass += 1
    print(f"  {npc_id}: enc={enc} intro={intro} posture={posture}")
print(f"  → {'✅ PASS' if enc_pass >= 3 else '❌ FAIL'} ({enc_pass}명 count > 0)")

# F3: NPC posture
posture_none = [nid for nid, n in npc_states.items() if n.get("posture") is None]
print(f"\n[F3] NPC posture=None: {len(posture_none)}명")
print(f"  → {'✅ PASS' if len(posture_none) == 0 else '❌ FAIL'}")

# F4: 감정축
print(f"\n[F4] NPC 감정축:")
emo_active = 0
for npc_id, npc in npc_states.items():
    emo = npc.get("emotional", {})
    trust = emo.get("trust", 0)
    fear = emo.get("fear", 0)
    if trust != 0 or fear != 0:
        emo_active += 1
        print(f"  {npc_id}: trust={trust} fear={fear}")
print(f"  → {'✅ PASS' if emo_active > 0 else '❌ FAIL'} ({emo_active}명 감정 변화)")

# F5: structuredMemory
structured = memory.get("structuredMemory", None)
story_summary = memory.get("storySummary", None)
print(f"\n[F5] structuredMemory:")
if structured:
    visit_log = structured.get("visitLog", [])
    npc_journal = structured.get("npcJournal", {})
    print(f"  visitLog: {len(visit_log)}건")
    print(f"  npcJournal: {len(npc_journal)}건")
    print(f"  → {'✅ PASS' if len(visit_log) > 0 else '❌ FAIL'}")
else:
    print(f"  structuredMemory: {structured}")
    print(f"  → ❌ FAIL (None)")
print(f"  storySummary: {'있음' if story_summary else '없음'}")

# F6: resolveOutcome (check from turn logs)
resolve_count = sum(1 for t in turn_logs if t.get("resolveOutcome"))
print(f"\n[F6] resolveOutcome 포함 턴: {resolve_count}/{len(turn_logs)}")
print(f"  → {'✅ PASS' if resolve_count > 0 else '⚠️ INFO (비도전 행위만 시 정상)'}")

# Summary
print("\n" + "="*60)
all_checks = {
    "F1_incidents": len(incidents) > 0,
    "F2_encounter": enc_pass >= 3,
    "F3_posture": len(posture_none) == 0,
    "F4_emotion": emo_active > 0,
    "F5_memory": structured is not None and len(structured.get("visitLog", [])) > 0,
}
passed = sum(1 for v in all_checks.values() if v)
print(f"종합: {passed}/{len(all_checks)} PASS")
for k, v in all_checks.items():
    print(f"  {'✅' if v else '❌'} {k}")

# Save full results
output = {
    "runId": run_id,
    "turns": turn_logs,
    "finalState": {
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
with open("playtest-reports/playtest_f4_verify.json", "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n로그 저장: playtest-reports/playtest_f4_verify.json")
