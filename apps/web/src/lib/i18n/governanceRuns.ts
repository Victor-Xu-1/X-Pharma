import { createTranslator } from "./translator";

export const governanceRunMessages = {
  执行配置: "Execution settings",
  模型: "Model",
  策略状态: "Policy status",
  当前策略: "Current policy",
  历史策略: "Historical policy",
  "Token / 成本": "Tokens / cost",
  未上报: "Not reported",
  "已上报 Token（不完整）：{tokens}": "Reported tokens (incomplete): {tokens}",
  开始时间: "Started at",
  完成时间: "Completed at",
  尚未完成: "Not completed",
  可审计指纹: "Audit fingerprints",
  校验结果: "Validation findings",
  未记录结构化校验错误: "No structured validation errors recorded",
} as const;
export const governanceRunText = createTranslator(governanceRunMessages);
