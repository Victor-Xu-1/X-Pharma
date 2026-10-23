import { getLocale } from "./i18n/locale";
import { STRUCTURE_EDITOR_LABELS, STRUCTURE_EDITOR_TEXT_LABELS } from "./i18n/structureEditor";

type Caption = { raw: string; written: string };
const captions = new WeakMap<Node, Map<string, Caption>>();
const generatedButtons = new WeakMap<HTMLButtonElement, number>();
const generatedInputs = new WeakSet<HTMLTextAreaElement>();
const ariaFromTitle = new WeakSet<HTMLButtonElement>();
const titleFromAria = new WeakSet<HTMLButtonElement>();
const protectedContent = "svg,canvas,textarea,input,output,[contenteditable],[data-source-owned]";
function remember(node: Node, key: string, raw: string, written: string) {
  let fields = captions.get(node);
  if (!fields) {
    fields = new Map();
    captions.set(node, fields);
  }
  fields.set(key, { raw, written });
}
function translate(
  node: Node,
  key: string,
  current: string,
  labels: Record<string, string>,
  write: (value: string) => void,
) {
  const prior = captions.get(node)?.get(key);
  const raw = prior?.written === current ? prior.raw : current;
  const trimmed = raw.trim(),
    chinese = labels[trimmed];
  if (!chinese) {
    captions.get(node)?.delete(key);
    return false;
  }
  const value = getLocale() === "zh-CN" ? chinese : trimmed;
  const start = raw.indexOf(trimmed),
    next = raw.slice(0, start) + value + raw.slice(start + trimmed.length);
  remember(node, key, raw, next);
  if (next !== current) write(next);
  return true;
}
function setAttribute(element: HTMLElement, key: string, value: string) {
  if (element.getAttribute(key) !== value) element.setAttribute(key, value);
}
function localizeButton(button: HTMLButtonElement) {
  if (button.closest("svg,[contenteditable],[data-source-owned]")) return;
  const title = button.getAttribute("title") ?? "",
    aria = button.getAttribute("aria-label") ?? "";
  const derivedAria = ariaFromTitle.has(button) && captions.get(button)?.get("aria-label")?.written === aria;
  const derivedTitle = titleFromAria.has(button) && captions.get(button)?.get("title")?.written === title;
  if (!derivedAria) ariaFromTitle.delete(button);
  if (!derivedTitle) titleFromAria.delete(button);
  const titleKnown = translate(button, "title", title, STRUCTURE_EDITOR_LABELS, (value) =>
    setAttribute(button, "title", value),
  );
  const ariaKnown = translate(button, "aria-label", aria, STRUCTURE_EDITOR_LABELS, (value) =>
    setAttribute(button, "aria-label", value),
  );
  if ((derivedAria || (titleKnown && !aria.trim())) && !button.getAttribute("aria-labelledby")) {
    const source = captions.get(button)?.get("title") ?? (title.trim() ? { raw: title, written: button.title } : null);
    if (source) {
      ariaFromTitle.add(button);
      remember(button, "aria-label", source.raw, source.written);
      setAttribute(button, "aria-label", source.written);
    }
  }
  if (derivedTitle || (ariaKnown && !title.trim())) {
    const source =
      captions.get(button)?.get("aria-label") ??
      (aria.trim() ? { raw: aria, written: button.getAttribute("aria-label") ?? aria } : null);
    if (source) {
      titleFromAria.add(button);
      remember(button, "title", source.raw, source.written);
      setAttribute(button, "title", source.written);
    }
  }
}
function localizeDynamicText(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  let current = walker.nextNode();
  while (current) {
    nodes.push(current as Text);
    current = walker.nextNode();
  }
  for (const node of nodes) {
    const parent = node.parentElement;
    if (!parent || parent.closest(protectedContent) || !parent.closest("button,label,h1,h2,h3,h4,h5,h6,legend"))
      continue;
    translate(node, "text", node.nodeValue ?? "", STRUCTURE_EDITOR_TEXT_LABELS, (value) => {
      node.nodeValue = value;
    });
  }
  for (const control of root.querySelectorAll<HTMLInputElement>('input[type="button"],input[type="submit"]')) {
    if (control.closest("[contenteditable],[data-source-owned]")) continue;
    translate(control, "value", control.value, STRUCTURE_EDITOR_TEXT_LABELS, (value) => {
      control.value = value;
    });
  }
}
/** Reversible UI captions only: never rewrite molecular SVG, source inputs or observed values. */
export function applyStructureEditorAccessibility(root: HTMLElement) {
  let unnamedButtonIndex = 0;
  for (const button of root.querySelectorAll<HTMLButtonElement>("button")) {
    if (button.closest("svg,[contenteditable],[data-source-owned]")) continue;
    const generated = generatedButtons.get(button);
    if (generated) {
      unnamedButtonIndex = Math.max(unnamedButtonIndex, generated);
      const current = button.getAttribute("aria-label");
      const ours = current === "Structure editor tool " + generated || current === "结构编辑器工具 " + generated;
      if (ours)
        setAttribute(
          button,
          "aria-label",
          getLocale() === "zh-CN" ? "结构编辑器工具 " + generated : "Structure editor tool " + generated,
        );
      else generatedButtons.delete(button);
    }
    localizeButton(button);
    const hasName =
      Boolean(button.getAttribute("aria-label")?.trim()) ||
      Boolean(button.getAttribute("aria-labelledby")?.trim()) ||
      Boolean(button.textContent?.trim());
    if (hasName) continue;
    if (button.title.trim()) setAttribute(button, "aria-label", button.title.trim());
    else {
      unnamedButtonIndex++;
      generatedButtons.set(button, unnamedButtonIndex);
      setAttribute(
        button,
        "aria-label",
        getLocale() === "zh-CN"
          ? "结构编辑器工具 " + unnamedButtonIndex
          : "Structure editor tool " + unnamedButtonIndex,
      );
    }
  }
  for (const textarea of root.querySelectorAll<HTMLTextAreaElement>("textarea")) {
    if (generatedInputs.has(textarea)) {
      const current = textarea.getAttribute("aria-label");
      if (current === "结构编辑器文本输入" || current === "Structure editor text input")
        setAttribute(
          textarea,
          "aria-label",
          getLocale() === "zh-CN" ? "结构编辑器文本输入" : "Structure editor text input",
        );
      else generatedInputs.delete(textarea);
    }
    const hasLabel =
      Boolean(textarea.getAttribute("aria-label")?.trim()) ||
      Boolean(textarea.getAttribute("aria-labelledby")?.trim()) ||
      Boolean(textarea.title.trim()) ||
      Boolean(textarea.placeholder.trim()) ||
      Boolean(textarea.labels?.length);
    if (!hasLabel) {
      generatedInputs.add(textarea);
      setAttribute(
        textarea,
        "aria-label",
        getLocale() === "zh-CN" ? "结构编辑器文本输入" : "Structure editor text input",
      );
    }
  }
  localizeDynamicText(root);
}
