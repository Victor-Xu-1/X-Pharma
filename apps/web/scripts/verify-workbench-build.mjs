import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { gzipSync } from "node:zlib";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");
const manifest = JSON.parse(readFileSync(resolve(dist, ".vite/manifest.json"), "utf8"));

const expectedViews = {
  research: [
    "src/views/ChemistryView.tsx",
    "src/views/CollectionsView.tsx",
    "src/views/CompanyView.tsx",
    "src/views/DealsView.tsx",
    "src/views/DiseaseView.tsx",
    "src/views/DrugView.tsx",
    "src/views/EntityDossierView.tsx",
    "src/views/EpidemiologyView.tsx",
    "src/views/EvidenceView.tsx",
    "src/views/ExplorerView.tsx",
    "src/views/KnowledgeView.tsx",
    "src/views/MonitoringView.tsx",
    "src/views/NewsView.tsx",
    "src/views/OverviewView.tsx",
    "src/views/PipelineView.tsx",
    "src/views/PatentsView.tsx",
    "src/views/RegulatoryView.tsx",
    "src/views/TargetView.tsx",
    "src/views/TrialsView.tsx",
  ],
  internal: [
    "src/views/CommercialView.tsx",
    "src/views/DataFactoryView.tsx",
    "src/views/EnterpriseView.tsx",
    "src/views/GovernanceView.tsx",
  ],
};
const approvedDeferredEntryModules = {
  research: ["node_modules/.pnpm/web-vitals@6.0.1/node_modules/web-vitals/dist/web-vitals.js"],
  internal: [],
};
const initialLoadBudgets = {
  research: {
    javascriptBytes: 512 * 1024,
    javascriptGzipBytes: 180 * 1024,
    cssBytes: 192 * 1024,
    cssGzipBytes: 40 * 1024,
  },
  internal: {
    javascriptBytes: 384 * 1024,
    javascriptGzipBytes: 140 * 1024,
    cssBytes: 192 * 1024,
    cssGzipBytes: 40 * 1024,
  },
};
const forbiddenInitialModuleFragments = [
  "node_modules/.pnpm/@rdkit+rdkit@",
  "node_modules/.pnpm/ketcher-",
  "src/components/StructureEditor.tsx",
  "src/components/TrendLineChart.tsx",
  "src/components/LandscapeBarChart.tsx",
];

function fail(message) {
  throw new Error(`workbench build boundary failed: ${message}`);
}

function readEntry(name, workbench) {
  const body = readFileSync(resolve(dist, name), "utf8");
  if (!body.includes(`data-workbench="${workbench}"`)) fail(`${name} has the wrong workbench marker`);
  const scripts = [...body.matchAll(/<script[^>]+src="\/?([^"?]+)"/g)].map((match) => match[1]);
  if (scripts.length === 0 || scripts.some((script) => !script.startsWith("assets/") || !script.endsWith(".js")))
    fail(`${name} contains an invalid built module script`);
  const entryScripts = scripts.filter((script) =>
    Object.values(manifest).some((chunk) => chunk.file === script && (chunk.dynamicImports?.length ?? 0) > 0),
  );
  if (entryScripts.length !== 1) fail(`${name} must load exactly one workbench application entry`);
  return {
    body,
    script: entryScripts[0],
    sha256: createHash("sha256").update(body).digest("hex"),
  };
}

function findChunkRecord(script) {
  const chunks = Object.entries(manifest).filter(([, chunk]) => chunk.file === script);
  if (chunks.length !== 1) fail(`manifest must contain exactly one chunk for ${script}`);
  return chunks[0];
}

function findChunk(script) {
  return findChunkRecord(script)[1];
}

function verifyViews(workbench, chunk) {
  const actual = [...(chunk.dynamicImports ?? [])].sort();
  const expected = [...expectedViews[workbench], ...approvedDeferredEntryModules[workbench]].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(`${workbench} dynamic import graph does not match its approved boundary`);
  }
  const actualViews = actual.filter((module) => module.startsWith("src/views/"));
  const forbidden = Object.values(expectedViews)
    .flat()
    .filter((view) => !expectedViews[workbench].includes(view));
  if (actualViews.some((view) => forbidden.includes(view))) {
    fail(`${workbench} imports a view owned by another workbench`);
  }
}

function verifyDeferredAsset(module, maximumBytes) {
  const deferred = manifest[module];
  if (deferred?.isDynamicEntry !== true) fail(`approved deferred module is missing: ${module}`);
  const bytes = statSync(resolve(dist, deferred.file)).size;
  if (bytes > maximumBytes) fail(`approved deferred module exceeds ${maximumBytes} bytes: ${module}`);
}

