# Kubernetes 生产部署

本文件记录当前可运行清单。最终生产技术线以 [GOAL.md](../GOAL.md) 第 11 节、[ADR 0004](adr/0004-open-source-technology-baseline.md) 和 [ADR 0005](adr/0005-mcp-commercial-metering-and-anti-extraction.md) 为准；Compose 已迁移到 PostgreSQL 18.4 和固定 RDKit 2026.03.3 cartridge 镜像，完成新旧卷双向演练、权威结构 schema、真实 exact/substructure/similarity 查询和收费 MCP 计算量结算。托管 HA/PITR 与化学检索规模压测仍未验收。OpenSearch 3.7 核心投影已进入代码和清单，但大规模相关性、容量和恢复验收尚未完成。业务运行面已收敛为 `pharma-api` 统一网关与 `pharma-jobs` 统一后台任务两个 Deployment；parser/OCR/ClamAV 仅作为不可信文件处理的隔离边界。MCP 商业计量、财务对账、billing-account 级跨 client/网络/凭据风险关联和受审批异步导出已实现，但目标 Envoy 的 DPoP/mTLS 持有证明、全局限流和客户真实 ERP/支付账户尚未完成生产验收，不能据此宣称开放收费 MCP。

## 前提

- Kubernetes 1.30+，支持 Pod Security `restricted`、HPA v2、PDB 和 NetworkPolicy。
- Envoy Gateway、公网入口证书、内部 parser/OCR 服务证书、WAF/限流策略。
- 托管 PostgreSQL 18 + RDKit HA/PITR、S3、OpenSearch 3.x、Temporal、TLS Valkey、企业 OIDC、模型网关。
- 支持 `ReadWriteMany` 的 Markdown 导出卷、只读企业来源卷和只读 OCR 模型卷。
- 私有镜像仓库和外部 secret manager。

清单位于 `deploy/kubernetes/base`，是生产基线模板，不包含任何真实密钥。

## 必须替换

部署前建立 overlay，至少替换：

- `ghcr.io/replace-org/...` 为已签名镜像 digest。
- `workspace.example.com`、`mcp.example.com`、OIDC URL 和 redirect URI。
- PostgreSQL、Valkey、OpenSearch、Temporal、S3、模型网关地址。
- S3 bucket、区域、三个 storage class、公网 TLS Secret 名称，以及 parser/OCR 服务端与客户端证书的企业 PKI/cert-manager 签发方式。
- `MCP_TRUSTED_PROXY_CIDRS` 占位值必须替换为 Envoy 及配置跳数内所有受信上游代理的精确 CIDR。
- 资源 requests/limits、HPA 上限和拓扑策略。

不要直接编辑 base 存放客户密钥或域名；每个环境使用独立 Kustomize overlay。

## 发布前 API Server 验证

生产候选必须在临时 kind API Server 中安装固定版本的 Envoy Gateway、External Secrets 和 OpenTelemetry CRD，再对 base 清单执行 server-side dry-run：

```bash
make kubernetes-acceptance \
  KUBERNETES_EVIDENCE=manifests/runtime/acceptance-smoke/kubernetes.json
```

脚本默认使用 `${XDG_CACHE_HOME:-$HOME/.cache}/pharma-intelligence/kubernetes-assets`。缓存条目按预期 SHA-256 命名、在读取时重新计算摘要，并通过文件锁防止并发发布半成品；摘要不匹配、符号链接或非普通文件不会被信任。冷缓存从固定 HTTPS URL 下载并做有界重试和断点续传，热缓存不访问上游。受控构建环境可以用 `--asset-cache DIR` 指定持久缓存，或用 `--asset-mirror-prefix https://mirror.example/` 经过 HTTPS 镜像传输；镜像不能替代仓库中的固定摘要。缓存目录只含可重新获取的公开构建资产，不得放入 Git、发布证据包或备份权威数据。

