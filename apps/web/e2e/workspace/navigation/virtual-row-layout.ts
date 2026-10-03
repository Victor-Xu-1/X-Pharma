import { expect, type Locator } from "@playwright/test";

async function readVirtualRows(shell: Locator) {
  return shell.evaluate((element) => {
    const viewport = element.querySelector<HTMLElement>(".virtual-table-viewport");
    const body = element.querySelector<HTMLElement>("tbody");
    const rows = [...element.querySelectorAll<HTMLElement>(".virtual-table-data-row")];
    const first = rows[0];
    if (!viewport || !body || !first) throw new Error("The dense virtual window is incomplete");
    return {
      scroll: viewport.scrollTop,
      canvasHeight: body.getBoundingClientRect().height,
      padding: Number.parseFloat(body.style.paddingTop),
      firstOffset: first.getBoundingClientRect().top - body.getBoundingClientRect().top,
      count: rows.length,
      rowHeight: first.getBoundingClientRect().height,
      maximumRows: Math.ceil(viewport.clientHeight / first.getBoundingClientRect().height) + 16,
      transforms: rows.map((row) => row.style.transform),
    };
  });
}

function expectBoundedNaturalRows(state: Awaited<ReturnType<typeof readVirtualRows>>) {
  expect(state.rowHeight).toBeGreaterThan(0);
  expect(state.count).toBeGreaterThan(0);
  expect(state.count).toBeLessThanOrEqual(state.maximumRows);
  expect(state.firstOffset).toBe(state.padding);
  expect(state.transforms.every((transform) => transform === "")).toBe(true);
}

export async function verifyVirtualRowLayout(shell: Locator) {
  const initial = await readVirtualRows(shell);
  expectBoundedNaturalRows(initial);
  const viewport = shell.locator(".virtual-table-viewport");
  try {
    await viewport.evaluate((element) => {
      element.scrollTop = (element.scrollHeight - element.clientHeight) / 2;
    });
    await expect.poll(async () => (await readVirtualRows(shell)).padding).toBeGreaterThan(0);
    const middle = await readVirtualRows(shell);
    expectBoundedNaturalRows(middle);
    expect(middle.canvasHeight).toBe(initial.canvasHeight);
  } finally {
    await viewport.evaluate((element, scroll) => {
      element.scrollTop = scroll;
    }, initial.scroll);
    await expect.poll(async () => (await readVirtualRows(shell)).padding).toBe(initial.padding);
  }
}
