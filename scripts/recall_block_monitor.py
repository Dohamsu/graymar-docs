#!/usr/bin/env python3
"""원문 주입 블록 감시 — 회상(arch/139) · 재회(arch/145 M2) 블록의 주입·복제 정본 모니터.

두 블록은 과거 턴 원문(NPC 대사)을 프롬프트에 다시 넣는다. 저모델은 넣은 문구를 그대로
복제하는 경향이 있어(불변식 50) 주입 대사가 그 턴 출력에 그대로 다시 나오는지를 본다.

롤백 기준 (arch/145 §3.5, 사전 등록):
  재회 블록 [지난 만남 원문] 이 실린 턴 중, 주입 대사와 그 턴 출력 사이에
  12자 이상 공통 부분 문자열이 있는 턴 비율 >= 20%  →  REENCOUNTER_RECALL_DISABLED 권고.
  판정은 주입 턴 10건 이상 누적 후 (미만이면 "표본 부족").
  회상 블록 [과거 장면 원문] 은 같은 지표를 참고로만 낸다 (사용자가 원문을 되물은 턴이라
  일부 일치는 정답일 수 있다).

사용:
  python3 scripts/recall_block_monitor.py            # 최근 14일
  python3 scripts/recall_block_monitor.py --days 3
  python3 scripts/recall_block_monitor.py --show 5   # 복제 사례 원문 5건
  python3 scripts/recall_block_monitor.py --json
종료코드: 롤백 기준 초과 1, 그 외 0 (DB 오류 2).
"""

import argparse
import json
import re
import subprocess
import sys

COPY_MIN_CHARS = 12
ROLLBACK_RATE = 0.20
MIN_SAMPLES = 10

BLOCKS = {
    "reencounter": "[지난 만남 원문]",
    "recall": "[과거 장면 원문]",
}

QUOTE_LINE_RE = re.compile(r'^[^:\n]{1,40}: "(.+)"\s*$')
OUTPUT_QUOTE_RE = re.compile(r'["“]([^"”]+)["”]')


def psql_json_rows(sql):
    out = subprocess.run(
        ["docker", "exec", "textRpg-db", "psql", "-U", "user", "-d", "textRpg",
         "-At", "-c", sql],
        capture_output=True, text=True, timeout=180,
    )
    if out.returncode != 0:
        print(f"psql 실패: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [json.loads(ln) for ln in out.stdout.splitlines() if ln.strip()]


def block_text(prompt_text, header):
    i = prompt_text.find(header)
    if i < 0:
        return None
    m = re.search(r"\n\n\[", prompt_text[i + len(header):])
    return prompt_text[i: i + len(header) + m.start()] if m else prompt_text[i:]


def injected_utterances(block):
    out = []
    for line in block.splitlines():
        if line.startswith("플레이어:"):
            continue
        m = QUOTE_LINE_RE.match(line.strip())
        if m:
            out.append(m.group(1))
    return out


def longest_common(a, b):
    """a·b 의 최장 공통 부분 문자열 길이 (DP, 대사 길이 수백 자라 충분)."""
    best = 0
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = psql_json_rows(f"""
      select json_build_object(
        'run', t.run_id, 'turn', t.turn_no, 'at', t.created_at,
        'prompt', t.llm_prompt, 'out', t.llm_output)::text
      from turns t
      where t.created_at > now() - interval '{int(args.days)} days'
        and t.llm_status = 'DONE'
        and t.llm_prompt is not null
        and (t.llm_prompt::text like '%지난 만남 원문%'
             or t.llm_prompt::text like '%과거 장면 원문%')
      order by t.created_at
    """)

    stats = {k: {"turns": 0, "copied": 0, "cases": []} for k in BLOCKS}
    for r in rows:
        prompt_text = "\n".join(
            m.get("content", "") for m in (r.get("prompt") or [])
            if isinstance(m.get("content"), str) and m.get("role") != "system"
        )
        output_quotes = OUTPUT_QUOTE_RE.findall(r.get("out") or "")
        for key, header in BLOCKS.items():
            blk = block_text(prompt_text, header)
            if not blk:
                continue
            utts = injected_utterances(blk)
            if not utts:
                continue
            s = stats[key]
            s["turns"] += 1
            best = 0
            pair = None
            for u in utts:
                for o in output_quotes:
                    n = longest_common(u, o)
                    if n > best:
                        best, pair = n, (u, o)
            if best >= COPY_MIN_CHARS:
                s["copied"] += 1
                s["cases"].append({
                    "run": r["run"][:8], "turn": r["turn"], "lcs": best,
                    "injected": pair[0], "output": pair[1],
                })

    verdict = "OK"
    re_s = stats["reencounter"]
    re_rate = re_s["copied"] / re_s["turns"] if re_s["turns"] else 0.0
    if re_s["turns"] < MIN_SAMPLES:
        verdict = "표본 부족"
    elif re_rate >= ROLLBACK_RATE:
        verdict = "롤백 권고 (REENCOUNTER_RECALL_DISABLED=1)"

    if args.json:
        print(json.dumps({
            "days": args.days, "verdict": verdict,
            **{k: {kk: vv for kk, vv in v.items() if kk != "cases"} for k, v in stats.items()},
            "reencounterCopyRate": round(re_rate, 3),
        }, ensure_ascii=False))
    else:
        print(f"원문 주입 블록 감시 — 최근 {args.days}일 (복제 기준: 공통 부분 문자열 {COPY_MIN_CHARS}자 이상)")
        for key, header in BLOCKS.items():
            s = stats[key]
            rate = s["copied"] / s["turns"] if s["turns"] else 0.0
            print(f"  {header:14s} 주입 {s['turns']:4d}턴 · 복제 {s['copied']:3d}턴 ({rate * 100:.1f}%)")
        print(f"재회 블록 판정: {verdict} (기준 {ROLLBACK_RATE * 100:.0f}% · 표본 {MIN_SAMPLES}턴 이상)")
        if args.show:
            for key in BLOCKS:
                for c in stats[key]["cases"][: args.show]:
                    print(f"\n[{key}] {c['run']} T{c['turn']} lcs={c['lcs']}")
                    print(f"  주입: {c['injected'][:120]}")
                    print(f"  출력: {c['output'][:120]}")
    sys.exit(1 if verdict.startswith("롤백") else 0)


if __name__ == "__main__":
    main()
