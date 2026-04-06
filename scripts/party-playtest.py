#!/usr/bin/env python3
"""
파티 런 플레이테스트 — 2계정으로 10턴 실제 플레이

파티 생성 → 가입 → 준비 → 던전 시작 → HUB 선택 → LOCATION 탐험 10턴
각 턴마다 A, B 독립 행동 제출 → 통합 결과 확인
"""

import json, time, uuid, random, sys, argparse

parser = argparse.ArgumentParser(description="Party playtest — 2 players, 10 turns")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
parser.add_argument("--turns", type=int, default=10, help="턴 수 (default: 10)")
parser.add_argument("--output", default="playtest-reports/party_playtest_result.json", help="결과 파일")
args = parser.parse_args()

BASE = args.base
MAX_TURNS = args.turns
PASSWORD = "Test1234!!"

try:
    import requests
except ImportError:
    print("pip install requests", flush=True)
    sys.exit(1)

# ── Actions pool ──
LOCATION_ACTIONS = [
    "주변을 살펴본다",
    "수상한 곳을 조사한다",
    "사람들에게 말을 건다",
    "조심스럽게 잠입한다",
    "거래를 시도한다",
    "도움을 준다",
    "경비병의 동태를 살핀다",
    "골목길을 탐색한다",
    "소문의 진위를 확인한다",
    "상인에게 뇌물을 건넨다",
    "설득한다",
    "위협한다",
]

LOCATIONS = ["go_market", "go_guard", "go_harbor", "go_slums"]
LOCATION_NAMES = {
    "go_market": "시장",
    "go_guard": "경비대",
    "go_harbor": "항구",
    "go_slums": "빈민가",
}


class Player:
    def __init__(self, name, preset, gender="male"):
        self.name = name
        self.preset = preset
        self.gender = gender
        self.session = requests.Session()
        self.token = ""
        self.user_id = ""
        safe_name = name.encode('ascii', 'ignore').decode() or f"player{random.randint(100,999)}"
        self.email = f"party_play_{safe_name}_{int(time.time())}_{random.randint(100,999)}@test.com"
        self.nickname = name

    def api(self, method, path, body=None, timeout=30):
        url = f"{BASE}{path}"
        try:
            headers = {"Content-Type": "application/json"}
            r = self.session.request(method, url, json=body, headers=headers, timeout=timeout)
            data = r.json() if r.text else {}
            return r.status_code, data
        except Exception as e:
            print(f"  [{self.name}] API error: {e}", flush=True)
            return 0, {}

    def register(self):
        s, r = self.api("POST", "/auth/register", {
            "email": self.email,
            "password": PASSWORD,
            "nickname": self.nickname,
        })
        if s == 201:
            self.token = r.get("token", "")
            self.user_id = r.get("user", {}).get("id", "")
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            return True
        print(f"  [{self.name}] 등록 실패: status={s} resp={r}", flush=True)
        return False


def poll_llm(player, run_id, turn_no, max_wait=90):
    """LLM 서술 완성 대기"""
    start = time.time()
    while time.time() - start < max_wait:
        _, data = player.api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            return llm.get("output", "")
        if status in ("FAILED", "SKIPPED"):
            return f"[LLM_{status}]"
        time.sleep(3)
    return "[LLM_TIMEOUT]"


# ═══════════════════════════════════════
print("=" * 60, flush=True)
print("  파티 런 플레이테스트 — 2인 협동 던전", flush=True)
print("=" * 60, flush=True)

# ── 0. 등록 ──
print("\n[0] 유저 등록", flush=True)
player_a = Player("용병대장", "DESERTER")
player_b = Player("약초사", "HERBALIST")

assert player_a.register(), "A 등록 실패"
assert player_b.register(), "B 등록 실패"
print(f"  A: {player_a.nickname} ({player_a.user_id[:8]}...)", flush=True)
print(f"  B: {player_b.nickname} ({player_b.user_id[:8]}...)", flush=True)

# ── 1. 파티 생성 + 가입 ──
print("\n[1] 파티 생성 + 가입", flush=True)
s, r = player_a.api("POST", "/parties", {"name": "그레이마르 용병단"})
assert s == 201, f"파티 생성 실패: {s}"
party_id = r["id"]
invite_code = r["inviteCode"]
print(f"  파티: {r['name']} (코드: {invite_code})", flush=True)

s, r = player_b.api("POST", "/parties/join", {"inviteCode": invite_code})
assert s == 200, f"가입 실패: {s} {r}"
print(f"  {player_b.nickname} 가입 완료 — 멤버 {r['memberCount']}명", flush=True)

