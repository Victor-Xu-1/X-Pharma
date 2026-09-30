# ADR 0012: 统一应用进程拓扑

- 状态：Accepted
- 日期：2026-07-29
- 决策所有者：平台架构、后端、数据和安全

## 背景

此前默认运行线把 API、MCP、Temporal worker、scheduler、OpenSearch projector、search maintenance、monitoring 和 billing delivery 分成多个业务容器。这些角色共享同一代码、领域模型、数据库和发布节奏，独立 Deployment 没有形成足够强的安全或数据权威边界，却增加了部署、密钥、网络策略、健康检查、发布证据和故障排查成本。

产品仍要求两个公开入口、自动入库、可重建检索、监控、商业计量和远程 Agent 调用。进程收敛不能删除这些能力，也不能把不可信文档解析移回持有业务凭据的进程。

## 决策

业务运行面最多保留三条常驻应用进程线：

1. `pharma-gateway`：单个 ASGI 进程承载 Web、HTTP API 和 Streamable HTTP MCP。`/mcp` 与 OAuth protected-resource metadata 路由到 MCP application，其余路径路由到 FastAPI application；两者共享一个受控 lifespan。MCP adapter 使用 loopback HTTP 调用同进程领域 API，保留现有认证、授权、计量和审计边界。
2. `pharma-jobs`：单个 Python 进程以受监督线程运行 Temporal worker/scheduler、OpenSearch projector/maintenance、monitoring 和启用后的 billing delivery。所有角色共享停止事件；任一角色异常或无故退出都使进程失败。关闭使用一个全局截止时间。每个角色继续发布独立心跳，容器健康检查必须验证所有启用角色新鲜、进程存在且 PID 完全相同。
3. `pharma-parser-service`：继续作为不可信文件解析安全边界，不持有平台数据库、对象存储、OIDC、MCP、AI 或 billing 凭据。

PostgreSQL、Valkey、OpenSearch、Temporal、对象存储和 OpenTelemetry 是基础设施。ClamAV 与可选 OCR 是受限文档处理依赖。它们不属于业务进程线，不得成为公开产品入口。OCR 继续独立是因为其大体积本地推理运行时、模型供应链和资源配额与生成式 LLM 无关；生成式 LLM 仍只允许第三方 HTTPS API。

Compose 只常驻 `api`、`worker`、`parser` 三个应用镜像服务。Kubernetes 只保留 `pharma-api` 和 `pharma-jobs` 两个业务 Deployment，parser/OCR/ClamAV 使用独立安全或基础设施清单。横向扩容复制进程类型，不新增按功能拆分的业务 Deployment。

旧的 `pharma-api`、`pharma-mcp`、`pharma-worker`、`pharma-search-projector`、`pharma-search-maintenance`、`pharma-monitoring-worker` 和 `pharma-billing-provider` CLI 可暂时保留用于隔离测试、运维和兼容探针，但不得进入默认 Compose/Kubernetes 运行拓扑。

## 取舍

- 收敛减少服务发现、容器数量、Secret 消费者、NetworkPolicy 和发布单元，但增大 jobs 内部角色的共同故障域。
- jobs 的 CPU/内存扩容会同时复制所有角色，不能独立调整某一个角色副本数。当前角色均具有 Temporal 幂等、数据库租约、`SKIP LOCKED` 或 transactional outbox 去重，因此允许多副本共同运行。
- MCP 与 Web/API 共进程减少内部网络跳转，但不能合并权限模型。MCP OAuth、DPoP、scope、商业权益、预留/结算和防提取门禁仍在 MCP 路径执行。
- parser、OCR 和 ClamAV 不并入 gateway/jobs，因为不可信输入、模型资源和病毒库形成可证明的安全与资源隔离边界。

若真实容量或故障数据证明某角色需要独立扩容，必须先提供负载、故障隔离和运维收益证据，再通过新 ADR 修改本决策；不得仅以“微服务更企业级”为理由拆分。

## 验收

- Compose 合并所有默认 overlay 后只能出现 `api`、`worker`、`parser` 三个常驻应用服务，退役服务不能被 telemetry/profile 覆盖层复活。
- Web/API 与 `/mcp` 由同一 gateway PID 服务；readiness 同时验证 API 200 和匿名 MCP 401。
- jobs 健康检查覆盖全部启用角色并验证同一 PID；任一角色失败会停止兄弟角色，超时关闭失败可观察。
- Kubernetes Deployment、Service、Gateway route、Secret、NetworkPolicy、HPA、PDB 和生产拓扑证据只引用当前工作负载。
- 真实 Compose、MCP、自动入库/搜索、浏览器和关闭重启路径必须通过；静态 YAML 或单元测试不能单独作为完成证据。

## 结果

本决策不改变两个公开产品入口、领域 API、MCP 工具、数据权威、计量或审核语义，只改变进程和部署拓扑。后续新增后台能力默认作为 `pharma-jobs` 内的新受监督角色实现；新增公开路径默认由 `pharma-gateway` 承载。
