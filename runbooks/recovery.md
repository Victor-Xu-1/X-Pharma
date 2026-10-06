# 备份、恢复与灾备手册

## 不可违反的规则

- 禁止在含真实数据的环境执行 `docker compose down -v`。
- 禁止把未校验的备份直接恢复到生产。
- 禁止只备份 PostgreSQL 而遗漏 S3 原始证据，或反之。
- 密钥从 secret manager 重建，不把明文 `.env` 放入备份包。
- 所有恢复先进入隔离环境，完成 RLS、checksum 和业务对账后才切流量。

## 生产备份策略

| 数据 | 最低策略 | 验证 |
|---|---|---|
| PostgreSQL | 每日全量 + 连续 WAL/PITR，多可用区和跨区域副本 | 每月时间点恢复 |
| MCP usage ledger | 与 PostgreSQL 同一 PITR；结算/outbox/账单引用不可分离恢复 | 按 request/idempotency/rate card 对账，无重复扣费或遗漏 settlement |
| S3 原始证据 | versioning、object lock/保留策略、跨区域复制 | 定期清单和 SHA-256 metadata 对账 |
| Kubernetes 配置 | Git tag、环境 overlay、镜像 digest | 在空集群渲染/部署 |
| Secret | secret manager 自身版本/恢复机制 | 轮换和 break-glass 演练 |
| OpenSearch/搜索投影 | 配置与映射备份；索引从 Raw/Parsed/Canonical 重建 | 已知问题集检索对账 |
| RAGFlow 离线迁移导出 | 独立保管签名/校验后的导出物和映射 | 不属于恢复核心链路，不在灾备环境建立在线连接 |
| Markdown | 可选归档 | 与数据库当前 page version hash 比较 |

建议初始目标为 RPO 5 分钟、RTO 30 分钟；只有实际演练达到后才能写入客户 SLA。

## PostgreSQL 恢复流程

1. 选择目标时间点和最近完整备份，记录恢复工单和负责人。
2. 创建隔离 PostgreSQL 实例，禁止应用连接生产入口。
3. 恢复全量备份并回放 WAL 到目标时间。
4. 使用 migration 身份运行 `alembic current`；只有旧版本才执行向前升级。
5. 运行 `pharma-db-provision` 恢复 runtime grant 和签名 tenant secret。
6. 使用 runtime 身份运行 `pharma-verify-rls`。
7. 对账 tenants、source versions、canonical domain tables、knowledge versions、audit events、usage reservations/settlements、credit balances 和 billing outbox。
8. 抽查多个租户，确认无上下文和伪造上下文都返回零记录。
9. 以恢复点前后的 request/idempotency key 重放商业调用，确认既有调用不重复扣费，未完成预留按策略释放或继续结算，并与外部账单聚合执行差异对账。

## 对象存储恢复

1. 从版本/复制 bucket 恢复到新 bucket，不覆盖唯一健康副本。
2. 对照数据库 `raw_object_uri`、`parsed_object_uri` 和 checksum 清单检查缺失对象。
3. 校验对象 metadata 的 `content-sha256` 与实际内容。
4. 使用只读凭据运行 parser/materialize 抽样测试。
5. 更新环境 bucket 配置后滚动 worker/API，不修改历史数据库 URI，除非执行受审计的 URI 映射迁移。

## 检索投影重建

OpenSearch 不是权威存储。发生损坏时：

1. 停止 projection reconcile，不停止 canonical read。
2. 从 SourceVersion/ParsedDocument 生成待重建清单。
3. 在新 OpenSearch 索引中批量导入并记录失败原因；不得为恢复创建新的 RAGFlow dataset。
4. 用靶点、公司、专利号、项目、实验类型和批次问题做引用对账。
5. 原子切换 tenant search alias/index mapping，并保留旧投影至观察窗口结束。

## 本地集成环境迁移

