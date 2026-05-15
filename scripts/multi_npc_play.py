#!/usr/bin/env python3
"""
보조 NPC 끼어들기 억제 검증용 다중 NPC 플레이테스트 (architecture/57).

before 로그(playtest-reports/multi_npc_play_20260514_065449.json)와 동일한 입력 시퀀스로
2~3명 NPC를 실측 — 보조 NPC 발화 빈도 / 동일 보조 NPC 연속 발화 / 메인 NPC 응답 유지 비교용.

사용법:
  python3 scripts/multi_npc_play.py --output playtest-reports/multi_npc_play_after.json
"""

import argparse
import json
import sys
import time
import uuid
import re
from typing import Optional

import requests

# ── CLI ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://localhost:3000/v1")
parser.add_argument("--output", default=f"playtest-reports/multi_npc_play_after_{int(time.time())}.json")
parser.add_argument(
    "--targets",
    default="edric,harlun,ronen",
    help="콤마 구분: edric, harlun, jwiwang, ronen 중 선택",
)
parser.add_argument(
    "--dump-prompt",
    action="store_true",
    help="첫 eval 턴의 LLM 프롬프트를 stderr 에 덤프 (focused 모드 진단용)",
)
args = parser.parse_args()

BASE = args.base


# ── NPC 시나리오 ─────────────────────────────────────────────────
# before 로그와 동일 인풋 시퀀스 — 직접 비교 가능
SCENARIOS = {
    "edric": {
        "name": "에드릭 베일(시장 회계사)",
        "target": "에드릭 베일",
        "targetHints": ["에드릭", "회계사", "날카로운 눈매"],
        "location_choice_kw": ["market", "market"],
        "approach": "은장부 상단의 회계사에게 다가간다",
        "evals": [
            ("일 인사", "안녕하시오. 장부 정리는 오늘도 바쁘시오?"),
            ("전문 질문", "숫자가 자꾸 어긋난다면 어디부터 의심하시오?"),
            ("개인 압박", "도박 빚 이야기를 들었소. 그게 장부 일과 관계 있소?"),
            ("위협", "협조하지 않으면 당신 이름이 먼저 오르내릴 것이오."),
            ("완화/연속성", "흥분시키려던 건 아니오. 방금 말한 장부 이야기만 분명히 하고 싶소."),
        ],
    },
    "harlun": {
        "name": "하를런 보스(항만)",
        "target": "하를런 보스",
        "targetHints": ["하를런", "보스", "투박한 노동자"],
        "location_choice_kw": ["harbor", "harbor"],
        "approach": "부두를 감독하는 거구 노동자에게 다가간다",
        "evals": [
            ("부두 일", "안녕하시오. 부두 일은 요즘 어떻소?"),
            ("개인/복서", "예전에 복서였다고 들었소. 아직도 주먹이 먼저 나가오?"),
            ("장부 질문", "형제단 사람들 중 장부를 본 자가 있소?"),
            ("위협", "숨기는 게 있다면 힘으로라도 듣겠소."),
            ("완화/연속성", "방금은 거칠었소. 그래도 형제단의 안전을 위해 묻는 것이오."),
        ],
    },
    "jwiwang": {
        "name": "쥐왕(빈민가)",
        "target": "쥐왕",
        "targetHints": ["쥐왕", "두건 쓴 사내"],
        "location_choice_kw": ["slums", "slums"],
        "approach": "두건 쓴 사내에게 다가간다",
        "evals": [
            ("영역 질문", "안녕하시오. 이곳 빈민가 분위기는 어떻소?"),
            ("과거", "예전엔 상인이셨다는 이야기를 들었소."),
            ("정보망/장부", "윗동네 권력자들이 장부를 숨긴다면 당신 정보망은 알 수 있소?"),
            ("위협", "계속 모른 척하면 거래가 아니라 압박으로 바뀔 것이오."),
            ("연속성", "아까 상인 시절 이야기를 했지요. 그래서 거래의 셈법으로 다시 묻겠소."),
        ],
    },
    # 로넨: 항만 노동 길드 서기관(의뢰자). 항만으로 이동 후 다시 찾아가 대화.
    # HUB choices: go_market/go_guard/go_harbor/go_slums — 로넨은 LABOR_GUILD 소속이므로 harbor 우선.
    "ronen": {
        "name": "로넨(의뢰자, 항만)",
        "target": "로넨",
        "targetHints": ["로넨", "서기관", "초조한"],
        "location_choice_kw": ["harbor"],
        "approach": "초조한 서기관 로넨을 찾아 다가간다",
        "evals": [
            ("사건 재확인", "장부가 정확히 언제 사라졌소?"),
            ("동선 추적", "그대가 그 장부를 마지막으로 본 시점은 언제요?"),
            ("위험 인지", "도난 사실을 상부에 보고하지 못한 이유가 무엇이오?"),
            ("의심/압박", "솔직히 말해 보시오. 진짜로 도난당한 게 맞소?"),
            ("위로/연속성", "방금 조금 거칠게 물었소. 그래도 끝까지 살펴주겠소."),
        ],
    },
}


