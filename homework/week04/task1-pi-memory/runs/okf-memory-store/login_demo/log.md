---
okf_version: "0.2"
project: "login_demo"
---

# login_demo 长期记忆变更日志
- `2026-11-20T08:17:12.412Z` **WRITE** `testing/session-test-entry` — rev 1 | title="login_demo 会话测试入口与运行命令" | sources=[tests/test_session.py, docs/testing-guide.md, docs/session-rules.md, app/session.py, python -m pytest tests/test_session.py -q]
- `2026-11-20T08:17:41.684Z` **UPDATE** `testing/session-test-entry` — rev 1 -> 2 | 测试迁移至 tests/auth/test_session.py 并同步 docs/testing-guide.md 的测试入口；已执行 python -m pytest tests/auth/test_session.py -q 与 python -m pytest -q，均为 3 passed。原 tests/test_session.py 已不存在。 | sources=[tests/auth/test_session.py, docs/testing-guide.md, docs/session-rules.md, app/session.py, python -m pytest tests/auth/test_session.py -q, python -m pytest -q]
