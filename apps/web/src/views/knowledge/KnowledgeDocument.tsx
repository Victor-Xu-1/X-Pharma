import { useId, useMemo } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { useMessages } from "../../lib/i18n";
import { knowledgeMessages, knowledgeText } from "../../lib/i18n/knowledge";
import { KnowledgeStructuredValue } from "./KnowledgeStructuredValue";
import { removeEmptyReferenceHeading } from "./knowledgeMarkdown";
import { knowledgePredicateLabel, publicKnowledgeLink, publicKnowledgeMarkdown } from "./knowledgeReading";
import "./knowledge-reading.css";

const sectionLabels: Record<string, keyof typeof knowledgeMessages> = {
  Identifiers: "公开标识",
  Evidence: "已记录要点",
  Sources: "来源",
};
const components: Components = {
  h1: ({ node: _node, ...props }) => <h3 {...props} />,
  h3: ({ node: _node, ...props }) => <h4 {...props} />,
  h4: ({ node: _node, ...props }) => <h5 {...props} />,
  h5: ({ node: _node, ...props }) => <h6 {...props} />,
  strong: ({ node: _node, children, ...props }) => (
    <strong {...props} title={typeof children === "string" ? children : undefined}>
      {typeof children === "string" ? knowledgePredicateLabel(children) : children}
    </strong>
  ),
  code: ({ node: _node, children, className, ...props }) => {
    const text = String(children);
    if (!className && !text.includes("\n") && /^\s*(?:\{|\[)/.test(text)) {
      try {
        const value: unknown = JSON.parse(text);
        if (value !== null && typeof value === "object") return <KnowledgeStructuredValue value={value} />;
      } catch {
        // Non-JSON code remains literal; never infer or silently repair a fact.
      }
    }
    return (
      <code {...props} className={className}>
        {children}
      </code>
    );
  },
  img: ({ alt }) => (
    <span className="knowledge-image-note">
      {knowledgeText("未自动加载图像：{alt}（地址见公开原文）", { alt: alt || knowledgeText("外部图片") })}
    </span>
  ),
  table: ({ node: _node, ...props }) => (
    <ScrollableTableRegion ariaLabel={knowledgeText("专题表格")}>
      <table aria-label={knowledgeText("专题表格")} {...props} />
    </ScrollableTableRegion>
  ),
};

export function KnowledgeDocument({ markdown, title }: { markdown: string; title: string }) {
  const text = useMessages(knowledgeMessages);
  const instance = useId().replace(/[^\w-]/g, "_");
  const footnoteLabelId = `knowledge-${instance}-footnote-label`;
  const documentComponents = useMemo<Components>(
    () => ({
      ...components,
      h2: ({ node: _node, id, children, ...props }) => (
        <h3 {...props} id={id === "footnote-label" ? footnoteLabelId : id}>
          {typeof children === "string" && Object.hasOwn(sectionLabels, children)
            ? text(sectionLabels[children])
            : children}
        </h3>
      ),
      a: ({ node: _node, href, children, ...props }) =>
        href ? (
          <a
            {...props}
            href={href}
            aria-describedby={
              props["aria-describedby"] === "footnote-label" ? footnoteLabelId : props["aria-describedby"]
            }
            target={href.startsWith("#") ? undefined : "_blank"}
            rel={href.startsWith("#") ? undefined : "noopener noreferrer"}
          >
            {children}
          </a>
        ) : (
          <span>{children}</span>
        ),
    }),
    [footnoteLabelId, text],
  );
  const original = publicKnowledgeMarkdown(markdown);
  const lines = original.trimStart().split("\n");
  const body = lines[0]?.trim() === `# ${title}` ? lines.slice(1).join("\n").trimStart() : original;
  return (
    <div className="knowledge-reading">
      <Markdown
        components={documentComponents}
        remarkPlugins={[remarkGfm, removeEmptyReferenceHeading]}
        remarkRehypeOptions={{
          clobberPrefix: `knowledge-${instance}-`,
          footnoteLabel: text("引用与来源"),
          footnoteBackLabel: text("返回正文引用"),
          footnoteLabelProperties: { className: [] },
        }}
        urlTransform={(url, key) => (key === "src" ? "" : publicKnowledgeLink(url))}
      >
        {body}
      </Markdown>
      <details className="knowledge-original-document">
        <summary>{text("查看公开原文 Markdown")}</summary>
        <p>{text("保留此版本的全部公开文本、结构化值和引用，便于核对；不额外验证或补全来源。")}</p>
        <textarea
          className="knowledge-source-text"
          rows={12}
          readOnly
          aria-label={text("此版本的完整公开原文")}
          value={original}
        />
      </details>
    </div>
  );
}
