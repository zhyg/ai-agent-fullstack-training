/**
 * pi coding agent 扩展：为 pi 增加按项目隔离的 OKF 长期记忆能力。
 *
 * 加载方式：
 *   npx pi -e ./extensions/project-memory.ts
 *
 * 注册工具（覆盖全部四个动作：写入、按项目查找并读取、更新、删除）：
 *   1. project_memory_write  - 写入项目长期记忆并返回真实保存路径
 *   2. project_memory_search - 按当前项目查找并读取记忆（支持自动核对来源文件是否存在）
 *   3. project_memory_read   - 按 id 读取单条记忆并核对来源路径
 *   4. project_memory_update - 更新已有记忆（递增 revision，保留审计日志）
 *   5. project_memory_delete - 删除活动记忆并在 log.md 留痕
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import {
  ProjectMemoryStore,
  formatSourceChecks,
  verifyMemorySources,
  type MemoryStatus,
  type MemoryType,
} from "../src/memory-store.js";

function getStore(ctx: Pick<ExtensionContext, "cwd">): ProjectMemoryStore {
  return new ProjectMemoryStore({
    projectRoot: ctx.cwd,
    storageRoot: process.env.PI_MEMORY_ROOT,
    projectId: process.env.PI_MEMORY_PROJECT_ID,
  });
}

function textResult(text: string, details: Record<string, unknown> = {}) {
  return {
    content: [{ type: "text" as const, text }],
    details,
  };
}

export default function projectMemoryExtension(pi: ExtensionAPI): void {
  // 1) 写入项目长期记忆
  pi.registerTool({
    name: "project_memory_write",
    label: "Write Project Memory",
    description:
      "将经过核实的当前项目长期知识（测试路径、运行命令、架构约定等）写入持久化 OKF Markdown 存储，并附上来源，返回实际保存路径。",
    promptSnippet: "写入当前项目的持久化长期记忆（OKF Markdown + index.md + log.md）",
    promptGuidelines: [
      "写入项目长期记忆前先读取源码、文档或实际命令输出，必须附带可核对的 sources。",
      "长期记忆仅作为定位线索与待核对依据；在新会话使用记忆前，应核对对应文件是否存在、与当前源码是否一致。",
    ],
    parameters: Type.Object({
      id: Type.String({
        description: "记忆唯一标识（目录风格，例如 testing/session-test-entry）",
      }),
      title: Type.String({ description: "记忆标题" }),
      description: Type.String({ description: "一句话摘要" }),
      type: Type.Optional(
        Type.Union([
          Type.Literal("Fact"),
          Type.Literal("Rule"),
          Type.Literal("Procedure"),
          Type.Literal("Decision"),
        ])
      ),
      tags: Type.Optional(Type.Array(Type.String(), { description: "检索标签列表" })),
      sources: Type.Array(Type.String(), {
        minItems: 1,
        description: "来源文件路径或命令依据列表（至少一项）",
      }),
      status: Type.Optional(
        Type.Union([
          Type.Literal("verified"),
          Type.Literal("unverified"),
          Type.Literal("deprecated"),
        ])
      ),
      body: Type.String({ description: "Markdown 正文（包含关键结论、命令与核对清单）" }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const store = getStore(ctx);
      const record = store.write({
        id: params.id,
        title: params.title,
        description: params.description,
        type: params.type as MemoryType | undefined,
        tags: params.tags,
        sources: params.sources,
        status: params.status as MemoryStatus | undefined,
        body: params.body,
      });
      return textResult(
        [
          `已写入项目长期记忆：${record.id} (rev ${record.revision})`,
          `项目标识：${record.project}`,
          `实际保存路径：${record.filePath}`,
          `目录文件：${store.indexPath}`,
          `来源：${record.sources.join(", ")}`,
        ].join("\n"),
        { record, indexPath: store.indexPath, logPath: store.logPath }
      );
    },
  });

  // 2) 按项目查找并读取记忆
  pi.registerTool({
    name: "project_memory_search",
    label: "Search Project Memory",
    description:
      "在当前项目的长期记忆存储中按关键词或标签查找并读取记忆内容，默认同时核对来源文件在当前工作区是否存在。",
    promptSnippet: "按当前项目检索并读取长期记忆，并核对来源文件是否存在",
    parameters: Type.Object({
      query: Type.Optional(Type.String({ description: "检索关键词（留空则列出全部）" })),
      tag: Type.Optional(Type.String({ description: "按标签过滤" })),
      limit: Type.Optional(Type.Number({ description: "返回条数上限，默认 5" })),
      verifySources: Type.Optional(
        Type.Boolean({ description: "是否核对 sources 中文件路径是否存在，默认 true" })
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const store = getStore(ctx);
      const verify = params.verifySources ?? true;
      const hits = store.search({
        query: params.query,
        tag: params.tag,
        limit: params.limit ?? 5,
        verifySources: verify,
      });
      if (hits.length === 0) {
        return textResult(
          `当前项目 (${store.projectKey}) 未检索到匹配记忆（存储目录：${store.storeDir}）。`,
          { projectKey: store.projectKey, hits: [] }
        );
      }
      const sections = hits.map((hit, idx) => {
        const rec = hit.record;
        const checks = hit.sourceChecks ? formatSourceChecks(hit.sourceChecks, { indent: "  " }) : "";
        return [
          `[${idx + 1}] ${rec.id} | ${rec.title} (rev ${rec.revision}, ${rec.status}, score=${hit.score})`,
          `路径：${rec.filePath}`,
          `摘要：${rec.description}`,
          `来源：${rec.sources.join(", ")}`,
          checks ? `来源核对：\n${checks}` : "",
          `正文：\n${rec.body}`,
        ]
          .filter(Boolean)
          .join("\n");
      });
      return textResult(sections.join("\n\n---\n\n"), {
        projectKey: store.projectKey,
        storeDir: store.storeDir,
        hits,
      });
    },
  });

  // 3) 按 id 精确读取并核对单条记忆
  pi.registerTool({
    name: "project_memory_read",
    label: "Read Project Memory",
    description: "按 id 读取当前项目的指定长期记忆全文，并核对来源文件在当前项目目录是否存在。",
    promptSnippet: "按 id 读取项目长期记忆详情并核对文件存在性",
    parameters: Type.Object({
      id: Type.String({ description: "记忆 id，例如 testing/session-test-entry" }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const store = getStore(ctx);
      const record = store.read(params.id);
      if (!record) {
        return textResult(`未找到记忆：${params.id}（项目：${store.projectKey}）`, {
          found: false,
        });
      }
      const checks = verifyMemorySources(store.projectRoot, record.sources);
      const checkText = formatSourceChecks(checks, { indent: "" });
      return textResult(
        [
          `ID：${record.id} (rev ${record.revision}, ${record.status})`,
          `标题：${record.title}`,
          `保存路径：${record.filePath}`,
          `来源核对：\n${checkText}`,
          "",
          record.body,
        ].join("\n"),
        { found: true, record, sourceChecks: checks }
      );
    },
  });

  // 4) 更新已有记忆
  pi.registerTool({
    name: "project_memory_update",
    label: "Update Project Memory",
    description:
      "当项目源码、测试路径或运行命令变化并经验证后，更新原长期记忆记录（递增 revision 并写入审计日志）。",
    promptSnippet: "更新已有项目长期记忆，同步刷新 index.md 与 log.md",
    parameters: Type.Object({
      id: Type.String({ description: "要更新的记忆 id" }),
      title: Type.Optional(Type.String()),
      description: Type.Optional(Type.String()),
      tags: Type.Optional(Type.Array(Type.String())),
      sources: Type.Optional(Type.Array(Type.String(), { minItems: 1 })),
      status: Type.Optional(
        Type.Union([
          Type.Literal("verified"),
          Type.Literal("unverified"),
          Type.Literal("deprecated"),
        ])
      ),
      body: Type.Optional(Type.String()),
      changeNote: Type.Optional(Type.String({ description: "本次更新原因与验证证据说明" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const store = getStore(ctx);
      const updated = store.update({
        id: params.id,
        title: params.title,
        description: params.description,
        tags: params.tags,
        sources: params.sources,
        status: params.status as MemoryStatus | undefined,
        body: params.body,
        changeNote: params.changeNote,
      });
      return textResult(
        [
          `已更新项目长期记忆：${updated.id} (rev ${updated.revision})`,
          `保存路径：${updated.filePath}`,
          `更新后来源：${updated.sources.join(", ")}`,
          `更新时间：${updated.updated_at}`,
        ].join("\n"),
        { record: updated }
      );
    },
  });

  // 5) 删除活动记忆
  pi.registerTool({
    name: "project_memory_delete",
    label: "Delete Project Memory",
    description: "从当前项目长期记忆中删除指定记录，同步更新 index.md 并在 log.md 记录删除原因。",
    promptSnippet: "删除当前项目的一条长期记忆",
    parameters: Type.Object({
      id: Type.String({ description: "要删除的记忆 id" }),
      reason: Type.Optional(Type.String({ description: "删除原因" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const store = getStore(ctx);
      const res = store.delete(params.id, params.reason || "deleted via tool");
      return textResult(
        res.deleted
          ? `已删除项目长期记忆：${params.id}（原路径：${res.filePath}）`
          : `未找到可删除的记忆：${params.id}`,
        res
      );
    },
  });

  // 会话启动/每轮 Agent 启动前：把当前项目已有记忆目录注入系统提示词，支持跨会话自动感知
  pi.on("before_agent_start", (event, ctx) => {
    const store = getStore(ctx);
    const digest = store.formatCatalogDigest();
    const memoryBlock = [
      "",
      "## 项目长期记忆（OKF Project Memory）",
      digest,
      "使用规则：",
      "1. 遇到项目路径、测试入口、历史约定问题时，优先调用 project_memory_search / project_memory_read 查找并核对当前文件是否存在。",
      "2. 写入或更新长期记忆前，必须读取真实文件或运行命令拿到证据，禁止凭猜测写入。",
    ].join("\n");
    return {
      systemPrompt: `${event.systemPrompt}\n${memoryBlock}`,
    };
  });

  // 斜杠命令：/memory-list 与 /memory-validate
  pi.registerCommand("memory-list", {
    description: "列出当前项目的全部长期记忆条目",
    async handler(_args, ctx) {
      const store = getStore(ctx);
      ctx.ui.notify(store.formatCatalogDigest(), "info");
    },
  });

  pi.registerCommand("memory-validate", {
    description: "校验当前项目长期记忆 OKF 目录与元数据完整性",
    async handler(_args, ctx) {
      const store = getStore(ctx);
      const report = store.validate();
      ctx.ui.notify(
        report.valid
          ? `OKF 校验通过：${report.recordCount} 条记录 (${report.storeDir})`
          : `OKF 校验失败：${report.errors.join("; ")}`,
        report.valid ? "info" : "warning"
      );
    },
  });
}
