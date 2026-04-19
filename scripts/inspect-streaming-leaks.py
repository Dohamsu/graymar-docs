#!/usr/bin/env python3
"""
스트리밍 도중 시스템 문자 노출 감지기.

턴 제출 직후 SSE 스트림에 접속하여, 토큰 수신마다 누적 buffer snapshot을
취하고 시스템 문자 패턴(@[...], @마커, [NPC_ID], [UNMATCHED], [THREAD] 등)이
중간에 잠깐이라도 나타났는지 기록한다.

최종 정리본(buffer 끝)과 타이핑 도중 상태를 모두 저장해 비교 가능.

사용법:
  python3 scripts/inspect-streaming-leaks.py --turns 5
"""
import argparse, json, re, sys, time, uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", flush=True); sys.exit(1)

BASE = "http://localhost:3000/v1"

# 타이핑 도중 "보이면 안 되는" 시스템 문자 패턴들
LEAK_PATTERNS = [
    (r'@\[[^\]]*\]', 'complete_marker'),       # 완성된 @[...] — 정상이지만 렌더 전 잠깐 노출 가능
    (r'@\[[^\]]*$', 'partial_marker'),          # 잘린 @[... — 타이핑 중에만 나타남
    (r'@마커', 'literal_marker_keyword'),
    (r'@NPC_[A-Z_0-9]+', 'raw_npc_id'),
    (r'\[NPC_[A-Z_0-9]+\]', 'bracket_npc_id'),
    (r'\[UNMATCHED\]', 'unmatched_tag'),
    (r'\[THREAD\]|\[/THREAD\]', 'thread_tag'),
    (r'\[MEMORY\]|\[/MEMORY\]', 'memory_tag'),
    (r'\[CHOICES\]', 'choices_tag'),
    (r'</?s>|<\|[^|]*\|>', 'special_token'),
    (r'(?:^|[^@])\[[^\]|]+\|/npc-portraits/', 'raw_portrait_marker'),
    (r'\[참고 선택지\]|\[서술|\[직전 NPC', 'system_section_header'),
]

