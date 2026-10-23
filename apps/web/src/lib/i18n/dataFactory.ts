import { factoryDialogMessages } from "./factoryDialogs";
import { factoryEditorMessages } from "./factoryEditor";
import { factoryHealthMessages } from "./factoryHealth";
import { factoryOperationMessages } from "./factoryOperations";
import { factoryOverviewMessages } from "./factoryOverview";
import { factoryQuarantineMessages } from "./factoryQuarantine";
import { factoryRunMessages } from "./factoryRuns";
import { factorySourceMessages } from "./factorySources";
import { factoryValidationMessages } from "./factoryValidation";
import { factoryVersionMessages } from "./factoryVersions";
import { createTranslator } from "./translator";

export const factoryMessages = {
  ...factorySourceMessages,
  ...factoryOverviewMessages,
  ...factoryHealthMessages,
  ...factoryRunMessages,
  ...factoryQuarantineMessages,
  ...factoryDialogMessages,
  ...factoryOperationMessages,
  ...factoryVersionMessages,
  ...factoryEditorMessages,
  ...factoryValidationMessages,
  自动数据源: "Data sources",
  接入自动数据源: "Connect data source",
  刷新数据工厂: "Refresh data factory",
  刷新: "Refresh",
  正在连接数据工厂: "Connecting to the data factory",
  源对象与版本: "Source assets and versions",
  "只读查看来源路径、版本哈希、处理阶段、恶意文件结果和解析文本":
    "Read source paths, version hashes, processing stages, malware findings and parsed text",
  正在读取源对象: "Loading source assets",
  正在刷新源对象: "Refreshing source assets",
  重试源对象: "Retry source assets",
  "上次读取的源对象（非实时）": "Previously read source assets (not live)",
  暂无源对象: "No source assets yet",
  "自动数据源发现文件后，版本和解析状态会显示在这里。":
    "Versions and parsing status appear here after a source discovers files.",
  源对象明细: "Source assets",
  源对象分页: "Source asset pagination",
  源对象上一页: "Previous source asset page",
  源对象下一页: "Next source asset page",
  上一页: "Previous page",
  下一页: "Next page",
  文件: "File",
  来源路径: "Source path",
  状态: "Status",
  处理方式: "Processing mode",
  最近发现: "Last observed",
  操作: "Actions",
  真实解析: "Parsing",
  仅登记资产: "Asset registration only",
  查看版本: "View versions",
  "查看 {name} 版本": "View versions of {name}",
  "第 {page} / {pages} 页，共 {total} 个对象": "Page {page} of {pages} · {total} source assets",
} as const;

export const factoryText = createTranslator(factoryMessages);
