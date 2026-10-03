import { expect, type Locator } from "@playwright/test";

async function readFixedColumns(shell: Locator) {
  return shell.evaluate((element) => {
    const viewport = element.querySelector<HTMLElement>(".virtual-table-viewport");
    const header = element.querySelector("thead tr");
    const row = element.querySelector("tbody tr");
    if (!viewport || !header || !row) throw new Error("Dense table layout is incomplete");
    const read = (parent: Element) =>
      [...parent.children].slice(0, 3).map((cell) => {
        const style = getComputedStyle(cell);
        const rect = cell.getBoundingClientRect();
        const text = document.createRange();
        text.selectNodeContents(cell);
        return {
          x: rect.x,
          width: rect.width,
          position: style.position,
          contentRects: text.getClientRects().length,
          fontReady: document.fonts.check(style.font),
        };
      });
    return {
      left: viewport.getBoundingClientRect().left + viewport.clientLeft,
      scroll: viewport.scrollLeft,
      maximumScroll: viewport.scrollWidth - viewport.clientWidth,
      header: read(header),
      row: read(row),
    };
  });
}

export async function verifyFixedColumnLayout(shell: Locator) {
  await shell.evaluate(() => document.fonts.ready);
  const initial = await readFixedColumns(shell);
  expect(initial.header).toHaveLength(3);
  expect(initial.row).toHaveLength(3);
  for (const cells of [initial.header, initial.row]) {
    for (const [index, cell] of cells.entries()) {
      expect(cell.fontReady).toBe(true);
      expect(cell.contentRects).toBeGreaterThan(0);
      if (index < 2) {
        expect(cell.position).toBe("sticky");
        expect(cell.x).toBe(initial.left + (index === 0 ? 0 : cells[0].width));
      }
    }
  }
  expect(initial.header.slice(0, 2).map((cell) => cell.width)).toEqual(
    initial.row.slice(0, 2).map((cell) => cell.width),
  );
  expect(initial.maximumScroll).toBeGreaterThanOrEqual(0);
  if (initial.maximumScroll === 0) {
    expect(initial.scroll).toBe(0);
    return;
  }
  const viewport = shell.locator(".virtual-table-viewport");
  try {
    await viewport.evaluate((element) => {
      element.scrollLeft = Math.min(64, element.scrollWidth - element.clientWidth);
    });
    await expect.poll(async () => (await readFixedColumns(shell)).scroll).toBeGreaterThan(0);
    const scrolled = await readFixedColumns(shell);
    for (const field of ["header", "row"] as const) {
      expect(scrolled[field].slice(0, 2).map((cell) => cell.x)).toEqual(
        initial[field].slice(0, 2).map((cell) => cell.x),
      );
      expect(scrolled[field][2].x).toBe(initial[field][2].x - scrolled.scroll + initial.scroll);
    }
  } finally {
    await viewport.evaluate((element, scroll) => {
      element.scrollLeft = scroll;
    }, initial.scroll);
    await expect.poll(async () => (await readFixedColumns(shell)).scroll).toBe(initial.scroll);
  }
}
