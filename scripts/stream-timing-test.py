#!/usr/bin/env python3
"""
LLM 스트리밍 응답 타이밍 분석 — 5회 테스트
OpenRouter API (Gemma 4 26B) 직접 호출, 청크 도착 시간 측정.
"""

import json
import os
import time
import re
import sys
from pathlib import Path

# .env에서 API 키 로드
env_path = Path(__file__).parent.parent / "server" / ".env"
env_vars = {}
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip()

API_KEY = env_vars.get("OPENAI_API_KEY", "")
BASE_URL = env_vars.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = env_vars.get("OPENAI_MODEL", "google/gemma-4-26b-a4b-it")

if not API_KEY:
    print("ERROR: OPENAI_API_KEY not found in server/.env")
    sys.exit(1)

# 게임 프롬프트 시뮬레이션 (실제 프롬프트와 유사한 길이/스타일)
SYSTEM_PROMPT = """당신은 중세 판타지 정치 음모 RPG '그레이마르'의 내레이터입니다.
2인칭 하오체로 서술하며, 감각적이고 몰입감 있는 묘사를 합니다.
NPC 대사는 반드시 따옴표 안에 작성합니다."""

USER_PROMPTS = [
    """장소: 시장 거리 (낮, 활기찬 분위기)
플레이어 행동: 상인에게 소문을 묻는다 (TALK, 카리스마 판정: 성공)
NPC: 날카로운 눈매의 회계사 (CAUTIOUS, trust: 30)
3~4문단으로 묘사하시오. NPC 대사를 1~2회 포함하시오.""",

    """장소: 경비대 지구 (밤, 긴장된 분위기)
플레이어 행동: 순찰 동선을 관찰한다 (OBSERVE, 통찰 판정: 부분성공)
NPC: 로넨 경비대장 (CAUTIOUS, trust: 45)
3~4문단으로 묘사하시오. NPC 대사를 1~2회 포함하시오.""",

    """장소: 잠긴 닻 선술집 (밤, 어두운 분위기)
플레이어 행동: 뒷골목에서 밀수꾼과 거래한다 (BRIBE, 카리스마 판정: 성공)
NPC: 그림자 상인 (HOSTILE→CAUTIOUS, trust: 15)
3~4문단으로 묘사하시오. NPC 대사를 1~2회 포함하시오.""",

    """장소: 총독 관저 앞 (낮, 위압적인 분위기)
플레이어 행동: 경비병에게 접근한다 (TALK, 카리스마 판정: 실패)
NPC: 관저 경비병 (HOSTILE, trust: 5)
3~4문단으로 묘사하시오. NPC 대사를 1~2회 포함하시오.""",

    """장소: 부두 창고 지구 (새벽, 안개 낀 분위기)
플레이어 행동: 수상한 화물을 조사한다 (INVESTIGATE, 통찰 판정: 성공)
NPC: 항만 인부 (FRIENDLY, trust: 60)
3~4문단으로 묘사하시오. NPC 대사를 1~2회 포함하시오.""",
]


