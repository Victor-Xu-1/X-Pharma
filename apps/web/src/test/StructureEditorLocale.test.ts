import { beforeEach, expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { applyStructureEditorAccessibility } from "../lib/structureEditorAccessibility";

beforeEach(() => setLocale("en"));
it("updates adapter-generated accessible names when a third-party toolbar reuses the same button for another action", () => {
  const root = document.createElement("div");
  root.innerHTML = '<button title="Aromatize (Alt+A)"><svg /></button>';
  setLocale("zh-CN");
  applyStructureEditorAccessibility(root);
  const button = root.querySelector("button");
  if (!button) throw Error("Toolbar button missing");
  button.setAttribute("title", "Dearomatize (Ctrl+Alt+A)");
  applyStructureEditorAccessibility(root);
  expect(button).toHaveAttribute("title", "去芳香化（Ctrl+Alt+A）");
  expect(button).toHaveAttribute("aria-label", "去芳香化（Ctrl+Alt+A）");
});
it("leaves the DOM untouched on an identical repeated adapter pass", () => {
  const root = document.createElement("div");
  root.innerHTML = '<button title="Aromatize (Alt+A)"><svg /></button><h2>Calculated Values</h2>';
  setLocale("zh-CN");
  applyStructureEditorAccessibility(root);
  const observer = new MutationObserver(() => {});
  observer.observe(root, { attributes: true, characterData: true, childList: true, subtree: true });
  applyStructureEditorAccessibility(root);
  expect(observer.takeRecords()).toHaveLength(0);
  observer.disconnect();
});
it("keeps known third-party toolbar and dialog captions English under the English interface", () => {
  const root = document.createElement("div");
  root.innerHTML =
    '<button title="Clear Canvas (Ctrl+Del)"><svg /></button><h2>Calculated Values</h2><button>Cancel</button>';
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("title", "Clear Canvas (Ctrl+Del)");
  expect(root.querySelector("button")).toHaveAttribute("aria-label", "Clear Canvas (Ctrl+Del)");
  expect(root.querySelector("h2")).toHaveTextContent("Calculated Values");
  expect(root.querySelectorAll("button")[1]).toHaveTextContent("Cancel");
});
it("switches the same mounted controls to Chinese and back without losing their original captions", () => {
  const root = document.createElement("div");
  root.innerHTML =
    '<button title="Aromatize (Alt+A)"><svg /></button><h2>Calculated Values</h2><input type="button" value="Close" />';
  setLocale("zh-CN");
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("title", "芳香化（Alt+A）");
  setLocale("en");
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("title", "Aromatize (Alt+A)");
  expect(root.querySelector("h2")).toHaveTextContent("Calculated Values");
  expect(root.querySelector<HTMLInputElement>("input")).toHaveValue("Close");
});
it("localizes only generated accessibility names while retaining explicit existing semantics", () => {
  const root = document.createElement("div");
  root.innerHTML =
    '<button><svg /></button><button aria-label="Original named action"><svg /></button><textarea></textarea>';
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("aria-label", "Structure editor tool 1");
  setLocale("zh-CN");
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("aria-label", "结构编辑器工具 1");
  expect(root.querySelectorAll("button")[1]).toHaveAttribute("aria-label", "Original named action");
  setLocale("en");
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("button")).toHaveAttribute("aria-label", "Structure editor tool 1");
  expect(root.querySelector("textarea")).toHaveAttribute("aria-label", "Structure editor text input");
});
it("does not translate chemical canvas annotations, editable source text or observed output values", () => {
  const root = document.createElement("div");
  root.innerHTML =
    '<svg><text>Cancel</text></svg><textarea>Apply</textarea><output>Exact Mass:</output><div contenteditable="true">Close</div><h2>Calculated Values</h2><label>Exact Mass:</label>';
  setLocale("zh-CN");
  applyStructureEditorAccessibility(root);
  expect(root.querySelector("text")).toHaveTextContent("Cancel");
  expect(root.querySelector("textarea")).toHaveValue("Apply");
  expect(root.querySelector("output")).toHaveTextContent("Exact Mass:");
  expect(root.querySelector("[contenteditable]")).toHaveTextContent("Close");
  expect(root.querySelector("h2")).toHaveTextContent("计算属性");
  expect(root.querySelector("label")).toHaveTextContent("精确质量：");
});
