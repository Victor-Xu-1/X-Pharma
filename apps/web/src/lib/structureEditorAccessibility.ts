const STRUCTURE_EDITOR_LABELS: Record<string, string> = {
  "Clear Canvas (Ctrl+Del)": "清空画板（Ctrl+Del）",
  "Open... (Ctrl+O)": "打开结构（Ctrl+O）",
  "Save as... (Ctrl+S)": "另存结构（Ctrl+S）",
  "Copy (Ctrl+C)": "复制（Ctrl+C）",
  "Paste (Ctrl+V)": "粘贴（Ctrl+V）",
  "Cut (Ctrl+X)": "剪切（Ctrl+X）",
  "Undo (Ctrl+Z)": "撤销（Ctrl+Z）",
  "Redo (Ctrl+Shift+Z)": "重做（Ctrl+Shift+Z）",
  "Aromatize (Alt+A)": "芳香化（Alt+A）",
  "Dearomatize (Ctrl+Alt+A)": "去芳香化（Ctrl+Alt+A）",
  "Layout (Ctrl+L)": "布局（Ctrl+L）",
  "Clean Up (Ctrl+Shift+L)": "清理结构（Ctrl+Shift+L）",
  "Calculate CIP (Ctrl+P)": "计算 CIP（Ctrl+P）",
  "Check Structure (Alt+S)": "检查结构（Alt+S）",
  "Calculated Values (Alt+C)": "计算属性（Alt+C）",
  "Add/Remove explicit hydrogens": "添加/移除显式氢",
  Settings: "设置",
  "Hand tool (Ctrl+Alt+H)": "平移工具（Ctrl+Alt+H）",
  "Rectangle Selection (Shift+Tab)": "矩形选择（Shift+Tab）",
  "Erase (Del)": "擦除（Del）",
  "Single Bond (1)": "单键（1）",
  Chain: "链工具",
  "Charge Plus (Equal)": "正电荷（Equal）",
  "Charge Minus (Minus)": "负电荷（Minus）",
  "Add Image": "添加图片",
  "Benzene (T)": "苯环（T）",
  "Cyclopentadiene (T)": "环戊二烯（T）",
  "Cyclohexane (T)": "环己烷（T）",
  "Cyclopentane (T)": "环戊烷（T）",
  "Cyclopropane (T)": "环丙烷（T）",
  "Cyclobutane (T)": "环丁烷（T）",
  "Cycloheptane (T)": "环庚烷（T）",
  "Cyclooctane (T)": "环辛烷（T）",
  "Structure Library (Shift+T)": "结构库（Shift+T）",
  "Hydrogen (H)": "氢（H）",
  "Carbon (C)": "碳（C）",
  "Nitrogen (N)": "氮（N）",
  "Oxygen (O)": "氧（O）",
  "Sulfur (S)": "硫（S）",
  "Phosphorus (P)": "磷（P）",
  "Fluorine (F)": "氟（F）",
  "Chlorine (L)": "氯（Cl）",
  "Bromine (B)": "溴（Br）",
  "Iodine (I)": "碘（I）",
  "Periodic Table": "元素周期表",
  "Any atom": "任意原子",
  "Extended Table": "扩展元素表",
};

const STRUCTURE_EDITOR_TEXT_LABELS: Record<string, string> = {
  "Calculated Values": "计算属性",
  "Chemical Formula": "化学式",
  "Chemical Formula:": "化学式：",
  "Molecular Weight": "分子量",
  "Molecular Weight:": "分子量：",
  "Decimal places": "小数位数",
  "Exact Mass": "精确质量",
  "Exact Mass:": "精确质量：",
  "Elemental Analysis": "元素分析",
  "Elemental Analysis:": "元素分析：",
  Check: "检查",
  Cancel: "取消",
  Apply: "应用",
  Close: "关闭",
};

function localizeButton(button: HTMLButtonElement) {
  const title = button.getAttribute("title")?.trim() || "";
  const ariaLabel = button.getAttribute("aria-label")?.trim() || "";
  const localized = STRUCTURE_EDITOR_LABELS[title] ?? STRUCTURE_EDITOR_LABELS[ariaLabel];
  if (!localized) return;
  button.setAttribute("title", localized);
  button.setAttribute("aria-label", localized);
}

function localizeDynamicText(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  let current = walker.nextNode();
  while (current) {
    textNodes.push(current as Text);
    current = walker.nextNode();
  }

  for (const textNode of textNodes) {
    const value = textNode.nodeValue ?? "";
    const trimmed = value.trim();
    const localized = STRUCTURE_EDITOR_TEXT_LABELS[trimmed];
    if (!localized) continue;
    const leading = value.slice(0, value.indexOf(trimmed));
    const trailing = value.slice(value.indexOf(trimmed) + trimmed.length);
    textNode.nodeValue = `${leading}${localized}${trailing}`;
  }

  for (const control of root.querySelectorAll<HTMLInputElement>('input[type="button"], input[type="submit"]')) {
    const localized = STRUCTURE_EDITOR_TEXT_LABELS[control.value.trim()];
    if (localized) control.value = localized;
  }
}

export function applyStructureEditorAccessibility(root: HTMLElement) {
  let unnamedButtonIndex = 0;
  for (const button of root.querySelectorAll<HTMLButtonElement>("button")) {
    localizeButton(button);
    const hasName =
      Boolean(button.getAttribute("aria-label")?.trim()) ||
      Boolean(button.getAttribute("aria-labelledby")?.trim()) ||
      Boolean(button.textContent?.trim());
    if (hasName) continue;
    unnamedButtonIndex += 1;
    button.setAttribute("aria-label", button.title.trim() || `结构编辑器工具 ${unnamedButtonIndex}`);
  }
  for (const textarea of root.querySelectorAll<HTMLTextAreaElement>("textarea")) {
    const hasLabel =
      Boolean(textarea.getAttribute("aria-label")?.trim()) ||
      Boolean(textarea.getAttribute("aria-labelledby")?.trim()) ||
      Boolean(textarea.title.trim()) ||
      Boolean(textarea.placeholder.trim()) ||
      Boolean(textarea.labels?.length);
    if (!hasLabel) textarea.setAttribute("aria-label", "结构编辑器文本输入");
  }
  localizeDynamicText(root);
}
