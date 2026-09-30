import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { type FormEvent, useEffect, useId, useMemo, useState } from "react";

type PageToken = number | { key: string };

function visiblePages(currentPage: number, totalPages: number): PageToken[] {
  const pages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  const bounded = [...pages].filter((page) => page >= 1 && page <= totalPages).sort((left, right) => left - right);
  const tokens: PageToken[] = [];

  bounded.forEach((page, index) => {
    const previous = bounded[index - 1];
    if (previous !== undefined && page - previous > 1) tokens.push({ key: `ellipsis-${previous}-${page}` });
    tokens.push(page);
  });
  return tokens;
}

export function ResultPagination({
  totalRows,
  offset,
  pageSize,
  onPageChange,
  notice,
  ariaLabel = "结果分页",
}: {
  totalRows: number;
  offset: number;
  pageSize: number;
  onPageChange: (offset: number) => void;
  notice?: string;
  ariaLabel?: string;
}) {
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
  const lastOffset = (totalPages - 1) * pageSize;
  const normalizedOffset = Math.min(lastOffset, Math.max(0, Math.floor(offset / pageSize) * pageSize));
  const currentPage = Math.floor(normalizedOffset / pageSize) + 1;
  const [draftPage, setDraftPage] = useState(String(currentPage));
  const [validationMessage, setValidationMessage] = useState("");
  const validationId = useId();
  const pageTokens = useMemo(() => visiblePages(currentPage, totalPages), [currentPage, totalPages]);

  useEffect(() => {
    setDraftPage(String(currentPage));
    setValidationMessage("");
  }, [currentPage]);

  useEffect(() => {
    if (offset !== normalizedOffset) onPageChange(normalizedOffset);
  }, [normalizedOffset, offset, onPageChange]);

  if (totalRows <= 0) return null;

  function goToPage(page: number) {
    const boundedPage = Math.min(totalPages, Math.max(1, page));
    if (boundedPage === currentPage) return;
    setValidationMessage("");
    onPageChange((boundedPage - 1) * pageSize);
  }

  function submitJump(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestedPage = Number(draftPage);
    if (!Number.isInteger(requestedPage) || requestedPage < 1 || requestedPage > totalPages) {
      setValidationMessage(`请输入 1 到 ${totalPages} 之间的页码`);
      return;
    }
    goToPage(requestedPage);
  }

  return (
    <nav className="domain-pagination" aria-label={ariaLabel}>
      <div className="domain-pagination-context">
        <strong>
          第 {currentPage} / {totalPages} 页
        </strong>
        <span>共 {totalRows} 条</span>
        {notice ? <small title={notice}>{notice}</small> : null}
      </div>
      <div className="domain-pagination-controls">
        <button
          className="icon-button"
          type="button"
          aria-label="首页"
          title="首页"
          disabled={currentPage === 1}
          onClick={() => goToPage(1)}
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label="上一页"
          title="上一页"
          disabled={currentPage === 1}
          onClick={() => goToPage(currentPage - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <fieldset className="domain-pagination-pages">
          <legend className="sr-only">页码</legend>
          {pageTokens.map((token) =>
            typeof token !== "number" ? (
              <span aria-hidden="true" key={token.key}>
                ...
              </span>
            ) : (
              <button
                type="button"
                className={token === currentPage ? "active" : ""}
                aria-current={token === currentPage ? "page" : undefined}
                aria-label={`第 ${token} 页`}
                key={token}
                onClick={() => goToPage(token)}
              >
                {token}
              </button>
            ),
          )}
        </fieldset>
        <button
          className="icon-button"
          type="button"
          aria-label="下一页"
          title="下一页"
          disabled={currentPage === totalPages}
          onClick={() => goToPage(currentPage + 1)}
        >
          <ChevronRight size={16} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label="末页"
          title="末页"
          disabled={currentPage === totalPages}
          onClick={() => goToPage(totalPages)}
        >
          <ChevronsRight size={16} />
        </button>
        <form className="domain-pagination-jump" aria-label="跳转页码" onSubmit={submitJump} noValidate>
          <label>
            <span>跳至</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={totalPages}
              step={1}
              value={draftPage}
              aria-label="目标页码"
              aria-invalid={Boolean(validationMessage)}
              aria-describedby={validationMessage ? validationId : undefined}
              onChange={(event) => {
                setDraftPage(event.target.value);
                setValidationMessage("");
              }}
            />
            <span>页</span>
          </label>
          <button type="submit" className="secondary-button">
            跳转
          </button>
        </form>
      </div>
      {validationMessage ? (
        <p className="domain-pagination-error" id={validationId} role="alert">
          {validationMessage}
        </p>
      ) : null}
    </nav>
  );
}
