import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

function source(relativePath: string) {
  const url = new URL(relativePath, import.meta.url);
  // Include the real on-demand domain sheet in design checks, without making it initial payload.
  if (relativePath === "../styles.css") {
    const domainPath = "../styles/knowledge.css";
    return `${stylesheetSource(url)}\n${stylesheetSource(new URL(domainPath, import.meta.url))}`;
  }
  return url.pathname.endsWith(".css") ? stylesheetSource(url) : readFileSync(fileURLToPath(url), "utf8");
}

it("keeps target primary filters bounded and readable instead of a fixed three-column minimum", () => {
  const layout = source("../styles.css");
  const filters = ruleBody(layout, ".target-evidence-filters");
  expect(filters).toContain("min-width: 0;");
  expect(filters).toContain("repeat(auto-fit, minmax(min(100%, 150px), 1fr))");
  expect(ruleBody(layout, ".target-evidence-filters select")).toContain("min-height: var(--ds-control-height);");
});

it("bounds knowledge coverage and version tracks while their tables and history remain scrollable", () => {
  const layout = source("../styles/knowledge.css");
  expect(ruleBody(layout, ".knowledge-governance")).toContain("grid-template-columns: minmax(0, 1fr);");
  expect(ruleBody(layout, ".knowledge-version-list")).toContain("overflow-y: auto;");
  expect(layout).toMatch(/\.knowledge-version-list\s*\{[^}]*overflow-x:\s*auto;/);
});

function stylesheetSource(url: URL, parents = new Set<string>()): string {
  if (parents.has(url.href)) throw new Error(`Circular stylesheet import: ${url.href}`);
  const ancestry = new Set(parents).add(url.href);
  return readFileSync(fileURLToPath(url), "utf8").replace(/@import\s+"([^"]+)";/g, (_match, path: string) =>
    stylesheetSource(new URL(path, url), ancestry),
  );
}

function tokenHex(css: string, token: string) {
  const value = css.match(new RegExp(`${token}\\s*:\\s*(#[0-9a-f]{6})`, "i"))?.[1];
  if (!value) throw new Error(`Missing color token ${token}`);
  return value;
}

function luminance(hex: string) {
  const channels = [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255);
  const linear = channels.map((channel) => (channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(foreground: string, background: string) {
  const light = Math.max(luminance(foreground), luminance(background));
  const dark = Math.min(luminance(foreground), luminance(background));
  return (light + 0.05) / (dark + 0.05);
}

function hardcodedPaletteLeaks(css: string) {
  return [...new Set([...css.matchAll(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d[^)]*\)/gi)].map((match) => match[0]))];
}

function selectorsWithPixelFontSizeBelow(css: string, minimum: number) {
  const selectors = new Set<string>();
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/gs)) {
    const size = match[2].match(/font-size:\s*(\d+)px\s*;/)?.[1];
    if (!size || Number(size) >= minimum) continue;

    for (const selector of match[1].split(",")) {
      const normalized = selector.trim().replace(/\s+/g, " ");
      if (normalized && !normalized.startsWith("@")) selectors.add(normalized);
    }
  }
  return [...selectors].sort();
}

function ruleBody(css: string, selector: string) {
  const normalizedTarget = selector.replace(/\s+/g, " ").trim();
  let groupedBody: string | undefined;
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/gs)) {
    const normalizedSelectors = (match[1] ?? "")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\s+/g, " ")
      .trim();
    const selectors = normalizedSelectors.split(",").map((item) => item.trim());
    if (normalizedSelectors === normalizedTarget) return match[2] ?? "";
    if (selectors.length === 1 && selectors[0] === normalizedTarget) return match[2] ?? "";
    if (selectors.includes(normalizedTarget) && groupedBody === undefined) groupedBody = match[2] ?? "";
  }
  if (groupedBody !== undefined) return groupedBody;
  throw new Error(`Missing design-system rule for ${selector}`);
}

function declarationBodyCount(css: string, declarations: string[]) {
  const expected = [...declarations].sort().join(";");
  return [...css.matchAll(/[^{}]+\{([^{}]*)\}/gs)].filter((match) => {
    const normalized = (match[1] ?? "")
      .split(";")
      .map((declaration) => declaration.trim())
      .filter(Boolean)
      .sort()
      .join(";");
    return normalized === expected;
  }).length;
}

