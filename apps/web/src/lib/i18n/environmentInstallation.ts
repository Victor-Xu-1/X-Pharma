export const environmentInstallationMessages = {
  受控安装与修复: "Controlled installation and repair",
  "只安装本项目的锁定依赖。网页生成计划；主机侧明确确认后执行，不重启 WSL、不停止其他项目。":
    "Install only this project's locked dependencies. The page prepares a plan; execution requires explicit host-side confirmation. It does not restart WSL or stop other projects.",
  选择安装范围: "Choose installation scope",
  "前提：{items}": "Prerequisites: {items}",
  "仅使用离线缓存（缺失时失败，不自动联网）": "Use offline cache only (fail if unavailable; no automatic downloads)",
  "先在主机侧检测并接入有效报告。": "Inspect the host and connect a valid report first.",
  "源码有未提交变更；请使用干净版本后重新检测。": "The source has uncommitted changes; inspect a clean revision again.",
  "正在生成…": "Preparing…",
  生成安装计划: "Prepare installation plan",
  已生成的安装计划: "Prepared installation plan",
  "安装计划已生成，尚未执行": "Installation plan prepared, not executed",
  "模式：{mode} · 绑定源码 {revision} · 计划 {id}": "Mode: {mode} · Bound source {revision} · Plan {id}",
  离线: "Offline",
  允许联网: "Network access allowed",
  下载安装计划: "Download installation plan",
  "将计划保存到 E 盘，由本地主机运行以下命令。执行器会复查版本、锁文件和有效期，并记录真实结果。":
    "Save the plan on the E drive and run the command on the local host. The executor rechecks the revision, lockfiles and expiry, and records actual results.",
  如何接入主机检测报告: "How to connect a host inspection report",
  "由本地运维运行只读检测，并将报告目录只读挂载给网关；不向网页暴露 Docker socket 或私人配置。":
    "Local operations run read-only checks and mount the report directory read-only for the gateway. The page has no Docker socket or private configuration access.",
  "请选择当前提供的安装范围。": "Choose an installation scope currently available.",
  暂无安装范围: "No installation scopes available",
  "当前没有可用配方；刷新状态后再检查。": "No recipes are currently available; refresh the status and check again.",
  "该范围不支持离线缓存。请选择其他范围，或明确取消离线限制。":
    "This scope does not support offline cache. Choose another scope or explicitly turn off the offline-only restriction.",
} as const;
