#!/usr/bin/env python3
"""
버그 리포트 모니터 — DB에서 open 상태 버그 리포트를 조회하여 분석 후 알림
crontab에 등록: 0 * * * * cd /Users/dohamsu/Workspace/graymar && python3 scripts/bug-monitor.py
"""

import subprocess
import json
import sys
import os
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(PROJECT_ROOT, "playtest-reports")
DOCKER_CONTAINER = "textRpg-db"
DB_USER = "user"
DB_NAME = "textRpg"

# .env에서 Slack 웹훅 URL 읽기
def get_slack_webhook():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            if line.startswith("SLACK_WEBHOOK_URL="):
                return line.strip().split("=", 1)[1]
    return None

def query_db(sql):
    """Docker를 통해 PostgreSQL 쿼리 실행"""
    result = subprocess.run(
        ["docker", "exec", DOCKER_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME,
         "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        print(f"DB 오류: {result.stderr}", file=sys.stderr)
        return []
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line:
            rows.append(line.split("\t"))
    return rows

def send_slack(text):
    webhook = get_slack_webhook()
    if not webhook:
        print("Slack 웹훅 URL 없음", file=sys.stderr)
        return
    subprocess.run(
        ["curl", "-s", "-X", "POST", "-H", "Content-type: application/json",
         "--data", json.dumps({"text": text}), webhook],
        capture_output=True, timeout=10
    )

def analyze_reports(reports):
    """카테고리별 분류 및 요약"""
    categories = {}
    for r in reports:
        rid, category, description, status, turn_no, run_id, created_at, recent_turns = r
        if category not in categories:
            categories[category] = []
        categories[category].append({
            "id": rid,
            "description": description or "(설명 없음)",
            "turn_no": turn_no,
            "run_id": run_id,
            "created_at": created_at,
            "recent_turns": recent_turns,
        })
    return categories

def generate_report(categories, total_count):
    """마크다운 리포트 생성"""
    kst = datetime.now(timezone(timedelta(hours=9)))
    lines = [
        f"# 버그 리포트 모니터 — {kst.strftime('%Y-%m-%d %H:%M KST')}",
        f"\n미해결 리포트: **{total_count}건**\n",
    ]

    category_labels = {
        "npc": "NPC 관련",
        "narrative": "서술/내러티브",
        "choices": "선택지",
        "judgment": "판정 시스템",
        "ui": "UI/UX",
        "other": "기타",
    }

    for cat, items in categories.items():
        label = category_labels.get(cat, cat)
        lines.append(f"\n## {label} ({len(items)}건)\n")
        for item in items:
            lines.append(f"- **[{item['id'][:8]}]** T{item['turn_no']} — {item['description']}")
            lines.append(f"  - Run: `{item['run_id'][:8]}...` | {item['created_at']}")

    # 패턴 분석
    lines.append("\n## 패턴 분석\n")
    if "npc" in categories:
        lines.append(f"- NPC 관련 이슈 {len(categories['npc'])}건 — 이름 노출, 태도 불일치, 소개 시스템 점검 필요")
    if "narrative" in categories:
        lines.append(f"- 서술 이슈 {len(categories['narrative'])}건 — LLM 프롬프트 또는 메모리 시스템 점검 필요")
    if "choices" in categories:
        lines.append(f"- 선택지 이슈 {len(categories['choices'])}건 — 이벤트 데이터 또는 선택지 생성 로직 점검 필요")
    if "judgment" in categories:
        lines.append(f"- 판정 이슈 {len(categories['judgment'])}건 — ResolveService 판정 로직 점검 필요")
    if not categories:
        lines.append("- 특이 패턴 없음")

    return "\n".join(lines)

def main():
    # 1. 미해결 버그 리포트 조회
    rows = query_db(
        "SELECT id, category, description, status, turn_no, run_id, "
        "created_at::text, recent_turns::text "
        "FROM bug_reports WHERE status = 'open' ORDER BY created_at DESC;"
    )

    if not rows:
        # 리포트 없으면 조용히 종료
        return

    total = len(rows)
    categories = analyze_reports(rows)

    # 2. 리포트 파일 저장
    kst = datetime.now(timezone(timedelta(hours=9)))
    filename = f"bug-monitor-{kst.strftime('%Y%m%d_%H%M')}.md"
    filepath = os.path.join(REPORT_DIR, filename)
    os.makedirs(REPORT_DIR, exist_ok=True)

    report = generate_report(categories, total)
    with open(filepath, "w") as f:
        f.write(report)

    # 3. 알림 전송
    cat_summary = ", ".join(f"{k}:{len(v)}" for k, v in categories.items())
    message = f"🐛 버그 리포트 모니터: {total}건 미해결 — {cat_summary}\n리포트: {filename}"
    send_slack(message)
    print(f"알림 전송 완료: {total}건, 저장: {filepath}")

if __name__ == "__main__":
    main()
