#!/usr/bin/env python3
"""프롬프트 예산 감시 — 백스톱 20,000자 상향(2026-09-01)의 정본 모니터.

배경 (CLAUDE.md 불변식 17):
  GRAND_TOTAL_CHAR_BUDGET 를 16,500→20,000자로 상향하면서, 신규 개방 밴드
  (16.5k~20k자)의 품질이 열화되지 않는지 관측하는 조건이 붙었다. 이 스크립트가
  그 판정의 정본이다 — 모델 × 프롬프트 길이 밴드별 어체 위반율(llm_speech_audit)
  과 백스톱 텔레메트리(llm_token_stats.promptChars/budgetTrimmed)를 집계한다.

롤백 신호:
  신규 밴드(16.5k~20k)의 어체 위반율이 기준 밴드(12k~16.5k 풀링) 대비
  +5%p 이상 (발화 표본 ≥ MIN_UTT) 이면 경보 + 종료코드 1.
  Luna(gpt-5.6-luna)는 패밀리 장문 약체(MRCR 41.3%)라 중점 감시 대상.

사용:
  python3 scripts/prompt_budget_monitor.py            # 최근 30일
  python3 scripts/prompt_budget_monitor.py --days 7
  python3 scripts/prompt_budget_monitor.py --json     # 기계 판독
"""

import argparse
import json
import subprocess
import sys

WATCH_CHARS = 16500   # server GRAND_TOTAL_WATCH_CHARS (구 상한 = 신규 밴드 시작)
CAP_CHARS = 20000     # server GRAND_TOTAL_CHAR_BUDGET
# 밴드 경보 최소 발화 표본. 2026-09-01 초기 실측에서 n=41(Luna, 상향 전 잔존
# 초과 턴)이 +5.0%p 경계선 정확히에서 발화 — 이항 CI ±11%p 라 판정 불능 표본.
# 60발화(± ~9%p)부터 경보, 미만은 표에서 육안 감시.
MIN_UTT = 60
DELTA_PP = 5.0        # 롤백 신호 임계 (기준 밴드 대비 +%p)
MAIN_MODELS = ("google/gemma-4-31b", "openai/gpt-5.6-luna")

BANDS = [
    ("b1", "<12k", 0, 12000),
    ("b2", "12-14k", 12000, 14000),
    ("b3", "14-16.5k", 14000, WATCH_CHARS),
    ("b4", "16.5-20k(신규)", WATCH_CHARS, CAP_CHARS),
    ("b5", ">20k(초과잔존)", CAP_CHARS, 10**9),
]


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


def band_case(col):
    parts = []
    for key, _, lo, hi in BANDS:
        parts.append(f"WHEN {col} >= {lo} AND {col} < {hi} THEN '{key}'")
    return "CASE " + " ".join(parts) + " END"


def collect(days):
    rows = psql(f"""
WITH t AS (
  SELECT llm_model_used AS model,
    (SELECT sum(length(e->>'content')) FROM jsonb_array_elements(llm_prompt) e) AS pc,
    (SELECT coalesce(sum((a->>'violations')::int),0)
       FROM jsonb_array_elements(llm_speech_audit) a) AS viol,
    (SELECT coalesce(sum((a->>'total')::int),0)
       FROM jsonb_array_elements(llm_speech_audit) a) AS utt
  FROM turns
  WHERE created_at > now() - interval '{days} days'
    AND llm_status='DONE' AND llm_prompt IS NOT NULL
    AND llm_speech_audit IS NOT NULL AND llm_model_used IS NOT NULL
)
SELECT model, {band_case('pc')} AS band, count(*), sum(utt), sum(viol)
FROM t WHERE pc IS NOT NULL GROUP BY 1,2 ORDER BY 1,2;""")
    data = {}
    for model, band, turns, utt, viol in rows:
        data.setdefault(model, {})[band] = {
            "turns": int(turns), "utt": int(utt or 0), "viol": int(viol or 0),
        }
    tele = psql(f"""
SELECT
  count(*) FILTER (WHERE llm_token_stats ? 'promptChars'),
  count(*) FILTER (WHERE llm_token_stats ? 'budgetTrimmed'),
  count(*) FILTER (WHERE llm_token_stats ? 'budgetOverChars'),
  coalesce(round(avg((llm_token_stats->>'promptChars')::int)), 0),
  coalesce(max((llm_token_stats->>'promptChars')::int), 0),
  coalesce(round((percentile_cont(0.95) WITHIN GROUP
    (ORDER BY (llm_token_stats->>'promptChars')::int))::numeric), 0)
FROM turns
WHERE created_at > now() - interval '{days} days'
  AND llm_token_stats IS NOT NULL AND llm_token_stats ? 'promptChars';""")
    keys = ["telemetryTurns", "trimmedTurns", "overTurns",
            "avgChars", "maxChars", "p95Chars"]
    telemetry = dict(zip(keys, (int(float(v or 0)) for v in tele[0]))) if tele else {}
    return data, telemetry


