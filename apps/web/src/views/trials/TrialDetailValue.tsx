export function DetailValue({ term, value }: { term: string; value: import("react").ReactNode }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value === null || value === undefined || value === "" ? "--" : value}</dd>
    </div>
  );
}
