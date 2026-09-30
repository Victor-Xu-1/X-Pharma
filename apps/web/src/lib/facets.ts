export function facetOptions(
  facets: Record<string, Record<string, number>> | undefined,
  name: string,
  selected: string | readonly string[],
) {
  const values = Object.keys(facets?.[name] ?? {});
  const selectedValues = Array.isArray(selected) ? selected : selected ? [selected] : [];
  for (const value of selectedValues) {
    if (!values.includes(value)) values.push(value);
  }
  return values.sort((left, right) => left.localeCompare(right));
}
