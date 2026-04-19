#!/usr/bin/env python3
"""
LLM 대사 형식 테스트 — 'NPC이름: "대사"' 패턴 준수율 확인
5회 테스트로 Gemma4 26B가 구조화된 대사 형식을 잘 따르는지 검증.
"""

import json
import os
import re
import time
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

# 새 대사 형식 규칙이 추가된 시스템 프롬프트
SYSTEM_PROMPT = """당신은 중세 판타지 왕국을 배경으로 한 텍스트 RPG의 서술자입니다.

## 역할
- 2인칭 시점("당신")으로 플레이어의 행동과 주변 상황을 서술합니다.
- 해라체(~다, ~했다, ~이다) 문어체로 통일합니다.

## ⚠️ 대사 출력 형식 (최우선 — 반드시 준수)
NPC 대사는 반드시 **별도 줄**에 아래 형식으로 작성하세요:

NPC별칭: "대사 내용"

✅ 올바른 예:
```
당신이 다가가자 회계사가 고개를 들었다.

날카로운 눈매의 회계사: "장부 쪽을 살펴봤는데, 수상한 움직임이 있소."

그는 서류를 내려놓으며 주변을 살폈다.
```

✅ 교차 대화:
```
날카로운 눈매의 회계사: "그건 확인이 필요하오."

젊은 경비병: "증거를 보여주시오."
```

### 규칙
- 대사 줄은 반드시 NPC별칭으로 시작, 콜론(:), 공백, 큰따옴표 순서
- 대사 줄 앞뒤에 빈 줄을 넣어 문단 분리
- 서술 텍스트와 대사를 같은 줄에 쓰지 말 것
- 서술체는 해라체, NPC 대사는 NPC 고유 어체

### ❌ 금지
- "그가 말했다. '대사'" ← 대사가 서술과 같은 줄 금지
- 발화자 없이 대사만 쓰기 금지
- @ 기호 사용 금지

## 서술 원칙
- 한국어만 사용. 영어 혼용 금지.
- 주인공은 "당신". 3인칭 금지.
- NPC가 플레이어를 지칭할 때: "그대" 또는 "당신".
- 분량: 3~4문단, 각 문단 2~3문장.
- NPC 대사를 1~2회 포함.
- 플레이어 직접 대사 금지 (행동 묘사만).
- 마크다운, 태그, 선택지 출력 금지. 순수 서술만.

## 출력 형식
산문 + 대사. 대사는 별도 줄에 "NPC별칭: \\"대사\\"" 형식으로."""

USER_PROMPTS = [
    """장소: 시장 거리 (낮)
플레이어 행동: 상인에게 소문을 묻는다 (TALK, 성공)
등장 NPC: 날카로운 눈매의 회계사 (CAUTIOUS, 하오체)
서술하시오.""",

    """장소: 경비대 지구 (밤)
플레이어 행동: 순찰 동선을 관찰한다 (OBSERVE, 부분성공)
등장 NPC: 로넨 경비대장 (CAUTIOUS, 하오체)
서술하시오.""",

    """장소: 잠긴 닻 선술집 (밤)
플레이어 행동: 술꾼에게 소문을 묻는다 (TALK, 성공)
등장 NPC: 수다스러운 뱃사람 (FRIENDLY, 반말), 무뚝뚝한 부두 감독관 (CAUTIOUS, 하오체)
서술하시오. 두 NPC가 번갈아 대화하는 장면 포함.""",

    """장소: 총독 관저 앞 (낮)
플레이어 행동: 경비병에게 접근한다 (TALK, 실패)
등장 NPC: 관저 경비병 (HOSTILE, 합쇼체)
서술하시오.""",

    """장소: 부두 창고 지구 (새벽)
플레이어 행동: 수상한 화물을 조사한다 (INVESTIGATE, 성공)
등장 NPC: 항만 인부 (FRIENDLY, 해요체)
서술하시오.""",
]


