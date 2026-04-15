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

import json, time, uuid, random, sys, argparse, os, subprocess, re

# --- CLI 인자 ---
parser = argparse.ArgumentParser(description="Playtest runner")
parser.add_argument("--turns", type=int, default=20, help="최대 턴 수 (default: 20)")
parser.add_argument("--preset", default="DESERTER", help="프리셋 (default: DESERTER)")
parser.add_argument("--gender", default="male", help="성별 (default: male)")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
parser.add_argument("--output", default=None, help="결과 JSON 파일 경로")
parser.add_argument("--loc-turns", type=int, default=4, help="장소당 체류 턴 수 (default: 4)")
parser.add_argument("--dry-run", action="store_true", help="LLM mock 모드 + 프롬프트 추출 (비용 0원)")
parser.add_argument("--choice-rate", type=float, default=0.25, help="LOCATION에서 CHOICE 선택 확률 (default: 0.25)")
parser.add_argument("--model", default=None, help="런타임 LLM 모델 전환")
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
    """LLM 폴링: GET /turns/:turnNo → llm.status / llm.output + UI 데이터"""
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            ui = data.get("serverResult", {}).get("ui", {})
            return {
                "output": llm.get("output") or "",
                "npcPortrait": ui.get("npcPortrait"),
                "speakingNpc": ui.get("speakingNpc"),
                "newsHeadlines": ui.get("newsHeadlines"),
            }
        if status in ("FAILED", "SKIPPED"):
            return {"output": f"[LLM_{status}]"}
        time.sleep(3)
    return {"output": "[LLM_TIMEOUT]"}

# ═══════════════════════════════════════
# 0. Dry-run: LLM provider를 mock으로 전환
# ═══════════════════════════════════════
if args.dry_run:
    print("=== DRY-RUN 모드: LLM mock + 프롬프트 추출 ===", flush=True)
    # 시작 시 mock 전환, 종료 시 원래 provider 복원
    _orig_provider = None

def dry_run_setup():
    """LLM provider를 mock으로 전환"""
    global _orig_provider
    status, resp = api("GET", "/settings/llm")
    _orig_provider = resp.get("provider", "openai")
    api("PATCH", "/settings/llm", {"provider": "mock"})
    print(f"  LLM provider: {_orig_provider} → mock", flush=True)

def dry_run_teardown():
    """원래 LLM provider로 복원"""
    if _orig_provider:
        api("PATCH", "/settings/llm", {"provider": _orig_provider})
        print(f"  LLM provider 복원: mock → {_orig_provider}", flush=True)

def get_prompt(run_id, turn_no):
    """턴의 LLM 프롬프트 추출 (includeDebug)"""
    _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}?includeDebug=true")
    debug = data.get("debug", {}) or {}
    return debug.get("llmPrompt")

# ═══════════════════════════════════════
# 1. Auth
# ═══════════════════════════════════════
print(f"=== 플레이테스트 시작 ({MAX_TURNS}턴, {args.preset}, {args.gender}, choice_rate={args.choice_rate}) ===", flush=True)

# 모델 전환 (선택적)
_orig_model = None
if args.model:
    _, settings = api("GET", "/settings/llm")
    _orig_model = settings.get("openaiModel", "")
    api("PATCH", "/settings/llm", {"openaiModel": args.model})
    print(f"모델 전환: {_orig_model} → {args.model}", flush=True)

status, resp = api("POST", "/auth/register", {"email": EMAIL, "password": PASSWORD, "nickname": NICKNAME})
if status != 201:
    status, resp = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = resp.get("token", "")
if not token:
    print(f"Auth 실패: {resp}", flush=True)
    sys.exit(1)
session.headers["Authorization"] = f"Bearer {token}"
print(f"Auth: {EMAIL}", flush=True)

if args.dry_run:
    dry_run_setup()

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
        elif choices and random.random() < args.choice_rate:
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
    llm_result = poll_llm(run_id, submitted_turn)
    narrative = llm_result.get("output", "") if isinstance(llm_result, dict) else llm_result

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
        "npcPortrait": llm_result.get("npcPortrait") if isinstance(llm_result, dict) else None,
        "rawInput": body.get("input", {}).get("text", ""),
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

