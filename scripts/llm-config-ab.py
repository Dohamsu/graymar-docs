#!/usr/bin/env python3
"""LLM 설정 A/B — 실 운영 프롬프트를 재생해 max_tokens × reasoning effort 조합 비교.

플레이 런이 아니라 **DB 에 저장된 실제 프롬프트(turns.llm_prompt)를 재생**한다.
합성 프롬프트로는 추론 소비량을 못 잰다 — Luna 의 추론 토큰은 프롬프트 복잡도에
비례해서, 단순 프롬프트에선 effort=max 도 50토큰이지만 실제 서술 프롬프트(8k tok
·형식 제약 다수)에선 500토큰을 넘는다 (2026-08-13 실측).

측정: 레이턴시 · 추론/출력 토큰 · 실과금 · finish_reason(length=절단) ·
      라벨 준수(`별칭: "대사"` — 시스템 프롬프트 P0-B) · 합쇼체 누출(P0-A 위반)

사용법:
  python3 scripts/llm-config-ab.py --model openai/gpt-5.6-luna \
      --prompts /tmp/prompts.json --configs 1024:none 2048:medium
"""

import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

KRW = 1500  # 환율 고정 (memory feedback_exchange_rate)
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    env = Path(__file__).resolve().parent.parent / "server" / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("OPENAI_API_KEY 없음")


def call(key, model, msgs, max_tokens, effort):
    body = {"model": model, "messages": msgs, "max_tokens": max_tokens}
    if effort:
        body["reasoning"] = {"effort": effort}
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=240))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return {"error": str(e)[:120]}
    ms = (time.perf_counter() - t0) * 1000
    if "error" in d:
        return {"error": str(d["error"])[:120]}
    c = d["choices"][0]
    u = d.get("usage") or {}
    return {
        "ms": ms,
        "text": c["message"]["content"] or "",
        "finish": c.get("finish_reason"),
        "in": u.get("prompt_tokens", 0),
        "out": u.get("completion_tokens", 0),
        "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
        "reason": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
        "cost": u.get("cost") or 0,
    }


# 원문(후처리 전) 기준 지표 — 서버가 고쳐주기 전 **모델의 실제 준수율**
QUOTE = re.compile(r'["“]([^"”\n]{4,})["”]')
HAPSYO = re.compile(r"(습니다|입니다|십니다)[.!?…]")


def score(text):
    labeled = unlabeled = 0
    for m in QUOTE.finditer(text):
        ls = text.rfind("\n", 0, m.start()) + 1
        prefix = text[ls : m.start()]
        # P0-B: `별칭: "대사"` — 같은 줄에 콜론 라벨이 선행해야 한다
        if re.search(r"\S\s*:\s*$", prefix):
            labeled += 1
        elif re.search(r"(적혀|쓰여|글씨|읽힌|쪽지|영수증|구절|노래)", prefix):
            pass  # 문서·노래 인용은 대사가 아님
        else:
            unlabeled += 1
    # P0-A: 서술체(따옴표 밖)는 해라체만 — 합쇼체는 위반
    narration = QUOTE.sub("", text)
    return {
        "labeled": labeled,
        "unlabeled": unlabeled,
        "hapsyo": len(HAPSYO.findall(narration)),
        "chars": len(text),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompts", required=True, help="[{msgs:[...]}] JSON")
    ap.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="max_tokens:effort (예: 1024:none 2048:medium)",
    )
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--price", default="0.10,0.60,0.01",
                    help="in,out,cache_read USD/M (분석 단가 — 캐시 순서 오염 보정용)")
    ap.add_argument("--dump", default=None, help="원문 저장 경로 (질적 대조용)")
    args = ap.parse_args()
    P_IN, P_OUT, P_CACHE = [float(x) for x in args.price.split(",")]

    key = api_key()
    prompts = json.load(open(args.prompts, encoding="utf-8"))
    print(f"프롬프트 {len(prompts)}건 × 설정 {len(args.configs)}종 × {args.repeat}회\n")

    rows = {}
    for cfg in args.configs:
        mt, eff = cfg.split(":")
        mt = int(mt)
        eff = None if eff == "-" else eff
        res = []
        for i, p in enumerate(prompts):
            for _ in range(args.repeat):
                r = call(key, args.model, p["msgs"], mt, eff)
                if "error" in r:
                    print(f"  [{cfg}] #{i} ❌ {r['error']}")
                    continue
                r.update(score(r["text"]))
                # 실과금(usage.cost)은 **호출 순서에 따라 캐시 적중이 달라져** 설정 간
                # 비교를 오염시킨다 (첫 설정이 캐시 미스를 전부 떠안음, 2026-08-13 실측).
                # 입력이 동일한 A/B 에서는 분석 단가가 정본이다.
                unc = max(0, r["in"] - r["cached"])
                r["calc"] = (unc * P_IN + r["cached"] * P_CACHE + r["out"] * P_OUT) / 1e6
                r["prompt_idx"] = i
                res.append(r)
            print(f"  [{cfg}] {i+1}/{len(prompts)}", end="\r", flush=True)
        rows[cfg] = res
        print(" " * 40, end="\r")

    hdr = (
        "%-14s %7s %7s %8s %8s %7s %8s %8s %5s %6s %6s"
        % ("config", "ms p50", "ms p90", "reasoning", "out", "본문", "실과금", "분석단가", "절단", "라벨%", "합쇼체")
    )
    print(hdr)
    print("-" * len(hdr))
    for cfg, res in rows.items():
        if not res:
            print(f"{cfg:<14} (표본 없음)")
            continue
        ms = sorted(r["ms"] for r in res)
        p50 = ms[len(ms) // 2]
        p90 = ms[min(int(len(ms) * 0.9), len(ms) - 1)]
        lab = sum(r["labeled"] for r in res)
        unl = sum(r["unlabeled"] for r in res)
        print(
            "%-14s %7.0f %7.0f %8.0f %8.0f %7.0f %8.2f %8.2f %5d %6.1f%% %6d"
            % (
                cfg,
                p50,
                p90,
                statistics.mean(r["reason"] for r in res),
                statistics.mean(r["out"] for r in res),
                statistics.mean(r["chars"] for r in res),
                statistics.mean(r["cost"] for r in res) * KRW,
                statistics.mean(r["calc"] for r in res) * KRW,
                sum(1 for r in res if r["finish"] == "length"),
                100 * lab / max(1, lab + unl),
                sum(r["hapsyo"] for r in res),
            )
        )
    if args.dump:
        Path(args.dump).write_text(json.dumps(
            {c: [{"prompt": r["prompt_idx"], "text": r["text"]} for r in rs]
             for c, rs in rows.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n원문 저장: {args.dump}")
    print("\n※ 실과금 = usage.cost — **호출 순서의 캐시 적중에 오염**됨. 설정 비교는 분석단가를 볼 것")
    print("※ 절단 = finish_reason 'length' (예산 초과로 서술이 끊긴 호출 수)")
    print("※ 라벨% = 원문 기준 `별칭: \"대사\"` 준수율 (서버 후처리 이전)")
    print("※ 합쇼체 = 서술체 P0-A 위반 (따옴표 밖 '~습니다/~입니다')")


if __name__ == "__main__":
    main()
