import { expect, it } from "vitest";
import { parseWorkbenchLocation, researchReturnLocation, workspaceUrl } from "../lib/workspaceRouting";

const targetId = "550e8400-e29b-41d4-a716-446655440000";
const drugId = "660e8400-e29b-41d4-a716-446655440000";
const rootSearch = "/workspace/research?view=explorer&q=EGFR&type=target&review=verified&offset=100";

function openDossier(previous: string, view: "target" | "drug") {
  return workspaceUrl(
    parseWorkbenchLocation(
      "research",
      `?view=${view}&entity=${view === "target" ? targetId : drugId}&from=${encodeURIComponent(previous)}`,
    ),
  );
}

function returnChain(path: string) {
  const frames: string[] = [];
  let location = researchReturnLocation(new URL(path, "https://pharma.local").searchParams.get("from"));
  for (let index = 0; location && index < 8; index++) {
    frames.push(workspaceUrl({ ...location, returnTo: undefined }));
    location = researchReturnLocation(location.returnTo);
  }
  return frames;
}

it("keeps the original search, filters and page after repeated target/drug research", () => {
  let path = rootSearch;
  for (const view of ["target", "drug", "target", "drug"] as const) path = openDossier(path, view);
  const frames = returnChain(path);
  expect(frames).toHaveLength(3);
  expect(frames[0]).toContain("view=target");
  expect(frames[1]).toContain("view=drug");
  expect(frames.at(-1)).toBe(rootSearch);
});

it("keeps an original professional query without growing the context over many transitions", () => {
  const root = workspaceUrl(
    parseWorkbenchLocation(
      "research",
      `?view=pipeline&target_entity_id=${targetId}&phase=phase_2&sort=drug_name%3Aasc&sort=phase%3Adesc&offset=40`,
    ),
  );
  let path = root;
  for (let index = 0; index < 30; index++) {
    path = openDossier(path, index % 2 ? "drug" : "target");
    const frames = returnChain(path);
    expect(frames.length).toBeLessThanOrEqual(3);
    expect(frames.at(-1)).toBe(root);
    expect(path.length).toBeLessThan(4096);
  }
});

it("does not replace the origin with a malformed, cross-workbench or external nested destination", () => {
  for (const invalid of [
    "https://evil.example/workspace/research?view=explorer",
    "/workspace/internal?view=enterprise",
    "/workspace/research?view=target&entity=not-a-uuid",
  ]) {
    const valid = `/workspace/research?view=drug&entity=${drugId}&from=${encodeURIComponent(invalid)}`;
    const parsed = researchReturnLocation(valid);
    expect(parsed?.view).toBe("drug");
    expect(parsed?.returnTo).toBeUndefined();
  }
});

it("keeps the same input/output length boundary and rejects ambiguous or unsafe top-level frames", () => {
  for (const invalid of [
    `/workspace/research?view=explorer&q=${"x".repeat(4096)}`,
    "/workspace/research?view=explorer&view=target",
    `/workspace/research?view=drug&entity=${drugId}&from=a&from=b`,
    "/workspace/research?view=explorer#fragment",
    "/workspace/research?view=explorer\\bad",
    "/workspace/research?view=explorer&q=\u0000",
  ])
    expect(researchReturnLocation(invalid)).toBeNull();
});

it("rejects excessive decoding work instead of relabeling a truncated context as the origin", () => {
  let path = "/workspace/research?view=overview";
  for (let index = 0; index < 16; index++) path = `/workspace/research?view=overview&from=${encodeURIComponent(path)}`;
  expect(path.length).toBeLessThan(4096);
  expect(researchReturnLocation(path)).toBeNull();
});
