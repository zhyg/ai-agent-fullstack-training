---
id: "testing/session-test-entry"
project: "login_demo"
type: Procedure
title: "login_demo 会话测试入口与运行命令"
description: "login_demo 会话测试已迁移到 tests/auth/test_session.py，统一运行命令为 python -m pytest tests/auth/test_session.py -q。"
tags: ["testing", "pytest", "session", "auth", "test-path"]
sources: ["docs/testing-guide.md", "tests/auth/test_session.py", "app/session.py", "app/auth.py", "docs/session-rules.md", "command: python -m pytest tests/auth/test_session.py -q"]
status: verified
created_at: "2026-11-20T09:36:44.065Z"
updated_at: "2026-11-20T09:37:08.249Z"
revision: 2
---

## 测试路径

- 测试文件：`tests/auth/test_session.py`（会话单元测试，唯一测试入口文件）
- 被测实现：`app/session.py`（`is_session_valid`、`refresh_expiry`、`SESSION_TTL_SECONDS`）与 `app/auth.py`
- 规则依据：`docs/session-rules.md`、`docs/testing-guide.md`

## 运行命令

```bash
python -m pytest tests/auth/test_session.py -q
```

- 必须使用 `python -m pytest` 形式，CI 只认这种写法；不要直接敲 `pytest tests/auth/test_session.py`。
- 指南要求运行前 `source .venv/bin/activate`；但当前工作区根目录下**不存在** `.venv`，直接运行上述命令即可通过（2026-11-20 实测 3 passed）。
- 全量测试可运行 `python -m pytest tests -q`，同样为 3 passed。
- 测试文件内部已自行把项目根目录插入 `sys.path`，从任意子目录执行也能定位 `app` 包。

## 关键用例

| 用例 | 覆盖点 |
| --- | --- |
| `test_expire_boundary` | `now == expires_at` 返回 `False`；到期前 1 秒返回 `True` |
| `test_refresh_extends_ttl` | 续期后到期时间后推 `SESSION_TTL_SECONDS`（30 分钟） |
| `test_logout_invalidates` | `logout` 后同一令牌判无效；重复 logout 返回 `False` |

## 约定与坑点

- 到期边界语义：有效条件为 `now < expires_at`，等于到期时刻即视为过期。
- 不要为通过测试而修改测试文件（由维护者负责）；新增功能需补对应用例并在提交说明写明用例名。
- 旧路径 `tests/test_session.py` 已不存在，引用测试入口时不要再用它。

## 核对清单

1. `ls tests/auth/test_session.py app/session.py docs/testing-guide.md` 确认文件仍在。
2. 运行 `python -m pytest tests/auth/test_session.py -q`，期望 `3 passed`。
3. 若用例数量、目录或文件名变化，更新本条记忆。
