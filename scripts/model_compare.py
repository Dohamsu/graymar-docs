#!/usr/bin/env python3
"""
3-모델 동시 비교 스크립트
같은 프리셋, 같은 행동 시퀀스로 5턴 실행 후 서술 품질 비교
"""

import json, time, uuid, sys, requests

BASE = "http://localhost:3000/v1"
PRESET = "DESERTER"
GENDER = "male"
MAX_TURNS = 5

# 고정 행동 시퀀스 (모든 모델에 동일 적용)
FIXED_ACTIONS = [
    {"type": "CHOICE", "desc": "accept_quest"},      # T1: HUB 퀘스트 수락
    {"type": "CHOICE", "desc": "go_market"},          # T2: HUB 시장 이동
    {"type": "ACTION", "text": "주변을 살펴본다"},      # T3: LOCATION 관찰
    {"type": "ACTION", "text": "수상한 곳을 조사한다"},  # T4: LOCATION 조사
    {"type": "ACTION", "text": "사람들에게 말을 건다"},  # T5: LOCATION 대화
]

MODELS = [
    ("qwen/qwen3-32b", "Qwen3_32B"),
    ("qwen/qwen3-next-80b-a3b-instruct", "Qwen3_Next80B"),
]

def api(session, method, path, body=None):
    url = f"{BASE}{path}"
    try:
        r = session.request(method, url, json=body, timeout=90)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        print(f"  API error: {e}", flush=True)
        return 0, {}

