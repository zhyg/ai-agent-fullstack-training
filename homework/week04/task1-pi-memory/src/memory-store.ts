/**
 * OKF v0.2 风格的项目长期记忆持久化存储（无向量数据库依赖）。
 *
 * 目录布局：
 *   <storageRoot>/<projectKey>/
 *     ├── index.md              # 项目记忆目录
 *     ├── log.md                # 追加式变更审计日志（write / update / delete）
 *     └── <category>/<name>.md  # 单条记忆（YAML Frontmatter + Markdown 正文）
 */

import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export type MemoryType = "Fact" | "Rule" | "Procedure" | "Decision";
export type MemoryStatus = "verified" | "unverified" | "deprecated";

export interface MemoryFrontmatter {
  id: string;
  project: string;
  type: MemoryType;
  title: string;
  description: string;
  tags: string[];
  sources: string[];
  status: MemoryStatus;
  created_at: string;
  updated_at: string;
  revision: number;
}

export interface MemoryRecord extends MemoryFrontmatter {
  body: string;
  filePath: string;
}

export interface SourceCheckResult {
  source: string;
  kind: "file" | "command_or_note";
  resolvedPath?: string;
  exists?: boolean;
}

export interface WriteMemoryInput {
  id: string;
  type?: MemoryType;
  title: string;
  description: string;
  tags?: string[];
  sources: string[];
  status?: MemoryStatus;
  body: string;
}

export interface UpdateMemoryInput {
  id: string;
  title?: string;
  description?: string;
  type?: MemoryType;
  tags?: string[];
  sources?: string[];
  status?: MemoryStatus;
  body?: string;
  changeNote?: string;
}

export interface SearchMemoryOptions {
  query?: string;
  tag?: string;
  type?: MemoryType;
  status?: MemoryStatus;
  limit?: number;
  verifySources?: boolean;
}

export interface SearchMemoryHit {
  record: MemoryRecord;
  score: number;
  sourceChecks?: SourceCheckResult[];
}

export interface ValidationReport {
  valid: boolean;
  projectKey: string;
  storeDir: string;
  recordCount: number;
  errors: string[];
}

const VALID_TYPES: ReadonlySet<string> = new Set(["Fact", "Rule", "Procedure", "Decision"]);
const VALID_STATUSES: ReadonlySet<string> = new Set(["verified", "unverified", "deprecated"]);

export function getDefaultStorageRoot(): string {
  return (
    process.env.PI_MEMORY_ROOT?.trim() ||
    path.join(os.homedir(), ".pi", "agent", "project-memory")
  );
}

/**
 * 根据项目根目录生成稳定且人类可读的 projectKey（目录名 + 路径短哈希），
 * 保证不同项目彻底隔离，同一项目跨会话自动命中同一目录。
 */
export function resolveProjectKey(projectRoot: string, explicitProjectId?: string): string {
  if (explicitProjectId && explicitProjectId.trim()) {
    const cleaned = explicitProjectId
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "");
    if (!cleaned || cleaned.includes("..")) {
      throw new Error(`Invalid project identifier: ${explicitProjectId}`);
    }
    return cleaned;
  }
  const canonical = fs.existsSync(projectRoot)
    ? fs.realpathSync(projectRoot)
    : path.resolve(projectRoot);
  const base = path
    .basename(canonical)
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "") || "project";
  const hash = crypto.createHash("sha256").update(canonical).digest("hex").slice(0, 8);
  return `${base}-${hash}`;
}

export function normalizeMemoryId(rawId: string): string {
  const id = rawId.trim().replace(/\.md$/i, "");
  if (!id) {
    throw new Error("Memory id cannot be empty.");
  }
  if (
    id.startsWith("/") ||
    id.startsWith("\\") ||
    id.includes("\\") ||
    id.includes("..") ||
    id.startsWith(".")
  ) {
    throw new Error(`Unsafe memory id (path traversal rejected): ${rawId}`);
  }
  if (!/^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$/.test(id)) {
    throw new Error(
      `Invalid memory id "${rawId}". Use letters, digits, '_', '-', and '/' segments (e.g. "testing/session-test-entry").`
    );
  }
  if (id === "index" || id === "log") {
    throw new Error(`Reserved memory id: ${id}`);
  }
  return id;
}

