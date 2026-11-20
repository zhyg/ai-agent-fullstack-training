/**
 * OKF Markdown + YAML Frontmatter 编解码模块。
 */

import {
  VALID_STATUSES,
  VALID_TYPES,
  type MemoryFrontmatter,
  type MemoryRecord,
  type MemoryStatus,
  type MemoryType,
} from "./types.js";

export function escapeYamlString(value: string): string {
  return JSON.stringify(value);
}

function serializeList(items: string[]): string {
  if (items.length === 0) return "[]";
  return `[${items.map((x) => escapeYamlString(x)).join(", ")}]`;
}

export function renderRecordMarkdown(meta: MemoryFrontmatter, body: string): string {
  const lines = [
    "---",
    `id: ${escapeYamlString(meta.id)}`,
    `project: ${escapeYamlString(meta.project)}`,
    `type: ${meta.type}`,
    `title: ${escapeYamlString(meta.title)}`,
    `description: ${escapeYamlString(meta.description)}`,
    `tags: ${serializeList(meta.tags)}`,
    `sources: ${serializeList(meta.sources)}`,
    `status: ${meta.status}`,
    `created_at: ${escapeYamlString(meta.created_at)}`,
    `updated_at: ${escapeYamlString(meta.updated_at)}`,
    `revision: ${meta.revision}`,
    "---",
    "",
    body.trim(),
    "",
  ];
  return lines.join("\n");
}

function parseYamlScalar(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    try {
      return String(JSON.parse(trimmed));
    } catch {
      return trimmed.slice(1, -1);
    }
  }
  if (trimmed.startsWith("'") && trimmed.endsWith("'")) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function parseYamlStringArray(raw: string): string[] {
  const trimmed = raw.trim();
  if (!trimmed || trimmed === "[]") return [];
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v));
      }
    } catch {
      const inner = trimmed.slice(1, -1).trim();
      if (!inner) return [];
      return inner.split(",").map((part) => parseYamlScalar(part));
    }
  }
  return [parseYamlScalar(trimmed)];
}

export function parseRecordMarkdown(content: string, filePath: string): MemoryRecord {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    throw new Error(`Invalid OKF memory file (missing YAML frontmatter): ${filePath}`);
  }
  const [, headerRaw, bodyRaw] = match;
  const fields: Record<string, string> = {};
  for (const line of headerRaw.split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim();
    if (key) fields[key] = val;
  }

  const type = parseYamlScalar(fields.type || "Fact") as MemoryType;
  const status = parseYamlScalar(fields.status || "verified") as MemoryStatus;
  const revision = Number.parseInt(parseYamlScalar(fields.revision || "1"), 10);

  return {
    id: parseYamlScalar(fields.id || ""),
    project: parseYamlScalar(fields.project || ""),
    type: VALID_TYPES.has(type) ? type : "Fact",
    title: parseYamlScalar(fields.title || ""),
    description: parseYamlScalar(fields.description || ""),
    tags: parseYamlStringArray(fields.tags || "[]"),
    sources: parseYamlStringArray(fields.sources || "[]"),
    status: VALID_STATUSES.has(status) ? status : "verified",
    created_at: parseYamlScalar(fields.created_at || ""),
    updated_at: parseYamlScalar(fields.updated_at || ""),
    revision: Number.isFinite(revision) && revision > 0 ? revision : 1,
    body: bodyRaw.trim(),
    filePath,
  };
}
