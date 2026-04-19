#!/usr/bin/env python3
"""
엔딩 최단경로 테스트 — fact 수집 최적화 런
퀘스트 전환 조건에 필요한 fact를 최단으로 수집하여 엔딩 도달.
"""

import json, time, uuid, sys, requests

BASE = "http://localhost:3000/v1"
EMAIL = f"speedrun_{int(time.time())}@test.com"
PASSWORD = "Test1234!!"
MAX_TURNS = 60

QUEST_ROUTE = [
    {"location": "go_market", "target_facts": ["FACT_LEDGER_EXISTS"], "max_turns": 8},
    {"location": None, "target_facts": ["FACT_WAGE_FRAUD_PATTERN", "FACT_TAMPERED_LOGS"], "max_turns": 10},
    {"location": "go_guard", "target_facts": ["FACT_INSIDE_JOB"], "max_turns": 10},
    {"location": "go_harbor", "target_facts": ["FACT_ROUTE_TO_EAST_DOCK", "FACT_SMUGGLE_ROUTE_GUILD"], "max_turns": 12},
    {"location": "go_guard", "target_facts": ["FACT_OFFICIAL_INQUIRY", "FACT_BOTH_SIDES_EVIDENCE"], "max_turns": 12},
]

EXPLORE_ACTIONS = [
    "수상한 곳을 조사한다", "소문의 진위를 확인한다", "주변을 살펴본다",
    "사람들에게 말을 건다", "설득한다", "경비병의 동태를 살핀다",
    "도움을 준다", "거래를 시도한다",
]

session = requests.Session()

def api(method, path, body=None):
    url = f"{BASE}{path}"
    try:
        r = session.request(method, url, json=body, timeout=30)
        if r.status_code >= 400:
            print(f"  ❌ {method} {path} → {r.status_code}", flush=True)
            return None
        return r.json() if r.text else {}
    except Exception as e:
        print(f"  ❌ {method} {path} → {e}", flush=True)
        return None

def get_run_state(run_id):
    """런 상태 전체 조회 — fact, questState, nodeType, choices"""
    data = api("GET", f"/runs/{run_id}")
    if not data:
        return [], "", "HUB", [], 0
    rs = data.get("runState", {})
    facts = rs.get("discoveredQuestFacts", [])
    quest_state = rs.get("questState", "S0_ARRIVE")
    node = data.get("currentNode", {})
    node_type = node.get("nodeType", "HUB")
    run_info = data.get("run", {})
    turn_no = run_info.get("currentTurnNo", 0)
    choices = []
    lr = data.get("lastResult", {})
    if lr and lr.get("choices"):
        choices = [c["id"] for c in lr["choices"]]
    return facts, quest_state, node_type, choices, turn_no

def submit_turn(run_id, turn_no, input_data):
    """턴 제출 + LLM 폴링"""
    resp = api("POST", f"/runs/{run_id}/turns", {
        "input": input_data,
        "idempotencyKey": str(uuid.uuid4()),
        "expectedNextTurnNo": turn_no,
    })
    if not resp:
        return None, turn_no
    actual_tn = resp.get("turnNo", turn_no)
    # LLM 폴링
    for _ in range(60):
        time.sleep(2)
        data = api("GET", f"/runs/{run_id}/turns/{actual_tn}")
        if data and data.get("llmStatus") in ("DONE", "SKIPPED", "FAILED"):
            return data, actual_tn
    return None, actual_tn

# === 메인 ===
print("=== 엔딩 스피드런 시작 ===", flush=True)

# 1. 회원가입 + 로그인
api("POST", "/auth/register", {"email": EMAIL, "password": PASSWORD, "nickname": "SpeedRunner"})
login = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
if not login or "token" not in login:
    print("로그인 실패", flush=True)
    sys.exit(1)
session.headers["Authorization"] = f"Bearer {login['token']}"

# 2. 런 생성
run_resp = api("POST", "/runs", {"presetId": "DESERTER", "gender": "male"})
run_id = run_resp.get("run", {}).get("id") or run_resp.get("id")
print(f"Run: {run_id}", flush=True)

# 3. accept_quest
_, tn = submit_turn(run_id, 1, {"type": "CHOICE", "choiceId": "accept_quest"})
total_turns = 1
action_idx = 0

