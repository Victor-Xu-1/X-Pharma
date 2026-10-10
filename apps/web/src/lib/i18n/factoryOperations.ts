export const factoryOperationMessages = {
  操作失败: "Operation failed",
  入库运行重放失败: "Ingestion run replay failed",
  入库运行取消失败: "Ingestion run cancellation failed",
  源版本重放失败: "Source version replay failed",
  隔离案件处置失败: "Quarantine decision failed",
  "当前运行状态不允许重放，请刷新后重试": "This run can no longer be replayed; refresh and try again",
  "当前运行已不能取消，请刷新后重试": "This run can no longer be canceled; refresh and try again",
} as const;
