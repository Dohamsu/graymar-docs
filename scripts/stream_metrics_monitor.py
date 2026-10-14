#!/usr/bin/env python3
"""서술 스트림 운영 지표 — arch/141·143·144 후속 관측의 정본 집계.

2026-10-12~14 에 서술 경로가 연달아 바뀌었다 (JSON 스키마 스트림, 보류 턴 부분
스트리밍, 이동 턴 송출, 빈 스트림 재시도, 생성 기록). 며칠 운영 뒤 "실제로 어떻게
도는가"를 한 번에 보는 스크립트다. 두 소스를 읽는다.

  DB  ai_turn_logs.pipeline_log.generation — 턴별 생성 경로·폴백 이벤트·실제 전송값
      turns.llm_output                     — 한자·가나 혼입 재발 (arch/144 §11)
  로그 /tmp/graymar-server.log (launchd 표준출력)
      [StreamHold]          — 송출 모드(stream/gated/hold)·prefixKept=false
      [HubTravel] … 축약 생략 — 흘린 이동 턴의 축약 생략 (arch/144 P4)
      [StructuredStream]    — 빈 스트림 재시도·non-stream 강등
      [TurnTiming:WORKER]   — 첫 토큰·첫 송출·총 시간
      [TurnTiming:POST]     — 턴 제출 응답 시간

경보(종료코드 1): 표본이 충분할 때만 판정한다.
  - prefixKept=false 가 부분 송출 턴의 2% 초과 (먼저 보낸 글이 최종본과 어긋남)
  - 빈 스트림 재시도 후에도 non-stream 강등이 생성 기록 턴의 3% 초과
  - 한자·가나 혼입 턴이 DONE 턴의 1% 초과

사용:
  python3 scripts/stream_metrics_monitor.py              # 최근 3일
  python3 scripts/stream_metrics_monitor.py --days 7
  python3 scripts/stream_metrics_monitor.py --json
  python3 scripts/stream_metrics_monitor.py --log /path/to/server.log
"""

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timedelta

DEFAULT_LOG = "/tmp/graymar-server.log"
MIN_SAMPLE = 30  # 경보 판정 최소 표본
PREFIX_MISS_MAX = 0.02
NONSTREAM_MAX = 0.03
FOREIGN_SCRIPT_MAX = 0.01

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOG_TS = re.compile(r"(\d{2}/\d{2}/\d{4}, \d{1,2}:\d{2}:\d{2} [AP]M)")
KV = re.compile(r"(\w+)=(\S+)")
# 고정 문자열 필터 — 정규식 없이 바이트 비교
LOG_NEEDLES = (
    "[StreamHold]",
    "축약 생략",
    "[StructuredStream]",
    "[TurnTiming:WORKER]",
    "[TurnTiming:POST]",
)


