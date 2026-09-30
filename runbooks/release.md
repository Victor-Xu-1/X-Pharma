# 商业版本发布手册

1. 工作树只包含本版本相关改动，无密钥、数据、缓存、截图或构建产物。
2. 在干净提交上运行 `make check`、`make security-check` 和适用的真实 PostgreSQL/MCP/浏览器/入库测试；本地 Development 可用 `make release-candidate` 自动记录，Pilot 额外传入已注册真实来源的 `--ingestion-source-id` 后自动执行两次入库和隔离恢复，Production 再用 [发布证据链](../docs/release-evidence.md) 的 `capture` 补齐外部门禁。禁止手工把旧报告改名为新版本证据，也禁止把低等级包改名冒充更高等级。
3. 用 `make production-evidence-handoff` 向外部责任方发布 requirements-only 交接包；不得分发可修改的策略副本或预填“通过”的 intake。
4. 在批准的目标环境运行 `make production-topology-live-probe`，把仓库外 `production-topology-report.json`、当前 release-mode 安全证据、非本地环境标识和只读 kube context 作为输入；探针必须真实核对多可用区节点、摘要镜像、PDB/HPA、NetworkPolicy、Gateway/路由和 Web/MCP TLS 入口。它拒绝本地上下文、凭据落盘和覆盖已有报告。将生成的 `production-topology-live-probe.json` 与拓扑声明、至少两项独立部署工件及三角色审批一起写入该类别 intake。
5. 全部外部 intake、工件和审批齐备后，用 `make production-evidence-batch` 原子登记权威策略定义的全部 Production 外部证据；任何类别失败都必须回滚整个暂存批次。
6. 用 `release_evidence.py audit` 或 `make release-audit` 核对目标等级的缺口；Production 只接受当前提交内的权威策略。可用 `RELEASE_STATEMENT_DIRS` 同时读取本地候选和外部批次，只有完整 statement 才能 `assemble`。Production 必须使用组织保管的 Ed25519 密钥和已验证签名 tag，另一台隔离机器必须执行 `verify`。
7. 确认 `alembic heads` 只有一个 head，`alembic check` 无漂移。
8. CI 在干净环境构建镜像；归档 image digest、SBOM 和审计结果。
9. 在预生产用真实 IdP、S3、Temporal、OpenSearch、模型和只读来源执行验收；历史迁移只验证隔离的只读 RAGFlow 离线导出命令，不把它加入运行拓扑。
10. 用真实商业测试账户验证 entitlement、rate card、额度预留/结算/冲正、幂等重试、并发余额、账单对账和计量 fail-closed；成功调用缺少 settlement 时停止发布。
11. 执行正常研究、深分页、字母/数字分片、跨 client 协同、凭据吊销和未授权导出测试，确认明确拒绝、告警和不篡改返回数据。
12. 执行容量、安全和备份恢复门禁，更新 `docs/commercial-readiness.md` 的证据。
13. 将当前候选摘要、备份恢复和生产拓扑报告放入仓库外受控证据根目录，以只读卷提供给 API 并设置 `PLATFORM_EVIDENCE_ROOT`；由管理员在内部工作台核对 schema、状态、迁移版本、队列、模型预算、SLO 和告警责任人。未配置或无效证据必须阻止签字，不能在 UI 中手工改为健康。
14. 创建不可变 Git tag；生产只部署 digest，不部署浮动 tag。
15. 先运行迁移 Job，再滚动 API/MCP/worker/scheduler。
16. 完成两个入口、RLS、真实入库、MCP 跨域数据查询、分页、证据引用和商业结算元数据的发布后烟测。
17. 观察错误率、延迟、队列、数据质量、计量对账和风险告警；达到回滚阈值立即停止发布。

任何未执行项都必须在发布记录中标记为未验证并由有权负责人接受风险，不能静默省略。
