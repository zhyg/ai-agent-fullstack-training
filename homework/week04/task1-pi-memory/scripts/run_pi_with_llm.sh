#!/usr/bin/env bash
# 一键使用真实 pi coding agent + project-memory 扩展 + 真实大模型跑通作业一三步验证
# （跨 3 个独立 pi --no-session 进程），写入 runs/step{1,2,3}_*.txt 并渲染 3 张终端截图到 screenshots/。
#
# 使用前请配置任意 pi 支持的模型 API Key，例如：
#   export DEEPSEEK_API_KEY="sk-..."
#   export PI_PROVIDER="deepseek"            # 默认 deepseek
#   export PI_MODEL="deepseek-v4-flash"      # 默认 deepseek-v4-flash
#
# 运行方式：
#   bash scripts/run_pi_with_llm.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEEK_DIR="$(cd "${TASK_DIR}/.." && pwd)"
RENDERER="${WEEK_DIR}/scripts/render_terminal_png.py"
PY_BIN="${WEEK_DIR}/task2-hybrid-rag/.venv/bin/python"
if [[ ! -x "${PY_BIN}" ]]; then
  PY_BIN="$(command -v python3)"
fi

PI_BIN="${TASK_DIR}/node_modules/.bin/pi"
if [[ ! -x "${PI_BIN}" ]]; then
  echo "未找到 ${PI_BIN}，请先在 ${TASK_DIR} 下运行 npm install" >&2
  exit 1
fi

export PI_PROVIDER="${PI_PROVIDER:-deepseek}"
export PI_MODEL="${PI_MODEL:-deepseek-v4-flash}"

cd "${TASK_DIR}"
node --import tsx scripts/run_pi_live.ts

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 1：pi 真实会话写入持久化项目长期记忆 (${PI_MODEL})" \
  --command "pi --no-session -e extensions/project-memory.ts --provider ${PI_PROVIDER} --model ${PI_MODEL} -p '...'" \
  --input "${TASK_DIR}/runs/step1_write.txt" \
  --output "${TASK_DIR}/screenshots/step1_write.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 2：全新 pi 会话读取记忆并核对文件存在性 (${PI_MODEL})" \
  --command "pi --no-session -e extensions/project-memory.ts --provider ${PI_PROVIDER} --model ${PI_MODEL} -p '...'" \
  --input "${TASK_DIR}/runs/step2_new_session_read.txt" \
  --output "${TASK_DIR}/screenshots/step2_new_session_read.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 3：全新 pi 会话迁移测试、跑测并更新记忆 (${PI_MODEL})" \
  --command "pi --no-session -e extensions/project-memory.ts --provider ${PI_PROVIDER} --model ${PI_MODEL} -p '...'" \
  --input "${TASK_DIR}/runs/step3_migrate_update.txt" \
  --output "${TASK_DIR}/screenshots/step3_migrate_update.png"

echo ""
echo "全部 3 个独立 pi 会话（${PI_PROVIDER}/${PI_MODEL}）执行完成，日志与 3 张截图已更新至 ${TASK_DIR}/screenshots/"