# V7: 프롬프트 누출 검증 (서술에 시스템 정보 노출)
print(f"\n[V7] 프롬프트 누출:", flush=True)
v7_issues = []
LEAK_PATTERNS = [
    (r"시도하여\s?(?:성공|실패)", "행동 결과 복붙"),
    (r"활성 단서:", "활성 단서 태그 노출"),
    (r"턴\s?\d+에서", "턴 번호 노출"),
    (r"플레이어가\s", "플레이어 3인칭"),
    (r"\[이번 턴", "프롬프트 블록 노출"),
    (r"\[판정:", "판정 블록 노출"),
    (r"\[상황 요약\]", "상황 요약 태그 노출"),
    (r"\[서술 규칙\]", "서술 규칙 태그 노출"),
    (r"엔진 해석:", "엔진 해석 노출"),
]
for t in turn_logs:
    narr = t.get("narrative", "")
    for pat, label in LEAK_PATTERNS:
        if re.search(pat, narr):
            v7_issues.append(f"T{t['turn']}: {label}")
if v7_issues:
    for issue in v7_issues:
        print(f"  ❌ {issue}", flush=True)
else:
    print(f"  ✅ 누출 없음", flush=True)

# V8: NPC 정합성 (소개 카드 ↔ 서술 @마커 일치)
print(f"\n[V8] NPC 정합성:", flush=True)
v8_issues = []
for t in turn_logs:
    narr = t.get("narrative", "")
    portrait = t.get("npcPortrait")
    if portrait and portrait.get("npcId"):
        portrait_id = portrait["npcId"]
        # 서술에 이 NPC의 @마커가 있는지
        markers = re.findall(r"@([A-Z][A-Z_0-9]+)\s", narr)
        bracket_markers = re.findall(r"@\[([^\]|]+)", narr)
        all_marker_names = markers + bracket_markers
        portrait_name = portrait.get("npcName", "")
        # NPC ID, 별칭(npcName), 또는 서술 본문에서 해당 NPC가 언급되었는지 확인
        # isNewlyIntroduced=true인 턴에서는 별칭→실명 전환이 일어남 → 실명도 매칭
        found = portrait_id in markers or any(portrait_name in m for m in bracket_markers)
        # 실명 매칭: 마커에 있는 이름이 portrait_name과 다르더라도 같은 NPC면 OK
        # 마커 이미지 경로에서 NPC 판별 (예: /npc-portraits/edric_veil.png → NPC_EDRIC_VEIL)
        if not found:
            portrait_img = portrait.get("imageUrl", "")
            for bm in bracket_markers:
                # @[이름|이미지] 형태에서 같은 이미지면 같은 NPC
                marker_full = re.findall(r"@\[([^\]|]+)\|([^\]]+)\]", narr)
                for mname, mimg in marker_full:
                    if portrait_img and portrait_img in mimg:
                        found = True
                        break
                if found:
                    break
        # 서술 본문에서 NPC 이름/별칭이 직접 언급되었는지도 확인
        if not found and portrait_name:
            found = portrait_name in narr
        if not found and narr and not narr.startswith("[LLM_"):
            v8_issues.append(f"T{t['turn']}: 카드={portrait_name}({portrait_id}) 서술에 없음")
    # @마커 NPC가 서술 문맥과 불일치 (화자 이름 ≠ 마커 이름)
    marker_matches = list(re.finditer(r'@\[([^\]|]+)(?:\|[^\]]+)?\]\s*["\u201C\u201D]', narr))
    for mm in marker_matches:
        marker_name = mm.group(1).strip()
        before = narr[max(0, mm.start() - 80):mm.start()]
        # "XX가 말했다" 패턴에서 XX ≠ marker_name이면 불일치
        speaker_match = re.search(r"([가-힣]{2,10})[이가은는]\s*(?:말|물|외|중얼|속삭|답|대답|되물)", before)
        if speaker_match:
            speaker = speaker_match.group(1)
            # 플레이어 지칭은 화자 후보에서 제외 (NPC 대사 앞에 "당신이 말을 걸자" 등)
            player_refs = {"당신", "그대", "용병", "자네", "이방인", "나그네", "손님", "낯선"}
            if speaker in player_refs:
                continue
            if speaker not in marker_name and marker_name not in speaker:
                v8_issues.append(f"T{t['turn']}: 화자={speaker} ≠ 마커={marker_name}")
