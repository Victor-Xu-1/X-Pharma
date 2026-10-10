import { ScrollableTableRegion } from "../ScrollableTableRegion";
/** Original evidence is disclosed verbatim through the shared keyboard-accessible scroll primitive. */
export function QualityRawRecord({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="quality-raw-record">
      <summary>{title}</summary>
      <ScrollableTableRegion ariaLabel={title} className="quality-raw-scroll">
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </ScrollableTableRegion>
    </details>
  );
}