结构化报告使用 `pharma.local-kubernetes-validation.v3`，记录冷/热缓存命中数、Kubernetes 服务端版本、固定 node image digest、三节点拓扑、CRD 组数、server-side dry-run、ClamAV 跨 worker/测试 zone 双副本实际运行、持久卷、单 Pod 替换、恶意样本阻断和临时集群清理结果。受控 kind 实测会先校验生产清单中的 ClamAV 固定镜像摘要，再为该本地集群创建临时标签并仅在动态测试清单中覆盖为 `imagePullPolicy: Never`；生产清单仍以原始 digest 完成 server-side dry-run，报告会显式记录覆盖引用和摘要校验结果。下载失败、摘要错误、API Server 拒绝资源、两个副本未跨节点/zone、任一时刻 Service 无 Ready 扫描副本、PVC 或布局身份变化、EICAR 未阻断或集群未清理都会使门禁失败。报告固定为 `production_claim=false`；目标集群的真实存储、CNI、镜像源、容量、真实节点/可用区故障和审批仍须另行提供 Production 证据。

## Secret 契约

按 `deploy/kubernetes/secret-contract.env.example` 的路径说明，从 secret manager 分别物化平台、文档处理、检索、模型、计费和迁移 Kubernetes Secret。要求：

- migration/runtime PostgreSQL 身份分离。
- human JWT、internal JWT、tenant context、MCP cursor、MCP correlation HMAC、billing statement、export manifest signing secret 和 API key salt 相互独立。
- 在 `production/document-processing` 创建独立的 `parser_service_token` 与 `ocr_service_token`；ESO 将其物化为 `pharma-document-processing-secrets`。两者至少 32 字节、互不相同且独立于所有平台签名密钥，只授予统一 jobs 进程及各自的隔离服务；不得把 parser 配置为进程内回退。
- OIDC、对象存储和 AI 治理模型凭据按最小权限授权。OpenSearch 必须创建独立 query/jobs 账号：query 账号只挂载 API 并只允许 cluster/readiness 元数据与三组 read alias 查询；jobs 账号只挂载统一 jobs 进程并允许版本化 template/pipeline、物理索引、alias 和投影写入。两个账号不得复用密码，也不得放入 `production/application` 通用 Secret。
- AI provider 能力必须在生产 ConfigMap/overlay 中显式声明：`AI_RESPONSE_FORMAT_MODE=json_schema|json_object|prompt_only`、`AI_THINKING_MODE` 和 `AI_INCLUDE_SCHEMA_IN_PROMPT` 必须与获批供应商契约一致。使用 MiMo 等会因 `response_format` 中止的 provider 时，必须选择 `prompt_only` 并打开 schema-in-prompt；服务端 Pydantic 校验仍是最终边界，不能以放宽校验换兼容。
- 轮换前验证双密钥/会话失效策略；禁止把 Secret YAML 提交 Git。

Embedding 使用独立 OpenBao 路径 `production/embedding` 和 ESO Secret `pharma-embedding-secrets`，只挂载到 `pharma-api` 与 `pharma-jobs`。该凭据只能调用批准的 embedding 模型，不能授予聊天、管理或其他模型权限；parser、OCR 和 ClamAV 不得读取。API/jobs 在构造 embedding 适配器时会立即校验，缺失时 readiness/启动失败关闭。轮换由 Reloader 触发这两个 Deployment 滚动更新，并在切换后执行 hybrid 查询与投影探针。

OpenSearch query/jobs 凭据分别存放在 `production/opensearch/query` 与 `production/opensearch/jobs`，由 ESO 物化为 `pharma-opensearch-query-secrets` 与 `pharma-opensearch-jobs-secrets`。前者只挂载 API，后者只挂载统一 jobs；Reloader 只滚动对应 Deployment。实际 OpenSearch client 在生产模式下缺少任一用户名/密码时立即失败关闭。

另由企业 PKI 或 cert-manager 分别物化 `pharma-parser-server-tls` 和 `pharma-parser-client-tls`，每个 Secret 包含 `tls.crt`、`tls.key` 和 `ca.crt`。服务端证书必须有 `serverAuth`、覆盖 `pharma-parser` 的集群 DNS SAN；客户端证书必须有 `clientAuth` 并绑定 jobs 身份。parser 只从服务端 Secret 读取私钥、从客户端 Secret 读取 CA；jobs 只从客户端 Secret 读取私钥、从服务端 Secret 读取 CA。两个 Deployment 监听两个 Secret 轮换，轮换后必须验证双向信任和在途 Temporal activity 重试。

