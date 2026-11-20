---
id: "testing/session-test-entry"
project: "login_demo"
type: Procedure
title: "login_demo 会话测试入口与运行命令"
description: "login_demo 会话单元测试已迁移至 tests/auth/test_session.py，统一入口为 python -m pytest tests/auth/test_session.py -q，实测 3 passed。"
tags: ["testing", "pytest", "session", "auth", "entrypoint", "command"]
sources: ["tests/auth/test_session.py", "docs/testing-guide.md", "docs/session-rules.md", "app/session.py", "python -m pytest tests/auth/test_session.py -q", "python -m pytest -q"]
status: verified
created_at: "2026-11-20T08:17:12.411Z"
updated_at: "2026-11-20T08:17:41.683Z"
revision: 2
---

## 结论

| 项 | 值 |
| --- | --- |
| 测试文件 | `tests/auth/test_session.py`（原 `tests/test_session.py` 已迁走，旧路径不存在） |
| 运行命令（CI 唯一认可形式） | `python -m pytest tests/auth/test_session.py -q` |
| 全量执行命令 | `python -m pytest -q` |
| 实测结果 | `3 passed in 0.01s`（2026-11-20 在本工作区执行，单文件与全量均通过） |

## 运行步骤

```bash
# 1. 在项目根目录（包含 app/、docs/、tests/ 的那一层）执行
cd runs/pi_live_workspace

# 2. 如有虚拟环境则先激活（当前无 .venv，可跳过，见下方"环境差异"）
source .venv/bin/activate

# 3. 跑测试
python -m pytest tests/auth/test_session.py -q

# 4. 或跑全部测试
python -m pytest -q
```

## 硬性约定（来自测试指南）

- 必须使用 `python -m pytest ...`，**不要**直接敲 `pytest tests/auth/test_session.py`；项目 CI 只认 `python -m pytest` 形式。
- 不要修改测试文件来让测试变绿，测试文件由维护者负责。
- 新增功能需补对应用例，并在提交说明中写明用例名。

## 关键用例与语义

- `test_expire_boundary`：`now == expires_at` 必须为 `False`；`expires_at - 1` 为 `True`。
- `test_refresh_extends_ttl`：续期后到期时间 = 请求到达时刻 + `SESSION_TTL_SECONDS`（30 分钟 = 1800 秒）。
- `test_logout_invalidates`：`logout` 后同一令牌立即失效，且重复 `logout` 返回 `False`。

规则依据：`docs/session-rules.md` 要求有效条件写作 `now < expires_at`，禁止 `now <= expires_at`（`app/session.py` 中 `is_session_valid` 已按此实现）。

## 迁移说明

- 测试已从 `tests/test_session.py` 移动到 `tests/auth/test_session.py`。
- 测试文件内部的根目录探测逻辑基于 `Path(__file__)` 向上查找 `app/` 目录，移动后无需改动即可从新路径导入 `app.*`。
- `docs/testing-guide.md` 的"测试入口"已同步更新为新路径，`updated` 改为 `2026-11-20`。

## 环境差异（已核对，需注意）

- `docs/testing-guide.md` 要求"运行前先激活虚拟环境：`source .venv/bin/activate`"，但当前工作区**没有 `.venv` 目录**。
- 实测直接用系统 `python`（Python 3.11.2，pytest 9.2.0）即可通过，无需激活虚拟环境。
- 若后续新建 `.venv`，再按文档先激活。

## 核对清单

1. `tests/auth/test_session.py` 是否存在，是否仍包含上述 3 个用例；旧 `tests/test_session.py` 应不存在。
2. `docs/testing-guide.md` 的"测试入口"是否仍为 `python -m pytest tests/auth/test_session.py -q`。
3. 重新执行该命令确认全绿，若用例数变化需更新本记忆。
4. `app/session.py` 中 `SESSION_TTL_SECONDS` 是否仍为 `30 * 60`。
