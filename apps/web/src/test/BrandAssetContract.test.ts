import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

function webFile(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)));
}

describe("maintainer-supplied X-Pharma brand", () => {
  it("preserves the original provided PNG exactly", () => {
    const original = webFile("../../brand/X-Pharma.png");
    expect(createHash("sha256").update(original).digest("hex")).toBe(
      "1099f1a295921cc9e229995cd84aced5a2e1022e223bf6140f65d585f7b7d591",
    );
  });

  it.each(["index.html", "research.html", "internal.html"])("uses the same icons in %s", (entry) => {
    const html = webFile(`../../${entry}`).toString("utf8");
    const document = new DOMParser().parseFromString(html, "text/html");
    expect(document.title).toMatch(/^X-Pharma(?: Operations)?$/);
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content")).toBe("#faf9f5");
    const links = Array.from(document.querySelectorAll('link[rel="icon"], link[rel="apple-touch-icon"]'));
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/src/assets/brand/X-Pharma-favicon-32.png",
      "/src/assets/brand/X-Pharma-favicon-16.png",
      "/src/assets/brand/X-Pharma-favicon.ico",
      "/src/assets/brand/X-Pharma-apple-touch-180.png",
    ]);
    expect(links.map((link) => link.getAttribute("sizes"))).toEqual([
      "32x32",
      "16x16",
      "16x16 32x32 48x48 64x64",
      "180x180",
    ]);
  });
});
