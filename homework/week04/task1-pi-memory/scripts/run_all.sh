#!/usr/bin/env bash
# 一键运行作业一端到端三步验证，并自动生成三张高清终端截图到 screenshots/。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEEK_DIR="$(cd "${TASK_DIR}/.." && pwd)"
RENDERER="${WEEK_DIR}/scripts/render_terminal_png.py"
PY_BIN="${WEEK_DIR}/task2-hybrid-rag/.venv/bin/python"
if [[ ! -x "${PY_BIN}" ]]; then
  PY_BIN="$(command -v python3)"
fi

cd "${TASK_DIR}"
npm run verify

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 1：写入持久化项目长期记忆 (Session 1)" \
  --command "npm run verify  # Step 1: project_memory_write" \
  --input "${TASK_DIR}/runs/step1_write.txt" \
  --output "${TASK_DIR}/screenshots/step1_write.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 2：全新会话读取记忆并核对文件存在性 (Session 2)" \
  --command "npm run verify  # Step 2: project_memory_search (fresh process)" \
  --input "${TASK_DIR}/runs/step2_new_session_read.txt" \
  --output "${TASK_DIR}/screenshots/step2_new_session_read.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业一 · 步骤 3：迁移测试、运行新命令并更新长期记忆 (Session 3)" \
  --command "npm run verify  # Step 3: migrate + pytest + project_memory_update" \
  --input "${TASK_DIR}/runs/step3_migrate_update.txt" \
  --output "${TASK_DIR}/screenshots/step3_migrate_update.png"

echo "作业一全部日志与 3 张截图已生成在 ${TASK_DIR}/screenshots/"
