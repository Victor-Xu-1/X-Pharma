import { createTranslator } from "./translator";
export const governanceQualityMessages = {
  完整率: "Completeness",
  重复率: "Duplicate rate",
  引用覆盖率: "Citation coverage",
  新鲜度覆盖率: "Freshness coverage",
  入库成功率: "Ingestion success",
  指标漂移: "Metric drift",
  未上报: "Not reported",
  不适用: "Not applicable",
  适用性未上报: "Applicability not reported",
  "样本 {numerator}/{denominator}": "Sample {numerator}/{denominator}",
  阈值: "Threshold",
  原始指标记录: "Original metric record",
  尚无质量快照: "No quality snapshots have been recorded",
  运行一次评估以建立首个质量基线: "Run an evaluation to establish the first quality baseline",
  正在读取质量快照: "Loading quality snapshots",
  "指标定义 {version}": "Metric definitions {version}",
  "所有处置写入不可变事件历史。": "Every action is recorded in immutable event history.",
} as const;
export const governanceQualityText = createTranslator(governanceQualityMessages);
