# OpenSearch 投影运维手册

OpenSearch 是可重建检索投影，不是权威数据库。PostgreSQL 保存 Canonical、Evidence、outbox 和 delivery 状态，对象存储保存不可变 Raw/Parsed 内容。任何恢复和重建都只能沿这个方向写入 OpenSearch，禁止从索引反向覆盖权威数据。

## 运行边界

- 产品公开入口仍只有人员工作台和 Agent MCP；OpenSearch 不创建公网 Ingress。
- 本地 Compose 固定使用经 digest 锁定的 OpenSearch 3.7.0，仅绑定 `127.0.0.1:9200`，安全插件关闭只适用于单机集成。
- 生产必须使用 HTTPS、证书校验、至少一个 replica、跨可用区节点、静态/传输加密和定期 snapshot repository。
- query role 仅供 API 使用，只允许读取三组 read alias，以及 readiness 所需的 cluster info/health、alias、mapping 和 search pipeline GET；禁止模板、pipeline、alias、索引和文档写入。
- jobs role 仅供统一 `pharma-jobs` 和受控重建 Job 使用，允许版本化 template/pipeline、物理索引、alias 与投影写入；禁止挂载到 API、parser、OCR 或 ClamAV。query/jobs 两个角色由独立 OpenBao 路径轮换。
- index 名称、alias、routing 和 DSL 由服务端固定，Web/MCP 调用者不能提供这些内部参数。
- Production 必须启用 `SEARCH_SEMANTIC_ENABLED`，通过独立最小权限 `SEARCH_EMBEDDING_API_KEY` 调用受治理模型网关；模型、维度、混合权重和候选上限属于发布配置，变更前必须重建与重评。

## 日常检查

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search ensure
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search status
docker compose -f compose.yaml -f compose.dev.yaml logs --since 30m worker
```

`status` 必须满足：

- cluster version 为受支持的 OpenSearch 3.x，health 为 `green`；本地单节点无 replica 时允许 `yellow`。
- `entities`、`evidence`、`knowledge` 的 read/write alias 都存在且指向预期物理索引。
- `pending`/`retry` 能持续下降，`processing` 不长期超过 lease 时间，`dead` 为零。

API readiness 在配置为 OpenSearch 时会检查集群可达。管理员还可通过工作台后端的 `/api/v1/admin/search/status` 查看相同边界信息；该 API 需要管理员会话，不能暴露为第三个入口。

## 投影与重试

统一 `pharma-jobs` 内的 search-projector 角色按租户消费 transactional outbox。每个 event/consumer 组合只有一条 delivery；外部索引写入使用确定性 document ID，因此进程在“索引成功、数据库提交前”崩溃时可安全重放。

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search drain --max-batches 1000
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search retry-dead
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search retry-dead --tenant-id <tenant-uuid>
```

重试有最大次数和指数退避。进入 dead 后不得无调查直接循环重放：先记录事件 ID、租户、错误类型、mapping/version、源对象 checksum 和修复工单；修复确定性根因后再执行显式 replay。

## 全量重建与原子切换

重建适用于 mapping 升级、索引损坏或恢复演练。它创建新的物理索引，直接从 PostgreSQL/对象存储重建全部租户数据，校验精确计数后原子切换 alias。旧索引保留观察窗口，不在命令内自动删除。

从 v1 lexical 索引升级到 v2 hybrid 索引时，必须先验证 embedding gateway 的模型 ID 与输出维度，再在批准的维护窗口停止统一 jobs 并执行全量重建。停止 jobs 会同时暂停自动入库、调度、监控和 billing delivery，操作前必须确认无在途工作并在结束后逐角色验证积压恢复。不能只更新 template 后继续向 v1 alias 写入；v2 切换前每个应检索文档都必须有非零、有限、维度完全匹配的向量。查询和投影任一侧模型不可用时保持失败关闭，不自动回退到 lexical 冒充同等检索质量。

```bash
docker compose -f compose.yaml -f compose.dev.yaml stop worker
docker compose -f compose.yaml -f compose.dev.yaml run --rm worker pharma-search rebuild --build-id 20260716-release1
docker compose -f compose.yaml -f compose.dev.yaml start worker
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker pharma-search status
```

切换前至少验证：

1. Canonical 实体数与新 `entities` 文档数一致。
2. 当前 Parsed/Evidence 应投影记录均存在，抽样 locator、source version、checksum 可回到原文。
3. 两个租户使用相同搜索词时互不可见。
4. 靶点、公司、专利号、项目名、实验类型和化合物批次金标查询达到批准的相关性门槛。
5. Web 与 MCP 对同一身份/筛选返回一致实体集合，MCP 仍执行 entitlement、计量和反枚举门禁。
6. hybrid 查询返回 `retrieval_mode=hybrid` 与正确 `embedding_model`，低于批准 `SEARCH_SEMANTIC_MIN_SCORE` 的近邻不会为凑满结果而返回，深分页未超过固定候选上限，模型超时、错误维度、NaN 和零向量均失败关闭。
7. readiness 逐一确认三个 read alias 只指向一个活动索引，索引 `_meta`、projection、`knn_vector` 维度与配置一致，且版本化 normalization pipeline 内容未漂移；任一不满足都不得接流量。

如新索引有缺陷，停止 projector，用一次 alias update 把全部 read/write alias 切回上一个物理索引，然后恢复上一兼容应用版本。不要逐个 alias 手工切换造成混合 schema。修复后重新创建新 build，不复用失败索引。

## 故障处理

| 现象 | 处理 |
|---|---|
| readiness 失败 | 检查 DNS/TLS/凭据、集群 health 和磁盘水位；保持两个入口 fail closed，不切换到数据库模糊搜索冒充生产检索 |
| delivery 持续 retry | 按 error class 检查 mapping、对象 checksum、网络和超时；确认是暂时故障后等待有界退避 |
| delivery dead | 建立工单并修复根因，按租户或全局显式 replay，核对前后计数 |
| alias 缺失/混合版本 | 在维护窗口停止统一 jobs，依据发布记录一次性恢复完整 alias 集；运行 `status` 和金标查询后再恢复流量 |
| 索引数据疑似越租户 | 立即关闭人员/MCP 两个入口并按 P0 响应；保留审计证据，验证 routing、tenant filter、RLS 和测试样本 |
| 磁盘/分片故障 | 先恢复集群容量；权威数据健康时可在新集群执行全量 rebuild，不能删除 PostgreSQL/outbox 来消除积压 |

## 备份与恢复证据

OpenSearch snapshot 用于缩短 RTO，但不能替代 PostgreSQL PITR 和对象存储版本化。每次生产发布归档 mapping/template 版本、alias 清单、集群版本、镜像 digest、索引计数、dead delivery 数、金标评估和重建耗时。季度至少从空集群执行一次全量重建并记录实际 RTO；只有演练达到批准指标后才能写入客户 SLA。
