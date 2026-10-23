import { expect, it } from "vitest";
import { domainExportCatalog } from "../lib/contracts/domainExports";
import { setLocale } from "../lib/i18n";
import { domainExportLabel, domainExportMessages } from "../lib/i18n/domainExport";

it("covers every canonical export dataset and field heading in both locales", () => {
  for (const catalog of Object.values(domainExportCatalog)) {
    for (const label of [catalog.label, ...catalog.fields.map((field) => field.label)]) {
      setLocale("zh-CN");
      expect(domainExportLabel(label)).toBe(label);
      setLocale("en");
      expect(domainExportLabel(label)).not.toMatch(/[\u3400-\u9fff]/u);
    }
  }
  expect(() => domainExportLabel("unregistered heading")).toThrow("Unknown export heading");
});

it("keeps export parameters identical across locales", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(domainExportMessages)) {
    expect(english.trim()).not.toBe("");
    expect(parameters(key)).toEqual(parameters(english));
  }
});
