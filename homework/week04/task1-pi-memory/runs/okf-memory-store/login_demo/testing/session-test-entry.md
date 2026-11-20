---
id: "testing/session-test-entry"
project: "login_demo"
type: Procedure
title: "login_demo 会话测试入口与运行命令"
description: "会话测试已迁移至 tests/auth/test_session.py，统一运行命令更新为 python -m pytest tests/auth/test_session.py -q。"
tags: ["testing", "session", "pytest"]
sources: ["tests/auth/test_session.py", "docs/testing-guide.md"]
status: verified
created_at: "2026-11-20T07:43:39.513Z"
updated_at: "2026-11-20T07:43:40.240Z"
revision: 2
---

# 会话测试入口与运行命令（已迁移更新）

- 当前测试文件路径：`tests/auth/test_session.py`
- 当前统一运行命令：`python -m pytest tests/auth/test_session.py -q`
- 历史路径（已失效）：`tests/test_session.py`（已迁移至 `tests/auth/test_session.py`）
- 最新实测结果：`...                                                                      [100%] | 3 passed in 0.01s`

# 核对清单

1. 确认 `tests/auth/test_session.py` 与 `docs/testing-guide.md` 存在且一致。
2. 旧路径 `tests/test_session.py` 已废弃，不得继续沿用。