if v8_issues:
    for issue in v8_issues[:5]:
        print(f"  ❌ {issue}", flush=True)
    if len(v8_issues) > 5:
        print(f"  ... 외 {len(v8_issues)-5}건", flush=True)
else:
    print(f"  ✅ 정합성 양호", flush=True)

# V9: 서술 품질 (반복/하오체 미마킹 + sanitize 오탐 + CHOICE 대화 맥락)
print(f"\n[V9] 서술 품질:", flush=True)
v9_issues = []

# V9-a: sanitize 오탐 검출 — 비정상적 NPC 별칭 치환 감지
for t in turn_logs:
    narr = t.get("narrative", "")
    # NPC unknownAlias가 일반 단어 속에 끼어있는 패턴 (예: "허덩치 큰 하역 인부지")
    suspicious_patterns = [
        (r"허.{5,15}지", "NPC alias 오삽입"),   # 허벅지 → 허+alias+지
        (r"[가-힣]덩치 큰 하역", "BG_DOCKER alias 오삽입"),
    ]
    for pat, desc in suspicious_patterns:
        if re.search(pat, narr):
            v9_issues.append(f"T{t['turn']}: sanitize 오탐 — {desc}")

# V9-b: CHOICE 턴에서 이전 대화 맥락 가정 감지
for t in turn_logs:
    narr = t.get("narrative", "")
    inp = t.get("input", "")
    if inp.startswith("CHOICE:") and t.get("nodeType") == "LOCATION":
        # "그대의 말대로", "그대가 말한", "이전에 대화한" 등 대화 전제 표현
        choice_dialog_refs = ["말대로라면", "말한 대로", "아까 말한", "이전에 대화한", "앞서 언급한"]
        for ref in choice_dialog_refs:
            if ref in narr:
                v9_issues.append(f"T{t['turn']}: CHOICE 턴 대화 맥락 가정 — '{ref}'")

# V9-c: dialogue_slot speaker_id 매칭 실패 감지 — @[무명 인물] fallback 사용
for t in turn_logs:
    narr = t.get("narrative", "")
    if "@[무명 인물]" in narr:
        v9_issues.append(f"T{t['turn']}: dialogue_slot fallback 대사 — @[무명 인물] (NPC_ID 매칭 실패)")

# 단어 반복 검출 (3턴 윈도우에서 같은 2글자+ 단어가 5회+)
for i in range(2, len(turn_logs)):
    window_narrs = [turn_logs[j].get("narrative", "") for j in range(max(0, i-2), i+1)]
    combined = " ".join(window_narrs)
    # @마커 내부 텍스트 제거 (NPC 별칭이 마커로 반복 카운트되는 것 방지)
    combined = re.sub(r"@\[[^\]]+\]", "", combined)
    words = re.findall(r"[가-힣]{2,4}", combined)
    from collections import Counter
    word_counts = Counter(words)
    # 일반 조사/어미 제외
    COMMON_WORDS = {"당신", "당신은", "당신의", "당신이", "당신을", "그는", "그의", "있다", "없다", "있었", "하고", "에서", "으로", "이다", "했다", "하는", "것이", "있는", "위에", "앞에", "속에", "조용한", "낡은", "어두운", "시장", "경비", "경비대", "항만", "부두", "선술집", "골목", "창고"}
    for word, cnt in word_counts.most_common(3):
        if cnt >= 5 and word not in COMMON_WORDS and len(word) >= 2:
            v9_issues.append(f"T{turn_logs[i]['turn']}: '{word}' {cnt}회 반복 (3턴 내)")
            break
