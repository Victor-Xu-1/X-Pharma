export const factoryOverviewMessages = {
  自动入库运行状态: "Ingestion status",
  "{active} 已启用 · {ready} 就绪": "{active} active · {ready} ready",
  "{count} 个来源未观测到就绪状态": "Readiness not observed for {count} sources",
  "第三方 LLM API": "Third-party LLM API",
  "远程 API 已配置": "Configured",
  已配置但未启用: "Configured, not enabled",
  待配置: "Not configured",
  "远程 API · {model}": "Remote API · {model}",
  未绑定第三方API: "No third-party API bound",
  最近运行: "Latest run",
  暂无: "None",
  等待数据源: "Waiting for a source",
  上次读取的状态: "Previously read state",
  "配置状态不代表 API 实测可用或某次抽取已完成。":
    "Configuration does not prove API availability or a completed extraction.",
} as const;
