# 平台迁移与可移植性

## 原则

目标架构不依赖当前 Windows 用户名、盘符、Docker Desktop volume 名或手工创建文件。项目代码、迁移、依赖锁、镜像定义和生产清单均应由 Git 干净克隆复现。

原始资料保持只读且不做原地迁移。平台迁移的是数据库、不可变对象、配置和索引投影，不是重新整理用户目录。

## 迁移单元

| 单元 | 权威性 | 迁移方式 |
|---|---|---|
| Git 仓库 | 代码权威 | 克隆固定 tag/commit，CI 重建签名镜像 |
| PostgreSQL | 主数据权威 | 一致性全量备份 + WAL/PITR；先迁移再切流量 |
| MCP usage ledger | 商业结算权威，位于 PostgreSQL | 与主库同一一致性点迁移；按 request/idempotency/rate card/余额和账单引用对账 |
| S3 对象 | 原始证据权威 | 版本化复制并校验 key、size、SHA-256 metadata |
| 企业来源目录 | 外部权威 | 新环境按相同逻辑路径只读挂载，更新 source root 映射 |
| Markdown | 下游投影 | 可复制，也可从知识页版本确定性重建 |
| OpenSearch | 目标下游投影 | 从 Canonical + Parsed/Evidence 重建并做检索金标对账 |
| RAGFlow | 隔离的离线迁移源 | 只读导出仍未转入 Raw/Evidence 的历史内容；不向新环境配置在线连接 |
| 密钥和 OIDC | 环境配置 | 从目标 secret manager 重新物化，不复制明文 `.env` |

## 蓝绿迁移顺序

1. 在隔离目标环境部署同版本应用和空托管依赖。
2. 校验镜像 digest、配置、OIDC redirect URI、MCP resource URL 和网络策略。
3. 恢复 PostgreSQL 到目标时间点，执行 `alembic upgrade head` 和 `alembic check`。
4. 运行 `pharma-db-provision`，确认 runtime role 非 superuser 且不具备 `BYPASSRLS`。
5. 复制 S3 对象并抽样/全量校验 checksum metadata。
6. 只读挂载来源目录；先禁用 scheduler，执行手工小样本对账。
7. 重建 OpenSearch 投影，比较文档数、版本数、失败数和代表性检索引用；历史 RAGFlow 仅用离线导出清单做剩余内容对账。
8. 运行人员登录、MCP 核心数据查询、证据引用、分页、RLS、真实入库和恢复烟测。
9. 使用隔离商业账户验证 entitlement、rate card、额度预留/结算、幂等重放、签名游标、累计覆盖限制和账单聚合对账。
10. 短暂停写，做最终增量同步；冻结旧环境新预留，处理 in-flight settlement 后再切换两个 DNS 入口。
11. 保留旧环境只读至回滚窗口结束，之后按数据保留策略销毁。

## 回滚条件

任一情况立即停止切流或回滚：

- 迁移版本与镜像期望 head 不一致。
- RLS verifier 失败或出现跨租户可见记录。
- 对象 checksum、来源版本数或关键引用对账失败。
- OIDC/MCP audience、scope 或 tenant claim 不符合契约。
- usage ledger 余额/预留/结算、幂等记录或外部账单聚合存在未解释差异。
- 错误率、P95 延迟或入库失败率超过已批准阈值。

迁移不执行数据库降级来回滚。应用切回旧环境，目标环境保留用于根因分析；修复后重新从受控备份前滚。