def psql(sql):
    out = subprocess.run(
        ["docker", "exec", "textRpg-db", "psql", "-U", "user", "-d", "textRpg",
         "-At", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        print(f"psql 실패: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [ln.split("|") for ln in out.stdout.strip().splitlines() if ln]


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def quantiles(vals):
    vals = sorted(v for v in vals if v is not None and v >= 0)
    if not vals:
        return None
    q = lambda p: vals[min(len(vals) - 1, int(round(p * (len(vals) - 1))))]
    return {
        "n": len(vals),
        "p50": q(0.5),
        "p90": q(0.9),
        "max": vals[-1],
        "avg": round(statistics.mean(vals)),
    }


# ── DB ──────────────────────────────────────────────────────────────


def collect_db(days):
    gen_rows = psql(f"""
SELECT pipeline_log->'generation'->>'path',
       coalesce(pipeline_log->'generation'->'events', '[]'::jsonb)::text,
       coalesce(pipeline_log->'generation'->'sent'->>'reasoning', ''),
       coalesce(pipeline_log->'generation'->>'modelUsed', '')
FROM ai_turn_logs
WHERE created_at > now() - interval '{days} days'
  AND pipeline_log ? 'generation';""")
    paths, events, reasoning, models = {}, {}, {}, {}
    for path, ev_json, sent_reasoning, model in gen_rows:
        paths[path] = paths.get(path, 0) + 1
        for ev in json.loads(ev_json):
            key = ev.split(":", 1)[0]
            events[key] = events.get(key, 0) + 1
        reasoning[sent_reasoning or "(무필드)"] = (
            reasoning.get(sent_reasoning or "(무필드)", 0) + 1
        )
        models[model or "?"] = models.get(model or "?", 0) + 1

    [[done, foreign]] = psql(f"""
SELECT count(*),
       count(*) FILTER (WHERE llm_output ~ '[一-鿿ぁ-ゟ゠-ヿ]')
FROM turns
WHERE created_at > now() - interval '{days} days'
  AND llm_status = 'DONE' AND llm_output IS NOT NULL;""")
    foreign_samples = psql(f"""
SELECT run_id, turn_no,
       substring(llm_output from '.{{0,12}}[一-鿿ぁ-ゟ゠-ヿ]+.{{0,12}}')
FROM turns
WHERE created_at > now() - interval '{days} days'
  AND llm_status = 'DONE' AND llm_output ~ '[一-鿿ぁ-ゟ゠-ヿ]'
ORDER BY created_at DESC LIMIT 5;""")
    return {
        "generationTurns": len(gen_rows),
        "paths": paths,
        "events": events,
        "sentReasoning": reasoning,
        "models": models,
        "doneTurns": int(done),
        "foreignScriptTurns": int(foreign),
        "foreignScriptSamples": [
            {"run": r[:8], "turn": int(t), "text": s.replace("\n", " ")}
            for r, t, s in foreign_samples
        ],
    }


# ── 로그 ─────────────────────────────────────────────────────────────


def iter_log(path, since):
    # 1GB 가 넘는 로그를 파이썬으로 전부 읽지 않도록 grep 으로 먼저 거른다
    # rg 가 있으면 rg (1.2GB 로그 0.2초), 없으면 BSD grep (약 30초)
    rg = shutil.which("rg") or (
        "/opt/homebrew/bin/rg" if os.path.exists("/opt/homebrew/bin/rg") else None
    )
    cmd = [rg, "--no-filename", "-F"] if rg else ["grep", "-F"]
    for needle in LOG_NEEDLES:
        cmd += ["-e", needle]
    proc = subprocess.run(
        cmd + [path], capture_output=True, text=True, errors="replace",
        env={**os.environ, "LC_ALL": "C"},
    )
    if proc.returncode not in (0, 1):
        print(f"로그 읽기 실패: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    for raw in proc.stdout.splitlines():
        line = ANSI.sub("", raw)
        m = LOG_TS.search(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%m/%d/%Y, %I:%M:%S %p")
        if ts >= since:
            yield line


def collect_log(path, days):
    since = datetime.now() - timedelta(days=days)
    modes, reasons = {}, {}
    gated_or_partial = prefix_miss = 0
    prefix_miss_samples = []
    condense_skip = empty_retry = nonstream_fallback = 0
    worker = {"firstToken": [], "firstEmit": [], "total": []}
    no_emit = 0
    post_total = []

    for line in iter_log(path, since):
        kv = dict(KV.findall(line))
        if "[StreamHold]" in line:
            # 구 형식(held=true/false) 과 신 형식(mode=…) 모두 받는다
            mode = kv.get("mode") or (
                "hold" if kv.get("held") == "true" else "stream"
            )
            modes[mode] = modes.get(mode, 0) + 1
            for r in kv.get("reasons", "-").split(","):
                if r and r != "-":
                    reasons[r] = reasons.get(r, 0) + 1
            if "prefixKept" in kv:
                gated_or_partial += 1
                if kv["prefixKept"] == "false":
                    prefix_miss += 1
                    if len(prefix_miss_samples) < 5:
                        prefix_miss_samples.append(
                            f"run={kv.get('run', '?')[:8]} turn={kv.get('turn')}"
                        )
        elif "축약 생략" in line:
            condense_skip += 1
        elif "[StructuredStream]" in line:
            if "스트림 1회 재시도" in line:
                empty_retry += 1
            elif "non-stream" in line:
                nonstream_fallback += 1
        elif "[TurnTiming:WORKER]" in line:
            for k in worker:
                if k in kv:
                    worker[k].append(int(kv[k]))
            if kv.get("firstEmit") == "-1":
                no_emit += 1
        elif "[TurnTiming:POST]" in line and "total" in kv:
            post_total.append(int(kv["total"]))

    return {
        "streamHold": {
            "modes": modes,
            "reasons": reasons,
            "prefixChecked": gated_or_partial,
            "prefixKeptFalse": prefix_miss,
            "prefixKeptFalseSamples": prefix_miss_samples,
        },
        "condenseSkipped": condense_skip,
        "emptyStreamRetry": empty_retry,
        "nonStreamFallback": nonstream_fallback,
        "workerTiming": {k: quantiles(v) for k, v in worker.items()},
        "workerNoEmitTurns": no_emit,
        "postTiming": quantiles(post_total),
    }


# ── 판정·출력 ────────────────────────────────────────────────────────


def judge(db, log):
    alerts = []
    sh = log["streamHold"]
    if sh["prefixChecked"] >= MIN_SAMPLE:
        rate = sh["prefixKeptFalse"] / sh["prefixChecked"]
        if rate > PREFIX_MISS_MAX:
            alerts.append(
                f"prefixKept=false {sh['prefixKeptFalse']}/{sh['prefixChecked']}"
                f" ({rate:.1%}) > {PREFIX_MISS_MAX:.0%}"
            )
    gen = db["generationTurns"]
    if gen >= MIN_SAMPLE:
        fallback = db["paths"].get("nonstream-json", 0) + db["paths"].get("text", 0)
        if fallback / gen > NONSTREAM_MAX:
            alerts.append(
                f"non-stream 강등 {fallback}/{gen} ({fallback / gen:.1%})"
                f" > {NONSTREAM_MAX:.0%}"
            )
    if db["doneTurns"] >= MIN_SAMPLE:
        rate = db["foreignScriptTurns"] / db["doneTurns"]
        if rate > FOREIGN_SCRIPT_MAX:
            alerts.append(
                f"한자·가나 혼입 {db['foreignScriptTurns']}/{db['doneTurns']}"
                f" ({rate:.1%}) > {FOREIGN_SCRIPT_MAX:.0%}"
            )
    return alerts


def fmt_counts(d):
    if not d:
        return "-"
    return ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda x: -x[1]))


def fmt_q(q):
    if not q:
        return "표본 없음"
    return f"n={q['n']} p50={q['p50']}ms p90={q['p90']}ms max={q['max']}ms avg={q['avg']}ms"


def print_report(days, db, log, alerts):
    sh = log["streamHold"]
    print(f"서술 스트림 지표 — 최근 {days}일\n")
    print("[생성 기록 — ai_turn_logs.pipeline_log.generation]")
    print(f"  턴 수: {db['generationTurns']}")
    print(f"  경로: {fmt_counts(db['paths'])}")
    print(f"  이벤트: {fmt_counts(db['events'])}")
    print(f"  실제 전송 추론: {fmt_counts(db['sentReasoning'])}")
    print(f"  모델: {fmt_counts(db['models'])}")
    print("\n[송출 — StreamHold]")
    print(f"  모드: {fmt_counts(sh['modes'])}")
    print(f"  보류·게이트 사유: {fmt_counts(sh['reasons'])}")
    print(
        f"  prefixKept=false: {sh['prefixKeptFalse']}/{sh['prefixChecked']}"
        + (f" ({pct(sh['prefixKeptFalse'], sh['prefixChecked'])}%)" if sh["prefixChecked"] else "")
        + (f"  예: {', '.join(sh['prefixKeptFalseSamples'])}" if sh["prefixKeptFalseSamples"] else "")
    )
    print(f"  이동 축약 생략(흘린 이동 턴): {log['condenseSkipped']}")
    print("\n[빈 스트림·강등 — StructuredStream]")
    print(f"  빈 스트림 재시도: {log['emptyStreamRetry']}  non-stream 강등: {log['nonStreamFallback']}")
    print("\n[시간 — TurnTiming]")
    wt = log["workerTiming"]
    print(f"  첫 토큰: {fmt_q(wt['firstToken'])}")
    print(f"  첫 송출: {fmt_q(wt['firstEmit'])}  (송출 없음 {log['workerNoEmitTurns']}턴)")
    print(f"  워커 총: {fmt_q(wt['total'])}")
    print(f"  턴 제출(POST): {fmt_q(log['postTiming'])}")
    print("\n[재발 — 한자·가나 혼입]")
    print(
        f"  {db['foreignScriptTurns']}/{db['doneTurns']} 턴"
        + (f" ({pct(db['foreignScriptTurns'], db['doneTurns'])}%)" if db["doneTurns"] else "")
    )
    for s in db["foreignScriptSamples"]:
        print(f"    run={s['run']} turn={s['turn']}: …{s['text']}…")
    print()
    if alerts:
        print("경보:")
        for a in alerts:
            print(f"  - {a}")
    else:
        print(f"경보 없음 (판정 최소 표본 {MIN_SAMPLE})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=float, default=3)
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = collect_db(args.days)
    log = collect_log(args.log, args.days)
    alerts = judge(db, log)
    if args.json:
        print(json.dumps({"days": args.days, "db": db, "log": log, "alerts": alerts},
                         ensure_ascii=False, indent=2))
    else:
        print_report(args.days, db, log, alerts)
    sys.exit(1 if alerts else 0)


if __name__ == "__main__":
    main()
