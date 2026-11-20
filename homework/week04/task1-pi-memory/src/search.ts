/**
 * 记忆检索打分（含中文 2-gram）与来源文件路径核对 / 格式化模块。
 */

import fs from "node:fs";
import path from "node:path";
import type { MemoryRecord, SourceCheckResult } from "./types.js";

export function extractSearchTerms(query: string): string[] {
  const lowered = query.toLowerCase().trim();
  if (!lowered) return [];
  const terms = new Set<string>();
  for (const token of lowered.split(/[\s,，。；;、:/\\|]+/)) {
    if (token) terms.add(token);
  }
  // 针对中文查询提取 2-gram，保证无外部中文分词器时依然能高精度召回
  const cjkRuns = lowered.match(/[\u4e00-\u9fff]{2,}/g) || [];
  for (const run of cjkRuns) {
    terms.add(run);
    for (let i = 0; i < run.length - 1; i++) {
      terms.add(run.slice(i, i + 2));
    }
  }
  return Array.from(terms);
}

export function scoreMemoryRecord(rec: MemoryRecord, terms: string[]): number {
  if (terms.length === 0) return 1;
  const idLower = rec.id.toLowerCase();
  const titleLower = rec.title.toLowerCase();
  const descLower = rec.description.toLowerCase();
  const tagsLower = rec.tags.join(" ").toLowerCase();
  const sourcesLower = rec.sources.join(" ").toLowerCase();
  const bodyLower = rec.body.toLowerCase();

  let score = 0;
  for (const term of terms) {
    if (idLower.includes(term)) score += 5;
    if (titleLower.includes(term)) score += 4;
    if (tagsLower.includes(term)) score += 3;
    if (descLower.includes(term)) score += 2.5;
    if (sourcesLower.includes(term)) score += 2;
    if (bodyLower.includes(term)) score += 1;
  }
  return score;
}

/**
 * 核对记忆中引用的来源路径在当前项目目录中是否真实存在。
 */
export function verifyMemorySources(projectRoot: string, sources: string[]): SourceCheckResult[] {
  const canonicalRoot = path.resolve(projectRoot);
  return sources.map((source) => {
    const trimmed = source.trim();
    const looksLikeFile =
      !trimmed.includes(" ") &&
      (trimmed.includes("/") || /\.(py|ts|js|md|json|yaml|yml|toml|txt|sh|csv|html|pdf)$/i.test(trimmed));
    if (!looksLikeFile) {
      return { source: trimmed, kind: "command_or_note" };
    }
    const candidate = path.resolve(canonicalRoot, trimmed);
    const withinRoot =
      candidate === canonicalRoot || candidate.startsWith(canonicalRoot + path.sep);
    if (!withinRoot) {
      return {
        source: trimmed,
        kind: "file",
        resolvedPath: candidate,
        exists: false,
      };
    }
    return {
      source: trimmed,
      kind: "file",
      resolvedPath: candidate,
      exists: fs.existsSync(candidate),
    };
  });
}

export function formatSourceChecks(
  checks: SourceCheckResult[],
  options: { indent?: string; includeResolvedPath?: boolean; asciiStatus?: boolean } = {}
): string {
  const indent = options.indent ?? "  ";
  const includePath = options.includeResolvedPath ?? true;
  const ascii = options.asciiStatus ?? false;
  return checks
    .map((c) => {
      if (c.kind === "file") {
        const status = ascii ? (c.exists ? "EXISTS" : "MISSING") : c.exists ? "存在" : "不存在";
        const suffix = includePath && c.resolvedPath ? ` (${c.resolvedPath})` : "";
        return `${indent}- [文件] ${c.source} => ${status}${suffix}`;
      }
      return `${indent}- [依据] ${c.source}`;
    })
    .join("\n");
}