# ── 2. 로비 준비 ──
print("\n[2] 로비 준비", flush=True)
player_a.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
s, r = player_b.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
print(f"  allReady={r.get('allReady')} canStart={r.get('canStart')}", flush=True)

# ── 3. 던전 시작 ──
print("\n[3] 던전 시작", flush=True)
s, r = player_a.api("POST", f"/parties/{party_id}/lobby/start")
assert s == 200, f"던전 시작 실패: {s} {r}"
run_id = r["runId"]
print(f"  runId={run_id[:12]}...", flush=True)

# ── 4. 솔로 런 플로우를 따라감 (A 계정으로) ──
# 현재 run 상태 확인
s, run_data = player_a.api("GET", f"/runs/{run_id}?turnsLimit=5")
if s != 200:
    print(f"  런 조회 실패: {s}", flush=True)
    sys.exit(1)

run_info = run_data.get("run", {})
current_turn_no = run_info.get("currentTurnNo", 0)
current_node_type = None

# lastResult에서 현재 상태 파악
last_result = run_data.get("lastResult", {})
if last_result:
    current_node_type = last_result.get("node", {}).get("type", "HUB")
    choices = last_result.get("choices", [])
    print(f"  현재 노드: {current_node_type} / 턴: {current_turn_no}", flush=True)
    if choices:
        print(f"  선택지: {[c.get('label','') for c in choices[:5]]}", flush=True)

# ── 5. 턴 루프 ──
turn_log = []
location_turns = 0
current_location = None

print(f"\n{'=' * 60}", flush=True)
print(f"  턴 루프 시작 ({MAX_TURNS}턴)", flush=True)
print(f"{'=' * 60}", flush=True)

