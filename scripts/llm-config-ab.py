#!/usr/bin/env python3
"""LLM 설정 A/B — 실 운영 프롬프트를 재생해 max_tokens × reasoning effort 조합 비교.

플레이 런이 아니라 **DB 에 저장된 실제 프롬프트(turns.llm_prompt)를 재생**한다.
합성 프롬프트로는 추론 소비량을 못 잰다 — Luna 의 추론 토큰은 프롬프트 복잡도에
비례해서, 단순 프롬프트에선 effort=max 도 50토큰이지만 실제 서술 프롬프트(8k tok
·형식 제약 다수)에선 500토큰을 넘는다 (2026-08-13 실측).

측정: 레이턴시 · 추론/출력 토큰 · 실과금 · finish_reason(length=절단) ·
      라벨 준수(`별칭: "대사"` — 시스템 프롬프트 P0-B) · 합쇼체 누출(P0-A 위반)

표본: 기본 **15건**(`--limit`). 2026-08-13 평가는 40건으로 돌렸고 그 수치가 arch/25
부록 E 에 남아 있다 — 15건과 직접 비교할 때는 표본 차이를 감안한다.
15건에서 잡히는 것과 못 잡는 것:
  - 잡힘: 형식 결함률 ~15% 이상(기대 2건+), 절단(finish=length), 추론 토큰량,
          레이턴시 중앙값, 단가 — 모두 건별 신호가 크다
  - 못 잡음: 한 자릿수 % 차이. 예로 gemini 라벨 준수 89.9%(40건 중 4건 미준수)는
          15건이면 기댓값 1.5건이라 0건이 나올 확률이 ~19% 다. 미세 차이 판정은
          3층(프로덕션 `llm_speech_audit` 누적)의 몫이고 이 층은 **선별용**이다.

사용법:
  python3 scripts/llm-config-ab.py --model openai/gpt-5.6-luna \
      --prompts /tmp/prompts.json --configs 1024:none 2048:medium
  python3 scripts/llm-config-ab.py ... --limit 40   # 정밀 판정이 필요할 때만
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


def _env(name):
    path = Path(__file__).resolve().parent.parent / "server" / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            val = line.split("=", 1)[1]
            # server/.env 는 값 뒤에 ` # 설명` 을 붙여 쓴다. 안 떼면 프로바이더 이름에
            # 주석이 통째로 붙어 allowlist 가 깨진 채 요청이 나간다(2026-08-14 실측).
            if not val.lstrip().startswith(('"', "'")):
                val = val.split(" #", 1)[0]
            return val.strip().strip("\"'")
    return None


def api_key():
    key = _env("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY 없음")
    return key


def provider_routing(model):
    """운영과 동일한 OpenRouter provider 라우팅을 server/.env 에서 재현한다.

    [2026-08-14] 이게 없어서 **레이턴시가 계속 과대 측정**됐다. 운영은
    `LLM_PROVIDER_ONLY_MAP` 으로 Gemma 31B 를 Friendli|Venice|Novita|CoreWeave 로
    묶고 `sort=throughput` 으로 고르는데, 하네스는 아무 제약 없이 쏴서 느린
    프로바이더에 붙었다. 같은 모델을 같은 기간에 재도:
        하네스 p50 8,378ms / p90 18,618ms   vs   운영 p50 3,165 / p90 11,049
    라우팅을 안 맞추면 allowlist 가 걸린 모델(Gemma)만 불리해져, 신규 후보와의
    속도 비교가 통째로 기운다.
    """
    routing = {}
    sort = _env("LLM_PROVIDER_SORT")
    if sort:
        routing["sort"] = sort
    ignore = _env("LLM_PROVIDER_IGNORE")
    if ignore:
        routing["ignore"] = [s.strip() for s in ignore.split(",") if s.strip()]
    raw = _env("LLM_PROVIDER_ONLY_MAP") or ""
    for entry in raw.split(";"):
        k, _, v = entry.partition("=")
        if k.strip() == model and v.strip():
            routing["only"] = [s.strip() for s in v.split("|") if s.strip()]
    return routing


def call(
    key, model, msgs, max_tokens, effort, penalty=False, temperature=None, routing=None
):
    body = {"model": model, "messages": msgs, "max_tokens": max_tokens}
    if routing:
        body["provider"] = routing
    if effort:
        body["reasoning"] = {"effort": effort}
    # 운영 재현 — 메인 서술은 temperature 0.8 + penalty 0.4/0.3 을 보낸다(불변식 50).
    # penalty 미지원 모델(GPT-5·Gemini 계열)에 붙이면 무시되거나 라우팅이 막히므로
    # **지원 모델에만** 켠다. 안 맞추면 반복 지표가 지원 모델에 불리하게 나온다.
    if temperature is not None:
        body["temperature"] = temperature
    if penalty:
        body["frequency_penalty"] = 0.4
        body["presence_penalty"] = 0.3
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
    ap.add_argument(
        "--limit",
        type=int,
        default=15,
        help="재생할 프롬프트 수 (기본 15, 0=전량). 파일에 몇 건이 들었든 여기서 자른다",
    )
    ap.add_argument("--price", default="0.10,0.60,0.01",
                    help="in,out,cache_read USD/M (분석 단가 — 캐시 순서 오염 보정용)")
    ap.add_argument("--dump", default=None, help="원문 저장 경로 (질적 대조용)")
    ap.add_argument("--penalty", action="store_true",
                    help="frequency/presence_penalty 동봉 (penalty 지원 모델만 — 운영 재현)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument(
        "--no-routing",
        action="store_true",
        help="server/.env 의 provider 라우팅(only/sort/ignore) 재현을 끈다 (기본은 켬)",
    )
    args = ap.parse_args()
    P_IN, P_OUT, P_CACHE = [float(x) for x in args.price.split(",")]

    key = api_key()
    routing = None if args.no_routing else provider_routing(args.model)
    prompts = json.load(open(args.prompts, encoding="utf-8"))
    total = len(prompts)
    if args.limit and args.limit > 0:
        prompts = prompts[: args.limit]
    calls = len(prompts) * len(args.configs) * args.repeat
    print(
        f"프롬프트 {len(prompts)}건"
        + (f" (파일 {total}건 중)" if len(prompts) < total else "")
        + f" × 설정 {len(args.configs)}종 × {args.repeat}회 = 요청 {calls}건"
    )
    # 라우팅을 찍어 둔다 — 이걸 안 맞추면 레이턴시 비교가 통째로 기운다.
    print(f"provider 라우팅: {routing or '(없음)'}\n")

    rows = {}
    for cfg in args.configs:
        mt, eff = cfg.split(":")
        mt = int(mt)
        eff = None if eff == "-" else eff
        res = []
        for i, p in enumerate(prompts):
            for _ in range(args.repeat):
                r = call(
                    key, args.model, p["msgs"], mt, eff,
                    args.penalty, args.temperature, routing,
                )
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
