export interface PipelineSignalFilterValues {
  hasClinicalResults: "" | "true" | "false";
  clinicalResultEvaluation: string;
  hasDeal: "" | "true" | "false";
  dealCurrency: string;
  dealTotalPotentialAmountMin: string;
  dealTotalPotentialAmountMax: string;
}

export const pipelineResultEvaluationLabels: Record<string, string> = {
  superior: "优于对照",
  positive: "积极",
  non_inferior: "非劣",
  similar: "相似",
  not_superior: "未显示优效",
  unfavorable: "不利",
  terminated: "终止",
};

export const pipelineBooleanSignalLabels: Record<string, string> = { true: "有", false: "无" };

export function validatePipelineSignalFilters(values: PipelineSignalFilterValues): string | null {
  if (values.hasClinicalResults === "false" && values.clinicalResultEvaluation) {
    return "选择“无临床结果”时不能同时限定结果评价";
  }
  const hasDealDetails = Boolean(
    values.dealCurrency || values.dealTotalPotentialAmountMin || values.dealTotalPotentialAmountMax,
  );
  if (values.hasDeal === "false" && hasDealDetails) {
    return "选择“无交易记录”时不能同时限定交易金额或币种";
  }
  if ((values.dealTotalPotentialAmountMin || values.dealTotalPotentialAmountMax) && !values.dealCurrency) {
    return "按交易金额查询时必须选择币种";
  }
  const amountMin = values.dealTotalPotentialAmountMin ? Number(values.dealTotalPotentialAmountMin) : undefined;
  const amountMax = values.dealTotalPotentialAmountMax ? Number(values.dealTotalPotentialAmountMax) : undefined;
  if (amountMin !== undefined && amountMax !== undefined && amountMin > amountMax) {
    return "交易潜在总额下限不能大于上限";
  }
  return null;
}
