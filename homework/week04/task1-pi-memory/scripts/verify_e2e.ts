#!/usr/bin/env node
/**
 * 作业一三步跨会话端到端验证脚本（使用独立子进程模拟“关闭会话 -> 启动全新会话”）。
 *
 * 步骤 1（会话 1 子进程）：读取 login_demo 的会话测试文件与测试说明，写入持久化长期记忆，输出真实保存路径。
 * 步骤 2（会话 2 全新子进程）：从当前项目长期记忆中检索会话测试入口，并核对对应文件是否存在。
 * 步骤 3（会话 3 全新子进程）：在独立工作副本中迁移测试到 tests/auth/test_session.py，同步修改测试说明，
 *                           真实运行 pytest 验证通过后更新长期记忆（rev 1 -> rev 2），并在会话 4 核对新旧路径与删除动作。
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TASK_DIR = path.resolve(__dirname, "..");
const SOURCE_DEMO = path.join(TASK_DIR, "login_demo");
const CLI_PATH = path.join(TASK_DIR, "src", "cli.ts");
const RUNS_DIR = path.join(TASK_DIR, "runs");
const WORKSPACE_COPY = path.join(RUNS_DIR, "login_demo_workspace");
const MEMORY_ROOT = path.join(RUNS_DIR, "okf-memory-store");

function findPytestPython(): string {
  const candidates = [
    path.resolve(TASK_DIR, "..", "task2-hybrid-rag", ".venv", "bin", "python"),
    "python3",
    "python",
  ];
  for (const bin of candidates) {
    try {
      execFileSync(bin, ["-m", "pytest", "--version"], { stdio: "pipe" });
      return bin;
    } catch {
      // try next
    }
  }
  throw new Error("未找到安装有 pytest 的 Python 解释器。请先创建 task2-hybrid-rag/.venv 或安装 pytest。");
}

function runCliInFreshProcess(args: string[]): string {
  return execFileSync(process.execPath, ["--import", "tsx", CLI_PATH, ...args], {
    cwd: WORKSPACE_COPY,
    encoding: "utf-8",
    env: {
      ...process.env,
      PI_MEMORY_ROOT: MEMORY_ROOT,
      PI_MEMORY_PROJECT_ID: "login_demo",
    },
  }).trim();
}

function main(): void {
  fs.rmSync(WORKSPACE_COPY, { recursive: true, force: true });
  fs.rmSync(MEMORY_ROOT, { recursive: true, force: true });
  fs.mkdirSync(RUNS_DIR, { recursive: true });
  fs.cpSync(SOURCE_DEMO, WORKSPACE_COPY, { recursive: true });

  const pyBin = findPytestPython();
  const guidePath = path.join(WORKSPACE_COPY, "docs", "testing-guide.md");
  const origTestPath = path.join(WORKSPACE_COPY, "tests", "test_session.py");

  // =========================================================================
  // 步骤 1：读取会话测试文件与测试说明，写入持久化存储（独立子进程 = 会话 1）
  // =========================================================================
  const guideText = fs.readFileSync(guidePath, "utf-8");
  const testText = fs.readFileSync(origTestPath, "utf-8");
  assert.match(guideText, /python -m pytest tests\/test_session\.py -q/);
  assert.match(testText, /def test_expire_boundary/);

  const initialPytestOut = execFileSync(pyBin, ["-m", "pytest", "tests/test_session.py", "-q"], {
    cwd: WORKSPACE_COPY,
    encoding: "utf-8",
  }).trim();

  const step1Body = [
    "# 会话测试入口与运行命令",
    "",
    "- 测试文件路径：`tests/test_session.py`",
    "- 统一运行命令：`python -m pytest tests/test_session.py -q`",
    "- 覆盖用例：`test_expire_boundary`、`test_refresh_extends_ttl`、`test_logout_invalidates`",
    `- 初次实测结果：\`${initialPytestOut.replace(/\n/g, " | ")}\``,
    "",
    "# 核对清单",
    "",
    "1. 新会话使用前，先确认 `tests/test_session.py` 与 `docs/testing-guide.md` 是否存在且一致。",
    "2. 若测试路径迁移，运行新命令验证通过后再更新本记忆。",
  ].join("\n");

  const writeOut = runCliInFreshProcess([
    "write",
    "--project",
    WORKSPACE_COPY,
    "--id",
    "testing/session-test-entry",
    "--type",
    "Procedure",
    "--title",
    "login_demo 会话测试入口与运行命令",
    "--description",
    "记录 login_demo 会话测试文件路径 tests/test_session.py 与统一运行命令 python -m pytest tests/test_session.py -q。",
    "--tag",
    "testing",
    "--tag",
    "session",
    "--tag",
    "pytest",
    "--source",
    "tests/test_session.py",
    "--source",
    "docs/testing-guide.md",
    "--body",
    step1Body,
  ]);

  const savedFilePath = path.join(MEMORY_ROOT, "login_demo", "testing", "session-test-entry.md");
  assert.equal(fs.existsSync(savedFilePath), true, "持久化记忆文件必须真实落盘");
  const savedContent = fs.readFileSync(savedFilePath, "utf-8");

  const step1Log = [
    "========================================================================",
    "步骤 1（会话 1）：读取会话测试文件与说明 -> 写入项目长期记忆持久化存储",
    "========================================================================",
    "提示词：读取当前项目的会话测试文件和测试说明，将测试路径和运行命令保存到项目长期记忆，附上来源。返回实际保存路径。",
    "",
    `[实测执行] $ python -m pytest tests/test_session.py -q`,
    `  ${initialPytestOut}`,
    "",
    "[工具回执] project_memory_write (独立进程执行)：",
    writeOut,
    "",
    "[落盘文件预览] " + savedFilePath,
    savedContent.trim(),
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step1_write.txt"), step1Log + "\n", "utf-8");
  console.log(step1Log);

  // =========================================================================
  // 步骤 2：关闭会话 1，启动全新进程（会话 2）查找并核对文件存在性
  // =========================================================================
  const searchOut = runCliInFreshProcess([
    "search",
    "--project",
    WORKSPACE_COPY,
    "--query",
    "会话测试入口",
  ]);
  assert.match(searchOut, /tests\/test_session\.py => EXISTS/);
  assert.match(searchOut, /docs\/testing-guide\.md => EXISTS/);

  const validateOut1 = runCliInFreshProcess(["validate", "--project", WORKSPACE_COPY]);
  assert.match(validateOut1, /VALIDATE PASS/);

  const step2Log = [
    "========================================================================",
    "步骤 2（全新会话 2）：跨进程检索项目长期记忆并核对文件存在性",
    "========================================================================",
    "提示词：从当前项目长期记忆中查找会话测试入口，再核对当前文件是否存在。",
    "",
    "[新进程说明] 已结束会话 1 进程，以下结果由全新 Node 子进程从磁盘读取：",
    "",
    "[工具回执] project_memory_search (query=\"会话测试入口\", verifySources=true)：",
    searchOut,
    "",
    "[OKF 完整性校验] " + validateOut1,
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step2_new_session_read.txt"), step2Log + "\n", "utf-8");
  console.log("\n" + step2Log);

  // =========================================================================
  // 步骤 3：制造项目变化（迁移测试 + 修改测试说明 + 跑新测试）-> 更新旧记录
  // =========================================================================
  const newTestDir = path.join(WORKSPACE_COPY, "tests", "auth");
  const newTestPath = path.join(newTestDir, "test_session.py");
  fs.mkdirSync(newTestDir, { recursive: true });
  fs.renameSync(origTestPath, newTestPath);
  assert.equal(fs.existsSync(origTestPath), false);
  assert.equal(fs.existsSync(newTestPath), true);

  const updatedGuideText = guideText
    .replaceAll("tests/test_session.py", "tests/auth/test_session.py")
    .replace("updated: 2026-09-20", "updated: 2026-11-20");
  fs.writeFileSync(guidePath, updatedGuideText, "utf-8");

  // 先在更新记忆前核对一次，证明旧记忆中的 tests/test_session.py 会被检测为 MISSING
  const preUpdateCheck = runCliInFreshProcess([
    "search",
    "--project",
    WORKSPACE_COPY,
    "--query",
    "会话测试入口",
  ]);
  assert.match(preUpdateCheck, /tests\/test_session\.py => MISSING/);

  // 真实运行新测试命令
  const migratedPytestOut = execFileSync(
    pyBin,
    ["-m", "pytest", "tests/auth/test_session.py", "-q"],
    {
      cwd: WORKSPACE_COPY,
      encoding: "utf-8",
    }
  ).trim();
  assert.match(migratedPytestOut, /3 passed/);

  const step3Body = [
    "# 会话测试入口与运行命令（已迁移更新）",
    "",
    "- 当前测试文件路径：`tests/auth/test_session.py`",
    "- 当前统一运行命令：`python -m pytest tests/auth/test_session.py -q`",
    "- 历史路径（已失效）：`tests/test_session.py`（已迁移至 `tests/auth/test_session.py`）",
    `- 最新实测结果：\`${migratedPytestOut.replace(/\n/g, " | ")}\``,
    "",
    "# 核对清单",
    "",
    "1. 确认 `tests/auth/test_session.py` 与 `docs/testing-guide.md` 存在且一致。",
    "2. 旧路径 `tests/test_session.py` 已废弃，不得继续沿用。",
  ].join("\n");

  const updateOut = runCliInFreshProcess([
    "update",
    "--project",
    WORKSPACE_COPY,
    "--id",
    "testing/session-test-entry",
    "--description",
    "会话测试已迁移至 tests/auth/test_session.py，统一运行命令更新为 python -m pytest tests/auth/test_session.py -q。",
    "--source",
    "tests/auth/test_session.py",
    "--source",
    "docs/testing-guide.md",
    "--change-note",
    "迁移测试至 tests/auth/test_session.py，同步修改 docs/testing-guide.md，实测 3 passed",
    "--body",
    step3Body,
  ]);

  // 启动全新会话 4 复查更新后的记忆
  const postUpdateSearch = runCliInFreshProcess([
    "search",
    "--project",
    WORKSPACE_COPY,
    "--query",
    "会话测试入口",
  ]);
  assert.match(postUpdateSearch, /rev 2/);
  assert.match(postUpdateSearch, /tests\/auth\/test_session\.py => EXISTS/);

  // 额外验证：写入并删除一条临时记忆，证明四个动作（写/查读/改/删）闭环完整
  runCliInFreshProcess([
    "write",
    "--project",
    WORKSPACE_COPY,
    "--id",
    "testing/temp-debug-note",
    "--title",
    "临时排查记录",
    "--description",
    "用于验证删除动作的临时条目",
    "--source",
    "docs/testing-guide.md",
    "--body",
    "临时调试打印说明，排查结束后删除。",
  ]);
  const deleteOut = runCliInFreshProcess([
    "delete",
    "--project",
    WORKSPACE_COPY,
    "--id",
    "testing/temp-debug-note",
    "--reason",
    "临时排查记录无长期复用价值，验证 delete 动作",
  ]);
  assert.match(deleteOut, /DELETE OK/);

  const logContent = fs.readFileSync(path.join(MEMORY_ROOT, "login_demo", "log.md"), "utf-8");

  const step3Log = [
    "========================================================================",
    "步骤 3（项目变化与更新记忆）：迁移测试 -> 修改说明 -> 实测通过 -> 更新记忆",
    "========================================================================",
    "提示词：将会话测试迁移到 tests/auth/test_session.py，同步修改测试说明，运行新测试命令。根据实际结果更新原来的长期记忆。",
    "",
    "[变更 1] 已迁移文件：tests/test_session.py -> tests/auth/test_session.py",
    "[变更 2] 已同步更新：docs/testing-guide.md",
    "[变更前核对] 旧记忆来源检查已准确发现失效路径：tests/test_session.py => MISSING",
    "",
    "[实测执行] $ python -m pytest tests/auth/test_session.py -q",
    `  ${migratedPytestOut}`,
    "",
    "[工具回执] project_memory_update (rev 1 -> rev 2)：",
    updateOut,
    "",
    "[新会话复查] project_memory_search (verifySources=true)：",
    postUpdateSearch,
    "",
    "[删除动作验证] project_memory_delete：",
    deleteOut,
    "",
    "[审计日志 log.md]：",
    logContent.trim(),
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step3_migrate_update.txt"), step3Log + "\n", "utf-8");
  console.log("\n" + step3Log);
}

main();