for phase_idx, phase in enumerate(QUEST_ROUTE):
    # 현재 상태 확인
    all_facts, quest_state, node_type, choices, current_tn = get_run_state(run_id)
    tn = current_tn + 1

    # 목표 fact 이미 발견됐으면 스킵
    remaining = [f for f in phase["target_facts"] if f not in all_facts]
    if not remaining:
        print(f"\n[Phase {phase_idx+1}] 이미 완료! facts 충족", flush=True)
        continue

    # 장소 이동 필요 시
    if phase["location"]:
        # COMBAT이면 도주
        if node_type == "COMBAT":
            for _ in range(8):
                data, tn = submit_turn(run_id, tn, {"type": "ACTION", "rawInput": "도주한다"})
                tn += 1; total_turns += 1
                _, _, node_type, _, _ = get_run_state(run_id)
                if node_type != "COMBAT": break

        # LOCATION이면 go_hub로 복귀
        if node_type == "LOCATION":
            # go_hub 선택지 사용
            _, _, _, ch, cur_tn = get_run_state(run_id)
            tn = cur_tn + 1
            if "go_hub" in ch:
                data, tn = submit_turn(run_id, tn, {"type": "CHOICE", "choiceId": "go_hub"})
            else:
                data, tn = submit_turn(run_id, tn, {"type": "ACTION", "rawInput": "선술집으로 돌아간다"})
            tn += 1; total_turns += 1
            # HUB 복귀 대기
            time.sleep(3)
            _, _, node_type, _, cur_tn = get_run_state(run_id)
            tn = cur_tn + 1

        # HUB에서 장소 선택
        if node_type == "HUB":
            data, tn = submit_turn(run_id, tn, {"type": "CHOICE", "choiceId": phase["location"]})
            tn += 1; total_turns += 1
            # LOCATION 진입 대기
            time.sleep(3)
            _, _, node_type, _, cur_tn = get_run_state(run_id)
            tn = cur_tn + 1

    print(f"\n[Phase {phase_idx+1}] 목표: {remaining} (T{total_turns}, {node_type})", flush=True)

    # 탐색 행동 반복
    for attempt in range(phase["max_turns"]):
        if total_turns >= MAX_TURNS: break

        # 상태 갱신
        all_facts, quest_state, node_type, choices, cur_tn = get_run_state(run_id)
        tn = cur_tn + 1
        remaining = [f for f in phase["target_facts"] if f not in all_facts]
        if not remaining:
            print(f"  ✅ Phase {phase_idx+1} 완료! state={quest_state} facts={len(all_facts)}개", flush=True)
            break

        # COMBAT → 도주
        if node_type == "COMBAT":
            data, tn = submit_turn(run_id, tn, {"type": "ACTION", "rawInput": "도주한다"})
            tn += 1; total_turns += 1
            print(f"  T{total_turns:02d} [COMBAT] → 도주", flush=True)
            continue

        # RUN_ENDED → 종료
        if node_type not in ("HUB", "LOCATION"):
            print(f"  ⚠️ 예상 외 노드: {node_type}", flush=True)
            break

        # 선택지 우선
        if choices and node_type != "HUB":
            non_hub = [c for c in choices if c != "go_hub"]
            # 탐색 관련 선택지 우선
            talk_c = next((c for c in non_hub if any(k in c for k in
                ["talk","observe","search","sneak","investigate","ask","listen","help","assess","tip","watch"])), None)
            pick = talk_c or (non_hub[0] if non_hub else None)
            if pick:
                data, tn = submit_turn(run_id, tn, {"type": "CHOICE", "choiceId": pick})
                resolve = data.get("resolveOutcome", "-") if data else "-"
                tn += 1; total_turns += 1
                print(f"  T{total_turns:02d} CHOICE:{pick[:25]:25s} {resolve}", flush=True)
                continue

        # 자유 행동
        action = EXPLORE_ACTIONS[action_idx % len(EXPLORE_ACTIONS)]
        action_idx += 1
        data, tn = submit_turn(run_id, tn, {"type": "ACTION", "rawInput": action})
        resolve = data.get("resolveOutcome", "-") if data else "-"
        tn += 1; total_turns += 1
        print(f"  T{total_turns:02d} ACTION:{action[:25]:25s} {resolve}", flush=True)

    if total_turns >= MAX_TURNS:
        print(f"\n⚠️ 최대 턴({MAX_TURNS}) 도달", flush=True)
        break

# === 최종 결과 ===
all_facts, quest_state, node_type, _, _ = get_run_state(run_id)
STAGES = ["S0", "S1", "S2", "S3", "S4", "S5"]
stage_idx = next((i for i, s in enumerate(STAGES) if quest_state.startswith(s)), 0)

print(f"\n{'='*50}", flush=True)
print(f"스피드런 결과", flush=True)
print(f"{'='*50}", flush=True)
print(f"총 턴: {total_turns}", flush=True)
print(f"퀘스트: {quest_state} ({stage_idx}/5단계)", flush=True)
print(f"발견 fact: {len(all_facts)}개 — {all_facts}", flush=True)
if stage_idx >= 5:
    print(f"🎉 엔딩 도달!", flush=True)
else:
    remaining_all = []
    for p in QUEST_ROUTE[max(0, stage_idx-1):]:
        remaining_all.extend([f for f in p["target_facts"] if f not in all_facts])
    print(f"남은 fact: {list(set(remaining_all))}", flush=True)
print(f"런 ID: {run_id}", flush=True)
