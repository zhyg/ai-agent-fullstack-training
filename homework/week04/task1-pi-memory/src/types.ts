/**
 * 项目长期记忆核心领域类型定义。
 */

export type MemoryType = "Fact" | "Rule" | "Procedure" | "Decision";
export type MemoryStatus = "verified" | "unverified" | "deprecated";

export const VALID_TYPES: ReadonlySet<string> = new Set(["Fact", "Rule", "Procedure", "Decision"]);
export const VALID_STATUSES: ReadonlySet<string> = new Set(["verified", "unverified", "deprecated"]);

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