# ── HTTP helpers ─────────────────────────────────────────────────
session = requests.Session()


def api(method: str, path: str, body=None, timeout: int = 30):
    try:
        r = session.request(method, f"{BASE}{path}", json=body, timeout=timeout)
        return r.status_code, (r.json() if r.text else {})
    except Exception as e:
        return 0, {"error": str(e)}


def poll_llm(run_id: str, turn_no: int, max_wait: int = 90) -> dict:
    start = time.time()
    while time.time() - start < max_wait:
        _, data = api("GET", f"/runs/{run_id}/turns/{turn_no}")
        llm = data.get("llm", {}) or {}
        s = llm.get("status", "")
        if s == "DONE":
            return {"status": "DONE", "text": llm.get("output") or "", "events": data.get("serverResult", {}).get("events", [])}
        if s in ("FAILED", "SKIPPED"):
            return {"status": s, "text": "", "events": []}
        time.sleep(2)
    return {"status": "TIMEOUT", "text": "", "events": []}


def auth_and_run() -> tuple[str, str, int]:
    email = f"npc_play_{uuid.uuid4().hex[:8]}@test.com"
    password = "Test1234!!"
    status, resp = api("POST", "/auth/register", {"email": email, "password": password, "nickname": "Tester"})
    if status != 201:
        status, resp = api("POST", "/auth/login", {"email": email, "password": password})
    token = resp.get("token")
    if not token:
        print(f"auth fail: {resp}", flush=True)
        sys.exit(1)
    session.headers["Authorization"] = f"Bearer {token}"
    status, resp = api("POST", "/runs", {"presetId": "DESERTER", "gender": "male"})
    if status not in (200, 201):
        print(f"run create fail: {status} {resp}", flush=True)
        sys.exit(1)
    run_id = resp["run"]["id"]
    current = resp["run"].get("currentTurnNo", 1)
    return token, run_id, current


def find_choice(choices, *keywords) -> Optional[dict]:
    for c in choices:
        cid = (c.get("id") or "").lower()
        label = (c.get("label") or "").lower()
        for kw in keywords:
            if kw in cid or kw in label:
                return c
    return None


def submit(run_id: str, current_turn: int, body) -> tuple[int, dict, int]:
    """expectedNextTurnNo 충돌 시 재시도. 반환: (status, resp, new_current)"""
    idem = str(uuid.uuid4())
    body = {**body, "expectedNextTurnNo": current_turn + 1, "idempotencyKey": idem}
    status, resp = api("POST", f"/runs/{run_id}/turns", body)
    if status == 409:
        expected = resp.get("details", {}).get("expected", current_turn + 1)
        body["expectedNextTurnNo"] = expected
        body["idempotencyKey"] = str(uuid.uuid4())
        status, resp = api("POST", f"/runs/{run_id}/turns", body)
    submitted = resp.get("turnNo", current_turn + 1)
    return status, resp, submitted


# ── 유틸: 서술에서 발화자/대사 추출 ───────────────────────────────
MARKER_RE = re.compile(r"@\[([^\]|]+)(?:\|[^\]]*)?\]\s*[\"“]([^\"”]+)[\"”]")


def extract_utterances(text: str) -> list[dict]:
    items = []
    for m in MARKER_RE.finditer(text):
        items.append({"speaker": m.group(1).strip(), "line": m.group(2).strip()})
    return items


def is_target_speaker(speaker: str, hints: list[str]) -> bool:
    return any(h in speaker for h in hints)


