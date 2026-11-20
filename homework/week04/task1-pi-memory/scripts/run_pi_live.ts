#!/usr/bin/env node
/**
 * 使用真实 pi coding agent + project-memory 扩展 + 真实大模型（默认 DeepSeek deepseek-v4-flash）
 * 跨 3 个完全独立的 pi 进程实跑作业一三步验证，并将结构化实测日志写入 runs/step{1,2,3}_*.txt。
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ProjectMemoryStore } from "../src/memory-store.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TASK_DIR = path.resolve(__dirname, "..");
const SOURCE_DEMO = path.join(TASK_DIR, "login_demo");
const EXT_PATH = path.join(TASK_DIR, "extensions", "project-memory.ts");
const PI_BIN = path.join(TASK_DIR, "node_modules", ".bin", "pi");
const RUNS_DIR = path.join(TASK_DIR, "runs");
const WORK_DIR = path.join(RUNS_DIR, "pi_live_workspace");
const MEMORY_ROOT = path.join(RUNS_DIR, "okf-memory-store");

interface ContentBlock {
  type: string;
  text?: string;
  id?: string;
  name?: string;
  arguments?: Record<string, unknown>;
}

interface PiMessage {
  role: string;
  content?: ContentBlock[] | string;
  toolCallId?: string;
  toolName?: string;
  isError?: boolean;
  provider?: string;
  model?: string;
  responseModel?: string;
  usage?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    totalTokens?: number;
  };
}

interface ParsedSession {
  provider: string;
  model: string;
  responseModel: string;
  totalTokens: number;
  turns: number;
  toolTrace: Array<{
    name: string;
    args: Record<string, unknown>;
    output: string;
    isError: boolean;
  }>;
  finalAnswer: string;
}

function buildRuntimePath(): string {
  const venvBin = path.resolve(TASK_DIR, "..", "task2-hybrid-rag", ".venv", "bin");
  const currentPath = process.env.PATH || "";
  if (fs.existsSync(venvBin) && !currentPath.split(":").includes(venvBin)) {
    return `${venvBin}:${currentPath}`;
  }
  return currentPath;
}

function extractText(content: ContentBlock[] | string | undefined): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  return content
    .filter((b) => b.type === "text" && typeof b.text === "string")
    .map((b) => b.text as string)
    .join("\n")
    .trim();
}

function summarizeArgs(name: string, args: Record<string, unknown>): string {
  const compact: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) {
    if (typeof v === "string" && v.length > 90 && (k === "body" || k === "content" || k === "newText" || k === "oldText")) {
      compact[k] = `${v.slice(0, 72).replace(/\n/g, "\\n")}... (${v.length} chars)`;
    } else {
      compact[k] = v;
    }
  }
  return `${name}(${JSON.stringify(compact)})`;
}

function summarizeToolOutput(name: string, output: string): string {
  const clean = output.trim();
  if (!clean) return "(empty)";
  if (name.startsWith("project_memory_") || name === "bash") {
    const lines = clean.split("\n");
    if (lines.length <= 16) return clean;
    return [...lines.slice(0, 14), `... (共 ${lines.length} 行，已截断)`].join("\n");
  }
  const lines = clean.split("\n");
  if (lines.length <= 4 && clean.length <= 240) return clean;
  return `${lines.slice(0, 2).join(" | ").slice(0, 160)} ... (共 ${lines.length} 行)`;
}

function runPiSession(prompt: string, provider: string, model: string): ParsedSession {
  const args = [
    "--offline",
    "--no-session",
    "-e",
    EXT_PATH,
    "--provider",
    provider,
    "--model",
    model,
    "--mode",
    "json",
    "-p",
    prompt,
  ];

  const stdout = execFileSync(PI_BIN, args, {
    cwd: WORK_DIR,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: 20 * 1024 * 1024,
    env: {
      ...process.env,
      PATH: buildRuntimePath(),
      PI_MEMORY_ROOT: MEMORY_ROOT,
      PI_MEMORY_PROJECT_ID: "login_demo",
    },
  });

  const events = stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as Record<string, unknown>;
      } catch {
        return null;
      }
    })
    .filter((item): item is Record<string, unknown> => item !== null);

  const agentEnd = [...events].reverse().find((ev) => ev.type === "agent_end");
  if (!agentEnd || !Array.isArray(agentEnd.messages)) {
    throw new Error("未在 pi JSON 输出中解析到 agent_end 事件。");
  }

  const messages = agentEnd.messages as PiMessage[];
  let detectedProvider = provider;
  let detectedModel = model;
  let responseModel = "";
  let totalTokens = 0;
  let turns = 0;

  const pendingCalls = new Map<string, { name: string; args: Record<string, unknown> }>();
  const toolTrace: ParsedSession["toolTrace"] = [];
  let finalAnswer = "";

  for (const msg of messages) {
    if (msg.role === "assistant") {
      turns += 1;
      if (msg.provider) detectedProvider = msg.provider;
      if (msg.model) detectedModel = msg.model;
      if (msg.responseModel) responseModel = msg.responseModel;
      if (msg.usage?.totalTokens) totalTokens += msg.usage.totalTokens;

      if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === "toolCall" && block.id && block.name) {
            pendingCalls.set(block.id, {
              name: block.name,
              args: (block.arguments as Record<string, unknown>) || {},
            });
          }
        }
      }
      const txt = extractText(msg.content);
      if (txt) finalAnswer = txt;
    } else if (msg.role === "toolResult") {
      const call = msg.toolCallId ? pendingCalls.get(msg.toolCallId) : undefined;
      toolTrace.push({
        name: msg.toolName || call?.name || "unknown",
        args: call?.args || {},
        output: extractText(msg.content),
        isError: Boolean(msg.isError),
      });
    }
  }

  return {
    provider: detectedProvider,
    model: detectedModel,
    responseModel,
    totalTokens,
    turns,
    toolTrace,
    finalAnswer,
  };
}

function formatToolTrace(session: ParsedSession): string {
  if (session.toolTrace.length === 0) {
    return "  (无工具调用)";
  }
  return session.toolTrace
    .map((item, idx) => {
      const status = item.isError ? "ERROR" : "OK";
      const out = summarizeToolOutput(item.name, item.output)
        .split("\n")
        .map((ln) => `      ${ln}`)
        .join("\n");
      return `  (${idx + 1}) [${status}] ${summarizeArgs(item.name, item.args)}\n${out}`;
    })
    .join("\n");
}

function main(): void {
  if (!fs.existsSync(PI_BIN)) {
    throw new Error(`未找到 ${PI_BIN}，请先运行 npm install`);
  }

  const provider = process.env.PI_PROVIDER || "deepseek";
  const model = process.env.PI_MODEL || (provider === "deepseek" ? "deepseek-v4-flash" : "");
  if (!model) {
    throw new Error("请通过 PI_MODEL 指定模型名称。");
  }

  fs.mkdirSync(RUNS_DIR, { recursive: true });
  fs.rmSync(WORK_DIR, { recursive: true, force: true });
  fs.rmSync(MEMORY_ROOT, { recursive: true, force: true });
  fs.cpSync(SOURCE_DEMO, WORK_DIR, { recursive: true });

  const store = new ProjectMemoryStore({
    projectRoot: WORK_DIR,
    storageRoot: MEMORY_ROOT,
    projectId: "login_demo",
  });

  // =========================================================================
  // 会话 1：写入持久化项目长期记忆
  // =========================================================================
  const prompt1 =
    "读取当前项目的会话测试文件和测试说明，将测试路径和运行命令保存到项目长期记忆，附上来源。返回实际保存路径。";
  console.log("=== [会话 1/3] 启动独立 pi 进程写入项目长期记忆 ===");
  const s1 = runPiSession(prompt1, provider, model);
  assert.ok(
    s1.toolTrace.some((t) => t.name === "project_memory_write" && !t.isError),
    "会话 1 必须调用 project_memory_write 并成功"
  );
  const recordsAfterS1 = store.list();
  assert.ok(recordsAfterS1.length >= 1, "会话 1 后磁盘上必须至少有一条 OKF 记忆");
  const primaryRecordS1 = recordsAfterS1[0];
  const savedFileContentS1 = fs.readFileSync(primaryRecordS1.filePath, "utf-8").trim();

  const step1Log = [
    "========================================================================",
    "步骤 1（真实 pi 会话 1）：读取测试文件与说明 -> 写入项目长期记忆",
    "========================================================================",
    `调用模型  : ${s1.provider} / ${s1.model} (turns=${s1.turns}, tokens=${s1.totalTokens})`,
    `挂载扩展  : extensions/project-memory.ts (PI_MEMORY_PROJECT_ID=login_demo)`,
    `提示词    : ${prompt1}`,
    "",
    "--- 工具调用轨迹 (pi 真实执行) ---",
    formatToolTrace(s1),
    "",
    "--- 模型最终回复 ---",
    s1.finalAnswer,
    "",
    `--- 落盘 OKF 文件预览 (${primaryRecordS1.filePath}) ---`,
    savedFileContentS1,
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step1_write.txt"), step1Log + "\n", "utf-8");
  console.log(step1Log);

  // =========================================================================
  // 会话 2：关闭会话 1，启动全新独立 pi 进程读取并核对记忆
  // =========================================================================
  const prompt2 = "从当前项目长期记忆中查找会话测试入口，再核对当前文件是否存在。";
  console.log("\n=== [会话 2/3] 启动全新独立 pi 进程读取并核对记忆 ===");
  const s2 = runPiSession(prompt2, provider, model);
  assert.ok(
    s2.toolTrace.some(
      (t) =>
        (t.name === "project_memory_search" || t.name === "project_memory_read") && !t.isError
    ),
    "会话 2 必须调用 project_memory_search 或 project_memory_read"
  );
  const validationS2 = store.validate();
  assert.equal(validationS2.valid, true, `OKF 校验失败: ${validationS2.errors.join("; ")}`);

  const step2Log = [
    "========================================================================",
    "步骤 2（全新独立 pi 会话 2）：跨会话查找长期记忆并核对文件存在性",
    "========================================================================",
    `调用模型  : ${s2.provider} / ${s2.model} (turns=${s2.turns}, tokens=${s2.totalTokens})`,
    `隔离说明  : 已退出会话 1 进程，以下由全新 pi --no-session 进程从磁盘恢复记忆`,
    `提示词    : ${prompt2}`,
    "",
    "--- 工具调用轨迹 (pi 真实执行) ---",
    formatToolTrace(s2),
    "",
    "--- 模型最终回复 ---",
    s2.finalAnswer,
    "",
    `[OKF 完整性校验] VALIDATE PASS (${validationS2.recordCount} records in ${validationS2.storeDir})`,
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step2_new_session_read.txt"), step2Log + "\n", "utf-8");
  console.log("\n" + step2Log);

  // =========================================================================
  // 会话 3：制造项目变化、迁移测试、运行新测试命令并更新长期记忆
  // =========================================================================
  const prompt3 =
    "将会话测试迁移到 tests/auth/test_session.py，同步修改测试说明，运行新测试命令。根据实际结果更新原来的长期记忆。";
  console.log("\n=== [会话 3/3] 启动全新独立 pi 进程迁移测试并更新长期记忆 ===");
  const s3 = runPiSession(prompt3, provider, model);
  assert.equal(
    fs.existsSync(path.join(WORK_DIR, "tests", "auth", "test_session.py")),
    true,
    "会话 3 必须将测试迁移至 tests/auth/test_session.py"
  );
  assert.equal(
    fs.existsSync(path.join(WORK_DIR, "tests", "test_session.py")),
    false,
    "会话 3 后旧测试路径 tests/test_session.py 不应再存在"
  );
  const updatedGuide = fs.readFileSync(path.join(WORK_DIR, "docs", "testing-guide.md"), "utf-8");
  assert.match(updatedGuide, /tests\/auth\/test_session\.py/, "docs/testing-guide.md 必须更新为新路径");
  assert.ok(
    s3.toolTrace.some((t) => t.name === "project_memory_update" && !t.isError),
    "会话 3 必须调用 project_memory_update 更新原长期记忆"
  );

  const recordsAfterS3 = store.list();
  const updatedRecord = recordsAfterS3.find((r) => r.id === primaryRecordS1.id) || recordsAfterS3[0];
  assert.ok(updatedRecord && updatedRecord.revision >= 2, "原记忆 revision 必须递增至 >= 2");
  const updatedFileContent = fs.readFileSync(updatedRecord.filePath, "utf-8").trim();
  const logContent = fs.readFileSync(store.logPath, "utf-8").trim();
  const validationS3 = store.validate();
  assert.equal(validationS3.valid, true, `更新后 OKF 校验失败: ${validationS3.errors.join("; ")}`);

  const step3Log = [
    "========================================================================",
    "步骤 3（全新独立 pi 会话 3）：迁移测试、运行新命令并更新长期记忆",
    "========================================================================",
    `调用模型  : ${s3.provider} / ${s3.model} (turns=${s3.turns}, tokens=${s3.totalTokens})`,
    `提示词    : ${prompt3}`,
    "",
    "--- 工具调用轨迹 (pi 真实执行) ---",
    formatToolTrace(s3),
    "",
    "--- 模型最终回复 ---",
    s3.finalAnswer,
    "",
    `--- 更新后 OKF 文件 (${updatedRecord.filePath}, rev ${updatedRecord.revision}) ---`,
    updatedFileContent,
    "",
    "--- 审计日志 log.md ---",
    logContent,
    "",
    `[OKF 完整性校验] VALIDATE PASS (${validationS3.recordCount} records in ${validationS3.storeDir})`,
    "========================================================================",
  ].join("\n");
  fs.writeFileSync(path.join(RUNS_DIR, "step3_migrate_update.txt"), step3Log + "\n", "utf-8");
  console.log("\n" + step3Log);
}

main();
