---
okf_version: "0.2"
project: "login_demo"
---

# login_demo 长期记忆变更日志
- `2026-11-20T09:36:44.067Z` **WRITE** `testing/session-test-entry` — rev 1 | title="login_demo 会话测试入口与运行命令" | sources=[docs/testing-guide.md, tests/test_session.py, app/session.py, docs/session-rules.md, command: python -m pytest tests/test_session.py -q]
- `2026-11-20T09:37:08.250Z` **UPDATE** `testing/session-test-entry` — rev 1 -> 2 | 会话测试文件由 tests/test_session.py 迁移到 tests/auth/test_session.py，并同步更新 docs/testing-guide.md 的路径与命令；已实际运行 `python -m pytest tests/auth/test_session.py -q` 与 `python -m pytest tests -q`，均为 3 passed。 | sources=[docs/testing-guide.md, tests/auth/test_session.py, app/session.py, app/auth.py, docs/session-rules.md, command: python -m pytest tests/auth/test_session.py -q]
- `2026-11-20T09:37:14.522Z` **WRITE** `testing/temp-debug-note` — rev 1 | title="临时排查记录（验证删除动作）" | sources=[docs/testing-guide.md]
- `2026-11-20T09:37:15.689Z` **DELETE** `testing/temp-debug-note` — 临时排查记录，仅用于验证删除动作，验证完成即删除。
