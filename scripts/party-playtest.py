#!/usr/bin/env python3
"""
파티 런 플레이테스트 — 2계정 실제 협동 플레이 + 2인 서사 검증

흐름:
  1. A, B 등록
  2. A, B 각자 대상 시나리오 솔로 런 선생성 (프리셋·시나리오 마킹 — lobby/start 계승용)
  3. A 파티 생성 → B 가입 → 둘 다 ready → A 던전 시작 (리더 최근 런 scenarioId/presetId 계승)
  4. HUB: 파티 투표로 장소 진입 (A 제안 → B 찬성 → 과반수 executeMove)
  5. LOCATION: A/B 2인 동시 행동 제출 → resolveTurn 통합 판정 → 통합 서사 폴링
  6. 서사 2인성 검증: 두 캐릭터 등장 여부, A/B 행동 반영, 복수 주체/NPC/묘사 존재

사용:
  python3 scripts/party-playtest.py --scenario star_sand_v1 --preset-a SS_DOCKHAND --preset-b SS_HEALER --turns 8
"""

import json, time, uuid, random, sys, argparse, re

parser = argparse.ArgumentParser(description="Party playtest — 2 players, 실측 서사 검증")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
parser.add_argument("--turns", type=int, default=8, help="LOCATION 턴 수 (default: 8)")
parser.add_argument("--scenario", default="star_sand_v1", help="시나리오 ID")
parser.add_argument("--preset-a", default="SS_DOCKHAND", help="플레이어 A 프리셋")
parser.add_argument("--preset-b", default="SS_HEALER", help="플레이어 B 프리셋")
parser.add_argument("--name-a", default="daejang", help="A 닉네임(ascii)")
parser.add_argument("--name-b", default="chiyu", help="B 닉네임(ascii)")
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

# ── LOCATION 행동 풀 (2인이 다른 행동을 하도록 분리) ──
ACTIONS_A = [
    "주변을 살펴본다",
    "수상한 흔적을 조사한다",
    "경비의 동태를 살핀다",
    "앞장서서 길을 연다",
    "낯선 이에게 말을 건다",
    "위협적으로 다가선다",
]
ACTIONS_B = [
    "사람들에게 조심스럽게 묻는다",
    "동료를 엄호하며 뒤를 살핀다",
    "부상자를 살피고 약초를 챙긴다",
    "소문의 진위를 확인한다",
    "구석을 뒤져 단서를 찾는다",
    "상대를 설득해본다",
]


class Player:
    def __init__(self, name, preset, gender="male"):
        self.name = name
        self.preset = preset
        self.gender = gender
        self.session = requests.Session()
        self.token = ""
        self.user_id = ""
        safe_name = re.sub(r"[^a-zA-Z0-9]", "", name) or f"p{random.randint(100,999)}"
        # 정본 테스터 계정 재사용 (register 실패 시 login fallback). 어드민 집계 제외 도메인.
        self.email = f"party_{safe_name.lower()}@test.com"
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
            "email": self.email, "password": PASSWORD, "nickname": self.nickname,
        })
        if s != 201:
            # 정본 계정 재사용 — 이미 존재하면 login fallback
            s, r = self.api("POST", "/auth/login", {
                "email": self.email, "password": PASSWORD,
            })
        if s in (200, 201) and r.get("token"):
            self.token = r.get("token", "")
            self.user_id = r.get("user", {}).get("id", "")
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            return True
        print(f"  [{self.name}] 인증 실패: status={s} resp={r}", flush=True)
        return False

    def create_solo_run(self, scenario_id):
        """시나리오/프리셋 마킹용 솔로 런 (lobby/start 계승 근거)"""
        s, r = self.api("POST", "/runs", {
            "presetId": self.preset, "gender": self.gender, "scenarioId": scenario_id,
        })
        if s in (200, 201):
            return r.get("run", {}).get("id", "") or r.get("runId", "")
        print(f"  [{self.name}] 솔로 런 생성 실패: {s} {json.dumps(r, ensure_ascii=False)[:200]}", flush=True)
        return None


def poll_llm(player, run_id, turn_no, max_wait=90):
    start = time.time()
    while time.time() - start < max_wait:
        _, data = player.api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            return llm.get("output", ""), data
        if status in ("FAILED", "SKIPPED"):
            return f"[LLM_{status}]", data
        time.sleep(3)
    return "[LLM_TIMEOUT]", {}


