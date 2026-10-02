import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { expect, test } from "vitest";

const viewRoot = resolve(process.cwd(), "src/views");
const targetRoot = join(viewRoot, "target");

function source(path: string): string {
  return readFileSync(path, "utf8");
}

function sourceFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    return entry.isDirectory() ? sourceFiles(path) : /\.tsx?$/.test(path) ? [path] : [];
  });
}

test("TargetView only orchestrates the dossier and explicitly owned panels", () => {
  const declarations = [...source(join(viewRoot, "TargetView.tsx")).matchAll(/^(?:export )?function (\w+)\(/gm)].map(
    (match) => match[1],
  );
  expect(declarations).toEqual(["TargetView"]);
});

test("target panel imports form an acyclic graph without importing the view facade", () => {
  const files = sourceFiles(targetRoot);
  const fileSet = new Set(files);
  const graph = new Map<string, string[]>();
  for (const file of files) {
    const edges: string[] = [];
    for (const match of source(file).matchAll(/^import[\s\S]*?from\s+"([^"]+)";/gm)) {
      const specifier = match[1];
      expect(specifier).not.toMatch(/(?:^|\/)TargetView$/);
      if (!specifier.startsWith(".")) continue;
      const path = resolve(dirname(file), specifier);
      const dependency = [`${path}.ts`, `${path}.tsx`].find((candidate) => fileSet.has(candidate));
      if (dependency) edges.push(dependency);
    }
    graph.set(file, edges);
  }
  function visit(file: string, ancestors: string[] = []) {
    expect(ancestors).not.toContain(file);
    for (const dependency of graph.get(file) ?? []) visit(dependency, [...ancestors, file]);
  }
  for (const file of files) visit(file);
});

test("target pipeline query and interaction state have one hook owner", () => {
  const files = sourceFiles(join(targetRoot, "pipeline"));
  const queryOwners = files.filter((file) => /\buseQuery\s*\(/.test(source(file)));
  expect(queryOwners).toEqual([join(targetRoot, "pipeline/useTargetPipeline.ts")]);
  for (const file of files.filter((path) => /(?:Filters|Toolbar|Table|Controls)\.tsx$/.test(path))) {
    expect(source(file)).not.toMatch(/\b(?:useQuery|useState|useEffect)\s*\(/);
  }
});

test("target presentation helpers have one definition and no facade re-export", () => {
  const files = [join(viewRoot, "TargetView.tsx"), ...sourceFiles(targetRoot)];
  for (const helper of ["pipelineSelectOptions", "pipelineProgramStatusLabel", "targetPipelineAppliedFilters"]) {
    const owners = files.filter((file) => new RegExp(`^(?:export )?function ${helper}\\(`, "m").test(source(file)));
    expect(owners).toEqual([join(targetRoot, "pipeline/presentation.ts")]);
  }
  expect(source(join(viewRoot, "TargetView.tsx"))).not.toMatch(/export.*pipeline(?:SelectOptions|ProgramStatusLabel)/);
});
