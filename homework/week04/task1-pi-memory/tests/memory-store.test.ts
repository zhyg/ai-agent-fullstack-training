import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import type { ExtensionAPI, ExtensionContext, ToolDefinition } from "@mariozechner/pi-coding-agent";
import projectMemoryExtension from "../extensions/project-memory.js";
import {
  ProjectMemoryStore,
  normalizeMemoryId,
  verifyMemorySources,
} from "../src/memory-store.js";

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test("CRUD lifecycle: write, search, read, update, delete, validate", () => {
  const root = makeTempDir("pi-mem-crud-");
  const projectDir = path.join(root, "login_demo");
  const storageRoot = path.join(root, "store");
  fs.mkdirSync(path.join(projectDir, "tests"), { recursive: true });
  fs.mkdirSync(path.join(projectDir, "docs"), { recursive: true });
  fs.writeFileSync(path.join(projectDir, "tests", "test_session.py"), "def test_ok(): pass\n");
  fs.writeFileSync(path.join(projectDir, "docs", "testing-guide.md"), "python -m pytest tests/test_session.py -q\n");

  const store = new ProjectMemoryStore({ projectRoot: projectDir, storageRoot });

  // 1. Write
  const written = store.write({
    id: "testing/session-entry",
    type: "Procedure",
    title: "会话测试入口",
    description: "测试文件与 pytest 运行命令",
    tags: ["testing", "session"],
    sources: ["tests/test_session.py", "docs/testing-guide.md"],
    body: "命令：`python -m pytest tests/test_session.py -q`",
  });
  assert.equal(written.revision, 1);
  assert.equal(fs.existsSync(written.filePath), true);
  assert.equal(fs.existsSync(store.indexPath), true);
  assert.equal(fs.existsSync(store.logPath), true);

  // Duplicate write rejected
  assert.throws(() =>
    store.write({
      id: "testing/session-entry",
      title: "dup",
      description: "dup",
      sources: ["tests/test_session.py"],
      body: "dup",
    })
  );

  // 2. Search & Read in a brand new store instance (simulating new session)
  const freshStore = new ProjectMemoryStore({ projectRoot: projectDir, storageRoot });
  const hits = freshStore.search({ query: "会话测试", verifySources: true });
  assert.equal(hits.length, 1);
  assert.equal(hits[0].record.id, "testing/session-entry");
  assert.equal(hits[0].sourceChecks?.every((c) => c.exists === true), true);

  const loaded = freshStore.read("testing/session-entry");
  assert.ok(loaded);
  assert.equal(loaded.title, "会话测试入口");

  // 3. Migrate file & verify old source becomes missing, then update
  fs.mkdirSync(path.join(projectDir, "tests", "auth"), { recursive: true });
  fs.renameSync(
    path.join(projectDir, "tests", "test_session.py"),
    path.join(projectDir, "tests", "auth", "test_session.py")
  );
  const staleChecks = verifyMemorySources(projectDir, loaded.sources);
  assert.equal(staleChecks[0].exists, false);

  const updated = freshStore.update({
    id: "testing/session-entry",
    sources: ["tests/auth/test_session.py", "docs/testing-guide.md"],
    body: "命令：`python -m pytest tests/auth/test_session.py -q`",
    changeNote: "migrated test path",
  });
  assert.equal(updated.revision, 2);
  const newChecks = verifyMemorySources(projectDir, updated.sources);
  assert.equal(newChecks.every((c) => c.exists === true), true);

  // Validate OKF bundle
  const validation = freshStore.validate();
  assert.equal(validation.valid, true);
  assert.equal(validation.recordCount, 1);

  // 4. Delete
  const del = freshStore.delete("testing/session-entry", "cleanup test");
  assert.equal(del.deleted, true);
  assert.equal(freshStore.read("testing/session-entry"), null);
  assert.equal(freshStore.list().length, 0);
  const logText = fs.readFileSync(freshStore.logPath, "utf-8");
  assert.match(logText, /WRITE/);
  assert.match(logText, /UPDATE/);
  assert.match(logText, /DELETE/);

  fs.rmSync(root, { recursive: true, force: true });
});

test("Project isolation: memories from project A never leak into project B", () => {
  const root = makeTempDir("pi-mem-iso-");
  const projA = path.join(root, "project-a");
  const projB = path.join(root, "project-b");
  const storageRoot = path.join(root, "store");
  fs.mkdirSync(projA, { recursive: true });
  fs.mkdirSync(projB, { recursive: true });

  const storeA = new ProjectMemoryStore({ projectRoot: projA, storageRoot });
  const storeB = new ProjectMemoryStore({ projectRoot: projB, storageRoot });

  storeA.write({
    id: "facts/secret-a",
    title: "Project A Only",
    description: "Belongs strictly to A",
    sources: ["README.md"],
    body: "A specific knowledge",
  });

  assert.equal(storeA.search({ query: "Project A" }).length, 1);
  assert.equal(storeB.search({ query: "Project A" }).length, 0);
  assert.equal(storeB.list().length, 0);

  fs.rmSync(root, { recursive: true, force: true });
});

