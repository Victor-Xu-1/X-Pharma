import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(webRoot, "../..");
const schemaPath = join(repositoryRoot, "docs", "openapi.json");
const requestTemplate = join(webRoot, "openapi", "request.ts");
const generatedDirectory = join(webRoot, "src", "lib", "generated");
const binaryName = process.platform === "win32" ? "openapi.cmd" : "openapi";
const generator = join(webRoot, "node_modules", ".bin", binaryName);

const mode = process.argv[2];
if (!new Set(["--check", "--write"]).has(mode) || process.argv.length !== 3) {
  console.error("Usage: node scripts/openapi-contract.mjs --check|--write");
  process.exit(2);
}
if (!existsSync(generator)) {
  console.error("OpenAPI generator is not installed. Run pnpm install first.");
  process.exit(2);
}

const temporaryRoot = mkdtempSync(join(tmpdir(), "pharma-openapi-"));
const temporaryOutput = join(temporaryRoot, "generated");

function files(root, current = root) {
  const entries = readdirSync(current, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const absolute = join(current, entry.name);
    return entry.isDirectory() ? files(root, absolute) : [relative(root, absolute).replaceAll("\\", "/")];
  });
}

function drift(expected, actual) {
  if (!existsSync(actual)) return ["generated client directory is missing"];
  const expectedFiles = files(expected);
  const actualFiles = files(actual);
  const names = [...new Set([...expectedFiles, ...actualFiles])].sort();
  return names.filter((name) => {
    if (!expectedFiles.includes(name) || !actualFiles.includes(name)) return true;
    return !readFileSync(join(expected, name)).equals(readFileSync(join(actual, name)));
  });
}

function normalizeGeneratedFiles(root) {
  for (const name of files(root)) {
    const path = join(root, name);
    const content = readFileSync(path, "utf8");
    writeFileSync(path, `${content.trimEnd()}\n`);
  }
}

try {
  const generated = spawnSync(
    generator,
    [
      "--input",
      schemaPath,
      "--output",
      temporaryOutput,
      "--client",
      "fetch",
      "--useOptions",
      "--useUnionTypes",
      "--indent",
      "2",
      "--request",
      requestTemplate,
    ],
    { cwd: webRoot, encoding: "utf8" },
  );
  if (generated.status !== 0) {
    process.stderr.write(generated.stdout ?? "");
    process.stderr.write(generated.stderr ?? "");
    process.exit(generated.status ?? 1);
  }
  normalizeGeneratedFiles(temporaryOutput);

  if (mode === "--write") {
    rmSync(generatedDirectory, { recursive: true, force: true });
    cpSync(temporaryOutput, generatedDirectory, { recursive: true });
    console.log(`Generated ${files(generatedDirectory).length} OpenAPI client files.`);
    process.exit(0);
  }

  const differences = drift(temporaryOutput, generatedDirectory);
  if (differences.length) {
    console.error("Generated OpenAPI client is stale. Run `pnpm api:generate` and commit the result.");
    for (const name of differences.slice(0, 25)) console.error(`  - ${name}`);
    if (differences.length > 25) console.error(`  - and ${differences.length - 25} more`);
    process.exit(1);
  }
  console.log(`OpenAPI client drift check passed (${files(generatedDirectory).length} files).`);
} finally {
  rmSync(temporaryRoot, { recursive: true, force: true });
}