PRESET = "DESERTER"
ACTIONS = [
    "주변을 살펴본다",
    "사람들에게 말을 건다",
    "골목을 조심스럽게 통과한다",
    "수상한 곳을 조사한다",
    "상인에게 가격을 물어본다",
]


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def api(method, path, body=None, token=None, timeout=30):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{BASE}{path}", json=body, headers=h, timeout=timeout)
    if not r.ok:
        log(f"{method} {path} {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
    return r.json() if r.text else {}


def register_login():
    email = f"leak_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.com"
    try:
        d = api("POST", "/auth/register", {"email": email, "password": "Test1234!!", "nickname": "Leak"})
    except requests.HTTPError:
        d = api("POST", "/auth/login", {"email": email, "password": "Test1234!!"})
    return d["token"]


def create_run(token):
    d = api("POST", "/runs", {
        "presetId": PRESET, "gender": "male", "characterName": "누수검증",
        "bonusStats": {"str": 1, "dex": 1, "wit": 2, "per": 1, "cha": 1, "con": 0},
    }, token=token)
    run = d.get("run") or {}
    return run.get("id") or d.get("runId"), run.get("currentTurnNo", 0), d.get("lastResult", {}).get("choices") or []


def get_run(token, run_id):
    return api("GET", f"/runs/{run_id}", token=token)


def stream_and_capture(token, run_id, turn_no, timeout=90):
    """SSE 스트림 연결 → 토큰 누적 → 각 snapshot에서 leak 탐지"""
    url = f"{BASE}/runs/{run_id}/turns/{turn_no}/stream"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    raw_buffer = ""
    snapshots = []        # (elapsed_ms, buffer_len, leaks: {pattern -> sample_matches})
    start = time.perf_counter()

    try:
        with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"): continue
                payload = raw[5:].strip()
                if not payload: continue
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                now_ms = (time.perf_counter() - start) * 1000
                t = ev.get("type")
                if t == "token":
                    text = ev.get("text", "") or ev.get("chunk", "")
                    if text:
                        raw_buffer += text
                        snap_leaks = {}
                        for pat, label in LEAK_PATTERNS:
                            ms = re.findall(pat, raw_buffer)
                            if ms:
                                snap_leaks[label] = ms[:3]
                        if snap_leaks:
                            snapshots.append({
                                "elapsedMs": round(now_ms, 1),
                                "bufLen": len(raw_buffer),
                                "leaks": snap_leaks,
                            })
                elif t == "done":
                    break
                elif t == "error":
                    return {"error": ev, "rawBuffer": raw_buffer, "snapshots": snapshots}
    except requests.Timeout:
        return {"error": {"timeout": True}, "rawBuffer": raw_buffer, "snapshots": snapshots}

    # 최종 버퍼에 남은 시스템 문자 (정리 전)
    final_leaks = {}
    for pat, label in LEAK_PATTERNS:
        ms = re.findall(pat, raw_buffer)
        if ms:
            final_leaks[label] = ms[:5]

    return {
        "totalMs": round((time.perf_counter() - start) * 1000, 1),
        "bufLen": len(raw_buffer),
        "rawBuffer": raw_buffer,
        "snapshots": snapshots,       # 타이핑 도중 leak이 있던 순간들
        "finalLeaks": final_leaks,     # 최종 raw buffer 잔재
    }


def submit_and_stream(token, run_id, expected, input_body):
    """턴 제출 → SSE 캡처 병행"""
    resp = api("POST", f"/runs/{run_id}/turns", {
        **input_body,
        "idempotencyKey": str(uuid.uuid4()),
        "expectedNextTurnNo": expected,
    }, token=token)
    tn = resp.get("turnNo", expected)
    return resp, stream_and_capture(token, run_id, tn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=5)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    token = register_login()
    run_id, cur, initial_choices = create_run(token)
    log(f"run: {run_id[:8]}, turn{cur}, initial_choices={len(initial_choices)}")
    pending_choices = initial_choices

    all_turns = []
    for i in range(args.turns):
        state = get_run(token, run_id)
        node_type = state.get("currentNode", {}).get("nodeType", "")
        last_choices = state.get("lastResult", {}).get("choices") or []
        expected = state.get("run", {}).get("currentTurnNo", cur) + 1
        if node_type == "HUB" and last_choices:
            body = {"input": {"type": "CHOICE", "choiceId": last_choices[0]["id"]}}
        elif pending_choices:
            body = {"input": {"type": "CHOICE", "choiceId": pending_choices[0]["id"]}}
            pending_choices = []
        else:
            body = {"input": {"type": "ACTION", "text": ACTIONS[i % len(ACTIONS)]}}
        try:
            resp, result = submit_and_stream(token, run_id, expected, body)
        except Exception as e:
            log(f"turn {expected} err: {e}")
            break

        tn = resp.get("turnNo", expected)
        snap = result.get("snapshots", [])
        final = result.get("finalLeaks", {})
        log(f"T{tn}: {len(snap)} leak snapshots, finalLeaks={'yes' if final else 'no'}")

        all_turns.append({
            "turnNo": tn,
            "totalMs": result.get("totalMs"),
            "bufLen": result.get("bufLen"),
            "rawBuffer": result.get("rawBuffer", "")[:800],
            "leakSnapshots": snap,
            "finalLeaks": final,
        })

    output = args.output or f"playtest-reports/streaming_leak_inspect_{int(time.time())}.json"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps({
        "runId": run_id,
        "turnsInspected": len(all_turns),
        "turns": all_turns,
        "patterns": [{"pattern": p, "label": l} for p, l in LEAK_PATTERNS],
    }, ensure_ascii=False, indent=2))
    log(f"saved: {output}")

    print("\n=== SUMMARY ===")
    total_snap = sum(len(t.get("leakSnapshots", [])) for t in all_turns)
    total_final = sum(1 for t in all_turns if t.get("finalLeaks"))
    print(f"turns: {len(all_turns)}")
    print(f"leak snapshots total: {total_snap}")
    print(f"turns with final buffer leaks: {total_final}/{len(all_turns)}")
    # 패턴 빈도
    from collections import Counter
    cnt = Counter()
    for t in all_turns:
        for snap in t.get("leakSnapshots", []):
            for label in snap.get("leaks", {}).keys():
                cnt[label] += 1
    if cnt:
        print("\nleak pattern counts (across all snapshots):")
        for k, v in cnt.most_common():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