def get_state(player, run_id):
    s, rd = player.api("GET", f"/runs/{run_id}?turnsLimit=1")
    if s != 200:
        return None, None, [], "RUN_ACTIVE"
    info = rd.get("run", {})
    lr = rd.get("lastResult", {}) or {}
    node = lr.get("node", {}).get("type", "HUB")
    choices = lr.get("choices", [])
    status = info.get("status", "RUN_ACTIVE")
    return info.get("currentTurnNo", 0), node, choices, status


# ═══════════════════════════════════════
print("=" * 64, flush=True)
print(f"  파티 플레이테스트 — 2인 협동 [{args.scenario}]", flush=True)
print("=" * 64, flush=True)

# ── 0. 등록 ──
print("\n[0] 유저 등록", flush=True)
player_a = Player(args.name_a, args.preset_a, "male")
player_b = Player(args.name_b, args.preset_b, "female")
assert player_a.register(), "A 등록 실패"
assert player_b.register(), "B 등록 실패"
print(f"  A: {player_a.nickname} ({player_a.preset}) {player_a.user_id[:8]}", flush=True)
print(f"  B: {player_b.nickname} ({player_b.preset}) {player_b.user_id[:8]}", flush=True)

# ── 0.5. 시나리오/프리셋 마킹용 솔로 런 ──
print(f"\n[0.5] 시나리오 마킹 솔로 런 생성 ({args.scenario})", flush=True)
ra = player_a.create_solo_run(args.scenario)
rb = player_b.create_solo_run(args.scenario)
assert ra and rb, "솔로 런 생성 실패 — 시나리오 계승 불가"
print(f"  A 솔로 런 {ra[:8]} / B 솔로 런 {rb[:8]}", flush=True)

# ── 1. 파티 생성 + 가입 ──
print("\n[1] 파티 생성 + 가입", flush=True)
s, r = player_a.api("POST", "/parties", {"name": "별빛 원정대"})
assert s == 201, f"파티 생성 실패: {s} {r}"
party_id = r["id"]; invite_code = r["inviteCode"]
print(f"  파티 {r['name']} (코드 {invite_code})", flush=True)
s, r = player_b.api("POST", "/parties/join", {"inviteCode": invite_code})
assert s == 200, f"가입 실패: {s} {r}"
print(f"  {player_b.nickname} 가입 — 멤버 {r.get('memberCount')}명", flush=True)

# ── 2. 로비 준비 ──
print("\n[2] 로비 준비", flush=True)
player_a.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
s, r = player_b.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
print(f"  allReady={r.get('allReady')} canStart={r.get('canStart')}", flush=True)

# ── 3. 던전 시작 ──
print("\n[3] 던전 시작 (시나리오 계승)", flush=True)
s, r = player_a.api("POST", f"/parties/{party_id}/lobby/start")
assert s == 200, f"던전 시작 실패: {s} {r}"
run_id = r["runId"]
print(f"  파티 런 {run_id[:12]}", flush=True)

# 계승된 시나리오 확인
s, rd = player_a.api("GET", f"/runs/{run_id}?turnsLimit=1")
run_scenario = rd.get("run", {}).get("scenarioId", "?")
members = rd.get("run", {}).get("runState", {}).get("partyMembers", []) if isinstance(rd.get("run", {}).get("runState"), dict) else []
print(f"  계승 scenarioId={run_scenario} | 파티멤버 {len(members)}명", flush=True)
if run_scenario != args.scenario:
    print(f"  ⚠️ 시나리오 불일치! 기대 {args.scenario}, 실제 {run_scenario}", flush=True)

# ── 4. 턴 루프 ──
turn_log = []
location_turns = 0
print(f"\n{'=' * 64}", flush=True)
print(f"  턴 루프 시작 (LOCATION 최대 {MAX_TURNS}턴)", flush=True)
print(f"{'=' * 64}", flush=True)

