import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, symlinkSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { ESLint } from "eslint";
import fixture from "./fixtures/next-root-glob.json";

const require = createRequire(import.meta.url);
const glob = require("fast-glob") as { globSync: (patterns: string | string[], options: { cwd: string; onlyDirectories: boolean }) => string[] };
let root: string;
beforeAll(() => {
  root = mkdtempSync(path.join(tmpdir(), "sfr-eslint-glob-test-"));
  for (const directory of fixture.directories) mkdirSync(path.join(root, directory), { recursive: true });
  writeFileSync(path.join(root, "packages/not-a-project"), "synthetic");
  symlinkSync(path.join(root, "packages/alpha"), path.join(root, "linked"), "dir");
  writeFileSync(path.join(root, "packages/beta/pages/about.tsx"), "");
  writeFileSync(path.join(root, "packages/alpha/app/page.tsx"), "");
});
afterAll(() => rmSync(root, { recursive: true }));

describe("Next ESLint glob replacement", () => {
  for (const sample of fixture.cases) {
    it(`preserves upstream directory matching: ${JSON.stringify(sample.pattern)}`, () => {
      const patterns = Array.isArray(sample.pattern) ? sample.pattern : sample.pattern.replace("<ROOT>", root);
      const result = glob.globSync(patterns, { cwd: root, onlyDirectories: true }).map(value => value.replace(root, "<ROOT>")).sort();
      expect(result).toEqual(sample.results);
    });
  }
  it("rejects the original 9,603-character attack without stack exhaustion", () => {
    const result = spawnSync(process.execPath, ["--input-type=module", "-e", `
      import { createRequire } from 'node:module';
      const require = createRequire(process.cwd() + '/package.json');
      try { require('fast-glob').globSync('{'.repeat(4800)+'a,b'+'}'.repeat(4800), {onlyDirectories:true}); process.exit(2); }
      catch(error) { console.log(JSON.stringify({name:error.name,message:error.message})); }
    `], { cwd: process.cwd(), encoding: "utf8", timeout: 5000 });
    expect(result.error).toBeUndefined();
    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({ name: "SyntaxError", message: "glob brace nesting exceeds limit" });
  });
  it("bounds all three consumed APIs before entering their parsers", () => {
    const adapter = require("micromatch");
    for (const method of ["makeRe", "scan", "braces"]) {
      expect(() => adapter[method]("{".repeat(129) + "a,b" + "}".repeat(129), { expand: true })).toThrow("glob brace nesting exceeds limit");
      expect(() => adapter[method]("a".repeat(10001), { expand: true })).toThrow("glob pattern exceeds length limit");
    }
    expect(adapter.braces("{".repeat(128) + "a,b" + "}".repeat(128), { expand: true })).toHaveLength(2);
    expect(adapter.braces("a".repeat(10000), { expand: true })).toEqual(["a".repeat(10000)]);
    expect(adapter.braces(String.raw`literal\{brace\}`, { expand: true })).toEqual(["literal{brace}"]);
    expect(() => adapter.braces("{a,b}".repeat(12), { expand: true })).toThrow("glob brace expansion exceeds limit");
  });
  it("reports expansion overflow instead of silently losing lint roots", () => {
    expect(() => glob.globSync("packages/web-{1..10000}", { cwd: root, onlyDirectories: true })).toThrow("glob brace expansion exceeds limit");
  });
  it("contains a different implementation with no braces package", () => {
    expect(require("micromatch/package.json").name).toBe("@sfr/fast-glob-patterns");
    expect(() => require.resolve("braces")).toThrow();
    expect(JSON.parse(readFileSync(path.join(path.dirname(require.resolve("eslint-config-next")), "../package.json"), "utf8")).version).toBe("16.4.3");
    expect(require("@next/eslint-plugin-next/package.json").version).toBe("16.4.3");
  });
  it("preserves all 113 existing rule settings on app, library and test files", async () => {
    const eslint = new ESLint();
    for (const file of ["app/page.tsx", "lib/analytics.ts", "tests/unit/analytics.test.ts"]) {
      const config = await eslint.calculateConfigForFile(file);
      const rules = Object.fromEntries(Object.entries(config.rules).sort(([a], [b]) => a.localeCompare(b)));
      expect(Object.keys(rules)).toHaveLength(113);
      expect(createHash("sha256").update(JSON.stringify(rules)).digest("hex")).toBe("e809ea1c5cccec205e74738d64d3f93ea3e7577838c1f5664d6a4305cf1500b5");
    }
  });
  it("still detects internal links in Pages/App roots and other Next violations", async () => {
    const eslint = new ESLint({ overrideConfig: { settings: { next: { rootDir: [path.join(root, "packages/{alpha,beta}")] } } } });
    const results = await eslint.lintText('export default function Page() { return <><a href="/about">Legacy</a><a href="/">App</a><img src="/x.png" alt="x"/><script src="/sync.js"/></>; }', { filePath: "app/page.tsx" });
    const messages = results.flatMap(result => result.messages);
    expect(messages.filter(message => message.ruleId === "@next/next/no-html-link-for-pages")).toHaveLength(2);
    expect(messages.some(message => message.ruleId === "@next/next/no-img-element")).toBe(true);
    expect(messages.some(message => message.ruleId === "@next/next/no-sync-scripts")).toBe(true);
  });
});