OCR 使用独立的 `pharma-ocr-server-tls`、`pharma-ocr-client-tls` 和 `OCR_SERVICE_TOKEN`，不得与 parser 复用私钥或 token。服务端证书覆盖 `pharma-ocr` DNS SAN；模型由 `pharma-ocr-models` 只读卷提供并在 Pod 启动时按仓库 manifest 重新计算摘要。完整操作边界见 [OCR 服务](ocr-service.md)。

## 部署顺序

```bash
kubectl kustomize deploy/kubernetes/base >/tmp/pharma-rendered.yaml
kubectl apply --server-side -f /tmp/pharma-rendered.yaml
kubectl -n pharma-intelligence wait --for=condition=complete job/pharma-migrate-0-1-0 --timeout=15m
kubectl -n pharma-intelligence rollout status deployment/pharma-api --timeout=10m
kubectl -n pharma-intelligence rollout status deployment/pharma-jobs --timeout=10m
kubectl -n pharma-intelligence rollout status deployment/pharma-parser --timeout=10m
kubectl -n pharma-intelligence rollout status deployment/pharma-ocr --timeout=15m
```

生产发布流水线应先独立运行迁移 Job，确认成功后再滚动工作负载。示例 base 为便于审查将资源放在一起，不能依赖无序 `kubectl apply` 自动保证迁移先于新应用。

搜索 mapping 或 embedding 维度变化时，在启动新 jobs 版本前按 [OpenSearch 运维手册](../runbooks/opensearch-operations.md) 创建并校验新版本物理索引，再一次性切换三个 alias。开启 semantic search 时若 alias 仍指向旧 schema，API readiness 和 jobs 启动都会失败关闭；不能通过临时关闭校验绕过重建。

每次含数据库迁移的版本更新 Job 名；旧 Job 可由 TTL 清理。迁移只允许向前，回滚应用时不自动执行 Alembic downgrade。

迁移 `2b5e8f1a7c93` 退出不属于产品边界的固定 Research Bundle/PPT 模块。它只在旧 `research_bundles` 表为空时删除该表；检测到任何历史行都会失败关闭。升级已有环境前必须按数据许可和审计流程导出历史产物、取得数据负责人确认并清空旧表，不能通过修改迁移或关闭检查强行删除。

## 运行角色

| Deployment | 默认副本 | 作用 |
|---|---:|---|
| `pharma-api` | 3，HPA 至 30 | 单个 `pharma-gateway` 进程承载工作台、BFF、内部领域 API 和远程 MCP；两个公开 host 进入同一 Service |
| `pharma-jobs` | 3，HPA 至 30 | 单个 `pharma-jobs` 进程监督 Temporal worker/scheduler、搜索 projector/maintenance、监控和 billing delivery 线程 |
| `pharma-parser` | 3，HPA 至 50 | 无业务凭据、无主动出站的隔离文档解析服务；每 Pod 一个有界解析子进程 |
| `pharma-ocr` | 3 | 无业务凭据、无主动出站的 PP-OCRv5 扫描件识别服务；每 Pod 一个推理槽 |

统一 jobs 的每个副本都运行相同角色集合；Temporal 固定 workflow ID、数据库租约、`FOR UPDATE SKIP LOCKED` 和幂等 outbox 使副本可安全接管。任一角色意外退出会触发共享停止事件，Pod 失败并由 Deployment 重启；readiness 还会校验所有角色心跳来自同一个 PID。

## 网络与入口

仅创建两个公开 HTTPRoute：

- 工作台 host -> `pharma-api:8080`
- MCP host -> `pharma-api:8080` 的 `/mcp`

商业 MCP 上线时目标 Envoy Gateway 必须在 MCP route 同时启用本地突发、全局分布式和带宽限制。base 中 `MCP_TRUSTED_PROXY_CIDRS=REPLACE_WITH_EXACT_TRUSTED_PROXY_CIDRS` 会使应用启动校验失败；目标 overlay 必须替换为 Envoy 实际 Pod CIDR 以及配置跳数内所有受信上游代理 CIDR，并按真实 LB/Envoy 链设置 `MCP_TRUSTED_PROXY_HOPS`。Envoy 必须删除客户端传入的 forwarding 头并按已验证代理链重建 `X-Forwarded-For`；生产请求若绕过可信代理、代理链不足或含未受信中间跳会失败关闭。`MCP_CORRELATION_HMAC_SECRET` 从 OpenBao 注入且独立于其他签名密钥，`MCP_CORRELATION_KEY_ID` 变更需要与风险窗口和审计留存协调。应用层执行 subscription/entitlement、PostgreSQL 额度预留/结算、统一签名游标、客户累计唯一覆盖、client/网络/凭据相关性和独立导出策略。OIDC `cnf` 在本层用于已签名确认键相关性；生产仍必须由目标 Envoy/IdP 验证 DPoP 或 mTLS 持有证明，不能仅凭存在 `cnf` 就认定 sender constraint 已验收。

