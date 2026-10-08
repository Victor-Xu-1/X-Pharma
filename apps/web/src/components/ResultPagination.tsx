import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { type FormEvent, useEffect, useId, useMemo, useState } from "react";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";

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
  ariaLabel = t("结果分页"),
}: {
  totalRows: number;
  offset: number;
  pageSize: number;
  onPageChange: (offset: number) => void;
  notice?: string;
  ariaLabel?: string;
}) {
  useLocale();
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
  const lastOffset = (totalPages - 1) * pageSize;
  const normalizedOffset = Math.min(lastOffset, Math.max(0, Math.floor(offset / pageSize) * pageSize));
  const currentPage = Math.floor(normalizedOffset / pageSize) + 1;
  const [draftPage, setDraftPage] = useState(String(currentPage));
  const [invalidPage, setInvalidPage] = useState(false);
  const validationMessage = invalidPage ? t("请输入 1 到 {pages} 之间的页码", { pages: totalPages }) : "";
  const validationId = useId();
  const pageTokens = useMemo(() => visiblePages(currentPage, totalPages), [currentPage, totalPages]);

  useEffect(() => {
    setDraftPage(String(currentPage));
    setInvalidPage(false);
  }, [currentPage]);

  useEffect(() => {
    if (offset !== normalizedOffset) onPageChange(normalizedOffset);
  }, [normalizedOffset, offset, onPageChange]);

  if (totalRows <= 0) return null;

  function goToPage(page: number) {
    const boundedPage = Math.min(totalPages, Math.max(1, page));
    if (boundedPage === currentPage) return;
    setInvalidPage(false);
    onPageChange((boundedPage - 1) * pageSize);
  }

  function submitJump(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestedPage = Number(draftPage);
    if (!Number.isInteger(requestedPage) || requestedPage < 1 || requestedPage > totalPages) {
      setInvalidPage(true);
      return;
    }
    goToPage(requestedPage);
  }

  return (
    <nav className="domain-pagination" aria-label={ariaLabel}>
      <div className="domain-pagination-context">
        <strong>{t("第 {page} / {pages} 页", { page: currentPage, pages: totalPages })}</strong>
        <span>{t("共 {count} 条", { count: totalRows })}</span>
        {notice ? <small title={notice}>{notice}</small> : null}
      </div>
      <div className="domain-pagination-controls">
        <button
          className="icon-button"
          type="button"
          aria-label={t("首页")}
          title={t("首页")}
          disabled={currentPage === 1}
          onClick={() => goToPage(1)}
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label={t("上一页")}
          title={t("上一页")}
          disabled={currentPage === 1}
          onClick={() => goToPage(currentPage - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <fieldset className="domain-pagination-pages">
          <legend className="sr-only">{t("页码")}</legend>
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
                aria-label={t("第 {page} 页", { page: token })}
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
          aria-label={t("下一页")}
          title={t("下一页")}
          disabled={currentPage === totalPages}
          onClick={() => goToPage(currentPage + 1)}
        >
          <ChevronRight size={16} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label={t("末页")}
          title={t("末页")}
          disabled={currentPage === totalPages}
          onClick={() => goToPage(totalPages)}
        >
          <ChevronsRight size={16} />
        </button>
        <form className="domain-pagination-jump" aria-label={t("跳转页码")} onSubmit={submitJump} noValidate>
          <label>
            <span>{t("跳至")}</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={totalPages}
              step={1}
              value={draftPage}
              aria-label={t("目标页码")}
              aria-invalid={Boolean(validationMessage)}
              aria-describedby={validationMessage ? validationId : undefined}
              onChange={(event) => {
                setDraftPage(event.target.value);
                setInvalidPage(false);
              }}
            />
            <span>{t("页")}</span>
          </label>
          <button type="submit" className="secondary-button">
            {t("跳转")}
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