本地 named volume 只适合研发。需要迁移时先停止写入，分别导出 PostgreSQL、对象卷和 Markdown，再在目标机器的相同代码 tag 上恢复。PostgreSQL custom-format 备份必须按二进制传输，不能通过文本重定向或文本编码工具中转 `pg_dump -Fc`。

## 恢复验收

- 两个入口可用，内部存储端口仍未公开。
- 数据库 head/RLS、OIDC 和 MCP 授权通过。
- 随机对象 checksum、解析页码/slide/sheet locator 正确。
- 自动扫描能识别 unchanged 文件，不重复创建版本。
- 新文件能走完自动入库；失败有持久化 finding。
- MCP 核心领域查询、分页、数据时点、quote、locator、coverage 和内容摘要稳定。
- MCP entitlement、额度、rate card、预留/结算、幂等重试和风险策略恢复；usage ledger 与账单聚合不存在未解释差异。
- 实测 RPO/RTO、告警时间和人工步骤已记录。

## 本地权威备份与隔离恢复演练

本地 Compose 环境使用以下脚本生成可迁移的权威备份。脚本不停止在线服务，不删除卷，也不备份可重建的 OpenSearch/Valkey 数据：

```bash
make backup
make restore-smoke BACKUP_DIR=backups/runtime-YYYYMMDD-HHMMSS
```

备份目录和文件分别使用 `0700` 与 `0600` 权限，并以 partial 目录完成后原子发布。六个权威载荷是业务 PostgreSQL、全局角色、Temporal、Temporal visibility、对象证据卷和 Markdown 卷；manifest 同时记录镜像 ID、Alembic head、实际表的精确行数和 SHA-256 清单。备份前后业务表计数发生变化时脚本会失败，不发布不一致快照。

新备份还记录实际 PostgreSQL 管理员和三个数据库各自的 owner。隔离演练与完整恢复共用已校验的清单解析器，不假定管理员或 owner 必须为 `pharma_app`；只接受安全标识符，拒绝保留库名和不完整元数据。原始 v1 备份仅保留已记录的默认 `pharma_intel/pharma_app` 合同；非默认旧部署缺少身份元数据时必须重新备份，不能猜测角色或修改原备份。完整恢复需要所有指定摘要镜像已在本机，缺失时失败，不自动联网拉取。

隔离恢复演练只使用新临时容器/临时卷，并执行：

1. 所有文件 SHA-256 校验。
2. PostgreSQL 全局角色与数据库恢复。
3. 表清单和逐表精确行数对账。
4. Alembic head 对账。
5. 使用 `NOSUPERUSER NOBYPASSRLS` 临时角色执行真实 `pharma-verify-rls`。
6. 对象证据和 Markdown 归档完整性与解压测试。
7. 无论成功或失败都删除隔离容器和临时卷，保留原备份供审计。

只有目标 Compose 项目不存在任何权威卷时，才可以执行完整恢复：

```bash
./scripts/restore-runtime-linux.sh /absolute/path/to/backups/runtime-YYYYMMDD-HHMMSS
```

完整恢复脚本拒绝覆盖已有卷。恢复完成后先执行 `make status`、`make search-rebuild` 和本节恢复验收，再允许切换流量。

生产环境仍必须使用云数据库连续 WAL/PITR、S3 versioning/object lock 和跨区域复制；本地脚本提供迁移与恢复契约证据，不能替代云平台的 RPO/RTO 演练。

## Interrupted Browser Acceptance Recovery

An interrupted local browser acceptance run can leave only explicitly marked fixture state: entities with `acceptance_fixture=true` in the default tenant and `e2e-*@example.test` accounts. Do not use the runtime API identity to remove that graph: it intentionally lacks ownership of append-only history tables.

