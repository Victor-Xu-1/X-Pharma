import { ListChecks, Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { CollectionDirectoryControls } from "../../components/CollectionDirectoryControls";
import { EmptyState, ErrorState, Spinner, StatusBadge } from "../../components/common";
import { ResponsiveDirectory } from "../../components/ResponsiveDirectory";
import type { useCollectionCatalog } from "../../lib/useCollectionCatalog";

export function CollectionCatalog({
  catalog,
  activeId,
  pending,
  onSelect,
  onCreate,
}: {
  catalog: ReturnType<typeof useCollectionCatalog>;
  activeId: string;
  pending: boolean;
  onSelect: (id: string) => void;
  onCreate: (name: string, visibility: "private" | "tenant") => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  async function create(event: FormEvent) {
    event.preventDefault();
    if (await onCreate(name.trim(), shared ? "tenant" : "private")) setName("");
  }
  return (
    <ResponsiveDirectory
      selectedKey={activeId || null}
      title="列表目录"
      summary={catalog.query.data ? `${catalog.query.data.total} 个列表` : "创建与筛选"}
      icon={<ListChecks size={18} aria-hidden="true" />}
      className="collections-list"
    >
      {(collapse) => (
        <>
          <form className="stack-form" onSubmit={(event) => void create(event)}>
            <label>
              新建对比列表
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="列表名称"
                aria-label="列表名称"
                maxLength={200}
                required
                disabled={pending}
              />
            </label>
            <label className="check-control" style={{ display: "flex" }}>
              <input
                type="checkbox"
                checked={shared}
                onChange={(event) => setShared(event.target.checked)}
                disabled={pending}
              />
              团队共享
            </label>
            <button className="primary-button" type="submit" disabled={!name.trim() || pending}>
              <Plus size={16} />
              创建
            </button>
          </form>
          <CollectionDirectoryControls catalog={catalog} />
          {catalog.query.isPending ? (
            <Spinner label="正在读取列表目录" />
          ) : catalog.query.error ? (
            <ErrorState
              message={catalog.query.error instanceof Error ? catalog.query.error.message : "列表目录加载失败"}
              retry={() => void catalog.query.refetch()}
            />
          ) : (
            <nav className="collection-picker" aria-label="对比列表目录" style={{ maxHeight: 520, overflow: "auto" }}>
              {catalog.query.data?.items.length ? (
                catalog.query.data.items.map((item) => (
                  <button
                    type="button"
                    className={activeId === item.id ? "active" : ""}
                    key={item.id}
                    aria-current={activeId === item.id ? "true" : undefined}
                    onClick={() => {
                      collapse();
                      onSelect(item.id);
                    }}
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.member_count}/20 条</small>
                    </span>
                    <StatusBadge value={item.visibility === "tenant" ? "团队共享" : "仅自己可见"} />
                  </button>
                ))
              ) : catalog.filter.q ? (
                <EmptyState title="没有匹配的列表" detail="调整名称或说明关键词；已打开的列表不会改变" />
              ) : (
                <p className="field-help">创建后，列表会出现在这里。</p>
              )}
            </nav>
          )}
        </>
      )}
    </ResponsiveDirectory>
  );
}
