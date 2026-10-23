export const factoryDialogMessages = {
  关闭: "Close",
  取消: "Cancel",
  返回: "Back",
  重放入库运行: "Replay ingestion run",
  "将按当前数据源治理配置重新扫描；原运行与发现项保持不变，新运行会单独记录并写入审计日志。":
    "Rescan with the current source governance configuration. The original run and findings remain unchanged; the new run is separately recorded and audited.",
  原工作流: "Original workflow",
  重放原因: "Replay reason",
  正在提交重放请求: "Submitting replay request",
  正在提交: "Submitting",
  确认重放: "Confirm replay",
  取消入库运行: "Cancel ingestion run",
  "取消请求只发送到该运行绑定的 Temporal 执行。已完成的不可变快照会保留，后续阶段将在安全检查点停止。":
    "Cancellation targets only this run's linked Temporal execution. Completed immutable snapshots are retained; later stages stop at a safe checkpoint.",
  运行关联标识: "Linked run identifier",
  取消原因: "Cancellation reason",
  正在提交取消请求: "Submitting cancellation request",
  正在取消: "Canceling",
  确认取消: "Confirm cancellation",
  "重放源版本 {number}": "Replay source version {number}",
  "恢复只复用已成功且仍可核验的前序产物，并从所选阶段重置后续状态。当前失败代码：":
    "Recovery reuses only successful, still-verifiable earlier artifacts and resets subsequent stages from the selected point. Current failure code:",
  "无（阶段状态失败）": "None (stage state failed)",
  恢复起点: "Recovery start stage",
  正在提交版本重放请求: "Submitting source version replay",
  文档解析: "Document parsing",
  运行发现项: "Run findings",
  运行说明: "Run note",
  刷新运行详情: "Refresh run details",
  "阶段信息来自上次读取，尚未重新确认当前状态。":
    "Stages reflect the previous read; current state has not been reconfirmed.",
  "上次读取的发现项（非实时）": "Previously read findings (not live)",
  可重试: "Retryable",
  不可重试: "Not retryable",
  该运行没有发现项: "No findings in this run",
  "运行在{stages}阶段失败，未生成发现项。请查看阶段详情，并在确认原因后重放。":
    "The run failed during {stages} and produced no findings. Inspect the stages and establish the cause before replaying.",
} as const;
