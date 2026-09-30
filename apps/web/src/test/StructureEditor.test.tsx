import { describe, expect, it } from "vitest";

import { applyStructureEditorAccessibility } from "../lib/structureEditorAccessibility";
import { isStructureApplyDisabled } from "../lib/structureEditorState";

describe("structure editor action state", () => {
  it("keeps apply unavailable until the editor has a structure", () => {
    expect(isStructureApplyDisabled({ ready: false, busy: false, hasStructure: false })).toBe(true);
    expect(isStructureApplyDisabled({ ready: true, busy: false, hasStructure: false })).toBe(true);
    expect(isStructureApplyDisabled({ ready: true, busy: true, hasStructure: true })).toBe(true);
    expect(isStructureApplyDisabled({ ready: true, busy: false, hasStructure: true })).toBe(false);
  });
});

describe("structure editor accessibility adapter", () => {
  it("names dynamically rendered icon buttons and unlabeled textareas without replacing existing semantics", () => {
    const root = document.createElement("div");
    root.innerHTML = `
      <button title="Aromatize (Alt+A)"><svg /></button>
      <button><svg /></button>
      <button aria-label="撤销"><svg /></button>
      <textarea></textarea>
      <textarea aria-label="已有标签"></textarea>
    `;

    applyStructureEditorAccessibility(root);

    const buttons = root.querySelectorAll("button");
    const textareas = root.querySelectorAll("textarea");
    expect(buttons[0]).toHaveAttribute("title", "芳香化（Alt+A）");
    expect(buttons[0]).toHaveAttribute("aria-label", "芳香化（Alt+A）");
    expect(buttons[1]).toHaveAttribute("aria-label", "结构编辑器工具 1");
    expect(buttons[2]).toHaveAttribute("aria-label", "撤销");
    expect(textareas[0]).toHaveAttribute("aria-label", "结构编辑器文本输入");
    expect(textareas[1]).toHaveAttribute("aria-label", "已有标签");
  });

  it("localizes third-party structure editor controls for Chinese users", () => {
    const root = document.createElement("div");
    root.innerHTML = `
      <button title="Clear Canvas (Ctrl+Del)"><svg /></button>
      <button aria-label="Carbon (C)"><svg /></button>
      <button title="Dearomatize (Ctrl+Alt+A)"><svg /></button>
      <button aria-label="Calculated Values (Alt+C)"><svg /></button>
      <button title="Add/Remove explicit hydrogens"><svg /></button>
    `;

    applyStructureEditorAccessibility(root);

    const buttons = root.querySelectorAll("button");
    expect(buttons[0]).toHaveAttribute("title", "清空画板（Ctrl+Del）");
    expect(buttons[0]).toHaveAttribute("aria-label", "清空画板（Ctrl+Del）");
    expect(buttons[1]).toHaveAttribute("title", "碳（C）");
    expect(buttons[1]).toHaveAttribute("aria-label", "碳（C）");
    expect(buttons[2]).toHaveAttribute("title", "去芳香化（Ctrl+Alt+A）");
    expect(buttons[2]).toHaveAttribute("aria-label", "去芳香化（Ctrl+Alt+A）");
    expect(buttons[3]).toHaveAttribute("title", "计算属性（Alt+C）");
    expect(buttons[3]).toHaveAttribute("aria-label", "计算属性（Alt+C）");
    expect(buttons[4]).toHaveAttribute("title", "添加/移除显式氢");
    expect(buttons[4]).toHaveAttribute("aria-label", "添加/移除显式氢");
  });

  it("localizes dynamically rendered structure dialogs and action values", () => {
    const root = document.createElement("div");
    root.innerHTML = `
      <section>
        <h2>Calculated Values</h2>
        <label>Chemical Formula:</label>
        <label>Molecular Weight:</label>
        <label>Decimal places</label>
        <label>Exact Mass:</label>
        <label>Elemental Analysis:</label>
        <button>Check</button>
        <button>Cancel</button>
        <input type="button" value="Close" />
      </section>
    `;

    applyStructureEditorAccessibility(root);

    expect(root).toHaveTextContent("计算属性");
    expect(root).toHaveTextContent("化学式：");
    expect(root).toHaveTextContent("分子量：");
    expect(root).toHaveTextContent("小数位数");
    expect(root).toHaveTextContent("精确质量：");
    expect(root).toHaveTextContent("元素分析：");
    expect(root.querySelector("button")).toHaveTextContent("检查");
    expect(root.querySelectorAll("button")[1]).toHaveTextContent("取消");
    expect(root.querySelector<HTMLInputElement>('input[type="button"]')).toHaveValue("关闭");
  });
});
