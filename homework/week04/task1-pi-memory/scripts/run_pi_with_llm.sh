#!/usr/bin/env bash
# 一键使用真实 pi coding agent + project-memory 扩展跑通作业一三步验证（跨 3 个独立 pi 会话）。
#
# 使用前请配置任意 pi 支持的模型 API Key，例如：
#   export DEEPSEEK_API_KEY="sk-..."   # 或 OPENAI_API_KEY / ANTHROPIC_API_KEY
#   export PI_PROVIDER="deepseek"      # 可选，按需传 --provider / --model
#   export PI_MODEL="deepseek-chat"    # 可选
#
# 运行方式：
#   bash scripts/run_pi_with_llm.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXT_PATH="${TASK_DIR}/extensions/project-memory.ts"
RUNS_DIR="${TASK_DIR}/runs"
WORK_DIR="${RUNS_DIR}/pi_live_workspace"
MEMORY_ROOT="${RUNS_DIR}/pi_live_memory"

mkdir -p "${RUNS_DIR}"
rm -rf "${WORK_DIR}" "${MEMORY_ROOT}"
cp -R "${TASK_DIR}/login_demo" "${WORK_DIR}"

PI_BIN="${TASK_DIR}/node_modules/.bin/pi"
if [[ ! -x "${PI_BIN}" ]]; then
  echo "未找到 ${PI_BIN}，请先在 ${TASK_DIR} 下运行 npm install" >&2
  exit 1
fi

EXTRA_ARGS=()
if [[ -n "${PI_PROVIDER:-}" ]]; then
  EXTRA_ARGS+=(--provider "${PI_PROVIDER}")
fi
if [[ -n "${PI_MODEL:-}" ]]; then
  EXTRA_ARGS+=(--model "${PI_MODEL}")
fi

export PI_MEMORY_ROOT="${MEMORY_ROOT}"
export PI_MEMORY_PROJECT_ID="login_demo"

echo "=== [会话 1/3] 写入项目长期记忆 ==="
(
  cd "${WORK_DIR}"
  "${PI_BIN}" --no-session -e "${EXT_PATH}" "${EXTRA_ARGS[@]}" -p \
    "读取当前项目的会话测试文件和测试说明，将测试路径和运行命令保存到项目长期记忆，附上来源。返回实际保存路径。"
) | tee "${RUNS_DIR}/pi_live_step1.txt"

echo ""
echo "=== [会话 2/3] 全新会话读取并核对记忆 ==="
(
  cd "${WORK_DIR}"
  "${PI_BIN}" --no-session -e "${EXT_PATH}" "${EXTRA_ARGS[@]}" -p \
    "从当前项目长期记忆中查找会话测试入口，再核对当前文件是否存在。"
) | tee "${RUNS_DIR}/pi_live_step2.txt"

echo ""
echo "=== [会话 3/3] 迁移测试、修改说明、运行新测试并更新记忆 ==="
(
  cd "${WORK_DIR}"
  "${PI_BIN}" --no-session -e "${EXT_PATH}" "${EXTRA_ARGS[@]}" -p \
    "将会话测试迁移到 tests/auth/test_session.py，同步修改测试说明，运行新测试命令。根据实际结果更新原来的长期记忆。"
) | tee "${RUNS_DIR}/pi_live_step3.txt"

echo ""
echo "全部 3 个独立 pi 会话执行完成，输出已保存至 ${RUNS_DIR}/pi_live_step{1,2,3}.txt"
