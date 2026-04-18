#!/usr/bin/env python3
"""
Gemma 4 모델 비교 벤치마크 — 26b-a4b vs 31b-it (또는 임의 2모델)

각 모델로 10턴 플레이를 돌리며 TTFT / TTLT / 프롬프트/완성 토큰 / 비용 측정.

사용법:
  python3 scripts/bench-models.py --models google/gemma-4-26b-a4b-it google/gemma-4-31b-it --turns 10

결과는 playtest-reports/bench_<timestamp>.json 에 저장.
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", flush=True)
    sys.exit(1)

BASE = "http://localhost:3000/v1"

# OpenRouter 가격표 (USD per 1M tokens) — https://openrouter.ai/google
PRICE = {
    "google/gemma-4-26b-a4b-it": {"input": 0.07, "output": 0.40},
    "google/gemma-4-31b-it": {"input": 0.13, "output": 0.38},
}

PRESETS = ["DESERTER", "SMUGGLER", "DOCKWORKER"]
# 실제 유저 플레이 스타일 — 별칭 변형, NPC 지목, 고위험 행동, 긴 문장 포함
ACTIONS = [
    "주변을 살펴본다",
    "창고 관리인에게 다가가 수상한 장부를 가리키며 해명을 요구한다",
    "토브렌에게 조용히 다가가 가족 이야기를 꺼내며 설득한다",
    "제복의 장교에게 동전 주머니를 슬쩍 보여주며 눈을 돌리라고 부탁한다",
    "하위크의 소매를 붙잡고 낮은 목소리로 위협하듯 진실을 캐묻는다",
    "두 병사가 대화하는 사이 몰래 등 뒤 서랍에서 단도를 훔친다",
    "상인에게 큰 소리로 거래를 제안하며 주변 사람들의 시선을 끈다",
    "관리인과 회계사를 동시에 불러 서로의 말이 엇갈리는지 확인한다",
    "골목 구석에서 뛰어나와 도망치려는 자의 다리를 걸어 넘어뜨린다",
    "낯선 여인에게 정중하게 인사하며 이 도시의 소문을 물어본다",
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def api(method, path, body=None, token=None, timeout=30):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, url, json=body, headers=headers, timeout=timeout)
    if not r.ok:
        log(f"API {method} {path} → {r.status_code}: {r.text[:400]}")
        r.raise_for_status()
    return r.json() if r.text else {}


def get_run(token, run_id):
    return api("GET", f"/runs/{run_id}", token=token)


def register_login():
    email = f"bench_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.com"
    try:
        data = api("POST", "/auth/register", {
            "email": email, "password": "Test1234!!", "nickname": "Bench",
        })
    except requests.HTTPError:
        data = api("POST", "/auth/login", {
            "email": email, "password": "Test1234!!",
        })
    return data["token"]


def set_model(token, model_id):
    data = api("PATCH", "/settings/llm", {"openaiModel": model_id}, token=token)
    return data.get("openaiModel") or data.get("model")


def create_run(token, preset="DESERTER"):
    data = api("POST", "/runs", {
        "presetId": preset,
        "gender": "male",
        "characterName": "벤치마커",
        "bonusStats": {"str": 1, "dex": 1, "wit": 2, "per": 1, "cha": 1, "con": 0},
    }, token=token)
    run = data.get("run") or {}
    run_id = run.get("id") or data.get("runId") or data.get("id")
    if not run_id:
        raise RuntimeError(f"runId not found in response keys={list(data.keys())}")
    current_turn = run.get("currentTurnNo", data.get("currentTurnNo", 1))
    initial_choices = data.get("lastResult", {}).get("choices") or []
    return run_id, current_turn, initial_choices


def submit_action(token, run_id, expected_next_turn, text):
    return api("POST", f"/runs/{run_id}/turns", {
        "idempotencyKey": str(uuid.uuid4()),
        "expectedNextTurnNo": expected_next_turn,
        "input": {"type": "ACTION", "text": text},
    }, token=token)


def submit_choice(token, run_id, expected_next_turn, choice_id):
    return api("POST", f"/runs/{run_id}/turns", {
        "idempotencyKey": str(uuid.uuid4()),
        "expectedNextTurnNo": expected_next_turn,
        "input": {"type": "CHOICE", "choiceId": choice_id},
    }, token=token)


def stream_turn(token, run_id, turn_no, timeout=120):
    """턴 제출 직후 SSE 스트림에 연결, TTFT/TTLT/토큰 수 측정"""
    url = f"{BASE}/runs/{run_id}/turns/{turn_no}/stream"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    start = time.perf_counter()
    ttft_ms = None
    ttlt_ms = None
    token_count = 0
    done_data = None
    error = None

    try:
        with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
            if r.status_code != 200:
                return {"error": f"SSE {r.status_code}", "totalMs": (time.perf_counter() - start) * 1000}
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if not raw.startswith("data:"):
                    continue
                payload = raw[5:].strip()
                if not payload:
                    continue
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                now = (time.perf_counter() - start) * 1000
                if ev.get("type") == "token":
                    token_count += 1
                    if ttft_ms is None:
                        ttft_ms = now
                    ttlt_ms = now
                elif ev.get("type") == "done":
                    ttlt_ms = now
                    done_data = ev
                    break
                elif ev.get("type") == "error":
                    error = ev
                    break
    except requests.Timeout:
        error = {"timeout": True}

    return {
        "ttft_ms": ttft_ms,
        "ttlt_ms": ttlt_ms,
        "tokenCount": token_count,
        "error": error,
        "doneData": done_data,
        "totalMs": (time.perf_counter() - start) * 1000,
    }


def get_turn_detail(token, run_id, turn_no):
    return api("GET", f"/runs/{run_id}/turns/{turn_no}", token=token)


def run_one_model(token, model_id, turns=10):
    log(f"=== Model: {model_id} ===")
    set_model(token, model_id)
    time.sleep(1)

    run_id, next_turn, initial_choices = create_run(token)
    log(f"Run created: {run_id[:8]}, start turn {next_turn}, initial choices: {len(initial_choices)}")

    results = []
    pending_choices = initial_choices

    for i in range(turns):
        expected = next_turn
        resp = None
        # 현재 노드 타입 조회 (HUB면 choice, LOCATION이면 action)
        try:
            state = get_run(token, run_id)
            node_type = state.get("currentNode", {}).get("nodeType", "")
            last_choices = state.get("lastResult", {}).get("choices") or []
            expected = state.get("run", {}).get("currentTurnNo", expected) + 1
        except Exception:
            node_type, last_choices = "", []

        def build_body(exp):
            if node_type == "HUB":
                chosen = last_choices[0] if last_choices else None
                if chosen:
                    return {"input": {"type": "CHOICE", "choiceId": chosen["id"]}, "expectedNextTurnNo": exp, "idempotencyKey": str(uuid.uuid4())}
            if pending_choices:
                return {"input": {"type": "CHOICE", "choiceId": pending_choices[0]["id"]}, "expectedNextTurnNo": exp, "idempotencyKey": str(uuid.uuid4())}
            return {"input": {"type": "ACTION", "text": ACTIONS[i % len(ACTIONS)]}, "expectedNextTurnNo": exp, "idempotencyKey": str(uuid.uuid4())}

        for attempt in range(3):
            try:
                body = build_body(expected)
                resp = api("POST", f"/runs/{run_id}/turns", body, token=token)
                break
            except requests.HTTPError as e:
                text = getattr(e.response, "text", "") or ""
                try:
                    err = e.response.json()
                except Exception:
                    err = {}
                if "TURN_NO_MISMATCH" in text:
                    got = err.get("details", {}).get("expected")
                    if got:
                        log(f"  turn {expected} → retry with expected={got}")
                        expected = got
                        continue
                log(f"  turn {expected} submit error: {e.response.status_code} {text[:200]}")
                break
            except Exception as e:
                log(f"  turn {expected} submit error: {e}")
                break
        if resp is None:
            break

        turn_no = resp.get("turnNo", expected)

        sse = stream_turn(token, run_id, turn_no, timeout=90)
        detail = {}
        try:
            detail = get_turn_detail(token, run_id, turn_no)
        except Exception:
            pass

        llm = detail.get("llm", {}) or {}
        stats = llm.get("tokenStats") or {}
        model_used = llm.get("modelUsed") or ""
        narrative = llm.get("output") or ""

        prompt = stats.get("prompt", 0)
        cached = stats.get("cached", 0)
        completion = stats.get("completion", 0)
        server_latency_ms = stats.get("latencyMs", 0)

        price = PRICE.get(model_id, {"input": 0, "output": 0})
        cost_usd = (prompt / 1_000_000) * price["input"] + (completion / 1_000_000) * price["output"]

        row = {
            "turnNo": turn_no,
            "modelUsed": model_used,
            "ttft_ms": sse.get("ttft_ms"),
            "ttlt_ms": sse.get("ttlt_ms"),
            "server_latency_ms": server_latency_ms,
            "streamToken_count": sse.get("tokenCount"),
            "promptTokens": prompt,
            "cachedTokens": cached,
            "completionTokens": completion,
            "costUsd": round(cost_usd, 6),
            "narrativeLen": len(narrative),
            "narrativeSample": narrative[:120],
            "error": sse.get("error"),
        }
        results.append(row)
        log(
            f"  turn {turn_no}: ttft={row['ttft_ms']:.0f}ms" if row["ttft_ms"] else f"  turn {turn_no}: ttft=None"
            + (f" ttlt={row['ttlt_ms']:.0f}ms p/c={prompt}/{completion}" if row["ttlt_ms"] else "")
        )

        # 다음 턴 번호 산출 + 다음 choices
        next_turn = turn_no + 1
        if resp.get("transition"):
            next_turn = resp["transition"].get("enterTurnNo", next_turn) + 1
        # 첫 프롤로그 choice 소비 후에는 항상 ACTION 기반으로 진행
        pending_choices = []

    return run_id, results


def summarize(rows):
    def pick(key):
        return [r[key] for r in rows if r.get(key) is not None]

    def p(arr, q):
        if not arr:
            return None
        s = sorted(arr)
        idx = min(int(len(s) * q / 100), len(s) - 1)
        return s[idx]

    ttft = pick("ttft_ms")
    ttlt = pick("ttlt_ms")
    srv = pick("server_latency_ms")
    prompt_total = sum(pick("promptTokens"))
    completion_total = sum(pick("completionTokens"))
    cost_total = sum(pick("costUsd"))

    return {
        "samples": len(rows),
        "ttft_ms": {"p50": p(ttft, 50), "p90": p(ttft, 90), "max": max(ttft) if ttft else None, "mean": sum(ttft) / len(ttft) if ttft else None},
        "ttlt_ms": {"p50": p(ttlt, 50), "p90": p(ttlt, 90), "max": max(ttlt) if ttlt else None, "mean": sum(ttlt) / len(ttlt) if ttlt else None},
        "server_latency_ms": {"p50": p(srv, 50), "p90": p(srv, 90), "max": max(srv) if srv else None, "mean": sum(srv) / len(srv) if srv else None},
        "promptTokens_total": prompt_total,
        "completionTokens_total": completion_total,
        "costUsd_total": round(cost_total, 6),
        "costUsd_per_turn_avg": round(cost_total / len(rows), 6) if rows else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    log(f"Registering bench user + JWT")
    token = register_login()
    log(f"Token: {token[:20]}...")

    report = {
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "turnsPerModel": args.turns,
        "models": [],
    }

    for model_id in args.models:
        run_id, rows = run_one_model(token, model_id, turns=args.turns)
        summary = summarize(rows)
        report["models"].append({
            "modelId": model_id,
            "runId": run_id,
            "summary": summary,
            "turns": rows,
        })
        ttft50 = summary['ttft_ms']['p50']
        ttlt50 = summary['ttlt_ms']['p50']
        log(
            f"SUMMARY {model_id}: "
            f"TTFT p50={ttft50:.0f}ms " if ttft50 else f"SUMMARY {model_id}: TTFT p50=n/a "
            f"TTLT p50={ttlt50:.0f}ms " if ttlt50 else "TTLT p50=n/a "
            f"cost=${summary['costUsd_total']:.4f}"
        )

    output = args.output or f"playtest-reports/bench_{int(time.time())}.json"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    log(f"Saved: {output}")

    # 간단 비교 프린트
    for entry in report["models"]:
        s = entry["summary"]
        def f(v):
            return f"{v:.0f}" if isinstance(v, (int, float)) else "n/a"
        log(
            f"SUM {entry['modelId']}: TTFT p50={f(s['ttft_ms']['p50'])}ms "
            f"TTLT p50={f(s['ttlt_ms']['p50'])}ms "
            f"cost=${s['costUsd_total']:.4f}"
        )
    if len(report["models"]) == 2:
        a, b = report["models"][0]["summary"], report["models"][1]["summary"]
        log("--- COMPARISON ---")
        for metric in ["ttft_ms", "ttlt_ms", "server_latency_ms"]:
            for q in ["p50", "p90", "mean"]:
                va, vb = a[metric][q], b[metric][q]
                if va and vb:
                    log(f"  {metric}.{q}: {va:.0f} → {vb:.0f}  ({(vb - va) / va * 100:+.1f}%)")
        log(f"  promptTokens: {a['promptTokens_total']} vs {b['promptTokens_total']}")
        log(f"  completionTokens: {a['completionTokens_total']} vs {b['completionTokens_total']}")
        log(f"  costTotal: ${a['costUsd_total']:.4f} vs ${b['costUsd_total']:.4f}")


if __name__ == "__main__":
    main()
