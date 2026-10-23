import { createTranslator } from "./translator";
export const governanceMaintenanceMessages = {
  检索投影维护: "Search projection maintenance",
  刷新投影任务: "Refresh maintenance jobs",
  一致性检查: "Consistency check",
  原子重建全局投影: "Atomic global projection rebuild",
  正在读取投影维护任务: "Loading maintenance jobs",
  全局原子重建: "Atomic global rebuild",
  尚无投影维护任务: "No maintenance jobs have been recorded",
  未上报: "Not reported",
  "实际 / 预期": "Observed / expected",
  重建全局检索投影: "Rebuild global search projections",
  "该操作影响所有组织的检索投影。构建新索引并校验后，后台才执行原子切换；不会直接改写 PostgreSQL 权威事实。":
    "This operation affects search projections for every organization. The worker builds and validates new indices before an atomic switch; authoritative PostgreSQL facts are not rewritten.",
  我确认需要重建所有组织的全局检索投影:
    "I confirm that the global search projections for every organization need to be rebuilt",
  确认重建: "Confirm rebuild",
  取消: "Cancel",
  关闭重建确认: "Close rebuild confirmation",
  "任务受理不代表重建成功，请查看后台任务状态与结果。":
    "An accepted request does not establish a successful rebuild. Check the worker's job status and results.",
} as const;
export const governanceMaintenanceText = createTranslator(governanceMaintenanceMessages);