默认 NetworkPolicy 拒绝所有流量，再显式允许 Envoy Gateway 到统一 API、DNS 和受限服务端口出站。parser/OCR 不使用平台通用 egress 策略，也没有 DNS/公网出站；只允许统一 jobs 分别调用 8070/8071 TCP。jobs 通过双向 TLS、独立 bearer token、请求长度和 SHA-256 绑定调用两项服务；生产配置校验禁止 HTTP、证书校验关闭、token 复用或缺失客户端证书。部署团队需要在目标 CNI 实测该边界，并按托管服务 CIDR 和 ingress namespace 收紧其余出站地址；base 中按端口开放是可移植起点，不是最终防火墙策略。详细边界见 [隔离文档解析服务](parser-sandbox.md) 和 [OCR 服务](ocr-service.md)。

## 首租户

迁移和 RLS 验证完成后，用 runtime 身份创建首租户和预绑定 OIDC 管理员：

```bash
kubectl -n pharma-intelligence exec deploy/pharma-api -- \
  pharma-bootstrap \
  --tenant-slug customer-a \
  --tenant-name "Customer A" \
  --skip-api-key \
  --admin-email admin@customer.example \
  --admin-oidc-issuer https://identity.customer.example \
  --admin-oidc-subject oidc-subject-value
```

不要创建共享管理员，也不要在命令行传生产本地密码。

### Agent API 密钥生命周期

租户管理员在内部工作台的“访问与生命周期”页创建 Agent API 密钥。创建和轮换响应使用 `Cache-Control: no-store`，完整密钥只显示一次；管理员必须立即存入获批的密钥管理器，平台不提供找回接口。列表只展示名称、前缀、scope、有效期、最后使用时间和商业 Client 绑定状态。

新创建的密钥默认尚未绑定收费账户。完成 rate card、账户、订阅和 entitlement 审批后，使用响应中的密钥 ID 作为 `pharma-commercial provision-client` 的 `--oauth-client-id` 与 `--subject-id`，并选择 `--actor-type api_key`。已绑定密钥从工作台执行轮换时会原子迁移 Client/subject 绑定；撤销会停用密钥及该 API-key subject，不能重新启用，只能重新创建或轮换。`pharma-api-key` 保留为受审计的 break-glass 轮换路径，不用于日常人工发放。

## 发布后验收

1. `alembic current` 与镜像期望 head 一致，`alembic check` 无漂移。
2. `pharma-verify-rls` 返回 `passed=true`。
3. OIDC 登录、登出、过期、错误 tenant 和禁用用户路径通过。
4. MCP initialize/list/call、错误 scope/audience/tenant 路径通过。
5. 一份真实文件从只读来源走完 snapshot、parse、governance、publish、knowledge。
6. parser 多副本健康、双向 TLS、无客户端证书/伪造客户端/错误服务端 CA、错误 token、摘要篡改、429/故障重试和无主动出站均通过；恶意样本在 parser 前由 ClamAV 阻断。
7. MCP 核心领域数据的来源、quote、locator、coverage、数据时点和内容摘要可复核。
8. `pharma-search status` 无 dead delivery；实体 facet/联想、证据 locator、租户隔离和 alias 重建通过。
9. HPA/PDB、节点驱逐、数据库主备切换、OpenSearch 节点故障和对象存储故障告警有效。

## 回滚

- 应用问题：把 Deployment 镜像回滚到兼容当前 schema 的上一 digest。
- 数据迁移问题：停止写入并按发布 runbook 恢复到隔离环境；不在生产直接执行 downgrade。
- 身份问题：保留运维 break-glass 流程，但不能关闭 MCP/OIDC 校验对外服务。
- 任何 RLS 或跨租户问题：立即关闭两个入口并按 P0 处理。
