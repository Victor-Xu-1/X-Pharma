type MarkdownNode = { type: string; depth?: number; value?: string; children?: MarkdownNode[] };

/** Remove only an empty source heading immediately before reference definitions. */
export function removeEmptyReferenceHeading() {
  return (tree: MarkdownNode) => {
    if (!tree.children) return;
    const children = tree.children;
    tree.children = children.filter((node, index) => {
      if (node.type !== "heading" || node.depth !== 2 || node.children?.length !== 1) return true;
      if (node.children[0].type !== "text" || node.children[0].value !== "Sources") return true;
      const following = children.slice(index + 1);
      return !following.length || !following.every((item) => ["footnoteDefinition", "definition"].includes(item.type));
    });
  };
}
