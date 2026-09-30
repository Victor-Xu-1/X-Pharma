# 正式验收输入包

本文件用于把代码完成后的正式数据、授权、UAT 和生产验收输入一次性交接给产品、数据、平台、安全、法务和客户团队。它不把本地测试或临时夹具升级为商业证据；只有外部证据归档并由责任人签字后，才能更新 [项目缺口清单](completion-gap-checklist.md) 的勾选状态。

## 当前基线

- 代码候选：当前工作树最新提交，交接前必须保持干净。
- 外部 capability matrix：Goal `v1.9.100`；`41` 项代码级能力已实现。
- 当前正式未闭合项：`global_search`、`personal_team_productivity` 两个业务域，以及 `dense_result_operations`、`personal_productivity_and_delivery`、`state_accessibility_and_responsive_quality`、`performance_and_visual_regression` 四个体验门禁。
- 代码与本地真实链路证据：前端全量 `362/362`，化学保存/刷新回放在真实 Chrome 四视口每次 `4/4`；完整套件两次均为 `123/124`，报告见 [release-evidence.md](release-evidence.md)。该证据不替代正式数据、人工 UAT 或生产环境验证，全球性能/稳定性门禁仍未通过。

## 必须提供的输入

| 输入包 | 对应缺口 | 必须提供 | 责任方 |
|---|---|---|---|
| 参考产品差异审计 | C-02 | 批准参考版本、授权访问记录、12 个外部工作域逐项任务结果、差异结论、适用性判断和产品签字 | 产品/专业用户 |
| 正式数据许可清单 | C-02/C-03/C-04/C-07/D-01/D-02 | 来源合同、字段和地域许可、数据截止时间、撤回规则、租户授权、允许的展示/导出范围 | 法务/数据负责人 |
| 正式数据样本与质量基线 | C-03/C-07/D-03/D-05 | 每个领域真实样本、覆盖率、缺失率、冲突率、freshness、失败 SLA、责任人和可复现快照 | 数据工程/质量 |
| 租户与共享策略 | C-04 | Viewer/Analyst/Admin 角色矩阵、跨租户共享规则、导出审批规则、撤回和审计要求 | IAM/产品/法务 |
| 专业用户 UAT 包 | C-02/C-03/C-04/C-07/C-08/R-09 | 每个核心任务的正/负样本、期望结果 ID、引用和权限结果；至少一名专业用户和一名数据管理员签字 | 产品/UAT |
| 可访问性人工包 | C-05 | 屏幕阅读器、键盘、焦点、对比度、语义和错误恢复记录；目标浏览器/辅助技术版本与缺陷关闭记录 | 可访问性负责人 |
| 系统缩放与设备包 | C-05 | Windows 200%/400% 缩放、目标浏览器和设备矩阵截图/录屏、无阻塞差异结论 | QA/IT |
| 生产 RUM 与负载包 | C-06/I-09/I-10 | 目标用户、设备、地区和版本的 LCP/INP/CLS/TTFB P75，批准 query mix、峰值、长稳、故障注入和 SLO 结果 | SRE/性能/产品 |
| 远程 Agent 生产包 | A-01/A-02/A-03/A-04/A-06/A-07 | TLS/WAF/IdP/OAuth/DPoP、至少两个 Agent 客户端、计量/账单、反搬运演练和审计证据 | Agent/安全/商业 |
| 生产平台与恢复包 | I-01-I-15/R-01-R-11 | 目标 Kubernetes、数据库/OpenSearch/对象存储 HA、PITR、灾备、secret manager、签名 tag、SBOM、渗透测试和上线批准 | 平台/SRE/安全 |

## 验收执行顺序

1. 先冻结来源、许可、租户和参考产品版本，生成带 SHA-256 的正式数据快照和输入清单。
2. 用正式权限矩阵执行正/负 UAT，记录 HTTP/MCP 状态、稳定实体 ID、引用定位、URL 恢复、导出审计和清理结果。
3. 在目标环境运行真实 Chrome/Edge、辅助技术、系统缩放、RUM、负载、故障注入和恢复演练；每个报告绑定 commit/tag、镜像 digest、浏览器版本和数据快照。
4. 由责任人签字后，才更新 `external-workbench-capability-matrix.json`、`completion-gap-checklist.md`、`commercial-readiness.md` 和本文件的状态。

## 不得使用的替代证据

本地 mock、演示数据、临时测试账户、截图推断、只有 URL 回显的查询、没有许可的第三方数据、Codex 内置浏览器布局、仅自动化 axe 结果、localhost MCP、历史报告或未绑定当前提交的镜像，都不能关闭上述正式缺口。