loc_turn_count = 0
guard = 0
while loc_turn_count < MAX_TURNS and guard < MAX_TURNS * 3:
    guard += 1
    cur_no, node, choices, status = get_state(player_a, run_id)
    if status != "RUN_ACTIVE":
        print(f"\n  런 종료: {status}", flush=True)
        break
    turn_no = cur_no + 1

    # ── HUB: 파티 투표로 장소 진입 ──
    if node == "HUB":
        choice_ids = [c.get("id") for c in choices]
        # 프롤로그 수락 단계 (accept_quest 등 go_ 아닌 CHOICE만 존재)
        move_choices = [c for c in choices
                        if (c.get("action", {}).get("payload", {}) or {}).get("locationId")
                        and str(c.get("id", "")).startswith("go_")]
        if not move_choices:
            # 프롤로그/특수 HUB 선택지 처리 — 파티 가드(go_만 허용)와 충돌 검사
            nongo = [c for c in choices if not str(c.get("id", "")).startswith("go_")]
            if nongo:
                pc = nongo[0]
                pcid = pc.get("id")
                print(f"\n── HUB 턴 {turn_no}: 프롤로그/특수 CHOICE '{pcid}' 처리", flush=True)
                # (1) 파티 API로 제출 시도 → 소프트락 여부 확인
                s, resp = player_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
                    "inputType": "CHOICE", "rawInput": pcid, "idempotencyKey": str(uuid.uuid4()),
                })
                if s >= 400:
                    print(f"  🐛 파티 API 거부 (소프트락 의심): {s} {json.dumps(resp, ensure_ascii=False)[:160]}", flush=True)
                    # (2) 솔로 API로 우회 (리더 대표 진행)
                    s2, resp2 = player_a.api("POST", f"/runs/{run_id}/turns", {
                        "input": {"type": "CHOICE", "choiceId": pcid},
                        "expectedNextTurnNo": turn_no, "idempotencyKey": str(uuid.uuid4()),
                    })
                    print(f"  ↪ 솔로 API 우회: {s2}", flush=True)
                    if s2 not in (200, 201):
                        print(f"  ❌ 우회도 실패 — 진입 불가: {json.dumps(resp2, ensure_ascii=False)[:160]}", flush=True)
                        break
                    turn_log.append({"turn": turn_no, "node": "HUB", "note": "prologue_softlock_bypassed", "choiceId": pcid, "partyRejectStatus": s})
                else:
                    print(f"  파티 API 수용: {s} {json.dumps(resp, ensure_ascii=False)[:120]}", flush=True)
                    turn_log.append({"turn": turn_no, "node": "HUB", "note": "prologue_party_ok", "choiceId": pcid})
                time.sleep(3)
                poll_llm(player_a, run_id, turn_no)
                continue
            print(f"  ⚠️ HUB 이동 선택지 없음. choices={choice_ids}", flush=True)
            break
        target = random.choice(move_choices)
        cid = target["id"]
        print(f"\n── HUB 턴 {turn_no}: 투표 이동 → {target.get('label', cid)} ({cid})", flush=True)

        # A가 파티 HUB CHOICE 제출 → 투표 생성
        s, resp = player_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "CHOICE", "rawInput": cid, "idempotencyKey": str(uuid.uuid4()),
        })
        if not resp.get("voteCreated"):
            print(f"  ⚠️ 투표 미생성: {s} {json.dumps(resp, ensure_ascii=False)[:200]}", flush=True)
            break
        vote_id = resp["vote"]["id"]
        print(f"  투표 생성 {vote_id[:8]} — B 찬성 대기", flush=True)

        # B 찬성 → 과반수(2/2) 도달 → executeMove
        s, vr = player_b.api("POST", f"/parties/{party_id}/votes/{vote_id}/cast", {"choice": "yes"})
        print(f"  B 찬성: {s} status={vr.get('status', '?')}", flush=True)

        # executeMove가 리더 계정 HUB 턴 자동 제출 → LOCATION 진입 서사 생성
        time.sleep(3)
        move_turn = turn_no
        narrative, _ = poll_llm(player_a, run_id, move_turn)
        snippet = narrative[:120].replace("\n", " ")
        print(f"  📖 진입: {snippet}...", flush=True)
        continue

    # ── LOCATION: 2인 동시 행동 ──
    if node == "LOCATION":
        loc_turn_count += 1
        action_a = random.choice(ACTIONS_A)
        action_b = random.choice(ACTIONS_B)
        print(f"\n── LOCATION 턴 {turn_no} (#{loc_turn_count}) ──", flush=True)
        print(f"  A({player_a.nickname}): \"{action_a}\"", flush=True)
        print(f"  B({player_b.nickname}): \"{action_b}\"", flush=True)

        s1, r1 = player_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "ACTION", "rawInput": action_a, "idempotencyKey": str(uuid.uuid4()),
        })
        s2, r2 = player_b.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "ACTION", "rawInput": action_b, "idempotencyKey": str(uuid.uuid4()),
        })
        print(f"  제출 A={s1}/acc={r1.get('accepted')}  B={s2}/acc={r2.get('accepted')}/all={r2.get('allSubmitted')}", flush=True)

        if r1.get("accepted") is False or r2.get("accepted") is False:
            print(f"  ⚠️ 제출 거부: A={json.dumps(r1, ensure_ascii=False)[:150]} B={json.dumps(r2, ensure_ascii=False)[:150]}", flush=True)

        time.sleep(3)
        narrative, turn_data = poll_llm(player_a, run_id, turn_no)

        # partyActions 확인 (통합 판정에 2인 행동이 실렸는지)
        s, td = player_a.api("GET", f"/parties/{party_id}/runs/{run_id}/turns/{turn_no}")
        party_actions = td.get("partyActions", []) or []
        sr = turn_data.get("serverResult", {}) or td.get("serverResult", {}) or {}
        events = sr.get("events", []) or []

        pa_desc = [((pa.get('nickname') or pa.get('userId', '?')[:6]) + ':' + (pa.get('rawInput') or '')[:12]) for pa in party_actions]
        print(f"  🧩 partyActions {len(party_actions)}건: {pa_desc}", flush=True)
        snippet = narrative[:400].replace("\n", " ")
        print(f"  📖 {snippet}...", flush=True)
        if events:
            print(f"  🎲 {[e.get('text','')[:24] for e in events[:3]]}", flush=True)

        turn_log.append({
            "turn": turn_no, "node": "LOCATION",
            "action_a": action_a, "action_b": action_b,
            "partyActions": [{"nick": pa.get("nickname"), "raw": pa.get("rawInput"), "auto": pa.get("isAutoAction")} for pa in party_actions],
            "narrative": narrative,
            "events": [e.get("text", "") for e in events[:5]],
        })
        continue

    # ── 기타 노드 (COMBAT 등) — A 대표 진행 ──
    if choices:
        c = random.choice(choices)
        cid = c.get("id", c.get("choiceId", ""))
        print(f"\n── {node} 턴 {turn_no}: 선택 {c.get('label', cid)}", flush=True)
        player_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
            "inputType": "CHOICE", "rawInput": cid, "idempotencyKey": str(uuid.uuid4()),
        })
        time.sleep(3)
        poll_llm(player_a, run_id, turn_no)
    else:
        break

