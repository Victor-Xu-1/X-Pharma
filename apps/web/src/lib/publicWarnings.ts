export const PUBLIC_COVERAGE_NOTICE = "结果可能受数据覆盖范围和来源更新时间影响。";

export function publicCoverageNotice(warnings: readonly string[] | null | undefined): string | undefined {
  return warnings?.length ? PUBLIC_COVERAGE_NOTICE : undefined;
}
