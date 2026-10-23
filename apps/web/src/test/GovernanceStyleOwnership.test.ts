import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

function read(path: string) {
  return readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
}
it("loads review layouts and their responsive authority only in the governance owner", () => {
  expect(read("../views/GovernanceView.tsx")).toContain('import "../styles/governance.css";');
  expect(read("../styles.css")).not.toContain("styles/governance.css");
  expect(read("../styles/chemistry.css")).not.toContain(".governance-layout");
  expect(read("../styles/chemistry.css")).not.toContain(".identity-scope-toolbar");
  expect(read("../styles/governance.css")).toContain("@media (max-width: 760px)");
  expect(read("../styles/governance.css")).not.toContain(".payload-comparison");
});
