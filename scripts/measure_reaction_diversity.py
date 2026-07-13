#!/usr/bin/env python3
"""
V11 — NPC 반응 다양성 계측 (arch/69 B0 정본)

turns.llm_npc_reaction(arch/69 B0 저장)을 전수 조회해, NPC posture별
reactionType 분포와 immediateGoal의 정보/자기목적 편향을 계측한다.

B1(반응 자기목적 주입) 전후 A/B 비교의 기준선. "잡담에도 immediateGoal이
정보 탐색으로 수렴"하는 §1 진단을 수치로 포착한다.

사용:
  python3 scripts/measure_reaction_diversity.py            # 전체 run
  python3 scripts/measure_reaction_diversity.py --run <id> # 특정 run
  python3 scripts/measure_reaction_diversity.py --pack graymar_v1
"""
import argparse
import json
import os
import re
import subprocess
from collections import defaultdict

DB_CONTAINER = "textRpg-db"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# immediateGoal 분류 — 정보축 vs 자기목적축 (word-level, 과매칭 주의)
INFO_KW = [
    "정보", "탐색", "파악", "캐", "알아내", "알아보", "단서", "진실", "확인",
    "떠보", "의도", "속셈", "비밀", "실체", "정체", "신뢰를 얻", "신뢰 얻",
    "더 깊", "캐묻", "추궁", "심문",
]
SELF_KW = [
    "장사", "손님", "팔", "일감", "일거리", "청소", "재고", "정리", "마무리",
    "경계", "쫓", "내보내", "잡담", "안부", "대접", "쉬", "휴식", "거래",
    "물건", "값", "흥정", "자기 일", "본업", "생계", "빚", "돈 벌",
    "평화", "조용", "무사", "거리 두", "엮이지",
]


def classify_goal(goal: str) -> str:
    info = any(k in goal for k in INFO_KW)
    self_ = any(k in goal for k in SELF_KW)
    if info and not self_:
        return "INFO"
    if self_ and not info:
        return "SELF"
    if info and self_:
        return "MIXED"
    return "OTHER"


def load_postures(pack: str) -> dict:
    path = os.path.join(ROOT, "content", pack, "npcs.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    items = d.get("npcs", d) if isinstance(d, dict) else d
    return {
        n["npcId"]: n.get("basePosture", "CAUTIOUS")
        for n in items
        if isinstance(n, dict) and "npcId" in n
    }


def fetch_reactions(run_id: str | None) -> list:
    where = "llm_npc_reaction IS NOT NULL"
    if run_id:
        where += f" AND run_id = '{run_id}'"
    q = f"SELECT llm_npc_reaction::text FROM turns WHERE {where} ORDER BY created_at;"
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "user", "-d", "textRpg", "-At", "-c", q],
        capture_output=True, text=True,
    ).stdout
    rows = []
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--pack", default="graymar_v1")
    args = ap.parse_args()

    postures = load_postures(args.pack)
    reactions = fetch_reactions(args.run)
    if not reactions:
        print("⚠️  llm_npc_reaction 데이터 없음. LOCATION 턴을 먼저 플레이하세요.")
        return

    # posture별 reactionType 분포
    by_posture = defaultdict(lambda: defaultdict(int))
    goal_by_posture = defaultdict(lambda: defaultdict(int))
    total = len(reactions)
    goal_total = defaultdict(int)

    for r in reactions:
        npc_id = r.get("npcId", "?")
        posture = postures.get(npc_id, "UNKNOWN")
        by_posture[posture][r.get("reactionType", "?")] += 1
        gcls = classify_goal(r.get("immediateGoal", ""))
        goal_by_posture[posture][gcls] += 1
        goal_total[gcls] += 1

    print(f"=== V11 반응 다양성 베이스라인 (표본 {total}건, pack={args.pack}) ===\n")

    print("[posture별 reactionType 분포]")
    for posture in sorted(by_posture):
        dist = by_posture[posture]
        n = sum(dist.values())
        parts = ", ".join(f"{k}:{v}" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
        print(f"  {posture:12s} (n={n:2d}): {parts}")

    print("\n[immediateGoal 정보/자기목적 분류]")
    info = goal_total["INFO"]
    self_ = goal_total["SELF"]
    mixed = goal_total["MIXED"]
    other = goal_total["OTHER"]
    print(f"  INFO(정보축)   : {info:3d} ({100*info/total:.0f}%)")
    print(f"  SELF(자기목적) : {self_:3d} ({100*self_/total:.0f}%)")
    print(f"  MIXED          : {mixed:3d} ({100*mixed/total:.0f}%)")
    print(f"  OTHER          : {other:3d} ({100*other/total:.0f}%)")
    print(f"\n  → 정보 편향도(INFO/전체): {100*info/total:.0f}%  "
          f"(B1 목표: 자기목적·MIXED 비중 상승, posture별 분화)")

    print("\n[posture별 goal 분류]")
    for posture in sorted(goal_by_posture):
        g = goal_by_posture[posture]
        n = sum(g.values())
        parts = ", ".join(f"{k}:{v}" for k, v in sorted(g.items(), key=lambda x: -x[1]))
        print(f"  {posture:12s} (n={n:2d}): {parts}")


if __name__ == "__main__":
    main()
