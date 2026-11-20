#!/usr/bin/env bash
# 一键运行作业二全部三步（建库 -> 三路检索对比与回答 -> 20 分钟同步更新验证），
# 并保存文本日志至 runs/、渲染 3 张高清终端截图至 screenshots/。
#
# 配置 DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY 后运行，
# 将自动调用真实大模型生成带来源引用的回答并刷新截图。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEEK_DIR="$(cd "${TASK_DIR}/.." && pwd)"
RENDERER="${WEEK_DIR}/scripts/render_terminal_png.py"
PY_BIN="${TASK_DIR}/.venv/bin/python"
if [[ ! -x "${PY_BIN}" ]]; then
  PY_BIN="$(command -v python3)"
fi

cd "${TASK_DIR}"
mkdir -p runs screenshots

echo "[1/3] 建立向量 + BM25 索引..."
"${PY_BIN}" ingest.py --overwrite | tee runs/step1_ingest.txt

echo ""
echo "[2/3] 三路查询对比与带来源回答..."
"${PY_BIN}" query.py --mode compare --top-k 5 "$@" | tee runs/step2_compare_answer.txt

echo ""
echo "[3/3] 副本更新至 20 分钟、同步更新两路索引并重查..."
"${PY_BIN}" update_verify.py --top-k 5 "$@" | tee runs/step3_update_verify.txt

"${PY_BIN}" "${RENDERER}" \
  --title "作业二 · 步骤 1：建立索引（BGE 向量 + BM25 同批节点）" \
  --command "python ingest.py --overwrite" \
  --input "${TASK_DIR}/runs/step1_ingest.txt" \
  --output "${TASK_DIR}/screenshots/step1_ingest.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业二 · 步骤 2：三路检索对比 (Vector / BM25 / RRF) 与带来源回答" \
  --command "python query.py --mode compare --top-k 5" \
  --input "${TASK_DIR}/runs/step2_compare_answer.txt" \
  --output "${TASK_DIR}/screenshots/step2_compare_answer.png"

"${PY_BIN}" "${RENDERER}" \
  --title "作业二 · 步骤 3：有效期更新至 20 分钟、两路索引同步更新与重查" \
  --command "python update_verify.py --top-k 5" \
  --input "${TASK_DIR}/runs/step3_update_verify.txt" \
  --output "${TASK_DIR}/screenshots/step3_update_verify.png"

echo ""
echo "作业二全部日志与 3 张截图已生成在 ${TASK_DIR}/screenshots/"
