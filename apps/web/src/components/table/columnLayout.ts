type ColumnTrack = { size: number; sortable: boolean };

/** Reserve room for complete word labels and their sort icon, not wider row actions. */
export function tableColumnLayout(columns: readonly ColumnTrack[]) {
  const sizes = columns.map(({ size, sortable }) => (sortable ? Math.max(120, size) : size));
  return {
    minWidth: sizes.reduce((total, size) => total + size, 0),
    gridColumns: sizes.map((size) => `minmax(${size}px, ${size}fr)`).join(" "),
  };
}