# ── 시나리오 1개 실행 ────────────────────────────────────────────
def run_scenario(scenario_key: str) -> dict:
    scen = SCENARIOS[scenario_key]
    print(f"\n=== {scen['name']} ===", flush=True)
    _, run_id, current = auth_and_run()

    logs: list[dict] = []

    def log_turn(phase, label, input_desc, narrative, status, events):
        utterances = extract_utterances(narrative)
        logs.append(
            {
                "phase": phase,
                "label": label,
                "input": input_desc,
                "turnNo": current,
                "status": status,
                "text": narrative,
                "utterances": utterances,
                "events": [
                    f"{e.get('payload', {}).get('npcName', '?')}이(가) "
                    f"{e.get('payload', {}).get('description', '?')}"
                    if e.get("kind") == "NPC"
                    else f"{e.get('kind')}:{e.get('payload', {}).get('description', '')[:30]}"
                    for e in events
                ][:10],
            }
        )

    # setup turns: accept_quest → move location → approach
    # location_choice_kw / approach 가 None 이면 해당 단계 스킵 (예: 로넨 — 의뢰 수락 후 그 자리에서 바로 대화)
    setup_inputs: list = [
        ("setup", "의뢰 수락", ("choice", "accept", "quest")),
    ]
    if scen.get("location_choice_kw"):
        setup_inputs.append(
            ("setup", "장소 이동", ("choice", *scen["location_choice_kw"]))
        )
    if scen.get("approach"):
        setup_inputs.append(("setup", "첫 접근", ("action", scen["approach"])))

    for phase, label, instr in setup_inputs:
        if instr is None:
            continue
        _, state = api("GET", f"/runs/{run_id}")
        current = state.get("run", {}).get("currentTurnNo", current)
        node_type = state.get("currentNode", {}).get("nodeType", "")
        choices = state.get("lastResult", {}).get("choices", [])

        if instr[0] == "choice":
            target = find_choice(choices, *instr[1:])
            if not target and choices:
                target = choices[0]
            if not target:
                # 이미 LOCATION이면 ACTION으로 fallback
                status, resp, submitted = submit(
                    run_id,
                    current,
                    {"input": {"type": "ACTION", "text": "주변을 살핀다"}},
                )
                input_desc = "ACTION:주변을 살핀다(fallback)"
            else:
                status, resp, submitted = submit(
                    run_id,
                    current,
                    {"input": {"type": "CHOICE", "choiceId": target.get("id", "")}},
                )
                input_desc = f"CHOICE:{target.get('id', '')}"
        else:
            text = instr[1]
            status, resp, submitted = submit(
                run_id, current, {"input": {"type": "ACTION", "text": text}}
            )
            input_desc = text

        if status not in (200, 201):
            print(f"  [setup-fail] {label}: {status}", flush=True)
            continue

        llm = poll_llm(run_id, submitted)
        log_turn(phase, label, input_desc, llm["text"], llm["status"], llm["events"])
        print(f"  [setup T{submitted}] {label}: {llm['status']}", flush=True)
        current = submitted

    # eval 직전 state 진단 — 로넨 같이 setup 단계 적은 시나리오에서 422 원인 추적용
    _, pre_eval_state = api("GET", f"/runs/{run_id}")
    pre_node = pre_eval_state.get("currentNode", {})
    pre_run = pre_eval_state.get("run", {})
    pre_choices = pre_eval_state.get("lastResult", {}).get("choices", [])
    choice_labels = [(c.get("id"), c.get("label", "")[:40]) for c in pre_choices]
    print(
        f"  [pre-eval state] turn={pre_run.get('currentTurnNo')} "
        f"node={pre_node.get('nodeType')!r} choices={choice_labels}",
        flush=True,
    )
    # 다른 시나리오와의 호환을 위해 current를 state 값으로 갱신
    current = pre_run.get("currentTurnNo", current)

    # eval turns (5개 dialogue) — focused 모드 적용 여부도 함께 측정
    SOCIAL_FOCUSED_ACTIONS = {
        "TALK",
        "PERSUADE",
        "BRIBE",
        "THREATEN",
        "HELP",
        "INVESTIGATE",
        "TRADE",
    }
    first_eval = True
    for label, text in scen["evals"]:
        status, resp, submitted = submit(
            run_id, current, {"input": {"type": "ACTION", "text": text}}
        )
        if status not in (200, 201):
            # 422 등 원인 진단을 위해 응답 body 1줄로 노출
            err_msg = (
                resp.get("message")
                or resp.get("error")
                or resp.get("details")
                or str(resp)[:160]
            )
            print(f"  [eval-fail] {label}: {status} — {err_msg}", flush=True)
            continue
        llm = poll_llm(run_id, submitted, max_wait=120)
        # focused 모드 적용 여부 — actionContext 의 actionType/parsedType + primaryNpcId 로 추정.
        _, debug_resp = api("GET", f"/runs/{run_id}/turns/{submitted}")
        ac = (debug_resp.get("serverResult", {}) or {}).get("ui", {}).get(
            "actionContext", {}
        ) or {}
        primary_npc_id = ac.get("primaryNpcId")
        action_kind = ac.get("actionType") or ac.get("parsedType") or ""
        approach = ac.get("approachVector") or ""
        turn_mode = ac.get("turnMode") or ""
        focused_active = bool(primary_npc_id) and (
            action_kind in SOCIAL_FOCUSED_ACTIONS
            or approach == "SOCIAL"
            or turn_mode == "CONVERSATION_CONT"
        )
        log_entry = {
            "primaryNpcId": primary_npc_id,
            "actionType": action_kind,
            "approachVector": approach,
            "turnMode": turn_mode,
            "focusedActive": focused_active,
        }
        log_turn("eval", label, text, llm["text"], llm["status"], llm["events"])
        # 직전에 append한 log 에 focused 메타 부착
        logs[-1]["focused"] = log_entry
        utt_count = len(extract_utterances(llm["text"]))
        print(
            f"  [eval T{submitted}] {label}: {llm['status']} | "
            f"focused={'ON' if focused_active else 'off'} ({action_kind or '-'}) "
            f"utterances={utt_count}",
            flush=True,
        )

        # 첫 eval 턴: focused 모드 진단용 프롬프트 덤프
        if first_eval and args.dump_prompt:
            _, debug_resp = api("GET", f"/runs/{run_id}/turns/{submitted}?includeDebug=true")
            dbg = debug_resp.get("debug", {}) or {}
            prompt = dbg.get("llmPrompt")
            ac = debug_resp.get("serverResult", {}).get("ui", {}).get("actionContext", {})
            sys.stderr.write(f"\n=== PROMPT DUMP T{submitted} ({scenario_key}) ===\n")
            sys.stderr.write(f"actionContext: primaryNpcId={ac.get('primaryNpcId')!r} actionType={ac.get('actionType')!r} targetNpcId={ac.get('targetNpcId')!r}\n")
            if isinstance(prompt, list):
                full = "\n=====\n".join(m.get("content", "") for m in prompt)
                for kw in [
                    "[1인 응답 강제",
                    "[대화 연속 상태",
                    "[NPC 관계",
                    "현재 관계",
                    "이 장소에 있는 인물",
                    "직전 턴에 이미 끼어든",
                    "조용한 문서 실무자",
                    "라이라 케스텔",
                ]:
                    if kw in full:
                        i = full.find(kw)
                        sys.stderr.write(f"  >>> FOUND '{kw}' at idx {i}\n")
                        sys.stderr.write(f"      {full[max(0,i-60):i+260].replace(chr(10),' / ')}\n")
                    else:
                        sys.stderr.write(f"  !!! NOT FOUND '{kw}'\n")
            else:
                sys.stderr.write(f"  llmPrompt type: {type(prompt).__name__}\n")
            sys.stderr.flush()
            first_eval = False

        current = submitted

    # ── score: 보조 NPC 끼어들기 메트릭 ──
    #   focused 모드 ON 턴에서의 보조 발화 = 위반(violation)
    #   focused OFF 턴에서의 보조 발화 = 허용(neutral) — 분위기 묘사 등 합법 끼어들기
    eval_logs = [l for l in logs if l["phase"] == "eval"]
    hints = scen["targetHints"]
    target_utt = 0
    aux_utt = 0
    aux_utt_violations = 0  # focused ON 턴에서의 보조 발화
    aux_utt_neutral = 0     # focused OFF 턴에서의 보조 발화
    focused_on_turns = 0
    focused_off_turns = 0
    aux_speakers_by_turn: list[list[str]] = []
    aux_speaker_freq: dict[str, int] = {}
    aux_violator_freq: dict[str, int] = {}  # focused 위반 인물 빈도
    for el in eval_logs:
        focused_active = bool((el.get("focused") or {}).get("focusedActive"))
        if focused_active:
            focused_on_turns += 1
        else:
            focused_off_turns += 1
        turn_aux: list[str] = []
        for u in el.get("utterances", []):
            sp = u.get("speaker", "")
            if is_target_speaker(sp, hints):
                target_utt += 1
            else:
                aux_utt += 1
                turn_aux.append(sp)
                aux_speaker_freq[sp] = aux_speaker_freq.get(sp, 0) + 1
                if focused_active:
                    aux_utt_violations += 1
                    aux_violator_freq[sp] = aux_violator_freq.get(sp, 0) + 1
                else:
                    aux_utt_neutral += 1
        aux_speakers_by_turn.append(turn_aux)

    # 동일 보조 NPC 연속(2턴+) 발화 카운트
    consecutive_runs: list[tuple[str, int]] = []  # (speaker, length)
    prev: Optional[str] = None
    run_len = 0
    for turn_aux in aux_speakers_by_turn:
        # 한 턴에 여러 명 있으면 첫 명 기준
        cur = turn_aux[0] if turn_aux else None
        if cur and cur == prev:
            run_len += 1
        else:
            if prev and run_len >= 2:
                consecutive_runs.append((prev, run_len))
            prev = cur
            run_len = 1 if cur else 0
    if prev and run_len >= 2:
        consecutive_runs.append((prev, run_len))

    score = {
        "evalTurns": len(eval_logs),
        "targetUtteranceCount": target_utt,
        "auxUtteranceCount": aux_utt,
        # architecture/57 핵심 메트릭 — focused 모드 적용 후 보조 끼어들기 위반/허용 분리
        "focusedOnTurns": focused_on_turns,
        "focusedOffTurns": focused_off_turns,
        "auxUtteranceViolations": aux_utt_violations,
        "auxUtteranceNeutral": aux_utt_neutral,
        "auxViolatorFreq": aux_violator_freq,
        "violationRate": (
            round(aux_utt_violations / focused_on_turns, 3)
            if focused_on_turns > 0
            else None
        ),
        "evalTurnsWithAuxInterjection": sum(1 for x in aux_speakers_by_turn if x),
        "auxSpeakerFreq": aux_speaker_freq,
        "consecutiveAuxRuns": [
            {"speaker": s, "length": n} for s, n in consecutive_runs
        ],
        "targetMainResponseTurns": sum(
            1
            for el in eval_logs
            if any(is_target_speaker(u.get("speaker", ""), hints) for u in el.get("utterances", []))
        ),
    }

    return {
        "id": scenario_key,
        "name": scen["name"],
        "target": scen["target"],
        "targetHints": hints,
        "runId": run_id,
        "logs": logs,
        "score": score,
    }


