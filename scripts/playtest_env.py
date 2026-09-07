"""플레이테스트 스크립트 공용 시크릿 로더 (보안 감사 2026-09-07 M7).

정본 테스터 계정(playtest@test.com)의 비밀번호가 공개 docs 레포의 스크립트 29곳에
평문 리터럴로 박혀 있었다. 이제 환경변수 → server/.env 순으로 읽는다.
서버 .env 는 gitignore·0600 이라 공개 레포에는 남지 않는다.

사용: `from playtest_env import playtest_password` 후 `PASSWORD = playtest_password()`.
python 은 실행 스크립트의 디렉터리(scripts/)를 sys.path 에 넣으므로 어디서 실행하든
import 된다.
"""

from __future__ import annotations

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_ENV = os.path.join(_REPO_ROOT, "server", ".env")


def read_server_env(key: str) -> str | None:
    """server/.env 에서 key 를 읽는다 (따옴표 제거). 없으면 None."""
    try:
        with open(_SERVER_ENV, encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def playtest_password() -> str:
    """PLAYTEST_PASSWORD (env 우선, server/.env 폴백). 둘 다 없으면 즉시 실패."""
    v = os.environ.get("PLAYTEST_PASSWORD") or read_server_env("PLAYTEST_PASSWORD")
    if not v:
        raise SystemExit(
            "PLAYTEST_PASSWORD 가 env 에도 server/.env 에도 없습니다 — "
            "테스터 계정 비밀번호는 더 이상 스크립트에 박혀 있지 않습니다."
        )
    return v
