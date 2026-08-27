#!/usr/bin/env python3
"""DB 의 실 운영 프롬프트(`turns.llm_prompt`)를 `llm-config-ab.py --prompts` 형식으로 뽑는다.

**합성 프롬프트로는 모델을 평가할 수 없다** — 추론 토큰은 프롬프트 복잡도에 비례해서,
단순 프롬프트에선 effort=max 도 50토큰이지만 실제 서술 프롬프트(8k tok·형식 제약 다수)
에선 500토큰을 넘는다 (memory project_model_ab_harness_traps #6, 2026-08-13 실측).

사용법:
  python3 scripts/extract-bench-prompts.py --limit 15 --out /tmp/prompts.json
  python3 scripts/extract-bench-prompts.py --node-type LOCATION --scenario karnholt_v1

  python3 scripts/llm-config-ab.py --model z-ai/glm-5.3-flash \
      --prompts /tmp/prompts.json --configs 2048:low --penalty --temperature 0.8
"""

import argparse
import json
import subprocess
import sys

CONTAINER = "textRpg-db"
DB_USER = "user"
DB_NAME = "textRpg"


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-tAc", sql],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.exit(f"psql 실패: {r.stderr.strip()[:300]}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--out", default="/tmp/prompts.json")
    ap.add_argument(
        "--node-type",
        default="LOCATION",
        help="LOCATION(서술 크리티컬 패스, 기본) | COMBAT | HUB | ALL",
    )
    ap.add_argument("--scenario", default=None, help="시나리오 팩 id 로 한정")
    ap.add_argument(
        "--min-chars",
        type=int,
        default=4000,
        help="프롬프트 총 길이 하한. 짧은 프롬프트만 뽑히면 추론 소비량을 과소 측정한다",
    )
    args = ap.parse_args()

    where = ["t.llm_prompt IS NOT NULL", "t.llm_status = 'DONE'"]
    if args.node_type != "ALL":
        where.append(f"t.node_type = '{args.node_type}'")
    if args.scenario:
        where.append(
            f"r.scenario_id = '{args.scenario}'"
        )
    # 런 테이블은 `runs` 가 아니라 `run_sessions` 다 (API 경로 /v1/runs 와 다름).
    sql = f"""
      SELECT t.llm_prompt::text
        FROM turns t
        JOIN run_sessions r ON r.id = t.run_id
       WHERE {' AND '.join(where)}
         AND length(t.llm_prompt::text) >= {args.min_chars}
       ORDER BY t.created_at DESC
       LIMIT {args.limit}
    """
    prompts = []
    for line in psql(sql).splitlines():
        line = line.strip()
        if not line:
            continue
        msgs = json.loads(line)
        # llm_prompt 는 OpenAI messages 배열 그대로 저장된다.
        if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
            prompts.append({"msgs": msgs})

    if not prompts:
        sys.exit("프롬프트 0건 — 조건을 완화하거나 --node-type ALL 로 재시도")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False)

    sizes = sorted(len(json.dumps(p, ensure_ascii=False)) for p in prompts)
    print(f"{len(prompts)}건 → {args.out}")
    print(f"프롬프트 길이 중앙값 {sizes[len(sizes)//2]:,}자 (최소 {sizes[0]:,} / 최대 {sizes[-1]:,})")


if __name__ == "__main__":
    main()
