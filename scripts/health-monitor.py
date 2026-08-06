#!/usr/bin/env python3
"""
운영 헬스 모니터 — pull형 어드민 관제를 push형 경보로 (하네스 보강 #4, 2026-08-06)

10분 주기(launchd com.graymar.health-monitor, StartInterval 600)로 관제 API를
폴링해 임계 초과 시에만 Slack 경보. bug-monitor.py와 같은 패턴(상태 파일 dedup,
.env 웹훅, launchd 상주)이며 시스템 python3 stdlib만 사용한다 (requests 없음).

감시 항목:
  1. server_down  — GET /v1/version 무응답 (launchd KeepAlive가 못 살리는 수준)
  2. db_down      — GET /v1/admin/health 의 ok/db false
  3. llm_stalled  — GET /v1/admin/runs/stuck 중 kind=LLM_STALLED ≥ 1
                    (IDLE_24H 는 방치 런이라 정상 — 경보 제외)
  4. llm_failures — GET /v1/admin/llm/failures 최근 60분 ≥ 3건 (실패율 급등)

경보 정책: 상태 전이(ok→bad)에 1회 + bad 지속 시 6시간 쿨다운 재경보 +
회복 전이(bad→ok)에 ✅ 1회. 같은 상태 반복 알림 없음.

수동 실행: python3 scripts/health-monitor.py [--dry-run]
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.expanduser("~/.hermes/state/graymar-health-monitor.json")
BASE = os.environ.get("HEALTH_BASE", "http://localhost:3000/v1")  # 테스트용 오버라이드
REALERT_COOLDOWN_HOURS = 6
LLM_FAILURE_WINDOW_MIN = 60
LLM_FAILURE_THRESHOLD = 3

DRY_RUN = "--dry-run" in sys.argv


def read_env_value(path, key):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.strip().split("=", 1)[1]
    return None


def http_get(path, headers=None, timeout=10):
    req = urllib.request.Request(f"{BASE}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def send_slack(text):
    if DRY_RUN:
        print(f"[dry-run] Slack: {text}")
        return
    webhook = read_env_value(os.path.join(PROJECT_ROOT, ".env"), "SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL 없음", file=sys.stderr)
        return
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=data, headers={"Content-type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Slack 전송 실패: {e}", file=sys.stderr)


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = f"{STATE_PATH}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def run_checks():
    """(key, bad?, 설명) 목록을 반환. 서버 다운이면 나머지 검사는 생략."""
    results = []

    version = http_get("/version", timeout=5)
    server_up = bool(version and version.get("server"))
    results.append(("server_down", not server_up,
                    "서버 응답 없음 (localhost:3000/v1/version)" if not server_up
                    else f"서버 {version.get('server')} 정상"))
    if not server_up:
        return results  # 아래 검사는 전부 같은 원인으로 실패 — 중복 경보 방지

    admin_token = read_env_value(
        os.path.join(PROJECT_ROOT, "server", ".env"), "ADMIN_TOKEN"
    )
    if not admin_token:
        # 토큰이 없으면 어드민 검사 불가 — 경보 대신 로그만 (설정 문제)
        print("ADMIN_TOKEN 없음 — 어드민 검사 생략", file=sys.stderr)
        return results
    admin_hdr = {"x-admin-token": admin_token}

    health = http_get("/admin/health", headers=admin_hdr)
    db_ok = bool(health and health.get("ok") and health.get("db"))
    results.append(("db_down", not db_ok,
                    f"admin/health 이상: {health}" if not db_ok else "DB 정상"))

    stuck = http_get("/admin/runs/stuck", headers=admin_hdr) or {}
    stalled = [s for s in stuck.get("stuck", []) if s.get("kind") == "LLM_STALLED"]
    results.append((
        "llm_stalled", len(stalled) >= 1,
        f"LLM_STALLED 런 {len(stalled)}건: "
        + ", ".join(f"{s['runId'][:8]}(t{s.get('turnNo')}, {s.get('sinceMinutes')}분)" for s in stalled[:5])
        if stalled else "스톨 런 없음",
    ))

    failures = (http_get("/admin/llm/failures?limit=50", headers=admin_hdr) or {}).get("failures", [])
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LLM_FAILURE_WINDOW_MIN)
    recent = []
    for fl in failures:
        try:
            ts = datetime.fromisoformat(str(fl.get("createdAt", "")).replace("Z", "+00:00"))
            if ts >= cutoff:
                recent.append(fl)
        except ValueError:
            continue
    results.append((
        "llm_failures", len(recent) >= LLM_FAILURE_THRESHOLD,
        f"최근 {LLM_FAILURE_WINDOW_MIN}분 LLM 실패 {len(recent)}건 "
        f"(임계 {LLM_FAILURE_THRESHOLD}) — 예: {str((recent[0].get('error') or {}).get('error', ''))[:120]}"
        if recent else "최근 실패 없음",
    ))
    return results


def main():
    state = load_state()
    now = datetime.now(timezone.utc)
    alerts, recoveries = [], []

    for key, bad, desc in run_checks():
        prev = state.get(key, {})
        prev_bad = prev.get("status") == "bad"
        if bad:
            last_alert = prev.get("last_alert_at")
            cooled = True
            if last_alert:
                try:
                    cooled = now - datetime.fromisoformat(last_alert) >= timedelta(
                        hours=REALERT_COOLDOWN_HOURS
                    )
                except ValueError:
                    pass
            if (not prev_bad) or cooled:
                alerts.append(f"• {key}: {desc}")
                state[key] = {"status": "bad", "last_alert_at": now.isoformat()}
            else:
                state[key] = {"status": "bad", "last_alert_at": last_alert}
        else:
            if prev_bad:
                recoveries.append(f"• {key} 회복: {desc}")
            state[key] = {"status": "ok"}

    if alerts:
        send_slack("🚨 [graymar health] 이상 감지\n" + "\n".join(alerts))
    if recoveries:
        send_slack("✅ [graymar health] 회복\n" + "\n".join(recoveries))
    if not alerts and not recoveries:
        print(f"{now.isoformat()} 이상 없음")

    save_state(state)


if __name__ == "__main__":
    main()
