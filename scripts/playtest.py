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
parser.add_argument("--character-name", default=None,
                    help="캐릭터 이름 (arch/91 통성명·재회 호명 경로 검증용. 미지정 시 이름 없는 런)")
parser.add_argument("--base", default="http://localhost:3000/v1", help="서버 URL")
parser.add_argument("--output", default=None, help="결과 JSON 파일 경로")
parser.add_argument("--loc-turns", type=int, default=4, help="장소당 체류 턴 수 (default: 4)")
parser.add_argument("--dry-run", action="store_true", help="LLM mock 모드 + 프롬프트 추출 (비용 0원)")
parser.add_argument("--choice-rate", type=float, default=0.25, help="LOCATION에서 CHOICE 선택 확률 (default: 0.25)")
parser.add_argument("--model", default=None, help="런타임 LLM 모델 전환")
parser.add_argument("--scenario", default=None, help="시나리오 팩 ID (default: 서버 기본=graymar_v1)")
parser.add_argument("--agent", default=None, help="에이전트 플레이어 페르소나 (coercer|chatty|weirdo|brawler) — LLM이 서술을 읽고 의도 연속 플레이 + 위화감 자동 노트")
parser.add_argument("--agent-model", default="openai/gpt-4.1-mini", help="에이전트 플레이어 LLM 모델 (OpenRouter)")
parser.add_argument("--turn-delay", type=float, default=0, help="턴 간 대기 초 (인간 페이스 모사 — AUTONOMOUS 팩 시드/디렉터 검증용)")
parser.add_argument("--new-account", action="store_true", help="정본 테스터 대신 새 계정 생성 (기본: playtest@test.com 재사용)")
parser.add_argument("--skip-version-check", action="store_true",
                    help="preflight 서버 버전 해시 대조 생략 (의도적으로 구버전/원격 빌드를 테스트할 때)")
args = parser.parse_args()

BASE = args.base
MAX_TURNS = args.turns
_run_ended_naturally = False  # [M1] 엔딩 도달 여부 — V0 부분 실행 판정 예외
# 정본 테스터 계정 재사용 (register 409 → login fallback). --new-account 시에만 새로 생성.
# 어드민 집계 제외·정리 대상은 테스트 도메인 기준 (server/src/common/tester.util.ts).
EMAIL = f"playtest_{int(time.time())}@test.com" if args.new_account else "playtest@test.com"
PASSWORD = "Test1234!!"
NICKNAME = "Tester"

# tavern 포함 — 거점 사랑방(arch/68 부록 B) 자유 대화 경로도 완주 회귀에 포함
LOCATIONS = ["market", "guard", "tavern", "harbor", "slums"]
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

# ═══════════════════════════════════════
# 0. Preflight (하네스 보강 #6, 2026-08-05)
# ═══════════════════════════════════════
# ③ cwd 자동 교정 — server/ 등에서 실행하면 playtest-reports/ 상대 경로가 깨지던
#    반복 실측 함정을 스크립트가 스스로 해소한다 (CLAUDE.md 플레이테스트 절).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.getcwd() != _REPO_ROOT:
    print(f"[preflight] cwd 교정: {os.getcwd()} → {_REPO_ROOT}", flush=True)
    os.chdir(_REPO_ROOT)

