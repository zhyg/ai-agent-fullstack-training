#!/usr/bin/env node
/**
 * 独立 CLI：直接调用 ProjectMemoryStore 执行写入、检索、读取、更新、删除、校验，
 * 便于跨独立操作系统进程验收持久化与项目隔离。
 */

import process from "node:process";
import {
  ProjectMemoryStore,
  verifyMemorySources,
  type MemoryStatus,
  type MemoryType,
} from "./memory-store.js";

function parseArgs(argv: string[]): { cmd: string; flags: Record<string, string | string[] | boolean> } {
  const [cmd = "help", ...rest] = argv;
  const flags: Record<string, string | string[] | boolean> = {};
  for (let i = 0; i < rest.length; i++) {
    const token = rest[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = rest[i + 1];
    if (next === undefined || next.startsWith("--")) {
      flags[key] = true;
    } else {
      i++;
      if (key === "tag" || key === "source") {
        const arr = (flags[key] as string[] | undefined) || [];
        arr.push(next);
        flags[key] = arr;
      } else {
        flags[key] = next;
      }
    }
  }
  return { cmd, flags };
}

function asString(v: string | string[] | boolean | undefined): string | undefined {
  if (typeof v === "string") return v;
  return undefined;
}

function asList(v: string | string[] | boolean | undefined): string[] {
  if (Array.isArray(v)) return v;
  if (typeof v === "string") return v.split(",").map((s) => s.trim()).filter(Boolean);
  return [];
}

function main(): void {
  const { cmd, flags } = parseArgs(process.argv.slice(2));
  const projectRoot = asString(flags.project) || process.cwd();
  const storageRoot = asString(flags["memory-root"]) || process.env.PI_MEMORY_ROOT;
  const projectId = asString(flags["project-id"]) || process.env.PI_MEMORY_PROJECT_ID;
  const store = new ProjectMemoryStore({ projectRoot, storageRoot, projectId });
  const asJson = Boolean(flags.json);

  const print = (data: unknown, fallbackText: string) => {
    if (asJson) {
      console.log(JSON.stringify(data, null, 2));
    } else {
      console.log(fallbackText);
    }
  };

  switch (cmd) {
    case "write": {
      const record = store.write({
        id: asString(flags.id) || "",
        title: asString(flags.title) || "",
        description: asString(flags.description) || "",
        type: (asString(flags.type) as MemoryType | undefined) || "Fact",
        tags: asList(flags.tag),
        sources: asList(flags.source),
        status: (asString(flags.status) as MemoryStatus | undefined) || "verified",
        body: asString(flags.body) || "",
      });
      print(
        { record, indexPath: store.indexPath, logPath: store.logPath },
        `WRITE OK\n  id         : ${record.id}\n  project    : ${record.project}\n  revision   : ${record.revision}\n  saved_path : ${record.filePath}\n  index_path : ${store.indexPath}\n  sources    : ${record.sources.join(", ")}`
      );
      break;
    }
    case "search": {
      const hits = store.search({
        query: asString(flags.query),
        tag: asString(flags.tag),
        verifySources: !flags["no-verify"],
      });
      const text =
        hits.length === 0
          ? `NO MATCHES in project ${store.projectKey}`
          : hits
              .map((h, i) => {
                const checks = (h.sourceChecks || [])
                  .map((c) =>
                    c.kind === "file"
                      ? `    - [文件] ${c.source} => ${c.exists ? "EXISTS" : "MISSING"}`
                      : `    - [依据] ${c.source}`
                  )
                  .join("\n");
                const indentedBody = h.record.body
                  .split("\n")
                  .map((line) => (line ? `    ${line}` : ""))
                  .join("\n");
                return `[${i + 1}] ${h.record.id} (rev ${h.record.revision}, score=${h.score})\n  title  : ${h.record.title}\n  path   : ${h.record.filePath}\n  sources: ${h.record.sources.join(", ")}\n${checks ? `  checks :\n${checks}\n` : ""}  body   :\n${indentedBody}`;
              })
              .join("\n\n");
      print({ projectKey: store.projectKey, storeDir: store.storeDir, hits }, text);
      break;
    }
    case "read": {
      const id = asString(flags.id) || "";
      const record = store.read(id);
      if (!record) {
        console.error(`Memory not found: ${id}`);
        process.exit(1);
      }
      const checks = verifyMemorySources(store.projectRoot, record.sources);
      print(
        { record, sourceChecks: checks },
        `READ OK: ${record.id} (rev ${record.revision})\npath: ${record.filePath}\n${record.body}`
      );
      break;
    }
    case "update": {
      const updated = store.update({
        id: asString(flags.id) || "",
        title: asString(flags.title),
        description: asString(flags.description),
        tags: flags.tag !== undefined ? asList(flags.tag) : undefined,
        sources: flags.source !== undefined ? asList(flags.source) : undefined,
        status: asString(flags.status) as MemoryStatus | undefined,
        body: asString(flags.body),
        changeNote: asString(flags["change-note"]),
      });
      print(
        { record: updated },
        `UPDATE OK\n  id         : ${updated.id}\n  revision   : ${updated.revision}\n  saved_path : ${updated.filePath}\n  sources    : ${updated.sources.join(", ")}`
      );
      break;
    }
    case "delete": {
      const id = asString(flags.id) || "";
      const res = store.delete(id, asString(flags.reason) || "deleted via cli");
      print(res, res.deleted ? `DELETE OK: ${id} (${res.filePath})` : `NOT FOUND: ${id}`);
      break;
    }
    case "list": {
      const records = store.list();
      print({ projectKey: store.projectKey, records }, store.formatCatalogDigest());
      break;
    }
    case "validate": {
      const report = store.validate();
      print(
        report,
        report.valid
          ? `VALIDATE PASS (${report.recordCount} records in ${report.storeDir})`
          : `VALIDATE FAIL: ${report.errors.join("; ")}`
      );
      if (!report.valid) process.exit(1);
      break;
    }
    default: {
      console.log(
        "Usage: cli.ts <write|search|read|update|delete|list|validate> --project <dir> [--memory-root <dir>] [--json]"
      );
    }
  }
}

main();
