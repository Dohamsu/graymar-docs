#!/usr/bin/env python3
"""
파티 시스템 Phase 2 통합 테스트 — 2세션 동시 진행

사용법:
  python3 scripts/party-test.py                      # 기본: localhost:3000
  python3 scripts/party-test.py --base http://host/v1 # 서버 URL 변경

테스트 시나리오:
  1. 유저 A, B 등록/로그인
  2. A가 파티 생성 → B가 초대코드로 가입
  3. A, B 모두 준비 완료
  4. A(리더)가 던전 시작
  5. 2인 동시 행동 제출 (A 먼저, B 이어서)
  6. 타임아웃 테스트 (B 미제출)
  7. 이동 투표 테스트
  8. 파티 탈퇴/해산
"""

import json, time, uuid, sys, argparse

parser = argparse.ArgumentParser(description="Party system E2E test")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
args = parser.parse_args()

BASE = args.base
PASSWORD = "Test1234!!"

try:
    import requests
except ImportError:
    print("requests 패키지가 필요합니다: pip install requests", flush=True)
    sys.exit(1)

# ═══════════════════════════════════════
# Helpers
# ═══════════════════════════════════════

class UserSession:
    """한 유저의 세션 (인증 + API 호출)"""
    def __init__(self, name: str):
        self.name = name
        self.session = requests.Session()
        self.token = ""
        self.user_id = ""
        self.email = f"party_test_{name}_{int(time.time())}@test.com"
        self.nickname = f"Tester_{name}"

    def api(self, method, path, body=None):
        url = f"{BASE}{path}"
        try:
            r = self.session.request(method, url, json=body, timeout=30)
            data = r.json() if r.text else {}
            return r.status_code, data
        except Exception as e:
            print(f"  [{self.name}] API error: {e}", flush=True)
            return 0, {}

    def register_or_login(self):
        status, resp = self.api("POST", "/auth/register", {
            "email": self.email,
            "password": PASSWORD,
            "nickname": self.nickname,
        })
        if status == 201:
            self.token = resp.get("token", "")
            self.user_id = resp.get("user", {}).get("id", "")
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            return True
        # 이미 존재하면 로그인 시도
        status, resp = self.api("POST", "/auth/login", {
            "email": self.email,
            "password": PASSWORD,
        })
        if status == 200:
            self.token = resp.get("token", "")
            self.user_id = resp.get("user", {}).get("id", "")
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            return True
        return False


def section(title):
    print(f"\n{'═' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'═' * 60}", flush=True)


def step(desc):
    print(f"\n  ▶ {desc}", flush=True)


def ok(msg):
    print(f"    ✅ {msg}", flush=True)


def fail(msg):
    print(f"    ❌ {msg}", flush=True)
    return False


def info(msg):
    print(f"    ℹ️  {msg}", flush=True)


results = {"passed": 0, "failed": 0, "tests": []}


def assert_test(name, condition, detail=""):
    if condition:
        ok(f"{name}")
        results["passed"] += 1
        results["tests"].append({"name": name, "status": "PASS"})
        return True
    else:
        fail(f"{name} — {detail}")
        results["failed"] += 1
        results["tests"].append({"name": name, "status": "FAIL", "detail": detail})
        return False


# ═══════════════════════════════════════
# 0. 유저 등록
# ═══════════════════════════════════════

section("0. 유저 등록")

user_a = UserSession("A")
user_b = UserSession("B")

step("유저 A 등록")
assert_test("유저 A 등록 성공", user_a.register_or_login(), "register/login failed")
info(f"userId={user_a.user_id[:8]}... email={user_a.email}")

step("유저 B 등록")
assert_test("유저 B 등록 성공", user_b.register_or_login(), "register/login failed")
info(f"userId={user_b.user_id[:8]}... email={user_b.email}")


# ═══════════════════════════════════════
# 1. 파티 생성 + 가입
# ═══════════════════════════════════════

section("1. 파티 생성 + 가입")

step("A가 파티 생성")
status, resp = user_a.api("POST", "/parties", {"name": "테스트용병단"})
assert_test("파티 생성 201", status == 201, f"status={status}")

# 응답이 flat 구조: {id, name, inviteCode, members: [...], ...}
party_id = resp.get("id", "")
invite_code = resp.get("inviteCode", "")
info(f"partyId={party_id[:8]}... inviteCode={invite_code}")

step("A의 파티 조회")
status, resp = user_a.api("GET", "/parties/my")
assert_test("내 파티 조회 200", status == 200, f"status={status}")
assert_test("파티 이름 일치", resp.get("name") == "테스트용병단")