# ── main ─────────────────────────────────────────────────────────
def main():
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    for t in targets:
        if t not in SCENARIOS:
            print(f"unknown target: {t} (valid: {list(SCENARIOS.keys())})", flush=True)
            sys.exit(1)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results = []
    for t in targets:
        results.append(run_scenario(t))

    out = {"server": BASE, "startedAt": started_at, "results": results}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n=== saved → {args.output} ===", flush=True)

    # ── summary ──
    print("\n=== 보조 NPC 끼어들기 메트릭 요약 (architecture/57) ===", flush=True)
    for r in results:
        s = r["score"]
        print(f"\n{r['name']}")
        print(f"  - eval turns: {s['evalTurns']} (focused ON {s['focusedOnTurns']} / OFF {s['focusedOffTurns']})")
        print(f"  - 메인 NPC 응답 턴 수: {s['targetMainResponseTurns']}/{s['evalTurns']}")
        print(f"  - 메인 NPC utterance 합계: {s['targetUtteranceCount']}")
        print(f"  - 보조 NPC utterance 합계: {s['auxUtteranceCount']}  (위반 {s['auxUtteranceViolations']} / 허용 {s['auxUtteranceNeutral']})")
        rate = s['violationRate']
        rate_s = f"{rate:.3f}" if rate is not None else "N/A"
        print(f"  - focused 위반률(위반/ON턴): {rate_s}")
        print(f"  - 위반 인물 빈도(focused ON 턴): {s['auxViolatorFreq']}")
        print(f"  - 보조 NPC 끼어든 턴 수: {s['evalTurnsWithAuxInterjection']}/{s['evalTurns']}")
        print(f"  - 보조 NPC 전체 빈도: {s['auxSpeakerFreq']}")
        print(f"  - 동일 보조 NPC 2턴+ 연속: {s['consecutiveAuxRuns']}")


if __name__ == "__main__":
    main()