# NPC 대사 미마킹 (따옴표 없는 NPC 어체 문장에 @마커 없음)
# 다양한 어체 지원: 하오체(~소/~오), 해요체(~요), 합쇼체(~다/~까), 반말(~야/~해), 해체(~지/~거든)
for t in turn_logs:
    narr = t.get("narrative", "")
    for line in narr.split("\n"):
        s = line.strip()
        # 하오체 미마킹만 체크 (다른 어체는 서술과 구분 어려움)
        if len(s) >= 10 and re.search(r"(?:하오|이오|시오|겠소|없소)[.!?]$", s) and "@[" not in line and not re.match(r"^(?:당신|그는|그녀)", s):
            v9_issues.append(f"T{t['turn']}: 대사 미마킹 — {s[:30]}")
if v9_issues:
    for issue in v9_issues[:5]:
        print(f"  ⚠️ {issue}", flush=True)
    if len(v9_issues) > 5:
        print(f"  ... 외 {len(v9_issues)-5}건", flush=True)
else:
    print(f"  ✅ 품질 양호", flush=True)

# Summary
print("\n" + "=" * 60, flush=True)
all_checks = {
    "V1_incidents": len(incidents) > 0,
    "V2_encounter": enc_pass >= 2,
    "V3_posture": len(posture_none) == 0,
    "V4_emotion": emo_active > 0,
    "V5_memory": structured is not None and len((structured or {}).get("visitLog", [])) > 0,
    "V6_resolve": resolve_count > 0,
    "V7_no_leak": len(v7_issues) == 0,
    "V8_npc_match": len(v8_issues) == 0,
    "V9_quality": len([i for i in v9_issues if "반복" in i]) <= 2,
}
passed = sum(1 for v in all_checks.values() if v)
print(f"종합: {passed}/{len(all_checks)} PASS", flush=True)
for k, v in all_checks.items():
    print(f"  {'✅' if v else '❌'} {k}", flush=True)

