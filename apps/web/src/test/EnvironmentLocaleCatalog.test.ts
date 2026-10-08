import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { environmentMessages, environmentSourceMessages, environmentSourceText } from "../lib/i18n/environment";
import { environmentInstallationMessages } from "../lib/i18n/environmentInstallation";
import { environmentOperationsMessages } from "../lib/i18n/environmentOperations";

it("pairs all environment message parameters without introducing another locale owner", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const catalog of [
    environmentMessages,
    environmentSourceMessages,
    environmentInstallationMessages,
    environmentOperationsMessages,
  ]) {
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(english), key).toEqual(parameters(key));
    }
  }
});

it("translates only complete fixed environment boilerplate and keeps original diagnostics and paths", () => {
  setLocale("en");
  expect(environmentSourceText("前端依赖")).toBe("Frontend dependencies");
  const raw = "私有诊断 /srv/wsl/example — 原始原因、许可证与版本 3.13.14";
  expect(environmentSourceText(raw)).toBe(raw);
  expect(environmentSourceText("前端依赖; additional required diagnostic credit")).toBe(
    "前端依赖; additional required diagnostic credit",
  );
  expect(environmentSourceText("constructor")).toBe("constructor");
  setLocale("zh-CN");
  expect(environmentSourceText("前端依赖")).toBe("前端依赖");
});