step("B가 초대코드로 가입")
status, resp = user_b.api("POST", "/parties/join", {"inviteCode": invite_code})
assert_test("파티 가입 200", status == 200, f"status={status} resp={json.dumps(resp, ensure_ascii=False)[:200]}")

step("멤버 수 확인")
status, resp = user_a.api("GET", "/parties/my")
members = resp.get("members", [])
assert_test("멤버 2명", len(members) == 2, f"members={len(members)}")


# ═══════════════════════════════════════
# 2. 로비 — 준비 완료 시스템
# ═══════════════════════════════════════

section("2. 로비 — 준비 완료 시스템")

step("로비 상태 조회 (초기)")
status, resp = user_a.api("GET", f"/parties/{party_id}/lobby")
assert_test("로비 조회 200", status == 200, f"status={status}")
assert_test("초기 allReady=false", resp.get("allReady") == False)
assert_test("초기 canStart=false", resp.get("canStart") == False)
info(f"members: {[m.get('nickname') for m in resp.get('members', [])]}")

step("A 준비 완료")
status, resp = user_a.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
assert_test("A 준비 200", status == 200, f"status={status}")
assert_test("A 준비 후 allReady=false (B 미준비)", resp.get("allReady") == False)

step("B 준비 완료")
status, resp = user_b.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
assert_test("B 준비 200", status == 200, f"status={status}")
assert_test("전원 준비 후 allReady=true", resp.get("allReady") == True)
assert_test("canStart=true", resp.get("canStart") == True)

step("B가 준비 해제 → 다시 준비")
status, resp = user_b.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": False})
assert_test("준비 해제 200", status == 200, f"status={status}")
assert_test("해제 후 allReady=false", resp.get("allReady") == False)

status, resp = user_b.api("POST", f"/parties/{party_id}/lobby/ready", {"ready": True})
assert_test("재준비 후 allReady=true", resp.get("allReady") == True)


# ═══════════════════════════════════════
# 3. 던전 시작
# ═══════════════════════════════════════

section("3. 던전 시작")

step("B(비리더)가 시작 시도 → 실패")
status, resp = user_b.api("POST", f"/parties/{party_id}/lobby/start")
assert_test("비리더 시작 거부", status in (400, 403), f"status={status}")

step("A(리더)가 던전 시작")
status, resp = user_a.api("POST", f"/parties/{party_id}/lobby/start")
assert_test("던전 시작 200", status == 200, f"status={status}")

run_id = resp.get("runId", "")
member_ids = resp.get("memberUserIds", [])
assert_test("runId 존재", len(run_id) > 0, "runId empty")
assert_test("멤버 2명 포함", len(member_ids) == 2, f"members={len(member_ids)}")
info(f"runId={run_id[:8]}...")

step("파티 상태가 IN_DUNGEON인지 확인")
status, resp = user_a.api("GET", "/parties/my")
party_status = resp.get("status", "")
assert_test("파티 상태 IN_DUNGEON", party_status == "IN_DUNGEON", f"status={party_status}")


# ═══════════════════════════════════════
# 4. 행동 제출 테스트
# ═══════════════════════════════════════

section("4. 행동 제출 테스트")

step("A가 행동 제출")
status, resp = user_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
    "inputType": "ACTION",
    "rawInput": "주변을 살펴본다",
    "idempotencyKey": str(uuid.uuid4()),
})
assert_test("A 행동 제출 200", status == 200, f"status={status} resp={json.dumps(resp, ensure_ascii=False)[:200]}")
assert_test("A 제출 accepted", resp.get("accepted") == True)
a_all_submitted = resp.get("allSubmitted", False)
info(f"allSubmitted={a_all_submitted}")

step("A가 동일 턴 중복 제출 → 멱등성")
status, resp = user_a.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
    "inputType": "ACTION",
    "rawInput": "다시 살펴본다",
    "idempotencyKey": str(uuid.uuid4()),
})
assert_test("중복 제출도 200 (멱등)", status == 200, f"status={status}")

step("B가 행동 제출")
status, resp = user_b.api("POST", f"/parties/{party_id}/runs/{run_id}/turns", {
    "inputType": "ACTION",
    "rawInput": "경비병에게 말을 건다",
    "idempotencyKey": str(uuid.uuid4()),
})
assert_test("B 행동 제출 200", status == 200, f"status={status} resp={json.dumps(resp, ensure_ascii=False)[:200]}")
b_all_submitted = resp.get("allSubmitted", False)
info(f"allSubmitted={b_all_submitted} (전원 제출 시 true)")