def call_llm(prompt_idx: int) -> dict | None:
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
        "max_tokens": 1024,
        "temperature": 0.8,
        "provider": {"sort": "latency"},
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            return {"text": text, "model": data.get("model", MODEL)}
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def analyze_format(text: str) -> dict:
    """대사 형식 준수 분석"""
    lines = text.split("\n")

    # 패턴 1: "NPC이름: \"대사\"" (올바른 형식)
    correct_pattern = re.compile(r'^([^":]{2,}):\s*"([^"]+)"')
    # 패턴 2: 서술 안에 섞인 대사 (기존 형식)
    inline_pattern = re.compile(r'[가-힣]+[이가은는].*[했했].*\.\s*"[^"]+"')
    # 패턴 3: 발화자 없이 대사만
    orphan_pattern = re.compile(r'^\s*"[^"]+"')

    correct_dialogues = []
    inline_dialogues = []
    orphan_dialogues = []
    narration_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        m = correct_pattern.match(stripped)
        if m:
            correct_dialogues.append({
                "line": i + 1,
                "speaker": m.group(1).strip(),
                "dialogue": m.group(2)[:40],
            })
        elif orphan_pattern.match(stripped):
            orphan_dialogues.append({"line": i + 1, "text": stripped[:60]})
        elif '"' in stripped:
            # 큰따옴표가 있지만 올바른 형식이 아닌 경우
            inline_dialogues.append({"line": i + 1, "text": stripped[:60]})
        else:
            narration_lines.append(stripped)

    total_dialogues = len(correct_dialogues) + len(inline_dialogues) + len(orphan_dialogues)
    compliance = len(correct_dialogues) / total_dialogues * 100 if total_dialogues > 0 else 0

    # 문단 분리 분석
    paragraphs = text.split("\n\n")
    paragraph_count = len([p for p in paragraphs if p.strip()])

    return {
        "total_dialogues": total_dialogues,
        "correct_format": len(correct_dialogues),
        "inline_format": len(inline_dialogues),
        "orphan_format": len(orphan_dialogues),
        "compliance_pct": round(compliance, 1),
        "correct_details": correct_dialogues,
        "inline_details": inline_dialogues,
        "orphan_details": orphan_dialogues,
        "paragraph_count": paragraph_count,
        "total_chars": len(text),
    }


def main():
    print(f"=== 대사 형식 테스트 ({MODEL}) ===\n")
    print("형식: NPC별칭: \"대사\"\n")

    results = []
    total_correct = 0
    total_dialogues = 0

    for i in range(5):
        print(f"[Test {i+1}/5] {USER_PROMPTS[i].split(chr(10))[1][:40]}...")
        resp = call_llm(i)
        if not resp:
            print("  FAILED\n")
            continue

        analysis = analyze_format(resp["text"])
        results.append({
            "prompt_idx": i,
            "text": resp["text"],
            "model": resp["model"],
            **analysis,
        })

        total_correct += analysis["correct_format"]
        total_dialogues += analysis["total_dialogues"]

        print(f"  준수율: {analysis['compliance_pct']}% ({analysis['correct_format']}/{analysis['total_dialogues']})")
        print(f"  문단: {analysis['paragraph_count']}개 | 글자: {analysis['total_chars']}자")

        if analysis["correct_details"]:
            for d in analysis["correct_details"]:
                print(f"    ✅ L{d['line']}: {d['speaker']}: \"{d['dialogue']}\"")
        if analysis["inline_details"]:
            for d in analysis["inline_details"]:
                print(f"    ❌ L{d['line']}: {d['text']}")
        if analysis["orphan_details"]:
            for d in analysis["orphan_details"]:
                print(f"    ⚠️ L{d['line']}: {d['text']}")

        print()
        print(f"  --- 전문 ---")
        for line in resp["text"].split("\n"):
            print(f"  | {line}")
        print(f"  --- 끝 ---\n")

        time.sleep(1)

    # 요약
    print("=" * 60)
    overall = round(total_correct / total_dialogues * 100, 1) if total_dialogues > 0 else 0
    print(f"전체 준수율: {overall}% ({total_correct}/{total_dialogues})")
    print(f"테스트 {len(results)}회 완료")

    # 저장
    out_path = Path(__file__).parent.parent / "playtest-reports" / "dialogue_format_test.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"결과 저장: {out_path}")


if __name__ == "__main__":
    main()