function escapeYamlString(value: string): string {
  return JSON.stringify(value);
}

function serializeList(items: string[]): string {
  if (items.length === 0) return "[]";
  return `[${items.map((x) => escapeYamlString(x)).join(", ")}]`;
}

function renderRecordMarkdown(meta: MemoryFrontmatter, body: string): string {
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

function extractSearchTerms(query: string): string[] {
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

export class ProjectMemoryStore {
  public readonly projectRoot: string;
  public readonly projectKey: string;
  public readonly storageRoot: string;
  public readonly storeDir: string;

  constructor(options: {
    projectRoot: string;
    storageRoot?: string;
    projectId?: string;
  }) {
    this.projectRoot = path.resolve(options.projectRoot);
    this.storageRoot = path.resolve(options.storageRoot || getDefaultStorageRoot());
    this.projectKey = resolveProjectKey(this.projectRoot, options.projectId);
    this.storeDir = path.join(this.storageRoot, this.projectKey);
  }

  private resolveRecordPath(id: string): string {
    const normalized = normalizeMemoryId(id);
    const target = path.resolve(this.storeDir, `${normalized}.md`);
    if (!target.startsWith(this.storeDir + path.sep)) {
      throw new Error(`Path escapes project memory directory: ${id}`);
    }
    return target;
  }

  public get indexPath(): string {
    return path.join(this.storeDir, "index.md");
  }

  public get logPath(): string {
    return path.join(this.storeDir, "log.md");
  }

  private ensureStoreDir(): void {
    fs.mkdirSync(this.storeDir, { recursive: true });
    if (!fs.existsSync(this.logPath)) {
      fs.writeFileSync(
        this.logPath,
        [
          "---",
          'okf_version: "0.2"',
          `project: ${escapeYamlString(this.projectKey)}`,
          "---",
          "",
          `# ${this.projectKey} 长期记忆变更日志`,
          "",
        ].join("\n"),
        "utf-8"
      );
    }
  }

  private appendLog(action: "WRITE" | "UPDATE" | "DELETE", id: string, detail: string): void {
    this.ensureStoreDir();
    const ts = new Date().toISOString();
    fs.appendFileSync(this.logPath, `- \`${ts}\` **${action}** \`${id}\` — ${detail}\n`, "utf-8");
  }

  private rebuildIndex(): void {
    this.ensureStoreDir();
    const records = this.list();
    const lines = [
      "---",
      'okf_version: "0.2"',
      `project: ${escapeYamlString(this.projectKey)}`,
      `project_root: ${escapeYamlString(this.projectRoot)}`,
      `updated_at: ${escapeYamlString(new Date().toISOString())}`,
      "---",
      "",
      `# ${this.projectKey} 项目长期记忆目录`,
      "",
      `项目路径：\`${this.projectRoot}\``,
      "",
    ];

    if (records.length === 0) {
      lines.push("（当前项目暂无活动记忆记录。）", "");
    } else {
      lines.push("## 记忆条目", "");
      for (const rec of records) {
        const tagText = rec.tags.length ? ` [${rec.tags.join(", ")}]` : "";
        lines.push(
          `- [${rec.title}](./${rec.id}.md) (\`${rec.id}\`, ${rec.type}, rev ${rec.revision}, ${rec.status})${tagText} - ${rec.description}`
        );
      }
      lines.push("");
    }
    lines.push("## 审计日志", "", "- [变更记录](./log.md)", "");
    fs.writeFileSync(this.indexPath, lines.join("\n"), "utf-8");
  }

  public write(input: WriteMemoryInput): MemoryRecord {
    const id = normalizeMemoryId(input.id);
    if (!input.title.trim()) throw new Error("title is required.");
    if (!input.description.trim()) throw new Error("description is required.");
    if (!input.sources || input.sources.length === 0) {
      throw new Error("sources must include at least one verifiable file path or evidence reference.");
    }
    const type: MemoryType = input.type || "Fact";
    if (!VALID_TYPES.has(type)) throw new Error(`Invalid memory type: ${type}`);
    const status: MemoryStatus = input.status || "verified";
    if (!VALID_STATUSES.has(status)) throw new Error(`Invalid memory status: ${status}`);

    const filePath = this.resolveRecordPath(id);
    if (fs.existsSync(filePath)) {
      throw new Error(`Memory "${id}" already exists at ${filePath}. Use update() instead.`);
    }

    this.ensureStoreDir();
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    const now = new Date().toISOString();
    const meta: MemoryFrontmatter = {
      id,
      project: this.projectKey,
      type,
      title: input.title.trim(),
      description: input.description.trim(),
      tags: (input.tags || []).map((t) => t.trim()).filter(Boolean),
      sources: input.sources.map((s) => s.trim()).filter(Boolean),
      status,
      created_at: now,
      updated_at: now,
      revision: 1,
    };
    const markdown = renderRecordMarkdown(meta, input.body);
    fs.writeFileSync(filePath, markdown, "utf-8");
    this.rebuildIndex();
    this.appendLog("WRITE", id, `rev 1 | title="${meta.title}" | sources=[${meta.sources.join(", ")}]`);
    return { ...meta, body: input.body.trim(), filePath };
  }

  public read(id: string): MemoryRecord | null {
    const filePath = this.resolveRecordPath(id);
    if (!fs.existsSync(filePath)) return null;
    return parseRecordMarkdown(fs.readFileSync(filePath, "utf-8"), filePath);
  }

  public list(): MemoryRecord[] {
    if (!fs.existsSync(this.storeDir)) return [];
    const results: MemoryRecord[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
        } else if (entry.isFile() && entry.name.endsWith(".md")) {
          if (dir === this.storeDir && (entry.name === "index.md" || entry.name === "log.md")) {
            continue;
          }
          results.push(parseRecordMarkdown(fs.readFileSync(full, "utf-8"), full));
        }
      }
    };
    walk(this.storeDir);
    results.sort((a, b) => a.id.localeCompare(b.id));
    return results;
  }

  public search(options: SearchMemoryOptions = {}): SearchMemoryHit[] {
    const records = this.list();
    const terms = extractSearchTerms(options.query || "");
    const tagFilter = options.tag?.trim().toLowerCase();
    const limit = options.limit && options.limit > 0 ? options.limit : 10;

    const hits: SearchMemoryHit[] = [];
    for (const rec of records) {
      if (options.type && rec.type !== options.type) continue;
      if (options.status && rec.status !== options.status) continue;
      if (tagFilter && !rec.tags.some((t) => t.toLowerCase() === tagFilter)) continue;

      let score = 0;
      if (terms.length === 0) {
        score = 1;
      } else {
        const idLower = rec.id.toLowerCase();
        const titleLower = rec.title.toLowerCase();
        const descLower = rec.description.toLowerCase();
        const tagsLower = rec.tags.join(" ").toLowerCase();
        const sourcesLower = rec.sources.join(" ").toLowerCase();
        const bodyLower = rec.body.toLowerCase();

        for (const term of terms) {
          if (idLower.includes(term)) score += 5;
          if (titleLower.includes(term)) score += 4;
          if (tagsLower.includes(term)) score += 3;
          if (descLower.includes(term)) score += 2.5;
          if (sourcesLower.includes(term)) score += 2;
          if (bodyLower.includes(term)) score += 1;
        }
      }

      if (score > 0) {
        hits.push({
          record: rec,
          score,
          sourceChecks: options.verifySources
            ? verifyMemorySources(this.projectRoot, rec.sources)
            : undefined,
        });
      }
    }

    hits.sort((a, b) => b.score - a.score || a.record.id.localeCompare(b.record.id));
    return hits.slice(0, limit);
  }

  public update(input: UpdateMemoryInput): MemoryRecord {
    const id = normalizeMemoryId(input.id);
    const existing = this.read(id);
    if (!existing) {
      throw new Error(`Memory "${id}" not found in project "${this.projectKey}".`);
    }

    const type = input.type ?? existing.type;
    if (!VALID_TYPES.has(type)) throw new Error(`Invalid memory type: ${type}`);
    const status = input.status ?? existing.status;
    if (!VALID_STATUSES.has(status)) throw new Error(`Invalid memory status: ${status}`);

    const updated: MemoryFrontmatter = {
      id,
      project: this.projectKey,
      type,
      title: input.title !== undefined ? input.title.trim() : existing.title,
      description: input.description !== undefined ? input.description.trim() : existing.description,
      tags: input.tags !== undefined ? input.tags.map((t) => t.trim()).filter(Boolean) : existing.tags,
      sources:
        input.sources !== undefined
          ? input.sources.map((s) => s.trim()).filter(Boolean)
          : existing.sources,
      status,
      created_at: existing.created_at,
      updated_at: new Date().toISOString(),
      revision: existing.revision + 1,
    };

    if (updated.sources.length === 0) {
      throw new Error("Updated memory must retain at least one source.");
    }

    const newBody = input.body !== undefined ? input.body.trim() : existing.body;
    fs.writeFileSync(existing.filePath, renderRecordMarkdown(updated, newBody), "utf-8");
    this.rebuildIndex();
    const note = input.changeNote?.trim() || "updated record";
    this.appendLog(
      "UPDATE",
      id,
      `rev ${existing.revision} -> ${updated.revision} | ${note} | sources=[${updated.sources.join(", ")}]`
    );
    return { ...updated, body: newBody, filePath: existing.filePath };
  }

  public delete(id: string, reason = "deleted by user/agent"): { deleted: boolean; filePath: string } {
    const normalized = normalizeMemoryId(id);
    const filePath = this.resolveRecordPath(normalized);
    if (!fs.existsSync(filePath)) {
      return { deleted: false, filePath };
    }
    fs.unlinkSync(filePath);
    // 清理已空的子目录
    let dir = path.dirname(filePath);
    while (dir !== this.storeDir && dir.startsWith(this.storeDir + path.sep)) {
      if (fs.readdirSync(dir).length === 0) {
        fs.rmdirSync(dir);
        dir = path.dirname(dir);
      } else {
        break;
      }
    }
    this.rebuildIndex();
    this.appendLog("DELETE", normalized, reason);
    return { deleted: true, filePath };
  }

  public formatCatalogDigest(): string {
    const records = this.list();
    if (records.length === 0) {
      return `当前项目 (${this.projectKey}) 尚无已保存的长期记忆。`;
    }
    const rows = records.map(
      (r) =>
        `- \`${r.id}\` (${r.type}, rev ${r.revision}, ${r.status}): ${r.title} — ${r.description} | sources: ${r.sources.join(", ")}`
    );
    return [
      `项目长期记忆目录 (${this.projectKey}，目录：${this.storeDir})：`,
      ...rows,
    ].join("\n");
  }

  public validate(): ValidationReport {
    const errors: string[] = [];
    if (!fs.existsSync(this.storeDir)) {
      return {
        valid: true,
        projectKey: this.projectKey,
        storeDir: this.storeDir,
        recordCount: 0,
        errors: [],
      };
    }
    if (!fs.existsSync(this.indexPath)) {
      errors.push("Missing index.md");
    }
    if (!fs.existsSync(this.logPath)) {
      errors.push("Missing log.md");
    }
    const records = this.list();
    for (const rec of records) {
      if (!rec.id) errors.push(`${rec.filePath}: missing id`);
      if (rec.project !== this.projectKey) {
        errors.push(`${rec.filePath}: project mismatch (${rec.project} != ${this.projectKey})`);
      }
      if (!rec.title) errors.push(`${rec.filePath}: missing title`);
      if (rec.sources.length === 0) errors.push(`${rec.filePath}: missing sources`);
    }
    return {
      valid: errors.length === 0,
      projectKey: this.projectKey,
      storeDir: this.storeDir,
      recordCount: records.length,
      errors,
    };
  }
}