function ruleContainingSelectors(css: string, selectors: string[]) {
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/gs)) {
    const normalizedSelectors = (match[1] ?? "").replace(/\s+/g, " ").trim();
    if (selectors.every((selector) => normalizedSelectors.includes(selector))) {
      return { body: match[2] ?? "", selectors: normalizedSelectors };
    }
  }
  throw new Error(`Missing design-system rule containing ${selectors.join(", ")}`);
}

function workspaceWhereRule(css: string, selector: string) {
  for (const match of css.matchAll(/:root\s+\.workspace-shell\s+:where\(([\s\S]*?)\)\s*\{([^}]*)\}/g)) {
    const selectors = match[1] ?? "";
    if (selectors.includes(selector)) return { body: match[2] ?? "", selectors };
  }
  throw new Error(`Missing workspace :where() rule containing ${selector}`);
}

describe("unified minimal biomedical light design system", () => {
  it("uses the AI visual target's restrained scientific accent without changing brand or table density", () => {
    const designSystem = source("../design-system.css");
    const palette = source("../components/chartPalette.ts");
    const layout = source("../styles.css");
    expect(designSystem).toContain("--ds-accent: #407f82;");
    expect(designSystem).toContain("--ds-accent-strong: #08656d;");
    expect(designSystem).toContain("--ds-accent-soft: #e8f4f3;");
    expect(designSystem).toContain("--ds-nav-active: #e6f2f2;");
    expect(ruleBody(designSystem, ".nav-button.active")).toContain("color: var(--ds-accent-strong);");
    expect(palette).toContain('primary: "#407f82"');
    expect(palette).toContain('primaryEmphasis: "#08656d"');
    expect(ruleBody(layout, ".page-heading h1")).toContain("font-size: 32px;");
    expect(ruleBody(layout, ".workspace-shell")).toContain("--sidebar-width: 224px;");
    expect(designSystem).toContain("--ds-action: #0d0d0d;");
    expect(designSystem).toContain("--ds-shadow-sm: none;");
    expect(ruleBody(layout, ".table-density-control button")).toContain("min-height: 27px;");
  });
  it("wraps full entity identifiers without hiding or clipping mobile dossier content", () => {
    const layout = source("../styles.css");
    const identity = ruleBody(layout, ".target-title-row > div > div:last-child");
    expect(identity).toContain("min-width: 0;");
    expect(identity).toContain("overflow-wrap: anywhere;");
    expect(identity).not.toContain("overflow: hidden");
    expect(ruleBody(layout, ".target-symbol")).toContain("flex-shrink: 0;");
    for (const selector of [
      ".drug-profile-identity",
      ".company-profile-identity",
      ".entity-dossier-title > div:last-child",
    ]) {
      const body = ruleBody(layout, selector);
      expect(body).toContain("min-width: 0;");
      expect(body).toContain("overflow-wrap: anywhere;");
      expect(body).not.toContain("overflow: hidden");
    }
  });
  it("lets composed candidate controls own a single input border", () => {
    const layout = source("../styles.css");
    expect(ruleBody(layout, ".professional-query-fields :where(input, select)")).toContain("width: 100%;");
    expect(ruleBody(layout, ".entity-filter-combobox input")).toContain("border: 0;");
    expect(layout).not.toMatch(/\.professional-query-fields input,\s*\.professional-query-fields select/);
  });

  it("uses white canvas, neutral navigation and one sans-serif hierarchy in both entrances", () => {
    const designSystem = source("../design-system.css");
    const baseStyles = source("../styles.css");
    const mount = source("../mount.tsx");
    const publicEntry = source("../research-main.tsx");
    const internalEntry = source("../internal-main.tsx");
    const combinedStyles = `${designSystem}\n${baseStyles}`;

    expect(designSystem).toContain("--ds-canvas: #ffffff;");
    expect(designSystem).toContain("--ds-nav: #f9f9f9;");
    expect(designSystem).toContain("--ds-ink-strong: #0d0d0d;");
    expect(designSystem).toContain("--ds-accent: #407f82;");
    expect(designSystem).toContain("--ds-accent-strong: #08656d;");
    expect(designSystem).toContain("--ds-action: #0d0d0d;");
    expect(designSystem).toContain("--ds-font-display: var(--ds-font-sans);");
    expect(designSystem).not.toMatch(/Georgia|Noto Serif|Songti SC|SimSun|#faf9f5|#f0eee6/i);
    expect(mount).toContain('import "./design-system.css";');
    expect(mount.indexOf('import "./styles.css";')).toBeLessThan(mount.indexOf('import "./design-system.css";'));
    expect(publicEntry).toContain("mountApplication");
    expect(internalEntry).toContain("mountApplication");
    expect(combinedStyles).not.toMatch(/#15262f|#22343d|#356b80|#a6c9d6|#f4f8fa|#dcecf2/i);
    expect(hardcodedPaletteLeaks(baseStyles)).toEqual([]);
    expect(combinedStyles).not.toMatch(
      /font-family:\s*(?:"Segoe UI"|"Cascadia Mono"|Georgia|ui-monospace|"SFMono-Regular")/i,
    );
    expect(combinedStyles).not.toContain("--font-mono");
    expect(combinedStyles).not.toContain("var(--font-mono)");
    expect(combinedStyles).not.toContain("!important");

    const componentRules = designSystem.slice(designSystem.indexOf("html,"));
    expect(componentRules).not.toMatch(/#[0-9a-f]{3,8}\b/i);
    expect(componentRules).not.toMatch(/(?:^|\n)\s*color:\s*var\(--ds-accent\)/i);
    expect(componentRules).not.toMatch(/border-radius:\s*(?:6|8)px/);

    const defined = new Set([...designSystem.matchAll(/(--ds-[a-z0-9-]+)\s*:/g)].map((match) => match[1]));
    const used = new Set([...combinedStyles.matchAll(/var\((--ds-[a-z0-9-]+)/g)].map((match) => match[1]));
    expect([...used].filter((token) => !defined.has(token))).toEqual([]);
  });

  it("uses a shared scientific chart accent without per-chart color overrides", () => {
    const palette = source("../components/chartPalette.ts");
    const chartSources = [
      source("../components/ClinicalTrialLandscape.tsx"),
      source("../components/LandscapeBarChart.tsx"),
      source("../components/TrendLineChart.tsx"),
    ].join("\n");

    expect(palette).not.toMatch(/#356b80|#0284c7|#a7d0d9/i);
    expect(palette).toContain("#407f82");
    expect(palette).not.toMatch(/#d97757|#9c4a2b/i);
    expect(chartSources).toContain("chartPalette");
    expect(chartSources).not.toMatch(/#[0-9a-f]{6}\b|rgba\(/i);
  });

  it("keeps text and semantic status tokens readable", () => {
    const designSystem = source("../design-system.css");
    const pairs = [
      ["--ds-ink", "--ds-surface"],
      ["--ds-ink-strong", "--ds-surface"],
      ["--ds-ink-muted", "--ds-surface"],
      ["--ds-ink-faint", "--ds-surface"],
      ["--ds-accent-strong", "--ds-surface"],
      ["--ds-ink", "--ds-accent-soft"],
      ["--ds-ink-strong", "--ds-accent-soft"],
      ["--ds-nav-muted", "--ds-nav"],
      ["--ds-nav-muted", "--ds-nav-active"],
      ["--ds-success", "--ds-success-soft"],
      ["--ds-warning", "--ds-warning-soft"],
      ["--ds-danger", "--ds-danger-soft"],
      ["--ds-action-text", "--ds-action"],
      ["--ds-action-text", "--ds-action-hover"],
      ["--ds-accent-strong", "--ds-accent-soft"],
      ["--ds-nav-text", "--ds-nav-hover"],
      ["--ds-ink-muted", "--ds-surface-muted"],
      ["--ds-info", "--ds-info-soft"],
      ["--ds-nav-text", "--ds-nav-active"],
      ["--ds-accent-strong", "--ds-nav-active"],
      ["--ds-ink-strong", "--ds-canvas"],
    ] as const;

    for (const [foregroundToken, backgroundToken] of pairs) {
      const ratio = contrast(tokenHex(designSystem, foregroundToken), tokenHex(designSystem, backgroundToken));
      expect(ratio, `${foregroundToken} on ${backgroundToken}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps both login entrances on the same neutral light surface", () => {
    const designSystem = source("../design-system.css");

    expect(designSystem).toMatch(/\.workspace-sidebar\s*\{[^}]*background: var\(--ds-nav\);/s);
    expect(ruleBody(designSystem, ".login-brand")).toContain("background: var(--ds-canvas);");
    expect(ruleContainingSelectors(designSystem, [".login-brand", ".enterprise-workbench"]).body).toContain(
      "color: var(--ds-ink);",
    );
    expect(ruleContainingSelectors(designSystem, [".brand-lockup", ".login-title h1"]).body).toContain(
      "color: var(--ds-ink-strong);",
    );
    expect(ruleBody(designSystem, ".workspace-sidebar .brand-lockup")).toContain("color: var(--ds-ink-strong);");
    expect(ruleContainingSelectors(designSystem, [".login-title .eyebrow", ".login-form > svg"]).body).toContain(
      "color: var(--ds-accent-strong);",
    );
    expect(ruleContainingSelectors(designSystem, [".login-title h1", ".virtual-table-cell > strong"]).body).toContain(
      "color: var(--ds-ink-strong);",
    );
    expect(ruleContainingSelectors(designSystem, [".login-title > p:last-child", ".login-brand"]).body).toContain(
      "color: var(--ds-ink);",
    );
    expect(ruleBody(designSystem, ".brand-lockup small,\n.login-version")).toContain("color: var(--ds-ink);");
  });

  it("keeps compact public-workspace labels readable", () => {
    const designSystem = source("../design-system.css");
    const compactLabels = designSystem.match(/\.muted-text,\s*\.date-range-fieldset label span\s*\{([^}]*)\}/)?.[1];
    const entityMetadata = ruleBody(designSystem, ".entity-governance-line");

    expect(compactLabels).toContain("color: var(--ds-ink-muted);");
    expect(compactLabels).toContain("font-size: 12px;");
    expect(entityMetadata).toContain("color: var(--ds-ink-muted);");
    expect(entityMetadata).toContain("font-size: var(--ds-text-xs);");
    expect(entityMetadata).toContain("line-height: var(--ds-leading-compact);");
  });

  it("keeps public and internal workspace microcopy at a readable minimum", () => {
    const designSystem = source("../design-system.css");
    const baseStyles = source("../styles.css");
    const microcopyRule = ruleContainingSelectors(designSystem, [
      ":root .workspace-shell",
      ".brand-lockup small",
      ".regulatory-source-reference",
      "button",
      "label",
      "legend",
      "small",
      "span",
    ]);
    const shellHierarchyRule = ruleBody(designSystem, ".sidebar-account-copy strong");
    const shellContextRule = ruleContainingSelectors(designSystem, [
      ".user-copy small",
      ".section-header p",
      ".eyebrow",
      ".result-summary",
      ".cell-subtitle",
      ".table-secondary",
    ]);
    const loginMicrocopyRule = designSystem.match(/\.brand-lockup small,\s*\.login-version\s*\{([^}]*)\}/);

    expect(designSystem).toContain("--ds-text-xs: 12px;");
    expect(designSystem).toContain("--ds-text-sm: 14px;");
    expect(designSystem).toContain("--ds-text-md: 16px;");
    expect(designSystem).toContain("--ds-leading-compact: 1.4;");
    expect(designSystem).toContain("--ds-leading-body: 1.5;");
    expect(ruleBody(designSystem, "body")).toContain("font-size: var(--ds-text-md);");
    expect(designSystem).not.toContain(".workspace-identity");
    expect(loginMicrocopyRule).not.toBeNull();
    expect(loginMicrocopyRule?.[1]).toContain("font-size: var(--ds-text-xs);");
    expect(loginMicrocopyRule?.[1]).toContain("line-height: var(--ds-leading-compact);");
    expect(shellHierarchyRule).toContain("font-size: var(--ds-text-sm);");
    expect(shellHierarchyRule).toContain("line-height: var(--ds-leading-compact);");
    expect(shellContextRule.body).toContain("font-size: var(--ds-text-xs);");
    expect(shellContextRule.body).toContain("line-height: var(--ds-leading-compact);");
    expect(microcopyRule.body).toContain("font-size: var(--ds-text-xs);");
    expect(microcopyRule.body).toContain("line-height: var(--ds-leading-compact);");

    const coveredSelectors = microcopyRule.selectors;
    const uncoveredSelectors = selectorsWithPixelFontSizeBelow(baseStyles, 10).filter(
      (selector) => !coveredSelectors.includes(selector),
    );
    expect(uncoveredSelectors).toEqual([]);
  });

  it("keeps repeated result-toolbar controls readable without loosening table rows", () => {
    const designSystem = source("../design-system.css");
    const baseStyles = source("../styles.css");
    const toolbarTypography = ruleContainingSelectors(designSystem, [
      ":root .workspace-shell",
      ".virtual-table-toolbar",
      ".domain-export-menu",
      ".table-column-menu",
      ".table-sort-menu",
      ":where(",
      "button",
      "summary",
      "label",
      "legend",
      "small",
      "span",
      "strong",
      ".table-sort-editor-heading",
      ".table-selection-status",
      ".table-preference-error",
    ]);

    expect(toolbarTypography.body).toContain("font-size: var(--ds-text-xs);");
    expect(toolbarTypography.body).toContain("line-height: var(--ds-leading-compact);");
    expect(ruleBody(baseStyles, ".table-result-action")).toContain("font-size: 10px;");
    expect(ruleBody(baseStyles, ".table-density-control button")).toContain("min-height: 27px;");
  });

  it("keeps public query controls readable across data domains", () => {
    const designSystem = source("../design-system.css");
    const baseStyles = source("../styles.css");
    const queryTypography = ruleContainingSelectors(designSystem, [
      ":root .workspace-shell",
      ".professional-query-builder",
      ".domain-filter-bar",
      "input",
      "summary",
    ]);
    const compactQueryModes = ruleContainingSelectors(designSystem, [
      ".segmented-control button",
      ".advanced-filter-panel > summary",
    ]);

    expect(queryTypography.body).toContain("font-size: var(--ds-text-sm);");
    expect(queryTypography.body).toContain("line-height: var(--ds-leading-body);");
    expect(compactQueryModes.body).toContain("font-size: var(--ds-text-xs);");
    expect(compactQueryModes.body).toContain("line-height: var(--ds-leading-compact);");
    expect(ruleBody(baseStyles, ".professional-query-builder > nav button")).toContain("font-size: var(--ds-text-xs);");
    expect(ruleBody(baseStyles, ".entity-search-candidate-heading strong")).toContain("font-size: var(--ds-text-xs);");
    expect(ruleBody(baseStyles, ".professional-more-fields > summary")).toContain("font-size: var(--ds-text-xs);");
    expect(ruleBody(baseStyles, ".segmented-control button")).not.toContain("font-size: 10px;");
    expect(ruleBody(baseStyles, ".advanced-filter-panel > summary")).not.toContain("font-size: 11px;");
  });

  it("keeps professional dossier prose readable without loosening dense data tools", () => {
    const designSystem = source("../design-system.css");
    const baseStyles = source("../styles.css");
    const metadata = ruleContainingSelectors(designSystem, [":root .workspace-shell", ".regulatory-source-reference"]);
    const prose = workspaceWhereRule(designSystem, ".trial-detail-note");

    for (const selector of [
      ".dossier-metrics dt",
      ".trial-detail-status",
      ".trial-disclosure-list article > :is(small, span)",
      ".trial-analysis-list p",
      ".deal-detail-list :is(span, small)",
      ".deal-rights-table :is(th, td)",
      ".regulatory-source-reference",
    ]) {
      expect(metadata.selectors, selector).toContain(selector);
    }
    expect(metadata.body).toContain("font-size: var(--ds-text-xs);");
    expect(metadata.body).toContain("line-height: var(--ds-leading-compact);");

    for (const selector of [
      ".trial-detail-grid dd",
      ".trial-disclosure-list article > :is(strong, p)",
      ":is(.trial-detail-note, .trial-eligibility-criteria, .trial-outcome-list > section > p)",
      ".deal-detail-list strong",
    ]) {
      expect(prose.selectors, selector).toContain(selector);
    }
    expect(prose.body).toContain("font-size: var(--ds-text-sm);");
    expect(prose.body).toContain("line-height: var(--ds-leading-body);");
    expect(ruleBody(baseStyles, ".table-density-control button")).toContain("min-height: 27px;");
  });

  it("keeps shared panel and selection treatments single-sourced for bundle headroom", () => {
    const designSystem = source("../design-system.css");
    const sharedPanels = ruleContainingSelectors(designSystem, [
      ".table-frame",
      ".governance-layout",
      ".collections-layout",
      ".trial-professional-page",
      ".patent-professional-page",
      ".deal-professional-page",
      ".professional-query-builder",
      ".intelligence-query-panel",
      ".advanced-filter-panel",
      ".domain-filter-bar",
      ".pipeline-filter-bar",
      ".trial-filter-bar",
      ".patent-filter-bar",
      ".deal-filter-bar",
      ".regulatory-filter-bar",
      ".epidemiology-filter-bar",
      ".news-display-control",
      ".pipeline-landscape",
      ".trial-landscape",
      ".epidemiology-trend-panel",
      ".user-center-identity-card",
      ".user-center-panel",
      ".user-center-account-actions",
    ]);

    expect(sharedPanels.body).toContain("border-color: var(--ds-border);");
    expect(sharedPanels.body).toContain("border-radius: var(--ds-radius-panel);");
    expect(sharedPanels.body).toContain("background: var(--ds-surface);");
    expect(sharedPanels.body).toContain("box-shadow: var(--ds-shadow-sm);");

    expect(
      declarationBodyCount(designSystem, [
        "background: var(--ds-surface)",
        "border-color: var(--ds-border)",
        "border-radius: var(--ds-radius-panel)",
        "box-shadow: var(--ds-shadow-sm)",
      ]),
    ).toBe(1);
    expect(
      declarationBodyCount(designSystem, ["background: var(--ds-accent-soft)", "color: var(--ds-accent-strong)"]),
    ).toBe(1);
    expect(declarationBodyCount(designSystem, ["border-radius: var(--ds-radius-control)", "min-height: 48px"])).toBe(1);
    expect(declarationBodyCount(designSystem, ["color: var(--ds-ink-muted)", "font-size: 12px"])).toBe(1);
  });

  it("keeps shared controls on one compact geometry rhythm", () => {
    const designSystem = source("../design-system.css");

    for (const token of [
      "--ds-radius-control: 10px;",
      "--ds-radius-panel: 12px;",
      "--ds-control-height: 44px;",
      "--ds-button-height: 40px;",
      "--ds-icon-control-size: 36px;",
    ]) {
      expect(designSystem).toContain(token);
    }

    const formControl = ruleBody(designSystem, ":root textarea");
    expect(formControl).toContain("min-height: var(--ds-control-height);");
    expect(formControl).toContain("border-radius: var(--ds-radius-control);");

    const primaryButton = ruleBody(designSystem, ".primary-button");
    expect(primaryButton).toContain("min-height: var(--ds-button-height);");

    const iconButton = ruleBody(designSystem, ".icon-button");
    expect(iconButton).toContain("width: var(--ds-icon-control-size);");
    expect(iconButton).toContain("height: var(--ds-icon-control-size);");

    const shellNavigation = designSystem.match(/\.nav-button,\s*\.collapse-button\s*\{([^}]*)\}/)?.[1];
    expect(shellNavigation).toContain("min-height: 48px;");
    expect(shellNavigation).toContain("border-radius: var(--ds-radius-control);");

    const baseStyles = source("../styles.css");
    const entityFilterControls = ruleContainingSelectors(baseStyles, [
      ".entity-filter-combobox",
      ".entity-filter-selection",
    ]);
    expect(entityFilterControls.body).toContain("border-radius: var(--ds-radius-control);");
  });

  it("keeps long dossier tab rails compact and tokenized", () => {
    const designSystem = source("../design-system.css");

    const tabRail = ruleBody(designSystem, ".tab-bar");
    expect(tabRail).toContain("border-bottom-color: var(--ds-border);");
    expect(tabRail).toContain("scrollbar-color: var(--ds-border-strong) transparent;");
    expect(tabRail).toContain("scrollbar-width: thin;");

    expect(ruleBody(designSystem, ".tab-bar::-webkit-scrollbar")).toContain("height: 6px;");
    expect(ruleBody(designSystem, ".tab-bar::-webkit-scrollbar-thumb")).toContain(
      "background: var(--ds-border-strong);",
    );
    expect(ruleBody(designSystem, ".tab-bar button")).toContain("color: var(--ds-ink-muted);");
    expect(ruleBody(designSystem, ".tab-bar button.active")).toContain("color: var(--ds-accent-strong);");
  });

  it("keeps high-density table scroll containers compact without removing overflow", () => {
    const designSystem = source("../design-system.css");
    const scrollContainers = ruleContainingSelectors(designSystem, [
      ".table-frame",
      ".virtual-table-viewport",
      ".entity-comparison-region",
    ]);

    expect(scrollContainers.body).toContain("scrollbar-color: var(--ds-border-strong) transparent;");
    expect(scrollContainers.body).toContain("scrollbar-width: thin;");

    const scrollbar = ruleContainingSelectors(designSystem, [
      ".table-frame::-webkit-scrollbar",
      ".virtual-table-viewport::-webkit-scrollbar",
      ".entity-comparison-region::-webkit-scrollbar",
    ]);
    expect(scrollbar.body).toContain("width: 8px;");
    expect(scrollbar.body).toContain("height: 6px;");
  });

  it("adapts the embedded structure editor to the biomedical control palette", () => {
    const designSystem = source("../design-system.css");
    const editorTopbar = ruleContainingSelectors(designSystem, ['.structure-editor-canvas [class*="App-module_top"]']);
    const editorTopbarButtons = ruleContainingSelectors(designSystem, [
      '.structure-editor-canvas [class*="App-module_top"] button[aria-label]',
    ]);
    const editorTools = ruleContainingSelectors(designSystem, [
      ".structure-editor-canvas",
      '[class*="ActionButton-module_button"]',
    ]);
    const selectedTool = ruleContainingSelectors(designSystem, [
      ".workspace-shell .structure-editor-canvas",
      '[class*="ActionButton-module_selected"]',
    ]);

    expect(editorTopbar.body).toContain("background: var(--ds-surface-muted);");
    expect(editorTopbar.body).toContain("border-bottom: 1px solid var(--ds-border);");
    expect(editorTopbar.body).toContain("box-shadow: none;");
    expect(editorTopbarButtons.body).toContain("color: var(--ds-ink-muted);");
    expect(editorTopbarButtons.body).toContain("border-radius: var(--ds-radius-control);");
    expect(editorTools.body).toContain("border: 1px solid var(--ds-border);");
    expect(editorTools.body).toContain("background: var(--ds-surface);");
    expect(editorTools.body).toContain("color: var(--ds-ink-muted);");
    expect(selectedTool.body).toContain("background: var(--ds-accent-soft);");
    expect(selectedTool.body).toContain("color: var(--ds-accent-strong);");
  });

  it("gives shared state recovery actions a clear quiet hierarchy", () => {
    const designSystem = source("../design-system.css");
    const message = ruleBody(designSystem, ".state-message");
    const detail = ruleBody(designSystem, ".state-message > span:not(.spinner)");
    const action = ruleBody(designSystem, ".state-message .text-button");
    const secondaryAction = ruleBody(designSystem, ".state-message .text-button + .text-button");

    expect(message).toContain("color: var(--ds-ink-muted);");
    expect(detail).toContain("max-width: 520px;");
    expect(detail).toContain("line-height: var(--ds-leading-body);");
    expect(action).toContain("min-height: var(--ds-button-height);");
    expect(action).toContain("border: 1px solid var(--ds-border-strong);");
    expect(action).toContain("border-radius: var(--ds-radius-control);");
    expect(action).toContain("background: var(--ds-surface);");
    expect(action).toContain("box-shadow: var(--ds-shadow-sm);");
    expect(secondaryAction).toContain("min-height: auto;");
    expect(secondaryAction).toContain("border-color: transparent;");
    expect(secondaryAction).toContain("box-shadow: none;");
  });

  it("preserves separate pointer targets for structure operations and their split menus", () => {
    const designSystem = source("../design-system.css");
    expect(
      ruleBody(
        designSystem,
        '.structure-editor-canvas [class*="App-module_top"] div:has(> .MuiIconButton-root.expanded)',
      ),
    ).toContain("min-width: 52px;");
    expect(
      ruleBody(designSystem, '.structure-editor-canvas [class*="App-module_top"] .MuiIconButton-root.expanded'),
    ).toContain("position: static;");
  });

  it("keeps governed facet loading states readable and theme-aligned", () => {
    const designSystem = source("../design-system.css");
    const placeholder = ruleBody(designSystem, ".professional-facet-placeholder");
    const label = ruleBody(designSystem, ".professional-facet-placeholder > span");
    const state = ruleBody(designSystem, ".professional-facet-placeholder small");

    expect(placeholder).toContain("border-color: var(--ds-border);");
    expect(placeholder).toContain("background: var(--ds-surface-muted);");
    expect(placeholder).toContain("color: var(--ds-ink-muted);");
    expect(label).toContain("color: var(--ds-ink-strong);");
    expect(label).toContain("font-size: 12px;");
    expect(state).toContain("font-size: 12px;");
    expect(
      contrast(tokenHex(designSystem, "--ds-ink-muted"), tokenHex(designSystem, "--ds-surface-muted")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps internal metadata and dense table text at the readable minimum", () => {
    const designSystem = source("../design-system.css");
    const readableInternalMetadata = ruleContainingSelectors(designSystem, [
      ".internal-workbench main :is(button, input, label, p, select, nav)",
    ]);

    expect(readableInternalMetadata.body).toContain("font-size: var(--ds-text-sm);");
    expect(readableInternalMetadata.body).toContain("line-height: var(--ds-leading-body);");
    expect(designSystem).not.toContain("select, small, span, dl *, th, td, nav");
  });

  it("keeps public query controls and workbench toolbars readable", () => {
    const styles = `${source("../styles.css")}\n${source("../design-system.css")}`;
    for (const selector of [
      ".research-entry p",
      ".inline-filter-options button",
      ".result-summary",
      ".result-summary small",
      ".mode-control button",
      ".structure-input-tabs button",
      ".chemistry-more-options summary",
      ".enterprise-toolbar",
      ".commercial-toolbar",
      ".inline-alert",
      ".target-title-row p",
      ".coverage-grid span",
      ".coverage-grid small",
      ".landscape-grid article > span small",
      ".landscape-grid article p",
    ]) {
      const readableRules = [...styles.matchAll(/([^{}]+)\{([^{}]*)\}/gs)].filter(
        (match) => match[1].includes(selector) && /font-size:\s*(?:12px|var\(--ds-text-(?:xs|sm)\))/.test(match[2]),
      );
      expect(readableRules.length, `${selector} has readable shared typography`).toBeGreaterThan(0);
    }
  });

  it("keeps closed workspace disclosures from rendering their collapsed content", () => {
    const designSystem = source("../design-system.css");
    const body = ruleBody(designSystem, ".workspace-shell details:not([open]) > :not(summary)");

    expect(body).toContain("display: none;");
  });

  it("bounds the mobile knowledge scroller instead of letting content overflow a capped parent", () => {
    const responsive = source("../styles/knowledge.css");
    const listBounds = ruleBody(
      responsive.slice(responsive.indexOf("@media (max-width: 760px)")),
      ".knowledge-page-list",
    );
    const indexBorders = ruleBody(
      responsive.slice(responsive.indexOf("@media (max-width: 760px)")),
      ".knowledge-index",
    );
    const knowledge = source("../styles/knowledge.css");
    expect(listBounds).toContain("max-height: 300px;");
    expect(indexBorders).not.toContain("max-height:");
    expect(ruleBody(knowledge, ".knowledge-page-list")).toContain("overflow-y: auto;");
    expect(ruleBody(knowledge, ".knowledge-count")).not.toContain("font-size:");
    expect(ruleBody(knowledge, ".knowledge-count")).not.toContain("text-transform:");
  });

  it("matches the preview hierarchy without clipping dossier titles or shrinking data controls", () => {
    const layout = source("../styles.css");
    expect(layout).not.toContain(".research-workbench .page-heading h1");
    expect(ruleBody(layout, ".entity-record-list .table-link-button")).toContain("white-space: normal;");
    expect(ruleBody(layout, ".company-source-summary")).toContain("padding: 20px;");
    expect(ruleBody(layout, ".landscape-grid")).toContain("repeat(auto-fit,");
    expect(ruleBody(layout, ".landscape-grid")).toContain("min(100%, 250px)");
    expect(ruleBody(layout, ".dossier-metrics")).toContain("repeat(auto-fit,");
    expect(ruleBody(layout, ".virtual-table-cell")).toContain("font-size: var(--ds-text-sm);");
    expect(ruleBody(layout, ".density-compact .virtual-table-cell")).toContain("font-size: var(--ds-text-xs);");
    expect(ruleBody(layout, ".inline-filter-options")).toContain("flex-wrap: wrap;");
    expect(source("../styles/dossiers.css")).not.toContain(".status-badge");
    expect(ruleBody(layout, ".entity-record-list article > .badge")).toContain("grid-column: 2;");
  });
});