1. Create and verify a runtime backup first. The backup SHA must be the verified `postgres.dump` checksum.
2. On Linux/WSL, run `./scripts/run-browser-acceptance.sh --recover-interrupted-run`. This reuses the tested cleanup order and refuses success unless the temporary-account and fixture-entity counts are zero.
3. On Windows Docker Desktop, run the native recovery entry with an explicit confirmation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\recover-interrupted-browser-acceptance.ps1 `
  -Apply -Confirmation CLEAN_SYNTHETIC_RUNTIME_DATA `
  -BackupSha256 <verified-postgres-dump-sha256> `
  -BackupDirectory <verified-runtime-backup-directory>
```

4. Verify `pharma-runtime-hygiene` reports zero findings and record the backup hash plus the recovery output in the incident log.

The recovery paths deliberately leave inactive historical test tenants untouched. They are quarantined audit records, not active user or agent data.

`pharma-runtime-hygiene` also fails when an inactive synthetic test tenant retains an entity, data source, source document, or knowledge page. Empty historical test-tenant shells remain a retention decision, not a virtual knowledge base.

## Unknown Alembic revision recovery

If `alembic current` or the migration container reports a revision that is absent
from the image's `migrations/versions` graph, treat the database as an incompatible
historical volume. Do not edit `alembic_version`, run `alembic stamp`, or start the
application against it to make the health check pass.

1. Keep the original volume stopped or read-only and create a verified runtime backup.
2. Identify the exact source tag/image that created the recorded revision, including
   its migration file and schema checksum. A similarly named current migration is
   not sufficient evidence.
3. Restore the backup into an isolated PostgreSQL instance and compare the schema,
   roles, RLS policies, and authoritative row counts with the current release.
4. Apply a reviewed forward-compatibility migration or restore into a fresh volume
   using an audited data migration. Preserve the original volume until application,
   search projection, RLS, and record-level reconciliation pass.
5. Record the source revision, migration plan, backup hash, row-count reconciliation,
   rollback point, and approval before changing the customer runtime.

The local verification on 2026-08-09 found `a7d2e9f4c160` in the existing core
volume, while the current source graph ends at `8c6d2e4f1a90`. A new isolated volume
completed the current migration chain; the historical volume remains unmodified.

## Docker Desktop reports running while the guest engine is unavailable

Docker Desktop's GUI or `docker desktop status` can report `running` while the
Linux guest engine, API proxy, or guest database is unreachable. Typical symptoms
are Docker client calls that never return, guest proxy connection refusals, and
`/health/ready` returning `503 Database unavailable` on every application entry.
The HTTP response proves that the dependency is unavailable; it does not prove
that a database volume was deleted or corrupted.

1. Stop issuing concurrent Docker management commands. Identify and terminate
   only CLI clients started by the current recovery attempt; do not terminate
   Docker Desktop background processes, WSL infrastructure, or unrelated tasks.
2. From the repository in WSL, run the bounded preflight below. It performs no
   restart, Compose mutation, or volume operation and fails before the service
   loop when the engine API does not answer:

   ```bash
   PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS=15 ./scripts/status.sh
   ```

   The timeout accepts integer values from 1 through 300 seconds. Every Docker
   and Compose call made by the status script uses this bound, and the 120-second
   service-readiness loop uses wall-clock time rather than a fixed call count.
3. Treat `docker desktop status` as supporting information only. The recovery
   gate is a successful server response from `docker --context default version`,
   followed by HTTP `200` from the intended `/health/ready` endpoints.
4. Do not automatically restart Docker Desktop or WSL, delete volumes, recreate
   databases, or run broad cleanup. Record the affected entrypoints, temporary
   users/sessions/audit rows, candidate containers/images, and the last verified
   backup before requesting an operator-approved restart.
5. After the engine recovers, first query the recorded temporary resource IDs,
   delete them in their reviewed dependency order, and prove user/session/audit
   counts are all zero. Remove only the named candidate container and image, then
   confirm the production containers and volumes were not replaced.
6. Re-run the bounded status check and the affected human/MCP acceptance path.
   A healthy GUI, a successful Docker CLI probe, or an HTTP liveness response is
   not a substitute for database readiness and the real user-path verification.