# ── 결과 저장 + 요약 ──
print(f"\n{'=' * 64}", flush=True)
print(f"  완료 — LOCATION {len(turn_log)}턴", flush=True)
print(f"{'=' * 64}", flush=True)

result = {
    "scenario": args.scenario,
    "players": [
        {"name": player_a.nickname, "preset": player_a.preset, "userId": player_a.user_id},
        {"name": player_b.nickname, "preset": player_b.preset, "userId": player_b.user_id},
    ],
    "partyId": party_id, "runId": run_id,
    "runScenario": run_scenario,
    "turnsPlayed": len(turn_log),
    "turnLog": turn_log,
}
with open(args.output, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"  결과 저장: {args.output}", flush=True)

# ── 2인 서사 검증 요약 ──
print(f"\n{'─' * 64}", flush=True)
print("  [2인 서사 검증]", flush=True)
loc_turns = [t for t in turn_log if t.get("node") == "LOCATION"]
two_actor_turns = sum(1 for t in loc_turns if len(t.get("partyActions", [])) >= 2)
# 서사에 두 캐릭터가 모두 등장하는지 (닉네임 기준)
both_named = 0
for t in loc_turns:
    narr = t.get("narrative", "")
    if player_a.nickname in narr and player_b.nickname in narr:
        both_named += 1
softlock = any(t.get("note") == "prologue_softlock_bypassed" for t in turn_log)
print(f"  · LOCATION 턴: {len(loc_turns)}", flush=True)
print(f"  · 2인 행동 수집 턴: {two_actor_turns}/{len(loc_turns)}", flush=True)
print(f"  · 두 캐릭터 모두 서사 등장: {both_named}/{len(loc_turns)}", flush=True)
print(f"  · 프롤로그 소프트락 발생: {'예 (accept_quest 파티 API 400)' if softlock else '아니오'}", flush=True)
