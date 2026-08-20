"""
초대 코드 발급 공용 헬퍼 (arch/107 §8).

비공개 테스트 가입 게이트(`INVITE_CODE_REQUIRED`)가 켜지면 신규 계정을 만드는
모든 검증 스크립트가 400 으로 막힌다. 서버에 "테스터 도메인은 예외" 같은 구멍을
두면 게이트 자체가 무의미해지므로, 대신 스크립트가 로컬 어드민 토큰으로 그때그때
1회용 코드를 발급받아 쓴다.

스크립트마다 `api()` 시그니처가 제각각이라(반환이 dict / (status, dict) / None 등)
이 모듈은 각 스크립트의 api 를 쓰지 않고 requests 로 직접 호출한다.

사용:
    from invite_util import add_invite_code
    body = add_invite_code({"email": ..., "password": ..., "nickname": ...}, BASE)
    api("POST", "/auth/register", body)
"""

import os

import requests

__all__ = ["mint_invite_code", "add_invite_code"]

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "server", ".env")


def _admin_token() -> str:
    """환경변수 우선, 없으면 server/.env 에서 읽는다 (로컬 검증 전용)."""
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if token:
        return token
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("ADMIN_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def mint_invite_code(base: str, note: str = "script 자동 발급", timeout: int = 10):
    """
    게이트가 켜져 있으면 1회용 초대 코드를 발급해 반환. 꺼져 있으면 None.

    실패해도 예외를 던지지 않는다 — 호출부는 코드 없이 register 를 시도하고
    서버 거절 메시지를 그대로 보게 된다(원인이 드러나는 편이 낫다).
    """
    try:
        st = requests.get(f"{base}/auth/invite-status", timeout=timeout)
        if not st.ok or not st.json().get("required"):
            return None
    except Exception:
        return None  # 게이트 상태를 모르면 굳이 발급하지 않는다

    token = _admin_token()
    if not token:
        print("⚠️  초대 게이트가 켜져 있는데 ADMIN_TOKEN 을 못 찾았습니다 — 가입이 거절됩니다.", flush=True)
        return None

    try:
        r = requests.post(
            f"{base}/admin/invite-codes",
            json={"maxUses": 1, "note": note},
            headers={"x-admin-token": token},
            timeout=timeout,
        )
        if not r.ok:
            print(f"⚠️  초대 코드 발급 실패: {r.status_code} {r.text[:120]}", flush=True)
            return None
        return r.json().get("code")
    except Exception as e:
        print(f"⚠️  초대 코드 발급 실패: {e}", flush=True)
        return None


def add_invite_code(body: dict, base: str, note: str = "script 자동 발급") -> dict:
    """register 바디에 초대 코드를 채워 반환. 게이트가 꺼져 있으면 원본 그대로."""
    code = mint_invite_code(base, note)
    if code:
        return {**body, "inviteCode": code}
    return body