test("Path traversal & reserved ids are strictly rejected", () => {
  for (const bad of ["../escape", "/abs/path", "a/../../b", "index", "log", "", ".hidden"]) {
    assert.throws(() => normalizeMemoryId(bad), `Expected rejection for: ${bad}`);
  }
});

test("pi extension registers all 5 tools, 2 slash commands, and before_agent_start hook", async () => {
  const root = makeTempDir("pi-ext-test-");
  const projectDir = path.join(root, "login_demo");
  const storageRoot = path.join(root, "store");
  fs.mkdirSync(path.join(projectDir, "tests"), { recursive: true });
  fs.writeFileSync(path.join(projectDir, "tests", "test_session.py"), "assert True\n");

  const prevRoot = process.env.PI_MEMORY_ROOT;
  process.env.PI_MEMORY_ROOT = storageRoot;

  try {
    const tools = new Map<string, ToolDefinition<any, any, any>>();
    const commands = new Map<string, unknown>();
    const handlers = new Map<string, (...args: any[]) => any>();

    const mockPi = {
      registerTool(def: ToolDefinition<any, any, any>) {
        tools.set(def.name, def);
      },
      registerCommand(name: string, opts: unknown) {
        commands.set(name, opts);
      },
      on(event: string, handler: (...args: any[]) => any) {
        handlers.set(event, handler);
      },
    } as unknown as ExtensionAPI;

    projectMemoryExtension(mockPi);

    assert.deepEqual(
      Array.from(tools.keys()).sort(),
      [
        "project_memory_delete",
        "project_memory_read",
        "project_memory_search",
        "project_memory_update",
        "project_memory_write",
      ]
    );
    assert.equal(commands.has("memory-list"), true);
    assert.equal(commands.has("memory-validate"), true);
    assert.equal(handlers.has("before_agent_start"), true);

    const ctx = { cwd: projectDir } as ExtensionContext;

    // Execute write tool
    const writeRes = await tools.get("project_memory_write")!.execute(
      "tc-1",
      {
        id: "testing/session-test",
        title: "Session Test Entry",
        description: "Test path and command",
        sources: ["tests/test_session.py"],
        body: "Run python -m pytest tests/test_session.py -q",
      },
      undefined,
      undefined,
      ctx
    );
    const writeText = (writeRes.content[0] as { text: string }).text;
    assert.match(writeText, /实际保存路径/);

    // Execute before_agent_start hook (new session prompt injection)
    const hook = handlers.get("before_agent_start")!;
    const injected = await hook({ systemPrompt: "BASE_PROMPT" }, ctx);
    assert.match(injected.systemPrompt, /testing\/session-test/);

    // Execute search tool
    const searchRes = await tools.get("project_memory_search")!.execute(
      "tc-2",
      { query: "Session Test" },
      undefined,
      undefined,
      ctx
    );
    assert.match((searchRes.content[0] as { text: string }).text, /存在/);

    // Execute update tool
    const updateRes = await tools.get("project_memory_update")!.execute(
      "tc-3",
      { id: "testing/session-test", body: "Updated body", changeNote: "updated" },
      undefined,
      undefined,
      ctx
    );
    assert.match((updateRes.content[0] as { text: string }).text, /rev 2/);

    // Execute delete tool
    const delRes = await tools.get("project_memory_delete")!.execute(
      "tc-4",
      { id: "testing/session-test", reason: "done" },
      undefined,
      undefined,
      ctx
    );
    assert.match((delRes.content[0] as { text: string }).text, /已删除/);
  } finally {
    if (prevRoot === undefined) {
      delete process.env.PI_MEMORY_ROOT;
    } else {
      process.env.PI_MEMORY_ROOT = prevRoot;
    }
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("Real pi DefaultResourceLoader loads extensions/project-memory.ts cleanly", async () => {
  const { DefaultResourceLoader } = await import("@mariozechner/pi-coding-agent");
  const agentDir = makeTempDir("pi-agent-dir-");
  try {
    const taskRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
    const loader = new DefaultResourceLoader({
      cwd: path.join(taskRoot, "login_demo"),
      agentDir,
      additionalExtensionPaths: [path.join(taskRoot, "extensions", "project-memory.ts")],
    });
    await loader.reload();
    const loaded = loader.getExtensions();
    assert.equal(loaded.errors.length, 0, `Unexpected extension load errors: ${JSON.stringify(loaded.errors)}`);
    assert.equal(loaded.extensions.length, 1);
    assert.deepEqual(
      Array.from(loaded.extensions[0].tools.keys()).sort(),
      [
        "project_memory_delete",
        "project_memory_read",
        "project_memory_search",
        "project_memory_update",
        "project_memory_write",
      ]
    );
    assert.deepEqual(Array.from(loaded.extensions[0].commands.keys()).sort(), [
      "memory-list",
      "memory-validate",
    ]);
  } finally {
    fs.rmSync(agentDir, { recursive: true, force: true });
  }
});