def stream_test(prompt_idx: int):
    """단일 스트리밍 테스트 — 청크별 타이밍 기록"""
    import urllib.request
    import ssl

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dimtale.com",
    }
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPTS[prompt_idx]},
        ],
        "stream": True,
        "max_tokens": 1024,
        "temperature": 0.8,
        "provider": {"sort": "latency"},
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()

    start_time = time.time()
    first_token_time = None
    chunks = []          # (elapsed_sec, token_text, cumulative_chars)
    full_text = ""
    token_count = 0

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            buffer = ""
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        elapsed = time.time() - start_time
                        if first_token_time is None:
                            first_token_time = elapsed
                        full_text += content
                        token_count += 1
                        chunks.append({
                            "t": round(elapsed, 3),
                            "token": content,
                            "cumul_chars": len(full_text),
                        })
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    total_time = time.time() - start_time

    # 문장 경계 분석
    sentence_ends = []
    for i, ch in enumerate(full_text):
        if ch in ".!?。" and i < len(full_text) - 1 and full_text[i + 1] in " \n":
            # 이 문자 위치에 대응하는 시간 찾기
            for c in chunks:
                if c["cumul_chars"] >= i:
                    sentence_ends.append({"char_pos": i, "t": c["t"], "sentence": full_text[max(0,i-40):i+1].strip()})
                    break

    # 따옴표(대사) 위치 분석
    dialogue_spans = []
    for m in re.finditer(r'["\u201C]([^"\u201D]{3,}?)["\u201D]', full_text):
        start_pos = m.start()
        end_pos = m.end()
        start_t = None
        end_t = None
        for c in chunks:
            if start_t is None and c["cumul_chars"] >= start_pos:
                start_t = c["t"]
            if c["cumul_chars"] >= end_pos:
                end_t = c["t"]
                break
        dialogue_spans.append({
            "text": m.group(1)[:30],
            "start_t": start_t,
            "end_t": end_t,
            "char_range": f"{start_pos}-{end_pos}",
        })

    # 줄바꿈 분석
    newline_positions = []
    for i, ch in enumerate(full_text):
        if ch == "\n":
            for c in chunks:
                if c["cumul_chars"] >= i:
                    newline_positions.append({"char_pos": i, "t": c["t"]})
                    break

    # 1초 단위 청크 분석
    second_buckets = {}
    for c in chunks:
        sec = int(c["t"])
        if sec not in second_buckets:
            second_buckets[sec] = {"tokens": 0, "chars": 0, "text": ""}
        second_buckets[sec]["tokens"] += 1
        second_buckets[sec]["chars"] += len(c["token"])
        second_buckets[sec]["text"] += c["token"]

    return {
        "prompt_idx": prompt_idx,
        "total_time": round(total_time, 2),
        "first_token_time": round(first_token_time, 3) if first_token_time else None,
        "total_tokens": token_count,
        "total_chars": len(full_text),
        "tokens_per_sec": round(token_count / total_time, 1) if total_time > 0 else 0,
        "sentence_ends": sentence_ends,
        "dialogue_spans": dialogue_spans,
        "newline_positions": newline_positions,
        "second_buckets": {str(k): {
            "tokens": v["tokens"],
            "chars": v["chars"],
            "text_preview": v["text"][:80],
        } for k, v in sorted(second_buckets.items())},
        "full_text": full_text,
    }


def main():
    print(f"=== LLM 스트리밍 타이밍 분석 ({MODEL}) ===\n")

    results = []
    for i in range(5):
        print(f"[Test {i+1}/5] {USER_PROMPTS[i][:40]}...")
        result = stream_test(i)
        if result:
            results.append(result)
            print(f"  TTFT: {result['first_token_time']}s | Total: {result['total_time']}s | "
                  f"Tokens: {result['total_tokens']} ({result['tokens_per_sec']} t/s) | "
                  f"Chars: {result['total_chars']}")
            print(f"  Sentences: {len(result['sentence_ends'])} | "
                  f"Dialogues: {len(result['dialogue_spans'])} | "
                  f"Newlines: {len(result['newline_positions'])}")
            print()
        else:
            print("  FAILED\n")
        time.sleep(1)  # rate limit 존중

    # 요약 통계
    print("\n" + "=" * 60)
    print("=== 요약 통계 ===")
    if results:
        avg_ttft = sum(r["first_token_time"] for r in results if r["first_token_time"]) / len(results)
        avg_total = sum(r["total_time"] for r in results) / len(results)
        avg_tps = sum(r["tokens_per_sec"] for r in results) / len(results)

        print(f"평균 TTFT (첫 토큰): {avg_ttft:.2f}s")
        print(f"평균 총 시간: {avg_total:.2f}s")
        print(f"평균 토큰/초: {avg_tps:.1f}")

        # 1초 단위 텍스트 누적량 분석
        print("\n=== 초별 텍스트 누적 패턴 ===")
        for r in results:
            print(f"\n[Test {r['prompt_idx']+1}]")
            for sec, data in sorted(r["second_buckets"].items(), key=lambda x: int(x[0])):
                print(f"  {sec}s: +{data['chars']}자 ({data['tokens']}토큰) | {data['text_preview'][:60]}")

        # 대사 타이밍
        print("\n=== 대사 도착 타이밍 ===")
        for r in results:
            if r["dialogue_spans"]:
                for d in r["dialogue_spans"]:
                    print(f"  [Test {r['prompt_idx']+1}] {d['start_t']:.1f}s~{d['end_t']:.1f}s: \"{d['text']}\"")

        # 문장 완성 타이밍
        print("\n=== 문장 완성 타이밍 ===")
        for r in results:
            print(f"\n[Test {r['prompt_idx']+1}]")
            for s in r["sentence_ends"]:
                print(f"  {s['t']:.1f}s: ...{s['sentence'][-30:]}")

    # JSON 저장
    out_path = Path(__file__).parent.parent / "playtest-reports" / "stream_timing_analysis.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n상세 결과 저장: {out_path}")


if __name__ == "__main__":
    main()