for turn_idx in range(MAX_TURNS):
    turn_no = current_turn_no + 1
    print(f"\n── 턴 {turn_no} ──", flush=True)

    # 현재 상태 다시 확인
    s, run_data = player_a.api("GET", f"/runs/{run_id}?turnsLimit=1")
    if s != 200:
        print(f"  런 조회 실패: {s}", flush=True)
        break

    run_info = run_data.get("run", {})
    current_turn_no = run_info.get("currentTurnNo", turn_no - 1)
    turn_no = current_turn_no + 1

    last_result = run_data.get("lastResult", {})
    current_node_type = last_result.get("node", {}).get("type", "HUB") if last_result else "HUB"
    choices = last_result.get("choices", []) if last_result else []
    run_status = run_info.get("status", "RUN_ACTIVE")

    if run_status != "RUN_ACTIVE":
        print(f"  런 종료: {run_status}", flush=True)
        break

    print(f"  노드: {current_node_type} | 선택지: {len(choices)}개", flush=True)

    # ── HUB: 장소 선택 (솔로 턴 — A만 제출) ──
    if current_node_type == "HUB":
        loc = random.choice(LOCATIONS)
        print(f"  → HUB 이동: {LOCATION_NAMES.get(loc, loc)}", flush=True)

        s, resp = player_a.api("POST", f"/runs/{run_id}/turns", {
            "input": {"type": "CHOICE", "choiceId": loc},
            "expectedNextTurnNo": turn_no,
            "idempotencyKey": str(uuid.uuid4()),
        })
        if s != 200 and s != 201:
            print(f"  ⚠️ HUB 턴 실패: {s} {json.dumps(resp, ensure_ascii=False)[:200]}", flush=True)
            break

        current_location = loc
        location_turns = 0

        # LLM 폴링
        narrative = poll_llm(player_a, run_id, turn_no)
        print(f"  📖 {narrative[:100]}..." if len(narrative) > 100 else f"  📖 {narrative}", flush=True)

        turn_log.append({
            "turn": turn_no,
            "node": "HUB",
            "action_a": f"CHOICE:{loc}",
            "action_b": "-",
            "narrative": narrative[:200],
        })

        current_turn_no = turn_no
        continue

    # ── LOCATION: 2인 동시 행동 (파티 턴) ──
    if current_node_type == "LOCATION":
        action_a = random.choice(LOCATION_ACTIONS)
        action_b = random.choice(LOCATION_ACTIONS)

        print(f"  A: \"{action_a}\"", flush=True)
        print(f"  B: \"{action_b}\"", flush=True)

        # 먼저 파티 턴 API로 행동 제출
        s1, r1 = player_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "ACTION",
            "rawInput": action_a,
            "idempotencyKey": str(uuid.uuid4()),
        })
        print(f"  A 제출: {s1} accepted={r1.get('accepted')}", flush=True)

        s2, r2 = player_b.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "ACTION",
            "rawInput": action_b,
            "idempotencyKey": str(uuid.uuid4()),
        })
        print(f"  B 제출: {s2} accepted={r2.get('accepted')} allSubmitted={r2.get('allSubmitted')}", flush=True)

        # resolveTurn이 비동기로 솔로 턴을 자동 제출하므로 대기
        time.sleep(3)

        # LLM 폴링 (resolveTurn이 생성한 턴)
        narrative = poll_llm(player_a, run_id, turn_no)
        snippet = narrative[:150] if len(narrative) > 150 else narrative
        print(f"  📖 {snippet}...", flush=True)

        # 턴 결과 조회
        _, turn_data = player_a.api("GET", f"/runs/{run_id}/turns/{turn_no}")
        sr = turn_data.get("serverResult", {}) or {}
        events = sr.get("events", []) or []
        if events:
            print(f"  🎲 이벤트: {[e.get('text','')[:30] for e in events[:3]]}", flush=True)

        location_turns += 1
        turn_log.append({
            "turn": turn_no,
            "node": "LOCATION",
            "action_a": action_a,
            "action_b": action_b,
            "narrative": narrative[:300],
            "events": [e.get("text", "") for e in events[:3]],
        })

        current_turn_no = turn_no

        # 4턴 후 HUB 복귀 (go_hub 선택)
        if location_turns >= 4:
            print(f"  → 4턴 경과, HUB 복귀 시도", flush=True)
            hub_turn = current_turn_no + 1

            # 선택지에서 go_hub 찾기
            s, rd = player_a.api("GET", f"/runs/{run_id}?turnsLimit=1")
            lr = rd.get("lastResult", {}) if s == 200 else {}
            ch = lr.get("choices", [])
            hub_choice = None
            for c in ch:
                cid = c.get("id", c.get("choiceId", ""))
                if "hub" in cid.lower() or "돌아" in c.get("label", ""):
                    hub_choice = cid
                    break

            if hub_choice:
                s, resp = player_a.api("POST", f"/runs/{run_id}/turns", {
                    "input": {"type": "CHOICE", "choiceId": hub_choice},
                    "expectedNextTurnNo": hub_turn,
                    "idempotencyKey": str(uuid.uuid4()),
                })
                if s == 200 or s == 201:
                    print(f"  → HUB 복귀 성공", flush=True)
                    current_turn_no = hub_turn
                    location_turns = 0
                else:
                    print(f"  → HUB 복귀 실패: {s}", flush=True)
            else:
                print(f"  → go_hub 선택지 없음, 계속 진행", flush=True)

        continue

    # ── COMBAT 등 기타 노드 ──
    if choices:
        choice = random.choice(choices)
        cid = choice.get("id", choice.get("choiceId", ""))
        print(f"  → 선택: {choice.get('label', cid)}", flush=True)

        s, resp = player_a.api("POST", f"/runs/{run_id}/turns", {
            "input": {"type": "CHOICE", "choiceId": cid},
            "expectedNextTurnNo": turn_no,
            "idempotencyKey": str(uuid.uuid4()),
        })
    else:
        action = random.choice(LOCATION_ACTIONS)
        print(f"  → 행동: {action}", flush=True)

        s, resp = player_a.api("POST", f"/runs/{run_id}/turns", {
            "input": {"type": "ACTION", "text": action},
            "expectedNextTurnNo": turn_no,
            "idempotencyKey": str(uuid.uuid4()),
        })

    if s == 200 or s == 201:
        narrative = poll_llm(player_a, run_id, turn_no)
        print(f"  📖 {narrative[:100]}...", flush=True)
    else:
        print(f"  ⚠️ 턴 실패: {s}", flush=True)

    current_turn_no = turn_no
    turn_log.append({
        "turn": turn_no,
        "node": current_node_type,
        "action_a": "auto",
        "action_b": "-",
    })

# ── 결과 저장 ──
print(f"\n{'=' * 60}", flush=True)
print(f"  플레이테스트 완료 — {len(turn_log)}턴 진행", flush=True)
print(f"{'=' * 60}", flush=True)

result = {
    "players": [
        {"name": player_a.nickname, "preset": player_a.preset, "userId": player_a.user_id},
        {"name": player_b.nickname, "preset": player_b.preset, "userId": player_b.user_id},
    ],
    "partyId": party_id,
    "runId": run_id,
    "turnsPlayed": len(turn_log),
    "turnLog": turn_log,
}

with open(args.output, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  결과 저장: {args.output}", flush=True)