def rate(cell):
    return 100.0 * cell["viol"] / cell["utt"] if cell and cell["utt"] else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    data, telemetry = collect(args.days)
    alarms = []

    for model in sorted(data):
        if not any(model.startswith(m) for m in MAIN_MODELS):
            continue
        bands = data[model]
        base = {"utt": 0, "viol": 0}
        for key in ("b2", "b3"):  # 기준 밴드: 12k~16.5k 풀링
            if key in bands:
                base["utt"] += bands[key]["utt"]
                base["viol"] += bands[key]["viol"]
        watch = bands.get("b4")
        base_rate, watch_rate = rate(base), rate(watch)
        if (watch and watch["utt"] >= MIN_UTT and base_rate is not None
                and watch_rate is not None
                and watch_rate >= base_rate + DELTA_PP):
            alarms.append({
                "model": model,
                "baseRate": round(base_rate, 1),
                "watchRate": round(watch_rate, 1),
                "watchUtt": watch["utt"],
            })

    if args.json:
        print(json.dumps({
            "days": args.days, "bands": data, "telemetry": telemetry,
            "alarms": alarms,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"[프롬프트 예산 감시] 최근 {args.days}일 — 상한 {CAP_CHARS:,}자 / "
              f"신규 밴드 >{WATCH_CHARS:,}자")
        for model in sorted(data):
            print(f"\n  {model}")
            for key, label, _, _ in BANDS:
                cell = data[model].get(key)
                if not cell:
                    continue
                r = rate(cell)
                r_str = f"{r:5.1f}%" if r is not None else "  n/a"
                mark = " ◀ 신규 밴드" if key == "b4" else ""
                print(f"    {label:>14}: {cell['turns']:4}턴 "
                      f"{cell['utt']:5}발화 위반 {r_str}{mark}")
        if telemetry.get("telemetryTurns"):
            print(f"\n  텔레메트리({telemetry['telemetryTurns']}턴): "
                  f"avg {telemetry['avgChars']:,} / p95 {telemetry['p95Chars']:,} / "
                  f"max {telemetry['maxChars']:,}자 · "
                  f"백스톱 절삭 {telemetry['trimmedTurns']}턴 · "
                  f"초과 잔존 {telemetry['overTurns']}턴")
        else:
            print("\n  텔레메트리 없음 — 상향 배포(2026-09-01) 이후 턴부터 쌓인다")
        if alarms:
            for a in alarms:
                print(f"\n  ❌ 롤백 검토 신호 — {a['model']}: 신규 밴드 위반 "
                      f"{a['watchRate']}% (기준 {a['baseRate']}%, "
                      f"n={a['watchUtt']}발화, +{DELTA_PP}%p 초과)")
        else:
            print("\n  ✅ 신규 밴드 열화 신호 없음"
                  " (표본 미달 밴드는 표만 참고)")

    sys.exit(1 if alarms else 0)


if __name__ == "__main__":
    main()
