"""login_demo 登录会话单元测试（对齐 docs/testing-guide.md）。"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保无论从哪个子目录执行测试，都能定位到 login_demo 根包
ROOT = Path(__file__).resolve()
while ROOT.parent != ROOT and not (ROOT / "app").is_dir():
    ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import check, expire_at, issue_token, logout, touch  # noqa: E402
from app.session import SESSION_TTL_SECONDS, is_session_valid, refresh_expiry  # noqa: E402


def test_expire_boundary() -> None:
    """覆盖 now == expires_at，期望返回 False；到期前 1 秒返回 True。"""
    now = 1_700_000_000
    expires = refresh_expiry(now)
    assert is_session_valid(expires - 1, expires) is True
    assert is_session_valid(expires, expires) is False
    assert is_session_valid(expires + 1, expires) is False


def test_refresh_extends_ttl() -> None:
    """覆盖续期后到期时间被推后 30 分钟（SESSION_TTL_SECONDS）。"""
    t0 = 1_700_000_000
    token = issue_token("u_1001", now=t0)
    assert expire_at(token) == t0 + SESSION_TTL_SECONDS

    t1 = t0 + 600
    new_exp = touch(token, now=t1)
    assert new_exp == t1 + SESSION_TTL_SECONDS
    assert check(token, now=new_exp - 1) is True
    assert check(token, now=new_exp) is False


def test_logout_invalidates() -> None:
    """退出登录后，同一个会话令牌应立即判定为无效。"""
    t0 = 1_700_000_000
    token = issue_token("u_1002", now=t0)
    assert check(token, now=t0 + 10) is True
    assert logout(token) is True
    assert check(token, now=t0 + 10) is False
    assert logout(token) is False
