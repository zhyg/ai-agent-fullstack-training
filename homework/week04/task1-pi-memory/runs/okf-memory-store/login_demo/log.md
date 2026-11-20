---
okf_version: "0.2"
project: "login_demo"
---

# login_demo 长期记忆变更日志
- `2026-11-20T07:43:39.515Z` **WRITE** `testing/session-test-entry` — rev 1 | title="login_demo 会话测试入口与运行命令" | sources=[tests/test_session.py, docs/testing-guide.md]
- `2026-11-20T07:43:40.242Z` **UPDATE** `testing/session-test-entry` — rev 1 -> 2 | 迁移测试至 tests/auth/test_session.py，同步修改 docs/testing-guide.md，实测 3 passed | sources=[tests/auth/test_session.py, docs/testing-guide.md]
- `2026-11-20T07:43:40.471Z` **WRITE** `testing/temp-debug-note` — rev 1 | title="临时排查记录" | sources=[docs/testing-guide.md]
- `2026-11-20T07:43:40.584Z` **DELETE** `testing/temp-debug-note` — 临时排查记录无长期复用价值，验证 delete 动作
