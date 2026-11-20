#!/usr/bin/env bash
# 一键运行作业一端到端验证：
# - 若环境已配置大模型 API Key（DEEPSEEK_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY）且未传 --offline-cli，
#   自动调用真实 pi 扩展（scripts/run_pi_with_llm.sh）跑通独立会话并更新 runs/ 与 screenshots/；
# - 否则以离线 CLI 模式运行 verify_e2e.ts，产物写入 runs/cli_offline/，避免覆盖真实 pi 日志与截图。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

OFFLINE_CLI=0
for arg in "$@"; do
  if [[ "${arg}" == "--offline-cli" ]]; then
    OFFLINE_CLI=1
  fi
done

cd "${TASK_DIR}"

if [[ "${OFFLINE_CLI}" -eq 0 ]] && [[ -n "${DEEPSEEK_API_KEY:-}${OPENAI_API_KEY:-}${ANTHROPIC_API_KEY:-}" ]]; then
  exec bash "${SCRIPT_DIR}/run_pi_with_llm.sh"
fi

echo "[离线模式] 未检测到模型 API Key（或指定了 --offline-cli），执行独立进程 CLI 存储验证..."
PI_VERIFY_OUTPUT_DIR="${TASK_DIR}/runs/cli_offline" npm run verify
echo ""
echo "离线 CLI 验证完成，输出保存在 ${TASK_DIR}/runs/cli_offline/（未覆盖真实 pi 日志与 screenshots/）。"
echo "如需使用真实 pi + 大模型重新生成 runs/ 与 screenshots/，请先配置 DEEPSEEK_API_KEY 后直接运行 bash scripts/run_all.sh。"