def poll_llm(session, run_id, turn_no, max_wait=120):
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api(session, "GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            return llm.get("output") or ""
        if status in ("FAILED", "SKIPPED"):
            return f"[LLM_{status}]"
        time.sleep(2)
    return "[LLM_TIMEOUT]"

def create_session(tag):
    s = requests.Session()
    email = f"compare_{tag}_{int(time.time())}@test.com"
    status, resp = api(s, "POST", "/auth/register", {"email": email, "password": "Test1234!!", "nickname": f"Cmp_{tag}"})
    if status != 201:
        status, resp = api(s, "POST", "/auth/login", {"email": email, "password": "Test1234!!"})
    token = resp.get("token", "")
    if not token:
        print(f"Auth failed for {tag}: {resp}", flush=True)
        sys.exit(1)
    s.headers["Authorization"] = f"Bearer {token}"
    return s

def switch_model(admin_session, model_name):
    """런타임 모델 전환"""
    api(admin_session, "PATCH", "/settings/llm", {"openaiModel": model_name})
    print(f"  → 모델 전환: {model_name}", flush=True)

def find_choice(choices, keyword):
    for c in choices:
        cid = c.get("id", "")
        if keyword in cid.lower():
            return c
    return None

def run_test(session, admin_session, model_name, label):
    """단일 모델 5턴 테스트"""
    print(f"\n{'='*60}", flush=True)
    print(f"모델: {label} ({model_name})", flush=True)
    print(f"{'='*60}", flush=True)

    # 모델 전환
    switch_model(admin_session, model_name)
    time.sleep(1)

    # 런 생성
    status, resp = api(session, "POST", "/runs", {"presetId": PRESET, "gender": GENDER})
    if status not in (200, 201):
        print(f"런 생성 실패: {status} {resp}", flush=True)
        return None

    run_id = resp["run"]["id"]
    current_turn = resp["run"].get("currentTurnNo", 1)
    print(f"Run: {run_id}", flush=True)

    results = []

    for ti in range(MAX_TURNS):
        idem = str(uuid.uuid4())

        # 상태 조회
        _, state = api(session, "GET", f"/runs/{run_id}")
        if not state:
            break
        run_status = state.get("run", {}).get("status", "")
        if run_status == "RUN_ENDED":
            print(f"  [RUN_ENDED at T{ti+1}]", flush=True)
            break

        current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
        node_type = state.get("currentNode", {}).get("nodeType", "")
        choices = state.get("lastResult", {}).get("choices", [])

        action = FIXED_ACTIONS[ti]

        if action["type"] == "CHOICE":
            target = find_choice(choices, action["desc"])
            if not target:
                # accept 없으면 첫 번째, go_ 없으면 아무거나
                for c in choices:
                    if action["desc"] in c.get("id", "").lower():
                        target = c
                        break
                if not target and choices:
                    if action["desc"].startswith("go_"):
                        for c in choices:
                            if "go_" in c.get("id", "").lower():
                                target = c
                                break
                    if not target:
                        target = choices[0]

            if target:
                body = {"input": {"type": "CHOICE", "choiceId": target["id"]}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
                input_desc = f"CHOICE:{target['id']}"
            else:
                body = {"input": {"type": "ACTION", "text": "주변을 살펴본다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
                input_desc = "ACTION:fallback_observe"
        else:
            body = {"input": {"type": "ACTION", "text": action["text"]}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"ACTION:{action['text']}"

        # 턴 제출
        t_start = time.time()
        status, resp = api(session, "POST", f"/runs/{run_id}/turns", body)

        if status == 409:
            expected = resp.get("details", {}).get("expected", current_turn + 1)
            body["expectedNextTurnNo"] = expected
            body["idempotencyKey"] = str(uuid.uuid4())
            status, resp = api(session, "POST", f"/runs/{run_id}/turns", body)

        if status not in (200, 201):
            print(f"  T{ti+1}: ERROR {status}", flush=True)
            continue

        server_result = resp.get("serverResult", {})
        resolve = server_result.get("ui", {}).get("resolveOutcome", None)
        submitted_turn = resp.get("turnNo", current_turn + 1)

        # LLM 폴링
        narrative = poll_llm(session, run_id, submitted_turn)
        t_elapsed = time.time() - t_start

        results.append({
            "turn": ti + 1,
            "nodeType": node_type,
            "input": input_desc,
            "resolve": resolve,
            "narrative": narrative,
            "latency_total_s": round(t_elapsed, 1),
            "narrative_len": len(narrative) if narrative else 0,
        })

        narr_preview = (narrative[:80] + "...") if narrative and len(narrative) > 80 else narrative
        print(f"  T{ti+1:02d} [{node_type:8s}] {input_desc[:30]:30s} resolve={resolve or '-':8s} {t_elapsed:.1f}s len={len(narrative) if narrative else 0}", flush=True)

        current_turn += 1

    return {"model": model_name, "label": label, "run_id": run_id, "turns": results}


# === Main ===
print("="*60, flush=True)
print("3-모델 비교 테스트 시작", flush=True)
print(f"프리셋: {PRESET}, 성별: {GENDER}, 턴: {MAX_TURNS}", flush=True)
print("="*60, flush=True)

# 관리자 세션 (모델 전환용)
admin = create_session("admin")

# 원래 모델 기록
_, orig = api(admin, "GET", "/settings/llm")
orig_model = orig.get("openaiModel", "google/gemini-2.5-flash-lite")
print(f"원래 모델: {orig_model}", flush=True)

all_results = []
for model_name, label in MODELS:
    sess = create_session(label)
    result = run_test(sess, admin, model_name, label)
    if result:
        all_results.append(result)

# 원래 모델 복원
switch_model(admin, orig_model)
print(f"\n모델 복원: {orig_model}", flush=True)

# 결과 저장
output_path = "playtest-reports/model_compare_3way.json"
with open(output_path, "w") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print(f"\n결과 저장: {output_path}", flush=True)

# === 비교 요약 출력 ===
print("\n" + "="*60, flush=True)
print("비교 요약", flush=True)
print("="*60, flush=True)

for r in all_results:
    turns = r["turns"]
    loc_turns = [t for t in turns if t["nodeType"] == "LOCATION"]
    avg_lat = sum(t["latency_total_s"] for t in turns) / len(turns) if turns else 0
    avg_len = sum(t["narrative_len"] for t in loc_turns) / len(loc_turns) if loc_turns else 0
    print(f"\n[{r['label']}]", flush=True)
    print(f"  평균 레이턴시: {avg_lat:.1f}초", flush=True)
    print(f"  LOCATION 평균 서술 길이: {avg_len:.0f}자", flush=True)
    for t in turns:
        if t["nodeType"] == "LOCATION" and t["narrative"]:
            print(f"\n  --- T{t['turn']} ({t['resolve'] or '-'}) ---", flush=True)
            # 서술 전체 출력 (태그 제거)
            narr = t["narrative"]
            # [CHOICES]...[/CHOICES] 제거
            import re
            narr_clean = re.sub(r'\[CHOICES\].*?\[/CHOICES\]', '', narr, flags=re.DOTALL)
            narr_clean = re.sub(r'\[MEMORY[^\]]*\].*?\[/MEMORY\]', '', narr_clean, flags=re.DOTALL)
            narr_clean = re.sub(r'\[THREAD\].*?\[/THREAD\]', '', narr_clean, flags=re.DOTALL)
            narr_clean = narr_clean.strip()
            print(f"  {narr_clean[:500]}", flush=True)

print("\n=== 비교 테스트 완료 ===", flush=True)