function verifyDeferredBoundary(parentModule, deferredModule, maximumParentBytes) {
  const parent = manifest[parentModule];
  const deferred = manifest[deferredModule];
  if (!parent || !deferred) fail(`deferred module boundary is missing: ${parentModule} -> ${deferredModule}`);
  if (!(parent.dynamicImports ?? []).includes(deferredModule)) {
    fail(`${parentModule} must defer ${deferredModule}`);
  }
  if (deferred.isDynamicEntry !== true) fail(`${deferredModule} is not emitted as a dynamic entry`);
  const parentBytes = statSync(resolve(dist, parent.file)).size;
  if (parentBytes > maximumParentBytes) {
    fail(`${parentModule} cold-path chunk exceeds ${maximumParentBytes} bytes`);
  }
}

function collectStaticClosure(entryModule) {
  const modules = new Set();
  const visit = (module) => {
    if (modules.has(module)) return;
    const chunk = manifest[module];
    if (!chunk) fail(`static import references a missing manifest module: ${module}`);
    modules.add(module);
    for (const imported of chunk.imports ?? []) visit(imported);
  };
  visit(entryModule);
  return modules;
}

function summarizeAssets(files) {
  let bytes = 0;
  let gzipBytes = 0;
  for (const file of files) {
    const body = readFileSync(resolve(dist, file));
    bytes += body.byteLength;
    gzipBytes += gzipSync(body).byteLength;
  }
  return { bytes, gzip_bytes: gzipBytes };
}

function verifyInitialLoad(workbench, script) {
  const [entryModule] = findChunkRecord(script);
  const modules = collectStaticClosure(entryModule);
  const forbidden = [...modules].filter((module) =>
    forbiddenInitialModuleFragments.some((fragment) => module.includes(fragment)),
  );
  if (forbidden.length > 0)
    fail(`${workbench} initial load includes deferred professional modules: ${forbidden.join(", ")}`);

  const javascriptFiles = new Set([...modules].map((module) => manifest[module].file));
  const cssFiles = new Set([...modules].flatMap((module) => manifest[module].css ?? []));
  const javascript = summarizeAssets(javascriptFiles);
  const css = summarizeAssets(cssFiles);
  const budget = initialLoadBudgets[workbench];
  if (javascript.bytes > budget.javascriptBytes)
    fail(`${workbench} initial JavaScript exceeds ${budget.javascriptBytes} bytes`);
  if (javascript.gzip_bytes > budget.javascriptGzipBytes)
    fail(`${workbench} initial gzip JavaScript exceeds ${budget.javascriptGzipBytes} bytes`);
  if (css.bytes > budget.cssBytes) fail(`${workbench} initial CSS exceeds ${budget.cssBytes} bytes`);
  if (css.gzip_bytes > budget.cssGzipBytes) fail(`${workbench} initial gzip CSS exceeds ${budget.cssGzipBytes} bytes`);
  return {
    javascript: { ...javascript, files: javascriptFiles.size },
    css: { ...css, files: cssFiles.size },
  };
}

const index = readEntry("index.html", "research");
const research = readEntry("research.html", "research");
const internal = readEntry("internal.html", "internal");
if (index.script !== research.script) fail("root and research aliases must load the same research application");
if (research.script === internal.script) fail("research and internal workbenches share an application entry chunk");
if (research.sha256 === internal.sha256) fail("research and internal HTML documents are identical");

verifyViews("research", findChunk(research.script));
verifyViews("internal", findChunk(internal.script));
verifyDeferredAsset(approvedDeferredEntryModules.research[0], 16 * 1024);
verifyDeferredBoundary("src/views/EpidemiologyView.tsx", "src/components/TrendLineChart.tsx", 64 * 1024);
verifyDeferredBoundary("src/views/ChemistryView.tsx", "src/components/StructureEditor.tsx", 64 * 1024);
const researchInitialLoad = verifyInitialLoad("research", research.script);
const internalInitialLoad = verifyInitialLoad("internal", internal.script);

process.stdout.write(
  `${JSON.stringify({
    status: "passed",
    schema: "pharma.workbench-build-boundary.v1",
    entries: {
      research: {
        script: research.script,
        document_sha256: research.sha256,
        views: expectedViews.research.length,
        initial_load: researchInitialLoad,
      },
      internal: {
        script: internal.script,
        document_sha256: internal.sha256,
        views: expectedViews.internal.length,
        initial_load: internalInitialLoad,
      },
    },
  })}\n`,
);