# ② 서버 버전 해시 대조 — "커밋 후 재시작 누락"으로 구버전 서버를 검증하는
#    false-PASS 방지. 양쪽 다 `git rev-parse --short HEAD` 산출이라 정확 비교.
#    로컬 서버 대상일 때만 강제 (원격은 HEAD가 다른 게 정상일 수 있음).
_SERVER_HASH = ""  # V12 원장 기록용 — preflight 를 건너뛰면 빈 값으로 남는다
if not args.skip_version_check and ("localhost" in BASE or "127.0.0.1" in BASE):
    _, _ver = api("GET", "/version")
    _server_hash = str(_ver.get("server", ""))
    _SERVER_HASH = _server_hash
    if not _server_hash:
        print(f"[preflight] 서버 응답 없음 ({BASE}/version) — 서버 기동을 먼저 확인", flush=True)
        sys.exit(2)
    _server_repo = os.path.join(_REPO_ROOT, "server")
    try:
        _local_hash = subprocess.run(
            ["git", "-C", _server_repo, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        _local_hash = ""
    if _local_hash and _server_hash != _local_hash:
        # 해시가 달라도 두 커밋 사이에 코드(src·의존성) 차이가 없으면 통과 —
        # ci.yml·README 같은 비코드 커밋마다 재시작을 요구하는 false-positive 방지.
        _code_diff = subprocess.run(
            ["git", "-C", _server_repo, "diff", "--quiet",
             f"{_server_hash}..{_local_hash}", "--",
             "src", "package.json", "pnpm-lock.yaml"],
            capture_output=True, text=True, timeout=10,
        )
        if _code_diff.returncode == 0:
            pass  # 비코드 커밋 차이 — 아래 OK 라인에서 함께 보고
        else:
            print(f"[preflight] 서버 버전 불일치: 기동 중={_server_hash} vs 로컬 HEAD={_local_hash}", flush=True)
            print("→ cd server && pnpm build && launchctl kickstart -k gui/$(id -u)/com.graymar.server", flush=True)
            print("→ 의도된 구버전 검증이면 --skip-version-check", flush=True)
            sys.exit(2)
    try:
        _dirty = subprocess.run(
            ["git", "-C", _server_repo, "status", "--porcelain", "--", "src"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        _dirty = ""
    if _dirty:
        print(f"[preflight] 경고: server/src 미커밋 변경 {len(_dirty.splitlines())}건 — 기동 중인 빌드에 미반영일 수 있음", flush=True)
    if _server_hash == _local_hash:
        print(f"[preflight] OK — 서버 {_server_hash} = 로컬 HEAD", flush=True)
    else:
        print(f"[preflight] OK — 서버 {_server_hash} ≠ HEAD {_local_hash}지만 코드 차이 없음(비코드 커밋)", flush=True)

def poll_llm(run_id, turn_no, max_wait=90, expect_choices=False):
    """LLM 폴링: GET /turns/:turnNo → llm.status / llm.output + UI 데이터

    expect_choices (V13, arch/98): 워커는 DONE 커밋 후 Track2가 llmChoices를
    쓴다 — DONE 즉시 반환하면 선택지 스냅샷이 빈다. LOCATION 턴은 실제
    클라이언트도 stream 'done'(Track2 완료 후)에서 선택지를 받으므로,
    최대 12초까지 선택지 기록을 추가 대기한다.
    """
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        status = llm.get("status", "")
        if status == "DONE":
            if expect_choices and not llm.get("choices"):
                for _ in range(4):  # 최대 ~12초 추가 대기 (Track2 nano)
                    time.sleep(3)
                    _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
                    llm = data.get("llm", {}) or {}
                    if llm.get("choices"):
                        break
            ui = data.get("serverResult", {}).get("ui", {})
            return {
                "output": llm.get("output") or "",
                "status": "DONE",
                "npcPortrait": ui.get("npcPortrait"),
                "speakingNpc": ui.get("speakingNpc"),
                "newsHeadlines": ui.get("newsHeadlines"),
                # V13 (arch/98): nano 최종 선택지 — 다양성·질문 응답 센서용
                "choices": llm.get("choices"),
            }
        if status in ("FAILED", "SKIPPED"):
            return {"output": f"[LLM_{status}]", "status": status}
        time.sleep(3)
    return {"output": "[LLM_TIMEOUT]", "status": "TIMEOUT"}

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
# 에이전트 플레이어 (--agent) — LLM이 서술을 읽고 의도 연속 플레이
#   무작위 봇이 못 만드는 "목적 있는 흐름"(연속 강압·긴 대화·기행)을 생성하고,
#   매 턴 직전 서술의 위화감(화자 스왑·기억 모순·뜬금 사건)을 자동 노트로 남긴다.
#   실측 근거: 버그 d20c1de8(구타 대상 스왑)은 의도 연속 4턴이 있어야만 발화.
# ═══════════════════════════════════════
AGENT_PERSONAS = {
    "coercer": (
        "당신은 강압적인 심문자다. 초반 1~2턴은 대상을 정해 말을 걸어 정보를 요구하고, "
        "거부당하면 협박 → 물리적 압박(팔 꺾기·멱살)으로 매 턴 강도를 올린다. "
        "한 번 정한 대상을 바꾸지 말고 끝까지 몰아붙여라. 대상 이름 대신 '그/그녀'로 이어가도 된다."
    ),
    "chatty": (
        "당신은 수다스러운 탐문가다. NPC와 길게 대화한다 — 인사, 안부, 소문 질문, 개인사 질문, "
        "감사, 작별까지 자연스러운 대화 흐름을 만든다. 상대가 한 말을 기억하고 되물어라 "
        "(예: '아까 창고 얘기를 했는데, 그게 어디죠?'). 같은 상대와 3~4턴 대화 후 다른 상대로."
    ),
    "weirdo": (
        "당신은 기행을 일삼는 괴짜다. 매 턴 예측 불가능한 행동을 한다 — 탁자 위에서 춤추기, "
        "허무맹랑한 거짓말('나는 왕의 사촌이다'), 물건을 이상하게 사용, 마법 주문 외치기, "
        "갑자기 물건 파괴, 뜬금없는 선물. 평범한 행동은 금지. 단 이동은 자유."
    ),
    # APPROACH(우호 접근) 관찰용 (arch/76 D3-c′): trust+attachment 를 한 NPC 에
    # 집중 축적. chatty 는 상대를 돌아가며 사귀어 두 축이 분산됨 (30턴 실측:
    # trust 는 미렐라, attach 는 브렌 — 같은 NPC 에 안 모임).
    "devotee": (
        "당신은 한 사람에게만 마음을 쓰는 단골이다. 처음 만난 대화 상대 한 명을 정하면 "
        "런이 끝날 때까지 그 사람하고만 어울린다 — 매 턴 그 사람에게 안부를 묻고, 고민을 들어주고, "
        "일을 거들고, 작은 선물을 하고, 개인사를 묻고, 자기 이야기도 털어놓는다. "
        "다른 인물이 말을 걸어도 짧게 응대하고 그 사람에게 돌아가라. 절대 다른 상대로 갈아타지 마라. "
        "장소를 옮겨야 하면 다시 그 사람이 있는 곳으로 돌아가라."
    ),
    # REPORT(신고) 관찰용 (arch/76 D3-c′): fear 없이 suspicion·불신만 축적.
    # fear 경로가 우선순위라 폭력·협박이 섞이면 FLEE가 선점해 REPORT를 못 본다.
    "sneaky_liar": (
        "당신은 수상쩍은 밀정이다. 폭력·협박·겁주기는 절대 금지 — 상대가 무서워하면 실패다. "
        "대신 매 턴 의심을 사는 행동을 한다: 몰래 서랍·선반 뒤지기, 잠입해서 엿듣기, "
        "뻔히 들통날 거짓말(신분 사칭, 앞뒤 안 맞는 이야기), 대답을 얼버무리며 화제 돌리기, "
        "같은 인물 주변을 맴돌며 소지품을 훔쳐보기. 한 장소에 오래 머물며 같은 인물 앞에서 "
        "수상한 행동을 반복하라. 떠나라고 해도 딴청 피우며 남아라."
    ),
    # 전투 기만 검증용 (arch/76 D3-combat): appraiseCombatTactic 분류 + 성향 민감도 실측
    "brawler": (
        "당신은 시비를 걸어 싸움을 만드는 주먹꾼이다. 장소에서는 1~2턴 안에 상대를 정해 시비를 "
        "걸고 직접 폭력으로 싸움을 시작한다 (예: '저 경비병을 밀치고 주먹을 휘두른다'). "
        "전투 중에는 정직한 공격과 기만을 번갈아 쓴다 — '뒤를 봐라, 네 동료가 쓰러졌다!' 같은 "
        "거짓 외침, 모래를 뿌리는 척, 항복하는 척하다 기습, 무기를 떨어뜨린 척. "
        "전투 턴의 절반은 반드시 기만을 구체적 문장으로 시도하라. 도망치지 마라."
    ),
}

_agent_env = {}
def _load_agent_env():
    if _agent_env:
        return _agent_env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                _agent_env["key"] = line.split("=", 1)[1]
            elif line.startswith("OPENAI_BASE_URL="):
                _agent_env["base"] = line.split("=", 1)[1]
    _agent_env.setdefault("base", "https://openrouter.ai/api/v1")
    return _agent_env

agent_notes = []       # [{turn, note}]
agent_parse_fail = 0

def agent_decide(persona_key, node_type, choices, last_narr, last_action, hp, loc_hint):
    """페르소나 유지 다음 행동 + 직전 서술 위화감 판정. 실패 시 None (무작위 fallback)."""
    global agent_parse_fail
    env = _load_agent_env()
    choice_lines = "\n".join(f"- {c.get('id')}: {c.get('label', '')}" for c in (choices or [])[:8])
    system = (
        f"{AGENT_PERSONAS[persona_key]}\n\n"
        "당신은 한국어 텍스트 RPG를 플레이 중이다. 아래 두 가지를 JSON으로만 출력한다.\n"
        "1) anomaly — 직전 서술을 평가: 다음 중 하나라도 있으면 1문장으로 지적, 없으면 null.\n"
        "   · 내 행동의 대상/대화 상대가 갑자기 다른 인물로 바뀜\n"
        "   · 내가 하지 않은 행동을 했다고 서술\n"
        "   · NPC가 방금 한 말/이전 대화와 모순\n"
        "   · 내 의도와 무관한 사건이 뜬금없이 끼어듦\n"
        "   · 직전 턴과 거의 같은 문장 반복\n"
        "2) 다음 행동 — 페르소나를 유지하며 직전 흐름을 잇는다.\n"
        '   ACTION: {"anomaly": ..., "type": "ACTION", "text": "1문장 행동/대사 (한국어)"}\n'
        '   CHOICE: {"anomaly": ..., "type": "CHOICE", "choiceId": "제공된 id 중 하나"}\n'
        "전투 중이면 전투 행동(공격·회피·도주·기만)을 text로. JSON 외 텍스트 금지."
    )
    user = (
        f"[상태] 노드: {node_type} / HP: {hp} / 위치 힌트: {loc_hint}\n"
        f"[직전 내 행동] {last_action or '(런 시작)'}\n"
        f"[직전 서술]\n{(last_narr or '(없음)')[:700]}\n\n"
        f"[선택지]\n{choice_lines or '(없음 — ACTION만 가능)'}\n\n다음 행동은?"
    )
    try:
        r = session.post(
            f"{env['base']}/chat/completions",
            headers={"Authorization": f"Bearer {env['key']}"},
            json={
                "model": args.agent_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": 200,
                "temperature": 0.9,
            },
            timeout=30,
        )
        txt = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{[\s\S]*\}", txt)
        d = json.loads(m.group(0))
        if d.get("anomaly"):
            agent_notes.append({"turn": None, "note": str(d["anomaly"])[:150]})
        if d.get("type") == "CHOICE" and d.get("choiceId") and any(c.get("id") == d["choiceId"] for c in (choices or [])):
            return {"type": "CHOICE", "choiceId": d["choiceId"]}
        if d.get("text"):
            return {"type": "ACTION", "text": str(d["text"])[:120]}
    except Exception:
        agent_parse_fail += 1
    return None

# ═══════════════════════════════════════
# 1. Auth
# ═══════════════════════════════════════
print(f"=== 플레이테스트 시작 ({MAX_TURNS}턴, {args.preset}, {args.gender}, choice_rate={args.choice_rate}) ===", flush=True)

status, resp = api("POST", "/auth/register", {"email": EMAIL, "password": PASSWORD, "nickname": NICKNAME})
if status != 201:
    status, resp = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = resp.get("token", "")
if not token:
    print(f"Auth 실패: {resp}", flush=True)
    sys.exit(1)
session.headers["Authorization"] = f"Bearer {token}"
print(f"Auth: {EMAIL}", flush=True)

# ── 포인트 잔액 사전 체크 (arch/85 채팅 5p/턴 — 잔액 0이면 전 턴 402로
#    0턴인데 조용히 PASS 나는 false-PASS 방지, 2026-07-23 실측) ──
_, _bal = api("GET", "/points/balance")
if _bal.get("enabled", False):
    _need = MAX_TURNS * int(_bal.get("chatCost", 5))
    if int(_bal.get("points", 0)) < _need:
        _redeem_code = os.environ.get("PLAYTEST_REDEEM_CODE", "")
        if _redeem_code:
            _, _red = api("POST", "/points/redeem", {"code": _redeem_code})
            if _red.get("balance") is not None:
                print(f"포인트 자동 충전: +{_red.get('granted')}p → 잔액 {_red.get('balance')}p", flush=True)
            _, _bal = api("GET", "/points/balance")
    if int(_bal.get("points", 0)) < _need:
        print(f"포인트 부족: 잔액 {_bal.get('points', 0)}p < 필요 {_need}p ({MAX_TURNS}턴 × {_bal.get('chatCost', 5)}p)", flush=True)
        print("→ PLAYTEST_REDEEM_CODE 환경변수로 충전 코드를 지정하거나 어드민 코드 발급 후 재실행 (memory: project_playtest_points_gate)", flush=True)
        sys.exit(2)

# 모델 전환 (선택적) — settings 엔드포인트는 JWT 필요 → 반드시 auth 이후
_orig_model = None
if args.model:
    _, settings = api("GET", "/settings/llm")
    _orig_model = settings.get("openaiModel", "")
    _, patched = api("PATCH", "/settings/llm", {"openaiModel": args.model})
    if patched.get("openaiModel") != args.model:
        print(f"모델 전환 실패: {patched}", flush=True)
        sys.exit(1)
    print(f"모델 전환: {_orig_model} → {args.model}", flush=True)

if args.dry_run:
    dry_run_setup()

# ═══════════════════════════════════════
# 2. Create Run
# ═══════════════════════════════════════
_run_body = {"presetId": args.preset, "gender": args.gender}
if args.character_name:
    _run_body["characterName"] = args.character_name
if args.scenario:
    _run_body["scenarioId"] = args.scenario
status, resp = api("POST", "/runs", _run_body)
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
last_narrative = ""   # 에이전트 모드 — 직전 턴 서술 (위화감 판정·행동 결정 입력)
last_input_desc = ""
bought_items = set()   # 4-A: 상점 구매 1회/아이템 제한
arc_committed = False  # 4-A: 아크 커밋 선택지 1회 클릭

for turn_i in range(MAX_TURNS):
    # 인간 플레이 페이스 모사 — AUTONOMOUS 팩은 Plot Seed 백그라운드 생성(60초~2분대
    # 실측)이 빠른 턴 제출을 못 따라잡으면 디렉터가 조용히 무발화 (2026-07-22 실측)
    if args.turn_delay > 0 and turn_i > 0:
        time.sleep(args.turn_delay)
    idem = str(uuid.uuid4())

    # Refresh state
    _, state = api("GET", f"/runs/{run_id}")
    if not state:
        print(f"  T{turn_i+1}: 상태 조회 실패", flush=True)
        break
    run_status = state.get("run", {}).get("status", "")
    if run_status == "RUN_ENDED":
        print(f"  [RUN_ENDED at turn {turn_i}]", flush=True)
        _run_ended_naturally = True
        break

    current_turn = state.get("run", {}).get("currentTurnNo", current_turn)
    node_type = state.get("currentNode", {}).get("nodeType", "")
    choices = state.get("lastResult", {}).get("choices", [])
    hp = state.get("runState", {}).get("hp", "?")
    gold = state.get("runState", {}).get("gold", 0) or 0

    # 4-A: 아크 커밋 선택지 감지 시 최우선 클릭 (arc_ 접두 규약, 1회)
    arc_choice = None
    if not arc_committed:
        for c in choices:
            if str(c.get("id", "")).startswith("arc_"):
                arc_choice = c
                break
    if arc_choice:
        body = {"input": {"type": "CHOICE", "choiceId": arc_choice["id"]}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
        input_desc = f"CHOICE:{arc_choice['id']} (arc)"
        arc_committed = True
    # 4-A: 상점 구매 — 현 장소 진열에서 살 수 있는 첫 품목 1회 구매
    elif node_type == "LOCATION" and not args.agent and (shop_target := next(
        (it for s in (state.get("lastResult", {}).get("ui", {}) or {}).get("shops", [])
         for it in s.get("items", [])
         if it.get("itemId") not in bought_items and gold >= it.get("price", 10**9)),
        None,
    )) and random.random() < 0.5:
        _eul = "을" if 0xAC00 <= ord(shop_target["name"][-1]) <= 0xD7A3 and (ord(shop_target["name"][-1]) - 0xAC00) % 28 else "를"
        body = {"input": {"type": "ACTION", "text": f"{shop_target['name']}{_eul} 구매한다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
        input_desc = f"ACTION:buy({shop_target['name']})"
        bought_items.add(shop_target["itemId"])
    # Determine input
    elif node_type == "HUB":
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
        agent_input = None
        if args.agent:
            agent_input = agent_decide(args.agent, node_type, choices, last_narrative, last_input_desc, hp, "전투 중")
            if agent_notes and agent_notes[-1]["turn"] is None:
                agent_notes[-1]["turn"] = turn_i  # 직전 턴 서술에 대한 노트
        if agent_input:
            body = {"input": agent_input, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"AGENT:{(agent_input.get('text') or agent_input.get('choiceId', ''))[:30]}"
        else:
            body = {"input": {"type": "ACTION", "text": "정면에서 검을 휘두른다"}, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = "ACTION:combat_attack"

    else:
        # LOCATION turn
        loc_turns += 1
        agent_input = None
        if args.agent and loc_turns <= args.loc_turns:
            agent_input = agent_decide(args.agent, node_type, choices, last_narrative, last_input_desc, hp, "장소 탐험 중")
            if agent_notes and agent_notes[-1]["turn"] is None:
                agent_notes[-1]["turn"] = turn_i
        if agent_input:
            body = {"input": agent_input, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
            input_desc = f"AGENT:{(agent_input.get('text') or agent_input.get('choiceId', ''))[:30]}"
        elif loc_turns > args.loc_turns:
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

    if status == 402:
        # 포인트 소진 — 계속 돌려봤자 전 턴 402라 즉시 중단 (침묵 진행 금지)
        print(f"  T{turn_i+1}: 포인트 소진(402) — 턴 제출 불가, 루프 중단", flush=True)
        break

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
    llm_result = poll_llm(
        run_id, submitted_turn, expect_choices=(node_type == "LOCATION")
    )
    narrative = llm_result.get("output", "") if isinstance(llm_result, dict) else llm_result

    # 카드 정합 분석 (2026-07-11): turnNo 기록이 로컬 카운터라 자동 진입 턴에서
    # 실제 커밋 턴과 어긋남 — 폴링(submitted_turn)과 동일한 응답 turnNo로 기록.
    current_turn = submitted_turn
    log_entry = {
        "turn": turn_i + 1,
        "turnNo": submitted_turn,
        "nodeType": node_type,
        "input": input_desc,
        "hp": hp,
        "eventId": matched_event,
        "resolveOutcome": resolve,
        "nodeOutcome": node_outcome,
        "events": [e.get("kind", "") for e in events],
        "narrative": narrative if narrative else "",
        # V11: 빈 서술(DONE인데 출력 없음)과 FAILED/TIMEOUT을 구분하기 위한 상태 기록
        "llmStatus": llm_result.get("status", "") if isinstance(llm_result, dict) else "",
        "npcPortrait": llm_result.get("npcPortrait") if isinstance(llm_result, dict) else None,
        "rawInput": body.get("input", {}).get("text", ""),
        # V10: 서술 화자(NpcResolver 최종) — 이벤트 정의 NPC와 대조용
        "primaryNpcId": action_ctx.get("primaryNpcId"),
        # V10 정밀화(2026-07-17): 분열은 이벤트 고유 선택지가 실제 노출됐을 때만
        # 플레이어 대면 — EventChoiceGate 폐기 턴을 FP로 세지 않기 위해
        # 이번 턴 응답(server_result)의 선택지 id를 기록
        "choiceIds": [
            c.get("id", "") for c in (server_result.get("choices") or [])
        ],
        # V13 (arch/98): nano 최종 선택지 (llm.choices — 없으면 서버 기본 유지 턴)
        "llmChoices": llm_result.get("choices") if isinstance(llm_result, dict) else None,
    }
    turn_logs.append(log_entry)

    last_narrative = narrative or last_narrative
    last_input_desc = input_desc

    evt_display = matched_event[:25] if matched_event else "-"
    print(f"  T{turn_i+1:02d} [{node_type:8s}] {input_desc[:35]:35s} evt={evt_display:25s} resolve={resolve or '-':8s} HP={hp}", flush=True)

    current_turn += 1

    if node_outcome == "RUN_ENDED":
        print(f"  [RUN_ENDED]", flush=True)
        _run_ended_naturally = True
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
#   [M1 감사 2026-08-12 — 체크리스트 C8/C2] 기존 판정은 `trust != 0 or fear != 0`
#   이었으나 **trust 는 콘텐츠 초기값이 있다** (팩별 5~14명, 예: NPC_SS_IREN 30).
#   프리셋 npcPostureOverrides 의 trustDelta 도 런 시작 시 얹힌다. 그래서 런에서
#   감정이 **전혀 움직이지 않아도** 게이트가 통과했다 — "감정축이 작동한다" 를
#   검증한다고 주장하면서 실제로는 "초기값이 0 이 아닌 NPC가 있다" 를 봤다.
#   판정을 **초기값이 0 인 축(fear·suspicion·attachment·respect)의 실변동**으로
#   바꾼다. trust 는 초기값 오염이 있어 계측으로만 남긴다.
#   근거: arch/100 §13 — fear p99 0.0 · suspicion 2.0% 만 0 아님.
print(f"\n[V4] NPC 감정축:", flush=True)
ZERO_INIT_AXES = ("fear", "suspicion", "attachment", "respect")
emo_active = 0          # 게이트 대상 — 초기값 0 축이 움직인 NPC 수
emo_trust_only = 0      # 계측 — trust 만 0 아님 (초기값일 수 있음)
for npc_id, npc in npc_states.items():
    emo = npc.get("emotional", {})
    moved = [a for a in ZERO_INIT_AXES if emo.get(a, 0)]
    if moved:
        emo_active += 1
        print(f"  {npc_id}: " + " ".join(f"{a}={emo.get(a)}" for a in moved)
              + f" (trust={emo.get('trust', 0)})", flush=True)
    elif emo.get("trust", 0):
        emo_trust_only += 1
print(f"  실변동 NPC {emo_active}명 · trust만 0아님 {emo_trust_only}명 "
      f"(초기값 포함이라 게이트 제외)", flush=True)

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
# [M1 감사 2026-08-12 — 체크리스트 C5] 표시명 → npcId 정규화 맵.
#   V8 은 화자 라벨과 마커 이름을 **문자열로** 비교해 왔다. 같은 NPC 를 역할명과
#   실명으로 부르면 불일치로 잡힌다 — 실측: 화자 '책임자' ≠ 마커 '마이렐 단 경'
#   (둘 다 NPC_MAIREL). arch/66 소개 이후 마커는 실명, 서술은 역할명을 쓰는
#   정상 동작인데 게이트가 오탐을 냈다. 비교는 반드시 ID 로 정규화 후 한다.
_v8_name2id = {}
try:
    _v8_pack = args.scenario or "graymar_v1"
    import os as _os8
    _v8_path = _os8.path.join(_os8.path.dirname(_os8.path.abspath(__file__)),
                              "..", "content", _v8_pack, "npcs.json")
    with open(_v8_path, encoding="utf-8") as _f8:
        _v8_raw = json.load(_f8)
    _v8_list = _v8_raw if isinstance(_v8_raw, list) else _v8_raw.get("npcs", [])
    for _n in _v8_list:
        _nid = _n.get("npcId")
        if not _nid:
            continue
        _cands = [_n.get("name"), _n.get("unknownAlias"), _n.get("shortAlias")]
        _alias = _n.get("unknownAlias") or ""
        if len(_alias.split()) > 1:
            _cands.append(_alias.split()[-1])      # 역할명 (책임자·장교·수녀)
        _cands += list(_n.get("aliases") or [])
        for _c in _cands:
            if isinstance(_c, str) and len(_c) >= 2:
                _v8_name2id.setdefault(_c, _nid)
except Exception as _e8:
    print(f"  ⚠️ V8 npcId 정규화 맵 로드 실패 ({_e8}) — 문자열 비교로 폴백", flush=True)


def _v8_same_npc(a: str, b: str) -> bool:
    """두 표시명이 같은 NPC 를 가리키는가 (ID 정규화 우선, 실패 시 문자열)."""
    ia, ib = _v8_name2id.get(a), _v8_name2id.get(b)
    if ia and ib:
        return ia == ib
    # 맵에 없으면(동적 NPC·환각 등) 기존 substring 비교로 폴백
    return a in b or b in a


    # @마커 NPC가 서술 문맥과 불일치 (화자 이름 ≠ 마커 이름)
    marker_matches = list(re.finditer(r'@\[([^\]|]+)(?:\|[^\]]+)?\]\s*["\u201C\u201D]', narr))
    for mm in marker_matches:
        marker_name = mm.group(1).strip()
        before = narr[max(0, mm.start() - 80):mm.start()]
        # 직전 대사 내부 텍스트 제거 — 대사 속 명사('떠도는 말들')를
        # 화자로 오인하는 오탐 방지 (cycle1 T23 실측, 2026-07-12)
        before = re.sub(r'["“][^"“”]*["”]?', ' ', before)
        # "XX가 말했다" 패턴에서 XX ≠ marker_name이면 불일치
        # '말'은 발화 동사형만 — 명사 '말(word)' ("그 말은") 제외
        speaker_match = re.search(r"([가-힣]{2,10})[이가은는]\s*(?:말(?=[하했])|말을\s*(?:걸|이어|꺼내|덧붙)|물(?=[었어으])|외치|외쳤|중얼|속삭|답하|답했|대답|되물)", before)
        if speaker_match:
            speaker = speaker_match.group(1)
            # 플레이어 지칭은 화자 후보에서 제외 (NPC 대사 앞에 "당신이 말을 걸자" 등)
            player_refs = {"당신", "그대", "용병", "자네", "이방인", "나그네", "손님", "낯선"}
            if speaker in player_refs:
                continue
            if not _v8_same_npc(speaker, marker_name):
                v8_issues.append(f"T{t['turn']}: 화자={speaker} ≠ 마커={marker_name}")
if v8_issues:
    for issue in v8_issues[:5]:
        print(f"  ❌ {issue}", flush=True)
    if len(v8_issues) > 5:
        print(f"  ... 외 {len(v8_issues)-5}건", flush=True)
else:
    print(f"  ✅ 정합성 양호", flush=True)

# ── 어휘 반복 정본 (arch/92 §8) ─────────────────────────────────────────────
#   순수 로직은 scripts/repetition_core.py — 인라인으로 두면 게이트 실패 경로를
#   실런 없이 검증할 수 없다(스크립트가 top-level 실행). 대명사 상수는 V9 반복
#   센서와 D5 지칭 집계가 이 정본을 함께 참조한다 (구: D5 지역 정의라 V9이
#   대명사를 게이트로 이중 처벌).
import repetition_core as _rep
_PRONOUN_OPENERS = _rep.PRONOUN_OPENERS
_PRONOUN_STEMS = _rep.PRONOUN_STEMS
_stem_word = _rep.stem_word


# V9: 서술 품질 (반복/하오체 미마킹 + sanitize 오탐 + CHOICE 대화 맥락)
print(f"\n[V9] 서술 품질:", flush=True)
v9_issues = []

# V9-a: 별칭 융합 잔존 감지 (테스트 감사 2026-07-12 재정의)
#   구 패턴(r"허.{5,15}지")은 "허투루 넘기지" 같은 정상 문장에 광역 오탐 (실측).
#   원 버그(alias 오삽입)는 서버 stripFusedAliasPrefix 계열로 근본 수정됨 —
#   이 검사는 서버 방어가 놓친 잔존을 감지하는 회귀 센서로 재정의:
#   알려진 unknownAlias 직전에 한글 1~2자가 공백 없이 밀착한 패턴만.
_ua_pool = []
try:
    def _collect_ua(o):
        if isinstance(o, dict):
            ua = o.get("unknownAlias")
            if o.get("npcId") and isinstance(ua, str) and len(ua) >= 4:
                _ua_pool.append(ua)
            for v in o.values():
                _collect_ua(v)
        elif isinstance(o, list):
            for v in o:
                _collect_ua(v)
    _collect_ua(_npcs_raw)
except Exception:
    pass
for t in turn_logs:
    narr = t.get("narrative", "")
    for ua in _ua_pool:
        for m in re.finditer(r"(?:^|[\s\"\u201C.,!?…])([가-힣]{1,2})" + re.escape(ua), narr):
            v9_issues.append(f"T{t['turn']}: 별칭 융합 잔존 — '{m.group(1)}{ua[:12]}…'")

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

# V9-c: @[무명 인물] 판별 — 의도/의심 구분 (2026-07-11 노이즈 정밀화)
#   무명은 두 종류: (a) 콘텐츠 외 즉흥 배경 인물("짐을 정리하던 인부") — 의도된
#   실루엣 처리(arch/46), (b) 알려진 NPC 대사가 무명 처리 — 결함. 직전 문맥에
#   알려진 NPC 이름/별칭이 있으면 (b) 의심으로만 경고, 없으면 계수하지 않는다.
_npc_alias_pool = []
# [arch/92 §8] 활성 팩 기준으로 로드 — 구 코드는 graymar_v1 경로 하드코딩이라
# 별빛모래·카른홀트 런에서 **다른 팩의 NPC 별칭 풀**로 판정하고 있었다
# (V9-c 무명 대사 의심 + D5-2 CONTENT_ALIAS 분류가 전부 오염).
_PACK_ID = args.scenario or "graymar_v1"
import os as _os
_CONTENT_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "content", _PACK_ID)
try:
    with open(_os.path.join(_CONTENT_DIR, "npcs.json"), encoding="utf-8") as _f:
        _npcs_raw = json.load(_f)
    def _collect_aliases(o):
        if isinstance(o, dict):
            if o.get("npcId"):
                for k in ("name", "unknownAlias", "shortAlias"):
                    v = o.get(k)
                    if isinstance(v, str) and len(v) >= 2:
                        _npc_alias_pool.append(v)
                for a in (o.get("aliases") or []):
                    if isinstance(a, str) and len(a) >= 2:
                        _npc_alias_pool.append(a)
            for v in o.values():
                _collect_aliases(v)
        elif isinstance(o, list):
            for v in o:
                _collect_aliases(v)
    _collect_aliases(_npcs_raw)
    # 유일 축약 단어 추가 — unknownAlias 마지막 단어가 단일 NPC로 해석되는 것만
    # (서버 resolveColonLabelNpc Tier 3과 동일 기준; '여인'처럼 다중이면 제외)
    from collections import Counter as _Counter
    _last_words = _Counter()
    def _collect_last_words(o):
        if isinstance(o, dict):
            ua = o.get("unknownAlias")
            if o.get("npcId") and isinstance(ua, str) and " " in ua:
                _last_words[ua.split()[-1]] += 1
            for v in o.values():
                _collect_last_words(v)
        elif isinstance(o, list):
            for v in o:
                _collect_last_words(v)
    _collect_last_words(_npcs_raw)
    # 3자 이상만 — 2자 축약('인부' 등)은 일반 직업명과 충돌해 즉흥 인물 오탐 (실측)
    _npc_alias_pool.extend(w for w, c in _last_words.items() if c == 1 and len(w) >= 3)
except Exception:
    pass  # 콘텐츠 로드 실패 시 구분 없이 전부 의심 경고 (보수적)

for t in turn_logs:
    narr = t.get("narrative", "")
    for _am in re.finditer(r"@\[무명 인물\]", narr):
        before = narr[max(0, _am.start() - 120):_am.start()]
        suspects = [a for a in _npc_alias_pool if a in before]
        if suspects or not _npc_alias_pool:
            v9_issues.append(
                f"T{t['turn']}: 무명 대사 의심 — 직전 문맥에 알려진 NPC({', '.join(suspects[:2]) or '?'}) 존재"
            )
        # 알려진 NPC 미등장 → 즉흥 배경 인물의 의도된 실루엣 — 계수 안 함

# ── 단어 반복 검출 (3턴 윈도우, arch/92 §8 재작성) ──────────────────────────
#   구 구현의 4대 결함을 함께 고친다:
#   ① 윈도우별 이슈 적재 → 한 반복이 최대 3윈도우에 걸려 단일 반복이 3이슈로
#      계상됐다(임계 <=2 즉시 초과). **단어 단위로 dedupe**하고 최대 카운트만 남긴다.
#   ② `[가-힣]{2,4}` 고정폭 절단 → 조사가 안 떨어져 감지 토큰 43종 중 53%가
#      조사 종결 어절('소리가'·'장부의'·'고개를'). 어절을 넓게 잡아 _stem_word로 정규화.
#   ③ 대명사('그녀는'·'그가')를 게이트로 이중 처벌 → arch/78 D5-1이 이미 측정·수용 중.
#   ④ 제외 목록이 graymar 지명 하드코딩 → 활성 팩 콘텐츠에서 파생.
#   NPC 실명·콘텐츠 별칭은 게이트에서 빼되 계측에는 남긴다(3턴 대화 중 이름 5~8회는 정상).
_REP_PLACE_WORDS = set()
try:
    with open(_os.path.join(_CONTENT_DIR, "locations.json"), encoding="utf-8") as _lf:
        _REP_PLACE_WORDS = _rep.extract_place_words(json.load(_lf))
except Exception:
    pass  # 로드 실패 시 지명이 반복으로 잡힐 수 있음 (보수적)

_rep_hits, _rep_alias_hits = _rep.detect(
    [t.get("narrative", "") for t in turn_logs],
    [t["turn"] for t in turn_logs],
    _rep.build_stopwords(_REP_PLACE_WORDS),
    _npc_alias_pool,
)
_rep_gate_failed, _rep_severe, _rep_too_many = _rep.evaluate_gate(_rep_hits)

for _w, _c, _tn in _rep_severe:
    v9_issues.append(f"T{_tn}: '{_w}' {_c}회 반복 (3턴 내) — 심각")
if _rep_too_many and not _rep_severe:
    v9_issues.append(
        f"반복 어휘 {len(_rep_hits)}종 (임계 {_rep.MAX_DISTINCT}종 초과): "
        + ", ".join(f"'{h.word}'×{h.count}" for h in _rep_hits[:6])
    )
# 계측 — 게이트 통과 여부와 무관하게 항상 보고 (만성 추이 관찰용)
if _rep_hits or _rep_alias_hits:
    _rep_line = ", ".join(f"{h.word}×{h.count}" for h in _rep_hits[:8])
    _alias_line = ", ".join(f"{h.word}×{h.count}" for h in _rep_alias_hits[:4])
    print(
        f"  · [계측] 반복 어휘 {len(_rep_hits)}종"
        + (f": {_rep_line}" if _rep_line else "")
        + (f" · 콘텐츠 별칭(게이트 제외) {_alias_line}" if _alias_line else ""),
        flush=True,
    )
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

# V10: 선택지-서술 NPC 정합 (arch/68 부록 L — 이벤트-서술 분열 감지)
#   버그 185a8ddd 계열: 매칭 이벤트가 특정 NPC(콘텐츠 payload.primaryNpcId)를
#   전제하는데 서술 화자(actionContext.primaryNpcId)가 다르면, 선택지는 이벤트
#   NPC를 가리키고 서술은 다른 NPC를 등장시키는 분열이 발생한다. EventChoiceGate
#   (유닛)는 게이트 로직을 검증하고, V10은 실런에서 실제 분열을 통합 감지한다.
print("\n[V10] 선택지-서술 NPC 정합:", flush=True)
v10_issues = []
_event_npc_map = {}
try:
    # [arch/92 §8] 활성 팩 기준 — 구 graymar_v1 하드코딩은 비-graymar 런에서
    # V10(이벤트-서술 NPC 정합) 게이트를 남의 팩 이벤트로 판정하게 만들었다.
    _ev_path = _os.path.join(_CONTENT_DIR, "events_v2.json")
    with open(_ev_path, encoding="utf-8") as _f:
        _ev_raw = json.load(_f)
    _ev_list = _ev_raw.get("events", _ev_raw) if isinstance(_ev_raw, dict) else _ev_raw
    _event_choice_map = {}
    for _e in _ev_list:
        _eid = _e.get("eventId")
        _enpc = (_e.get("payload") or {}).get("primaryNpcId")
        if _eid and _enpc:
            _event_npc_map[_eid] = _enpc
            _event_choice_map[_eid] = {
                c.get("id") for c in ((_e.get("payload") or {}).get("choices") or []) if c.get("id")
            }
except Exception as _e:
    print(f"  (events_v2 로드 실패: {_e})", flush=True)
    _event_choice_map = {}
for t in turn_logs:
    if t.get("nodeType") != "LOCATION":
        continue
    eid = t.get("eventId")
    event_npc = _event_npc_map.get(eid)
    speaker = t.get("primaryNpcId")
    # 정밀화(2026-07-17): 이벤트 고유 선택지가 이번 턴 응답에 실제 노출된 경우만
    # 플레이어 대면 분열 — EventChoiceGate가 폐기한 턴(정상 player-first)은 제외.
    _offered = set(t.get("choiceIds") or [])
    _event_choices_exposed = bool(_event_choice_map.get(eid, set()) & _offered)
    if event_npc and speaker and event_npc != speaker and _event_choices_exposed:
        v10_issues.append(f"T{t['turn']}: 이벤트 NPC({event_npc}) ≠ 서술 화자({speaker}) — 선택지-서술 분열 [{eid}]")
if v10_issues:
    for issue in v10_issues[:5]:
        print(f"  ❌ {issue}", flush=True)
    if len(v10_issues) > 5:
        print(f"  ... 외 {len(v10_issues)-5}건", flush=True)
else:
    print(f"  ✅ 정합성 양호", flush=True)

# V11: 서술 존재·형식 (arch/25 D-8 백로그 ② — 하드 결함 게이트)
#   배경: run 71637853 — 12턴 중 5턴 빈 서술(0토큰 DONE)인데 V1~V10 전부 통과.
#   기존 게이트는 서술 존재를 암묵 전제로 내용 품질만 검사 — 빈 서술은 검사 대상이
#   없어 역설적으로 무사통과. 빈 서술·서술 자리 raw JSON(run 01d79acc T5 실측)은
#   해석 여지 없는 하드 결함이라 1건이라도 FAIL. FAILED/TIMEOUT 턴은 서버 3층
#   방어(server ccadb18)가 작동한 결과라 게이트 비대상 — 카운트만 노출해
#   allowlist 프로바이더 악화 관찰(task #3) 재료로 남긴다.
print("\n[V11] 서술 존재·형식:", flush=True)
v11_issues = []
v11_failed_count = 0
for t in turn_logs:
    _status = t.get("llmStatus", "")
    _narr = (t.get("narrative") or "").strip()
    if _status == "SKIPPED" or _narr == "[LLM_SKIPPED]":
        continue  # 정당한 무서술 턴 (프롤로그 등)
    if _status in ("FAILED", "TIMEOUT") or _narr in ("[LLM_FAILED]", "[LLM_TIMEOUT]"):
        v11_failed_count += 1
        continue
    if not _narr:
        v11_issues.append(f"T{t['turn']}: 빈 서술 (llmStatus=DONE)")
    elif re.match(r'^\s*\{\s*"', _narr):
        v11_issues.append(f"T{t['turn']}: 서술 선두 raw JSON 누출 — {_narr[:40]!r}")
if v11_issues:
    for issue in v11_issues[:5]:
        print(f"  ❌ {issue}", flush=True)
    if len(v11_issues) > 5:
        print(f"  ... 외 {len(v11_issues)-5}건", flush=True)
else:
    print("  ✅ 빈 서술·JSON 누출 없음", flush=True)
if v11_failed_count:
    print(f"  ⚠️ FAILED/TIMEOUT 턴 {v11_failed_count}건 — 서버 방어 작동 (게이트 비대상, 프로바이더 관찰 재료)", flush=True)

# V12: 프롬프트 예산 — 재비대 가드 (arch/79 2차 + arch/95 §6, 2026-07-27)
#   배경: arch/79(7/19) 이후 3주간 신규 블록 5계열+규칙 재성장으로 백스톱 발동률이
#   0%→35%로 자랐는데 감시 지표가 없어 아무도 못 봤다 — 그 부작용이 [NPC 일상]
#   잡담 화제 블록 상시 삭제(D 블록 미주입 버그)였다. 턴별 최종 프롬프트
#   (includeDebug llmPrompt, 백스톱 절삭 후) 총 문자수를 집계해 게이트한다.
#   - 발동 추정: 절삭 후에도 ≥16,000자에 남는 턴 — 백스톱이 스냅샷 제거로도 상한
#     (GRAND_TOTAL 16,500자)을 못 맞춘 턴의 근사치. 정밀 판정은 서버 [GrandBudget] 로그.
#   - FAIL 시 대응은 프롬프트 다이어트가 정본 — 상한 상향으로 풀지 말 것 (arch/95 §6).
PROMPT_BUDGET_CAP = 16500      # server token-budget.service.ts GRAND_TOTAL_CHAR_BUDGET
PROMPT_FIRE_PROXY = 16000      # 발동 추정 임계 (상한의 ~97%)
PROMPT_AVG_LIMIT = 15000       # 평균 경보선 (2026-07-27 압축 후 실측 avg 12.7k + 18% 여유)
# [arch/79 §11.3] 다회 런 누적 판정 — 단일 런은 n=14~20이라 발동 1건이 5%p다.
V12_POOL_RUNS = 3              # 판정 창: 최근 3런 풀링 (n≈50 → 1턴 ≈ 2%p)
V12_MIN_RUNS = 2               # 이 미만이면 게이트 보류 (참고 수치만)
V12_LEDGER_KEEP = 20           # 원장 보존 런 수
# V13 도 같은 병을 앓는다 — 런당 nano 선택지가 27~36개라 1개가 약 3%p.
# 2026-08-07 실측: 런 단위로는 6/7 FAIL 인데 같은 날 누적은 33/198=16.7% 로
# 게이트(15%)를 통과했다. 편중이 아니라 표본 크기가 만든 착시였다.
V13_POOL_RUNS = 3
V13_MIN_RUNS = 2


def append_gate_ledger(ledger_name, entry, pool_runs, keep=V12_LEDGER_KEEP):
    """게이트 원장에 이번 런을 적고 판정 창(최근 pool_runs 런)을 돌려준다.

    런 단위 표본이 작아 노이즈에 뒤집히는 게이트(V12·V13)를 다회 런 누적으로
    판정하기 위한 공용 IO. 판정식 자체는 호출부가 정한다 — V12 는 가중 평균이
    추가로 필요해 창을 직접 다룬다.

    원장은 playtest-reports/ 아래 로컬 파일이며 런별 서버 해시를 함께 남긴다.
    코드 변경을 사이에 둔 창은 해석 시 분리할 것.
    """
    path = os.path.join("playtest-reports", ledger_name)
    ledger = []
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                ledger = json.load(f)
            if not isinstance(ledger, list):
                ledger = []
    except Exception:
        ledger = []
    ledger.append(entry)
    ledger = ledger[-keep:]
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 원장 저장 실패 (판정은 계속): {e}", flush=True)
    return ledger[-pool_runs:]
print("\n[V12] 프롬프트 예산 (재비대 가드):", flush=True)
prompt_sizes = []
for t in turn_logs:
    _tn = t.get("turnNo")
    if not _tn:
        continue
    try:
        _p = get_prompt(run_id, _tn)
    except Exception:
        _p = None
    if not _p:
        continue
    _msgs = _p if isinstance(_p, list) else [_p]
    _total = sum(
        len((m or {}).get("content") or "") if isinstance(m, dict) else len(str(m))
        for m in _msgs
    )
    if _total > 0:
        prompt_sizes.append((t["turn"], _total))
prompt_budget_metrics = None
if prompt_sizes:
    _sizes = [s for _, s in prompt_sizes]
    _p_avg = sum(_sizes) // len(_sizes)
    _p_max = max(_sizes)
    _fired = [(tt, s) for tt, s in prompt_sizes if s >= PROMPT_FIRE_PROXY]
    _fire_rate = len(_fired) / len(_sizes)

    # [arch/79 §11.3 → 다회 런 누적 판정, 2026-08-07] 단일 런 판정 폐기.
    #   런당 표본이 14~20턴이라 발동 1건 = 5%p이고, 게이트 20% 선에서 ±1턴이
    #   통과/실패를 가른다 (run1 대화연속 6턴·발동 2건 vs run3 3턴·발동 4건).
    #   실제로 무손실 압축 후에도 발동률이 21%로 고정돼 게이트가 신호를 못 냈다.
    #   → 최근 N런의 **원시 카운트를 풀링**해 판정한다 (rate 평균이 아니라
    #     sum(fired)/sum(turns) — 런별 턴 수 차이를 자동 가중).
    #   표본이 1런뿐이면 참고 표시만 하고 게이트는 통과 처리 (오탐 방지).
    _window = append_gate_ledger(
        "v12_ledger.json",
        {
            "runId": run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            # 서버 해시는 preflight 에서만 채워진다 (--skip-version-check 시 빈 값)
            "server": _SERVER_HASH,
            "sampleTurns": len(_sizes),
            "fireProxyCount": len(_fired),
            "avgChars": _p_avg,
        },
        pool_runs=V12_POOL_RUNS,
    )
    _pool_turns = sum(r.get("sampleTurns", 0) for r in _window)
    _pool_fired = sum(r.get("fireProxyCount", 0) for r in _window)
    _pool_rate = _pool_fired / _pool_turns if _pool_turns else 0.0
    # 가중 평균 — 런별 턴 수로 가중 (단순 평균은 짧은 런을 과대 반영)
    _pool_avg = (
        sum(r.get("avgChars", 0) * r.get("sampleTurns", 0) for r in _window) // _pool_turns
        if _pool_turns else 0
    )
    _pooled_enough = len(_window) >= V12_MIN_RUNS
    v12_pass = (
        (_pool_rate <= 0.20 and _pool_avg <= PROMPT_AVG_LIMIT)
        if _pooled_enough else True
    )

    prompt_budget_metrics = {
        "avgChars": _p_avg,
        "maxChars": _p_max,
        "sampleTurns": len(_sizes),
        "fireProxyCount": len(_fired),
        "fireProxyRate": round(_fire_rate, 3),
        "capChars": PROMPT_BUDGET_CAP,
        # 누적 판정 근거 (게이트가 보는 값)
        "pooledRuns": len(_window),
        "pooledTurns": _pool_turns,
        "pooledFireCount": _pool_fired,
        "pooledFireRate": round(_pool_rate, 3),
        "pooledAvgChars": _pool_avg,
        "gateApplied": _pooled_enough,
    }
    print(f"  프롬프트 총량: avg {_p_avg:,}자 / max {_p_max:,}자 (표본 {len(_sizes)}턴, 상한 {PROMPT_BUDGET_CAP:,}자)", flush=True)
    print(f"  이번 런 발동 추정(≥{PROMPT_FIRE_PROXY:,}자): {len(_fired)}/{len(_sizes)}턴 ({_fire_rate*100:.0f}%)", flush=True)
    print(f"  누적 판정({len(_window)}런): {_pool_fired}/{_pool_turns}턴 ({_pool_rate*100:.0f}%) · 가중 avg {_pool_avg:,}자", flush=True)
    if not _pooled_enough:
        print(f"  ⚠️ 표본 부족({len(_window)}/{V12_MIN_RUNS}런) — 게이트 보류(통과 처리). 참고용 수치만 기록", flush=True)
    elif v12_pass:
        print("  ✅ 예산 정상 — 재비대 없음", flush=True)
    else:
        print("  ❌ 재비대 경보 — 프롬프트 다이어트 필요 (상한 상향으로 풀지 말 것, arch/95 §6)", flush=True)
else:
    v12_pass = True
    print("  ⚠️ 프롬프트 표본 없음 (includeDebug 미보존?) — 게이트 스킵", flush=True)

# V13: 선택지 다양성 + 질문 응답 (arch/98, 2026-08-05)
#   배경: 실유저 14일 표본에서 TALK/OBSERVE/INVESTIGATE 91%·적극 축 2% 편중과
#   NPC 질문 턴 92% 응답 선택지 부재 실측. P1(적극 축 positive 주입)·P2(질문
#   명시 주입)의 효과를 런 단위로 감시한다.
#   게이트: 적극 축(소극 3종 외) 비율 ≥15% AND 소극 3종 ≤80%.
#   질문 응답률은 표본이 작아(런당 질문 턴 1~3) 계측만 — 게이트 제외.
print("\n[V13] 선택지 다양성·질문 응답 (arch/98):", flush=True)
PASSIVE_AFFS = {"TALK", "OBSERVE", "INVESTIGATE"}
_aff_counts = {}
_q_turns = 0
_q_answered = 0
_ANSWER_RE = re.compile(r"답한|답변|대답|들려준|들려주|설명한|설명해|밝힌|말해준|수락|거절|동의|부인|되묻|인정한|털어놓|응한다|^(그렇|아니|맞[다소]|알겠|좋[다소])|(있다|없다|않겠다|하겠다|모른다|싶다)$")
for t in turn_logs:
    lcs = t.get("llmChoices") or []
    # 폴링 스냅샷 race 보정: 워커는 DONE 커밋 후 Track2가 llmChoices를 쓴다 —
    # DONE 즉시 반환한 poll_llm 스냅샷에는 선택지가 없을 수 있어 재조회한다.
    if not lcs and t.get("turnNo"):
        try:
            time.sleep(0.4)  # 연속 재조회 rate limit(429) 회피 — 2026-08-05 실측
            _st, _detail = api("GET", f"/runs/{run_id}/turns/{t['turnNo']}")
            lcs = (_detail.get("llm") or {}).get("choices") or []
            if not lcs:
                print(f"  [V13-debug] t{t['turnNo']} 재조회 무선택지 (status={_st})", flush=True)
        except Exception as _e:
            print(f"  [V13-debug] t{t.get('turnNo')} 재조회 예외: {_e}", flush=True)
            lcs = []
    labels = []
    for c in lcs:
        label = c.get("label", "")
        payload = (c.get("action") or {}).get("payload") or {}
        if payload.get("returnToHub") or "돌아간다" in label:
            continue  # go_hub 슬롯 제외
        labels.append(label)
        aff = payload.get("affordance")
        if aff:
            _aff_counts[aff] = _aff_counts.get(aff, 0) + 1
    # 질문 응답: 서술이 물음표 대사로 닫힌 턴만
    narr = (t.get("narrative") or "").rstrip()
    if labels and re.search(r'[?？]["”]?\s*$', narr):
        _q_turns += 1
        if any(_ANSWER_RE.search(l) for l in labels):
            _q_answered += 1
_aff_total = sum(_aff_counts.values())
choice_diversity_metrics = None
if _aff_total >= 6:  # nano 선택지 2턴분 미만이면 표본 부족
    _active = sum(n for a, n in _aff_counts.items() if a not in PASSIVE_AFFS)
    _passive = _aff_total - _active
    _active_ratio = _active / _aff_total
    _passive_ratio = _passive / _aff_total

    # [2026-08-07] V12 와 같은 이유로 다회 런 누적 판정 — 런당 선택지 27~36개라
    # 1개가 약 3%p 이고, 15% 선에서 ±1개가 통과/실패를 갈랐다.
    _v13_win = append_gate_ledger(
        "v13_ledger.json",
        {
            "runId": run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "server": _SERVER_HASH,
            "affTotal": _aff_total,
            "activeCount": _active,
        },
        pool_runs=V13_POOL_RUNS,
    )
    _v13_total = sum(r.get("affTotal", 0) for r in _v13_win)
    _v13_active = sum(r.get("activeCount", 0) for r in _v13_win)
    _v13_pool_active = _v13_active / _v13_total if _v13_total else 0.0
    # [2026-08-10] 소극 조건 삭제 — 소극 = 100% − 적극 이라 `적극 ≥15% AND
    #   소극 ≤80%` 는 `적극 ≥20%` 하나로 붕괴했고, 명시된 15% 임계가 도달 불가
    #   상태였다(누적 18%인데 FAIL 실측). 게이트는 목표치 아래에 두는 것이 정상이고
    #   arch/98 §4 의 목표가 "적극 축 20%±" 이므로 의도된 게이트 값은 15% 다.
    #   소극 비율은 계측·표시용으로만 남긴다.
    _v13_pool_passive = 1 - _v13_pool_active
    _v13_enough = len(_v13_win) >= V13_MIN_RUNS
    v13_pass = (_v13_pool_active >= 0.15) if _v13_enough else True

    choice_diversity_metrics = {
        "affCounts": _aff_counts,
        "activeRatio": round(_active_ratio, 3),
        "questionTurns": _q_turns,
        "questionAnswered": _q_answered,
        # 누적 판정 근거 (게이트가 실제로 보는 값)
        "pooledRuns": len(_v13_win),
        "pooledAffTotal": _v13_total,
        "pooledActiveCount": _v13_active,
        "pooledActiveRatio": round(_v13_pool_active, 3),
        "gateApplied": _v13_enough,
    }
    _dist = ", ".join(f"{a}:{n}" for a, n in sorted(_aff_counts.items(), key=lambda x: -x[1]))
    print(f"  affordance 분포: {_dist}", flush=True)
    print(f"  이번 런 적극 축: {_active_ratio*100:.0f}% · 소극 3종 {_passive_ratio*100:.0f}%", flush=True)
    print(f"  누적 판정({len(_v13_win)}런): 적극 {_v13_active}/{_v13_total} ({_v13_pool_active*100:.0f}%, 게이트 ≥15%) · 소극 {_v13_pool_passive*100:.0f}% (계측)", flush=True)
    if _q_turns:
        print(f"  질문 턴 응답 선택지: {_q_answered}/{_q_turns} (계측 전용 — 목표 70%+)", flush=True)
    if not _v13_enough:
        print(f"  ⚠️ 표본 부족({len(_v13_win)}/{V13_MIN_RUNS}런) — 게이트 보류(통과 처리)", flush=True)
    else:
        print("  ✅ 다양성 정상" if v13_pass else "  ❌ 편중 경보 — 적극 축 주입(P1) 점검 필요", flush=True)
else:
    v13_pass = True
    print(f"  ⚠️ nano 선택지 표본 부족 ({_aff_total}개) — 게이트 스킵", flush=True)

# Summary
print("\n" + "=" * 60, flush=True)
all_checks = {
    # V0 — 실행 턴 존재 게이트: 턴 0건이면 나머지 검증은 전부 무의미 (포인트
    # 소진·서버 다운 등으로 0턴인데 8/11 PASS 나던 false-PASS 방어, 2026-07-23)
    # [M1 감사 2026-08-12 — 체크리스트 C2] 기존은 `> 0` 이라 **부분 실행**을
    #   못 잡았다. 15턴 요청 → 3턴 사망도 통과하고, 그 얇은 표본으로 나머지
    #   게이트가 전부 PASS 를 찍는다 (분모가 작으면 위반도 안 나온다).
    #   엔딩 자연 종료는 정당하므로 예외. 그 외에는 요청 턴의 50% 이상 요구.
    "V0_turns_executed": len(turn_logs) > 0 and (
        _run_ended_naturally or len(turn_logs) >= MAX_TURNS * 0.5),
    "V1_incidents": len(incidents) > 0,
    "V2_encounter": enc_pass >= 2,
    "V3_posture": len(posture_none) == 0,
    "V4_emotion": emo_active > 0,
    "V5_memory": structured is not None and len((structured or {}).get("visitLog", [])) > 0,
    "V6_resolve": resolve_count > 0,
    "V7_no_leak": len(v7_issues) == 0,
    "V8_npc_match": len(v8_issues) == 0,
    # [arch/92 §8] 구 `len([i for i in v9_issues if "반복" in i]) <= 2` 는
    # ① 이슈 문면 substring 매칭이라 계측 항목이 게이트로 새고 ② 슬라이딩 윈도우
    # 중복 계수로 단일 반복이 3이슈가 되던 구조. 판정을 불린 하나로 확정한다.
    "V9_quality": not _rep_gate_failed,
    "V10_choice_npc_match": len(v10_issues) == 0,
    "V11_narrative_present": len(v11_issues) == 0,
    # V12 — 프롬프트 예산 재비대 가드 (arch/95 §6): 발동 추정률 ≤20% AND avg ≤15,000자
    "V12_prompt_budget": v12_pass,
    # V13 — 선택지 다양성 (arch/98): 적극 축 ≥15% AND 소극 3종 ≤80%
    "V13_choice_diversity": v13_pass,
}
passed = sum(1 for v in all_checks.values() if v)
print(f"종합: {passed}/{len(all_checks)} PASS", flush=True)
for k, v in all_checks.items():
    print(f"  {'✅' if v else '❌'} {k}", flush=True)
if len(turn_logs) == 0:
    print("❌ 하드 FAIL: 실행 턴 0건 — 종합 판정 무효 (포인트 잔액/서버 상태 확인)", flush=True)
elif len(turn_logs) < MAX_TURNS * 0.5:
    print(f"⚠️ 요청 턴수 미달: {len(turn_logs)}/{MAX_TURNS} — 표본 부족, 게이트 판정 주의", flush=True)

# ── 어휘 반복 계측 (2-B, arch/68 후속 — 판단용 상시 리포트, 게이트 아님) ──
_all_narr = " ".join((t.get("narrative") or "") for t in turn_logs)
_tokens = re.findall(r"[가-힣]{2,4}", _all_narr)
_STOP = {"있다", "있는", "있었", "당신", "그대", "그의", "그녀", "하는", "하며", "하고",
         "것이", "들이", "에서", "으로", "를", "그리고", "하지만", "듯이", "채로",
         "속에", "위로", "사이", "소리", "시선", "모습", "순간", "고개"}
_freq = {}
for _tk in _tokens:
    if _tk in _STOP:
        continue
    _freq[_tk] = _freq.get(_tk, 0) + 1
_top = sorted(_freq.items(), key=lambda x: -x[1])[:5]
print("\n어휘 반복 톱5 (계측):", ", ".join(f"{w}×{c}" for w, c in _top), flush=True)

# ── 에이전트 플레이어 위화감 노트 (--agent 모드) ──
if args.agent:
    print("\n" + "─" * 60, flush=True)
    print(f"에이전트 플레이어 리포트 (persona={args.agent}, model={args.agent_model})", flush=True)
    print("─" * 60, flush=True)
    if agent_notes:
        for n in agent_notes:
            print(f"  ⚠️ T{n['turn']}: {n['note']}", flush=True)
    else:
        print("  ✅ 위화감 노트 없음", flush=True)
    if agent_parse_fail:
        print(f"  (에이전트 응답 파싱 실패 {agent_parse_fail}회 — 무작위 fallback)", flush=True)

# ═══════════════════════════════════════
# 4.5 서사 방향 계측 (D4 + D1-c, arch/76 — 판단용 상시 리포트, 게이트 아님)
# ═══════════════════════════════════════
print("\n" + "─" * 60, flush=True)
print("서사 방향 계측 (D4 + D1-c, arch/76)", flush=True)
print("─" * 60, flush=True)
from collections import Counter

def _word_ngrams(text, n=3):
    """@마커 제거 후 한글 토큰 word n-gram 집합"""
    toks = re.findall(r"[가-힣]{2,}", re.sub(r"@\[[^\]]+\]", "", text or ""))
    return set(tuple(toks[i:i+n]) for i in range(len(toks) - n + 1))

# D4-1: 서술 n-gram 반복률 — 턴 간 3-gram 중복 비율 + 인접 턴 자카드 유사도
_turn_tris = [(t["turn"], _word_ngrams(t.get("narrative", ""))) for t in turn_logs if t.get("narrative")]
_tri_seen = {}
for _tn, _tg in _turn_tris:
    for _g in _tg:
        _tri_seen.setdefault(_g, set()).add(_tn)
_tri_total = len(_tri_seen)
_tri_repeated = sum(1 for _turns in _tri_seen.values() if len(_turns) >= 2)
trigram_repeat_ratio = _tri_repeated / _tri_total if _tri_total else 0.0
_jac_pairs = []
for (_, a), (_, b) in zip(_turn_tris, _turn_tris[1:]):
    if a or b:
        _jac_pairs.append(len(a & b) / len(a | b))
adjacent_jaccard = sum(_jac_pairs) / len(_jac_pairs) if _jac_pairs else 0.0
print(f"[D4-1] 서술 3-gram 반복률: {trigram_repeat_ratio:.3f} ({_tri_repeated}/{_tri_total}) · 인접 턴 자카드 평균: {adjacent_jaccard:.3f}", flush=True)

# D4-2: 이벤트·premise 다양성 — 매칭 소스 히스토그램 + distinct 비율
_EVT_PREFIXES = ["BEAT_", "SIT_", "PROC_", "EVT_", "FREE_PLAYER_", "FREE_CONV_"]
_src_hist = Counter()
_evt_ids = []
for t in turn_logs:
    if t.get("nodeType") != "LOCATION" or not t.get("eventId"):
        continue
    eid = t["eventId"]
    _evt_ids.append(eid)
    _src = next((p.rstrip("_") for p in _EVT_PREFIXES if eid.startswith(p)), "OTHER")
    _src_hist[_src] += 1
distinct_event_ratio = len(set(_evt_ids)) / len(_evt_ids) if _evt_ids else 0.0
print(f"[D4-2] 이벤트 소스 분포: {dict(_src_hist)} · distinct 비율: {distinct_event_ratio:.2f}", flush=True)

# D4-3 (2026-07-17 재조준): 구 '억제 위반' 계측 폐기 — playerThreads는 플레이어
#   행동 카운터(장소×접근×목표, 엔딩 성향 요약 소비)라 신규 생성은 위반이 아니라
#   행동 다양성이다. 서사가 벌린 떡밥의 미해소는 사건(incident) 축이 정본.
#   교체: ① 스레드 상태 분포(정보성 — COMPLETED 정산 배선 후 유의미)
#         ② 미해소 사건 공존 수 (서사 방향 감시의 본래 의도)
_threads = world_state.get("playerThreads", []) or []
_UNRESOLVED = {"EMERGING", "ACTIVE"}
from collections import Counter as _Counter
_status_dist = _Counter(_t.get("status", "?") for _t in _threads)
_approach_kinds = len({_t.get("approachVector") for _t in _threads})
_open_incidents = sum(1 for _i in (world_state.get("activeIncidents") or []) if not _i.get("resolved"))
print(f"[D4-3] 행동 스레드: 총 {len(_threads)}개 · 상태 {dict(_status_dist)} · 접근 다양성 {_approach_kinds}종 (정보성)", flush=True)
print(f"[D4-3b] 미해소 사건 공존: {_open_incidents}건" + (" ⚠️ 3건+ — 떡밥 과적 신호" if _open_incidents >= 3 else ""), flush=True)

# D4-4 + D1-c: 자율 팩 — 무진행 감시 + 의도 정합 채택률 (AUTHORED 런은 데이터 없음)
_plot_progress = run_state.get("plotProgress") or {}
_adoptions = _plot_progress.get("beatAdoptions") or []
_adopted_n = _plot_progress.get("adoptedBeatCount", 0)
_discarded_n = _plot_progress.get("discardedBeatCount", 0)
_key_facts_n = len(_plot_progress.get("discoveredKeyFactIds", []))
intent_alignment_rate = None
_stall_flag = False
_premise_diversity = None
if _adopted_n or _discarded_n or _adoptions:
    _al_true = sum(1 for a in _adoptions if a.get("aligned") is True)
    _al_false = sum(1 for a in _adoptions if a.get("aligned") is False)
    _al_neutral = sum(1 for a in _adoptions if a.get("aligned") is None)
    if _al_true + _al_false:
        intent_alignment_rate = _al_true / (_al_true + _al_false)
    # 무진행 감시: 비트는 채택되는데 keyFact 발견 0 → "무한 생성·무진행" 신호
    _stall_flag = _adopted_n >= 3 and _key_facts_n == 0
    # premise 다양성: 채택 premise 간 2-gram 자카드 평균 (낮을수록 다양)
    _prem_grams = [_word_ngrams(a.get("premise", ""), 2) for a in _adoptions if a.get("premise")]
    if len(_prem_grams) >= 2:
        _pj = [len(a & b) / len(a | b) for i, a in enumerate(_prem_grams) for b in _prem_grams[i+1:] if a or b]
        _premise_diversity = 1 - (sum(_pj) / len(_pj)) if _pj else None
    print(f"[D4-4] 자율 진행: 비트 채택 {_adopted_n} · 폐기 {_discarded_n} · keyFact 발견 {_key_facts_n}" + (" · ⚠️ 무진행 신호(채택 3+ & fact 0)" if _stall_flag else ""), flush=True)
    _rate_str = f"{intent_alignment_rate:.0%}" if intent_alignment_rate is not None else "N/A(전부 행동 무관)"
    print(f"[D1-c] 의도 정합 채택률: {_rate_str} (일치 {_al_true} / 불일치 {_al_false} / 무관 {_al_neutral})" + (f" · premise 다양성: {_premise_diversity:.2f}" if _premise_diversity is not None else ""), flush=True)
    for a in _adoptions:
        print(f"  T{a.get('turnNo')}: {a.get('beatId')} action={a.get('actionType')} aligned={a.get('aligned')} — {(a.get('premise') or '')[:40]}", flush=True)
else:
    print(f"[D4-4/D1-c] 자율 팩 데이터 없음 (AUTHORED 런 또는 비트 미발화)", flush=True)

# D5: 지칭 명사구 반복 + 대명사 개시어율 (서술 품질 사이클 2026-07-18)
#   ① 대명사 개시어율 — 서버 extractOverusedOpeners와 동일 전처리(마커 대사·인용
#      제거, [.!?…다] 문장 분리, 첫 단어 한글 2+자)를 재현하되, 대명사 화이트리스트
#      계열을 1키로 합산해 측정한다 (서버 패치 전/후 비교 기준 지표).
#   ② 지칭 명사구 반복 — 주어형 토큰(은/는/이/가 조사 제거 stem)을 런 전체 누적으로
#      집계해 3회+ 반복을 보고. 분류: CONTENT_ALIAS(콘텐츠 별칭·실명 풀 매칭) /
#      NON_ALIAS(즉흥 지칭·일반 명사 후보 — 사람 지칭 여부는 리포트 검토로 판정).
#      판단용 상시 리포트이며 게이트 아님. 별칭 풀은 V9-c의 _npc_alias_pool 재사용
#      (로드 실패 시 전량 NON_ALIAS로 보고됨에 유의).
# [arch/92 §8] _PRONOUN_OPENERS / _PRONOUN_STEMS 는 V9 앞 공용 상수 블록으로
# 이동 — V9 반복 센서와 정본을 공유한다 (구: D5 지역 정의라 V9이 대명사를
# 게이트로 이중 처벌).
_d5_sent_total = 0
_d5_pronoun_initial = 0
_d5_opener_counts = Counter()
_d5_stem_counts = Counter()
for _t in turn_logs:
    _txt = _t.get("narrative", "")
    if not _txt:
        continue
    # 서버 전처리 재현: 마커+대사 → 인용 제거
    _narr = re.sub(r'@\[[^\]]*\]\s*"[^"]*"', "", _txt)
    _narr = re.sub(r'"[^"]*"', "", _narr)
    _narr = re.sub(r"@\[[^\]]*\]", "", _narr)
    for _raw in re.split(r"(?<=[.!?…다])\s+", _narr):
        _s = _raw.strip()
        if len(_s) < 6:
            continue
        _first = _s.split()[0] if _s.split() else ""
        if not re.match(r"^[가-힣]{2,}", _first):
            continue
        _d5_sent_total += 1
        if _first in _PRONOUN_OPENERS:
            _d5_pronoun_initial += 1
            _d5_opener_counts["그/그녀(대명사)"] += 1
        else:
            _d5_opener_counts[_first] += 1
    # 주어형 stem 집계 (조사 앞 한글 2~6자)
    for _stem in re.findall(r"([가-힣]{2,6})(?:은|는|이|가)\s", _narr):
        if _stem in _PRONOUN_STEMS:
            continue
        _d5_stem_counts[_stem] += 1
pronoun_opener_rate = _d5_pronoun_initial / _d5_sent_total if _d5_sent_total else 0.0
_d5_opener_top = _d5_opener_counts.most_common(5)
print(f"[D5-1] 대명사 개시어율: {pronoun_opener_rate:.1%} ({_d5_pronoun_initial}/{_d5_sent_total}) · top 개시어: " + ", ".join(f"{k}×{v}" for k, v in _d5_opener_top), flush=True)
_d5_referent_repeats = []
for _stem, _n in _d5_stem_counts.most_common():
    if _n < 3:
        break
    _cls = "CONTENT_ALIAS" if any(_stem == _a or _stem in _a or _a in _stem for _a in _npc_alias_pool) else "NON_ALIAS"
    _d5_referent_repeats.append({"stem": _stem, "count": _n, "cls": _cls})
if _d5_referent_repeats:
    _d5_top10 = _d5_referent_repeats[:10]
    print("[D5-2] 지칭/명사 반복 (런 누적 3회+, top 10): " + ", ".join(f"{r['stem']}({'C' if r['cls'] == 'CONTENT_ALIAS' else 'N'},{r['count']})" for r in _d5_top10), flush=True)
    _d5_non_alias_max = max((r["count"] for r in _d5_referent_repeats if r["cls"] == "NON_ALIAS"), default=0)
    if _d5_non_alias_max >= 3:
        print(f"  ↳ NON_ALIAS 3회+ 존재 — 즉흥 지칭 후보 검토 필요 (착수 트리거 후보)", flush=True)
else:
    print("[D5-2] 지칭/명사 반복 3회+ 없음", flush=True)

direction_metrics = {
    "trigramRepeatRatio": trigram_repeat_ratio,
    "adjacentJaccard": adjacent_jaccard,
    "eventSourceHistogram": dict(_src_hist),
    "distinctEventRatio": distinct_event_ratio,
    "threadTotal": len(_threads),
    "threadUnresolved": sum(1 for _t in _threads if _t.get("status") in _UNRESOLVED),
    "threadStatusDist": dict(_status_dist),
    "threadApproachKinds": _approach_kinds,
    "openIncidents": _open_incidents,
    "beatAdopted": _adopted_n,
    "beatDiscarded": _discarded_n,
    "keyFactsDiscovered": _key_facts_n,
    "beatStallFlag": _stall_flag,
    "intentAlignmentRate": intent_alignment_rate,
    "premiseDiversity": _premise_diversity,
    "beatAdoptions": _adoptions,
    "pronounOpenerRate": pronoun_opener_rate,
    "sentenceTotal": _d5_sent_total,
    "openerTop": [{"opener": k, "count": v} for k, v in _d5_opener_top],
    "referentRepeats": _d5_referent_repeats,
}

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
        # [arch/92 §8] 실행 팩 기록 — 없으면 사후 리포트 분석에서 어느 팩 런인지
        # 알 수 없어 콘텐츠 파생 판정(별칭·지명)을 재현할 수 없다 (77런 회고 시 실측).
        "scenario": _PACK_ID,
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
    "promptBudget": prompt_budget_metrics,
    "narrativeMetrics": narrative_metrics,
    "outcomeDistribution": outcome_distribution,
    "directionMetrics": direction_metrics,
    "agentPlay": (
        {
            "persona": args.agent,
            "model": args.agent_model,
            "notes": agent_notes,
            "parseFailures": agent_parse_fail,
        }
        if args.agent
        else None
    ),
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

# V0 하드 FAIL — 0턴 실행은 exit 1 (CI/자동화에서 침묵 통과 방지)
if len(turn_logs) == 0:
    sys.exit(1)
