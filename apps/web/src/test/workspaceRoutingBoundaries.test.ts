import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const modules = ["types", "catalog", "queryValues", "queryParser", "querySerializer"] as const;
const libraryRoot = resolve(process.cwd(), "src/lib");
const allowed: Record<(typeof modules)[number], readonly string[]> = {
  types: [],
  catalog: ["types"],
  queryValues: ["catalog"],
  queryParser: ["types", "catalog", "queryValues"],
  querySerializer: ["types", "catalog", "queryValues"],
};

describe("workspace URL ownership", () => {
  it.each(modules)("keeps %s dependencies directed without importing the public entry", (name) => {
    const source = readFileSync(resolve(libraryRoot, "workspace", `${name}.ts`), "utf8");
    expect(source).not.toMatch(/(?:from\s+|import\s*\()\s*["'][^"']*workspaceRouting["']/);
    const localImports = [...source.matchAll(/(?:from\s+|import\s*\()\s*["']\.\/([^"']+)["']/g)].map(
      (match) => match[1],
    );
    expect(localImports.every((dependency) => allowed[name].includes(dependency ?? ""))).toBe(true);
  });

  it("keeps source-context validation in one public owner", () => {
    const facade = readFileSync(resolve(libraryRoot, "workspaceRouting.ts"), "utf8");
    expect(facade).toContain("function researchReturnLocation(");
    expect(facade).toContain("const maximumReturnFrames = 16");
    expect(facade).toContain("const retainedReturnFrames = 3");
    expect(facade).toContain("parseResearchReturnFrame(cursor)");
    expect(facade).not.toContain("parseResearchReturnLocation");
    expect(facade).toContain("4_096");
    for (const name of ["queryParser", "querySerializer"]) {
      const source = readFileSync(resolve(libraryRoot, "workspace", `${name}.ts`), "utf8");
      expect(source).toContain("normalizeReturnPath: ReturnPathNormalizer");
      expect(source).not.toContain("function researchReturnLocation(");
    }
  });
});