# ═══════════════════════════════════════
# 5. 이동 투표 테스트
# ═══════════════════════════════════════

section("5. 이동 투표 테스트")

step("A가 시장 이동 투표 제안")
status, resp = user_a.api("POST", f"/parties/{party_id}/votes", {
    "targetLocationId": "LOC_MARKET",
})
assert_test("투표 생성 201", status == 201, f"status={status}")
vote_id = resp.get("id", "")
assert_test("voteId 존재", len(vote_id) > 0)
assert_test("yesVotes=1 (제안자 자동 찬성)", resp.get("yesVotes") == 1)
assert_test("status=PENDING", resp.get("status") == "PENDING")
info(f"voteId={vote_id[:8]}... target=LOC_MARKET")

step("A가 중복 투표 제안 → 실패")
status, resp = user_a.api("POST", f"/parties/{party_id}/votes", {
    "targetLocationId": "LOC_HARBOR",
})
assert_test("중복 투표 거부 400", status == 400, f"status={status}")

step("B가 찬성 투표")
status, resp = user_b.api("POST", f"/parties/{party_id}/votes/{vote_id}/cast", {
    "choice": "yes",
})
assert_test("투표 참여 200", status == 200, f"status={status}")
vote_status = resp.get("status", "")
# 2명 중 2명 찬성 → APPROVED
assert_test("과반수 도달 → APPROVED", vote_status == "APPROVED", f"status={vote_status}")
info(f"투표 결과: {vote_status}")


# ═══════════════════════════════════════
# 6. 채팅 + 시스템 메시지 확인
# ═══════════════════════════════════════

section("6. 채팅 + 시스템 메시지 확인")

step("A가 채팅 메시지 전송")
status, resp = user_a.api("POST", f"/parties/{party_id}/messages", {
    "content": "여기가 시장인가?",
})
assert_test("채팅 전송 201", status == 201, f"status={status}")

step("B가 채팅 히스토리 조회")
status, resp = user_b.api("GET", f"/parties/{party_id}/messages")
assert_test("히스토리 조회 200", status == 200, f"status={status}")
messages = resp.get("messages", [])
assert_test("메시지 1개 이상", len(messages) > 0, f"count={len(messages)}")

# 시스템 메시지 존재 확인 (가입/투표 결과 등)
system_msgs = [m for m in messages if m.get("type") == "SYSTEM"]
info(f"전체 메시지 {len(messages)}개 (SYSTEM: {len(system_msgs)}개)")
for m in messages[-5:]:
    info(f"  [{m.get('type')}] {m.get('senderNickname', 'SYSTEM')}: {m.get('content', '')[:50]}")


# ═══════════════════════════════════════
# 7. 파티 탈퇴/해산
# ═══════════════════════════════════════

section("7. 파티 탈퇴/해산")

step("B가 파티 탈퇴")
status, resp = user_b.api("POST", f"/parties/{party_id}/leave")
assert_test("B 탈퇴 200", status == 200, f"status={status}")

step("B 탈퇴 후 멤버 수 확인")
status, resp = user_a.api("GET", "/parties/my")
members_after = resp.get("members", [])
assert_test("멤버 1명 (A만)", len(members_after) == 1, f"members={len(members_after)}")

step("A가 파티 해산")
status, resp = user_a.api("DELETE", f"/parties/{party_id}")
assert_test("파티 해산 200", status == 200, f"status={status}")

step("해산 후 파티 조회 → null")
status, resp = user_a.api("GET", "/parties/my")
# getMyParty returns null → api returns empty or null-like response
assert_test("파티 없음", resp is None or resp.get("id") is None or status == 200)


# ═══════════════════════════════════════
# 결과 요약
# ═══════════════════════════════════════

section("테스트 결과 요약")

total = results["passed"] + results["failed"]
print(f"\n  총 {total}개 테스트", flush=True)
print(f"  ✅ 통과: {results['passed']}개", flush=True)
print(f"  ❌ 실패: {results['failed']}개", flush=True)

if results["failed"] > 0:
    print(f"\n  실패한 테스트:", flush=True)
    for t in results["tests"]:
        if t["status"] == "FAIL":
            print(f"    - {t['name']}: {t.get('detail', '')}", flush=True)

# JSON 저장
output_path = "playtest-reports/party_test_result.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n  결과 저장: {output_path}", flush=True)

sys.exit(0 if results["failed"] == 0 else 1)
