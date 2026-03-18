#!/usr/bin/env python3
"""Context Coherence Reinforcement 통합 런 테스트 (20턴)"""

import json
import time
import random
import requests

BASE = "http://localhost:3000/v1"
LOG_FILE = "/Users/dohamsu/Workspace/mdfile/playtest-log.json"

def main():
    rand_suffix = random.randint(1000, 99999)

    # 1. 회원가입
    print("=== 1. Auth ===")
    reg = requests.post(f"{BASE}/auth/register", json={
        "email": f"ccr_test_{rand_suffix}@test.com",
        "password": "test1234",
        "nickname": "CCR테스터"
    }).json()
    token = reg.get("token")
    if not token:
        print(f"Auth failed: {reg}")
        return
    print(f"Token: {token[:20]}...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2. RUN 생성
    print("=== 2. Create RUN ===")
    run_resp = requests.post(f"{BASE}/runs", json={"presetId": "DESERTER", "gender": "male"}, headers=headers).json()
    run_id = run_resp.get("run", {}).get("id") or run_resp.get("runId")
    if not run_id:
        print(f"Run creation failed: {run_resp}")
        return
    print(f"RunID: {run_id}")

    # 초기 상태에서 선택지 확인
    last_result = run_resp.get("lastResult", {})
    available_choices = last_result.get("choices", [])
    current_node = run_resp.get("currentNode", {})
    node_type = current_node.get("nodeType", "")
    print(f"Initial node: {node_type}, choices: {[c.get('id') for c in available_choices]}")

    turn_idx = 1  # expectedNextTurnNo starts at 1
    turns_log = []

    def submit(input_type, text=None, choice_id=None):
        nonlocal turn_idx, available_choices, node_type
        idem_key = f"ccr_{run_id}_{turn_idx}_{int(time.time()*1000)}"

        body = {"expectedNextTurnNo": turn_idx, "idempotencyKey": idem_key}
        if input_type == "ACTION":
            body["input"] = {"type": "ACTION", "text": text}
        else:
            body["input"] = {"type": "CHOICE", "choiceId": choice_id}

        resp = requests.post(f"{BASE}/runs/{run_id}/turns", json=body, headers=headers).json()

        accepted = resp.get("accepted", False)
        if not accepted:
            msg = resp.get("message") or resp.get("error") or resp.get("code") or "unknown"
            details = resp.get("details", {})
            print(f"  Turn {turn_idx} REJECTED: {msg} {details}")
            # TURN_NO_MISMATCH → 서버의 expected로 동기화
            code = resp.get("code", "")
            if code == "TURN_NO_MISMATCH" and "expected" in details:
                turn_idx = details["expected"]
                print(f"    → turn_idx synced to {turn_idx}")
            return "rejected"

        turn_no = resp.get("turnNo", 0)
        sr = resp.get("serverResult") or {}
        resolve = sr.get("ui", {}).get("resolveOutcome", "N/A")
        llm_obj = resp.get("llm") or {}
        llm_status = llm_obj.get("status", "N/A")
        meta = resp.get("meta") or {}
        node_outcome = meta.get("nodeOutcome", "N/A")
        node_type = meta.get("nodeType", node_type)

        # 선택지 갱신
        available_choices = sr.get("choices", [])

        print(f"  Turn {turn_no}: type={node_type} resolve={resolve} llm={llm_status} outcome={node_outcome}")

        # LLM 폴링 (최대 60초)
        narrative = ""
        llm_choices = []
        if llm_status in ("PENDING", "RUNNING"):
            for _ in range(30):
                time.sleep(2)
                try:
                    poll = requests.get(f"{BASE}/runs/{run_id}/turns/{turn_no}", headers=headers).json()
                    poll_llm = poll.get("llm") or {}
                    poll_status = poll_llm.get("status", "")
                    if poll_status == "DONE":
                        narrative = poll_llm.get("output") or poll_llm.get("narrative") or ""
                        llm_choices = poll_llm.get("choices") or []
                        llm_status = "DONE"
                        if narrative:
                            print(f"    LLM: {narrative[:80]}...")
                        # 선택지 갱신 (LLM 선택지 포함)
                        if llm_choices:
                            available_choices = llm_choices
                        break
                    elif poll_status == "FAILED":
                        llm_status = "FAILED"
                        break
                except Exception:
                    pass

        events = sr.get("events", [])
        summary_short = (sr.get("summary") or {}).get("short", "")

        turns_log.append({
            "turnNo": turn_no,
            "inputType": input_type,
            "inputText": text or "",
            "choiceId": choice_id or "",
            "resolveOutcome": resolve,
            "llmStatus": llm_status,
            "narrative": (narrative or "")[:500],
            "summary": summary_short,
            "choices": available_choices,
            "llmChoices": llm_choices,
            "events": events,
            "nodeOutcome": node_outcome,
            "nodeType": node_type,
        })

        turn_idx += 1

        if node_outcome == "RUN_ENDED":
            print(f"  *** RUN ENDED at turn {turn_no} ***")
            return "ended"

        # NODE_ENDED → 새 노드 전이 발생, RUN 상태 재조회하여 동기화
        if node_outcome == "NODE_ENDED":
            time.sleep(1)
            try:
                run_check = requests.get(f"{BASE}/runs/{run_id}", headers=headers).json()
                cn = run_check.get("currentNode") or {}
                node_type = cn.get("nodeType", node_type)
                lr = run_check.get("lastResult") or {}
                available_choices = lr.get("choices", [])
                # currentTurnNo + 1 = expectedNextTurnNo
                ct = run_check.get("run", {}).get("currentTurnNo") or run_check.get("currentTurnNo")
                if ct is not None:
                    turn_idx = ct + 1
                print(f"    → Node transition: {node_type}, choices={[c.get('id') for c in available_choices]}, nextTurn={turn_idx}")
            except Exception as e:
                print(f"    → Run state refresh failed: {e}")

        return "ok"

    # === 턴 시퀀스 ===
    print("=== 3. 턴 시퀀스 시작 ===")

    # HUB 단계: CHOICE로 시작
    if node_type == "HUB" and available_choices:
        choice_id = available_choices[0].get("id")
        print(f"  [HUB] Selecting choice: {choice_id}")
        result = submit("CHOICE", choice_id=choice_id)
        if result == "ended":
            pass  # continue to logging
        time.sleep(0.5)

    # 현재 node_type 확인 — HUB면 한번 더 CHOICE
    for _ in range(5):  # HUB를 벗어날 때까지 최대 5번
        if node_type != "HUB":
            break
        if available_choices:
            # LOCATION 선택지 우선
            loc_choices = [c for c in available_choices if "LOC" in (c.get("id") or "").upper() or "시장" in (c.get("label") or "") or "거리" in (c.get("label") or "")]
            choice = loc_choices[0] if loc_choices else available_choices[0]
            choice_id = choice.get("id")
            print(f"  [HUB] Selecting: {choice_id} ({choice.get('label', '')})")
            result = submit("CHOICE", choice_id=choice_id)
            if result == "ended":
                break
            time.sleep(0.5)
        else:
            print("  [HUB] No choices available, trying ACTION")
            result = submit("ACTION", text="주변을 둘러본다")
            time.sleep(0.5)

    # LOCATION 턴들 (ACTION 기반)
    location_actions = [
        "상인에게 말을 건다",
        "그 상인에게 밀수에 대해 더 캔다",
        "장부를 보여달라고 설득한다",
        "주변 사람들에게 소문을 묻는다",
        "항만 부두로 이동한다",
        "부두에서 수상한 활동을 관찰한다",
        "부두 노동자에게 밀수 경로를 묻는다",
        "선원에게 위협하며 정보를 캔다",
        "경비대 지구로 이동한다",
        "경비대 주변을 조사한다",
        "경비병에게 최근 사건을 묻는다",
        "빈민가로 이동한다",
        "어두운 골목을 몰래 조사한다",
        "노숙자에게 뒷골목 소문을 묻는다",
        "시장 거리로 돌아간다",
        "이전에 만난 상인을 다시 찾는다",
        "상인에게 장부 건을 다시 물어본다",
        "주변을 더 살핀다",
        "거점으로 돌아간다",
    ]

    for action_text in location_actions:
        if len(turns_log) >= 21:
            break

        # CHOICE 필요 시 (HUB 복귀 등) 자동 처리
        if node_type == "HUB":
            if available_choices:
                # 이동 관련 선택지 찾기
                move_choices = [c for c in available_choices
                    if any(kw in (c.get("label") or "").lower() for kw in ["시장", "항만", "부두", "경비", "빈민", "거리", "이동"])
                    or "LOC" in (c.get("id") or "").upper()]
                choice = move_choices[0] if move_choices else available_choices[0]
                print(f"  [HUB→LOCATION] Selecting: {choice.get('id')} ({choice.get('label', '')})")
                result = submit("CHOICE", choice_id=choice.get("id"))
                if result == "ended":
                    break
                time.sleep(0.5)
                continue
            else:
                result = submit("ACTION", text=action_text)
                if result == "ended":
                    break
                time.sleep(0.5)
                continue

        # LOCATION에서 ACTION
        result = submit("ACTION", text=action_text)
        if result == "ended":
            break
        # CHOICE 응답이 왔는데 ACTION 못하는 경우 CHOICE 자동 처리
        if result == "rejected" and available_choices:
            choice = available_choices[0]
            print(f"  [Auto-CHOICE] {choice.get('id')} ({choice.get('label', '')})")
            result = submit("CHOICE", choice_id=choice.get("id"))
            if result == "ended":
                break
        time.sleep(0.5)

    # 4. RUN 상태 조회
    print(f"\n=== 4. RUN 상태 (총 {len(turns_log)}턴 완료) ===")
    run_state_raw = requests.get(f"{BASE}/runs/{run_id}", headers=headers)
    run_state_resp = json.loads(run_state_raw.text, strict=False) if run_state_raw.text else {}
    # runState는 여러 경로에 있을 수 있음
    rs = run_state_resp.get("runState") or run_state_resp.get("run", {}).get("runState") or {}
    status = run_state_resp.get("status") or run_state_resp.get("run", {}).get("status", "N/A")
    # Debug: top-level keys and runState location
    print(f"Response keys: {list(run_state_resp.keys())[:15]}")
    if "run" in run_state_resp:
        print(f"run keys: {list(run_state_resp['run'].keys())[:15]}")
    # Also check memory
    mem = run_state_resp.get("memory") or {}
    print(f"memory keys: {list(mem.keys())[:15]}")
    print(f"Status: {status}")
    print(f"HP: {rs.get('hp', 'N/A')}")
    print(f"Gold: {rs.get('gold', 'N/A')}")
    print(f"RunState keys: {list(rs.keys())[:15]}")

    # actionHistory 마지막 5개
    print("\n=== 5. actionHistory (마지막 5개) ===")
    ah = rs.get("actionHistory", [])
    for entry in ah[-5:]:
        print(f"  {json.dumps(entry, ensure_ascii=False)[:200]}")
    if not ah:
        print("  (empty)")

    # structuredMemory
    print("\n=== 6. structuredMemory 스냅샷 ===")
    ws = rs.get("worldState") or {}
    print(f"WorldState heat={ws.get('hubHeat', 0)}, safety={ws.get('hubSafety', 'N/A')}")

    sm = rs.get("structuredMemory") or {}
    print(f"visitLog entries: {len(sm.get('visitLog', []))}")
    print(f"npcJournal entries: {len(sm.get('npcJournal', []))}")
    print(f"llmExtracted entries: {len(sm.get('llmExtracted', []))}")
    print(f"npcKnowledge keys: {list((sm.get('npcKnowledge') or {}).keys())}")
    print(f"milestones: {len(sm.get('milestones', []))}")
    if sm.get('visitLog'):
        print(f"  visitLog sample: {json.dumps(sm['visitLog'][-1], ensure_ascii=False)[:200]}")
    if sm.get('npcKnowledge'):
        for npc_id, entries in (sm.get('npcKnowledge') or {}).items():
            print(f"  npcKnowledge[{npc_id}]: {len(entries)} entries")
            for e in entries[:2]:
                print(f"    - {e.get('text','')[:60]}")

    # 로그 저장
    log_data = {
        "turns": turns_log,
        "runState": {
            "status": run_state_resp.get("status"),
            "hp": rs.get("hp"),
            "gold": rs.get("gold"),
            "actionHistory": ah,
            "worldState": ws,
            "structuredMemory": sm,
        },
        "runId": run_id,
    }
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"\n=== 완료 ===")
    print(f"로그 파일: {LOG_FILE}")
    print(f"RunID: {run_id}")

if __name__ == "__main__":
    main()