# ═══════════════════════════════════════
# 5. Git Version Tagging
# ═══════════════════════════════════════
def git_info(repo_dir):
    """서버 레포의 git 정보 수집"""
    try:
        git_hash = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        git_branch = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        git_message = subprocess.check_output(
            ["git", "-C", repo_dir, "log", "-1", "--format=%s"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return {"hash": git_hash, "branch": git_branch, "message": git_message}
    except Exception:
        return {"hash": None, "branch": None, "message": None}

server_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server")
git = git_info(server_dir)

# 서술 분석 메트릭 계산
all_narratives = [t.get("narrative", "") for t in turn_logs if t.get("narrative")]
all_dialogues = []
meta_phrases = ["아시다시피", "이전에 말씀", "말한 바와 같이", "앞서 말씀"]
exit_kw = ["멀어지", "떠나려", "사라지", "등을 돌", "가려는", "자리를 뜨"]
reapproach_kw = ["다시 다가", "다시 찾아", "다시 접근"]

meta_count = 0
exit_count = 0
reapproach_count = 0
halmi_contamination = 0

for narr in all_narratives:
    dialogues = re.findall(r'"([^"]+)"', narr)
    all_dialogues.extend(dialogues)
    for d in dialogues:
        for mp in meta_phrases:
            if mp in d:
                meta_count += 1
    for kw in exit_kw:
        if kw in narr:
            exit_count += 1
    for kw in reapproach_kw:
        if kw in narr:
            reapproach_count += 1
    if "이 할미" in narr and "미렐라" not in narr and "약초" not in narr:
        halmi_contamination += 1

hao_count = sum(1 for d in all_dialogues if any(x in d for x in ["하오", "겠소", "이오", "않소", "있소"]))
narr_lens = [len(n) for n in all_narratives] if all_narratives else [0]

narrative_metrics = {
    "totalNarratives": len(all_narratives),
    "totalChars": sum(narr_lens),
    "avgCharsPerTurn": sum(narr_lens) / len(narr_lens) if narr_lens else 0,
    "minChars": min(narr_lens) if narr_lens else 0,
    "maxChars": max(narr_lens) if narr_lens else 0,
    "totalDialogues": len(all_dialogues),
    "haoSoRatio": hao_count / len(all_dialogues) if all_dialogues else 0,
    "metaExpressionCount": meta_count,
    "speechContamination": halmi_contamination,
    "exitKeywordCount": exit_count,
    "reapproachCount": reapproach_count,
}

# 판정 분포
outcomes = [t["resolveOutcome"] for t in turn_logs if t.get("resolveOutcome")]
from collections import Counter
oc = Counter(outcomes)
outcome_distribution = {
    "success": oc.get("SUCCESS", 0),
    "partial": oc.get("PARTIAL", 0),
    "fail": oc.get("FAIL", 0),
    "total": len(outcomes),
}

# discoveredQuestFacts
discovered_facts = run_state.get("discoveredQuestFacts", [])

# NPC 만남 수
npc_met = sum(1 for n in npc_states.values() if n.get("encounterCount", 0) > 0)

# ═══════════════════════════════════════
# 6. Save Output (JSON + DB)
# ═══════════════════════════════════════
output = {
    "meta": {
        "preset": args.preset,
        "gender": args.gender,
        "maxTurns": MAX_TURNS,
        "actualTurns": len(turn_logs),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git": git,
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
        "discoveredQuestFacts": discovered_facts,
    },
    "verification": all_checks,
    "narrativeMetrics": narrative_metrics,
    "outcomeDistribution": outcome_distribution,
}

output_path = args.output
if not output_path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"playtest-reports/playtest_{ts}.json"

os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
with open(output_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n로그 저장: {output_path}", flush=True)

# DB 저장 (PostgreSQL 직접 연결)
try:
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # .env에서 읽기
        env_path = os.path.join(server_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path) as ef:
                for line in ef:
                    if line.startswith("DATABASE_URL="):
                        db_url = line.strip().split("=", 1)[1]
                        break

    if db_url:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO playtest_results (
                run_id, git_hash, git_branch, git_message, server_version,
                preset, gender, max_turns, actual_turns, loc_turns,
                verification, pass_count,
                final_hp, final_gold, npc_met_count, incident_count, discovered_fact_count,
                outcome_distribution, narrative_metrics, raw_data, note
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            run_id, git.get("hash"), git.get("branch"), git.get("message"), "0.0.1",
            args.preset, args.gender, MAX_TURNS, len(turn_logs), args.loc_turns,
            json.dumps(all_checks), passed,
            run_state.get("hp"), run_state.get("gold"), npc_met, len(incidents), len(discovered_facts),
            json.dumps(outcome_distribution), json.dumps(narrative_metrics), json.dumps(output), None,
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB 저장 완료 (playtest_results)", flush=True)
    else:
        print(f"DB 저장 스킵 (DATABASE_URL 없음)", flush=True)
except ImportError:
    print(f"DB 저장 스킵 (psycopg2 미설치 — pip install psycopg2-binary)", flush=True)
except Exception as e:
    print(f"DB 저장 실패: {e}", flush=True)

# ═══════════════════════════════════════
# Dry-run: 프롬프트 추출 + 복원
# ═══════════════════════════════════════
if args.dry_run:
    print("\n" + "=" * 60, flush=True)
    print("DRY-RUN: LLM 프롬프트 추출", flush=True)
    print("=" * 60, flush=True)

    prompts = {}
    for log in turn_logs:
        tn = log.get("turn", 0)
        prompt = get_prompt(run_id, tn)
        if prompt:
            prompts[tn] = prompt
            # system 메시지의 길이만 요약
            for i, msg in enumerate(prompt):
                role = msg.get("role", "?") if isinstance(msg, dict) else "?"
                content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                content_len = len(content) if isinstance(content, str) else len(json.dumps(content))
                print(f"  T{tn:02d} [{role:9s}] {content_len:5d}자", flush=True)
            print(flush=True)

    # 프롬프트 전문 저장
    prompt_file = (args.output or "playtest_dryrun.json").replace(".json", "_prompts.json")
    with open(prompt_file, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"\n프롬프트 저장: {prompt_file}", flush=True)

    dry_run_teardown()

# 모델 복원
if _orig_model and args.model:
    api("PATCH", "/settings/llm", {"openaiModel": _orig_model})
    print(f"모델 복원: {args.model} → {_orig_model}", flush=True)

print(f"=== 플레이테스트 완료 ===", flush=True)
