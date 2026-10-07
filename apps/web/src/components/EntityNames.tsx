import type { Entity } from "../lib/types";
import "./EntityNames.css";

export function EntityNames({ entity }: { entity: Pick<Entity, "name" | "aliases"> }) {
  const canonical = entity.name.trim().replace(/\s+/g, " ").toLowerCase();
  const names = new Map<string, string>();
  for (const raw of entity.aliases ?? []) {
    const alias = raw.trim();
    const normalized = alias.replace(/\s+/g, " ").toLowerCase();
    if (normalized && normalized !== canonical && !names.has(normalized)) names.set(normalized, alias);
  }
  const aliases = [...names.values()];
  if (!aliases.length) return null;
  const renderNames = (items: string[]) => (
    <ul className="entity-name-list">
      {items.map((alias) => (
        <li key={alias}>{alias}</li>
      ))}
    </ul>
  );
  return (
    <section className="entity-names" aria-label="别名与研发代号">
      <h3>别名与研发代号</h3>
      {renderNames(aliases.slice(0, 6))}
      {aliases.length > 6 ? (
        <details>
          <summary>更多别名（{aliases.length - 6}）</summary>
          {renderNames(aliases.slice(6))}
        </details>
      ) : null}
    </section>
  );
}
