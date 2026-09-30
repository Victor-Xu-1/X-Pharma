# 生产平台安装与密钥轮换手册

## 固定版本与安装顺序

唯一版本基线是 `deploy/kubernetes/platform/versions.env`。生产变更必须经过依赖审计、预生产升级和回滚演练，不使用 `latest`。

1. 建立多可用区 Kubernetes 集群、默认拒绝网络策略、持久卷、DNS 和证书签发器。
2. 安装 OpenBao HA integrated storage，并配置云 KMS 自动解封、审计设备、快照、跨区复制和 break-glass 流程。
3. 安装 External Secrets Operator 与 Stakater Reloader；ESO 只能读取本命名空间允许的 OpenBao 路径。
4. 安装 Envoy Gateway、Gateway API CRD 和 `deploy/kubernetes/platform/envoy-gateway-class.yaml`。
5. 安装 OpenTelemetry Operator，把 Collector 的中心出口地址和授权头改成企业观测平台地址。
6. 执行迁移 Job，验证 Alembic head 与 RLS，再部署统一 API gateway、统一 jobs 和隔离 parser/OCR。
7. 最后创建生产 DNS。公网只允许 `workspace.example.com` 和 `mcp.example.com` 两个入口。

推荐安装命令以版本文件中的值替换：

```bash
helm upgrade --install openbao oci://ghcr.io/openbao/charts/openbao --version 0.27.1 --namespace openbao --create-namespace --set server.image.tag=2.6.0
helm upgrade --install external-secrets oci://ghcr.io/external-secrets/charts/external-secrets --version 2.7.0 --namespace external-secrets --create-namespace --set installCRDs=true
helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm --version 1.8.2 --namespace envoy-gateway-system --create-namespace
helm upgrade --install reloader oci://ghcr.io/stakater/charts/reloader --version 2.2.12 --namespace reloader --create-namespace
```

## OpenBao 权限边界

启用 Kubernetes auth 后，将 `pharma-secret-reader` 绑定到只读策略。策略只允许：

```hcl
path "pharma-kv/data/production/application" { capabilities = ["read"] }
path "pharma-kv/data/production/migration" { capabilities = ["read"] }
path "pharma-kv/data/production/observability" { capabilities = ["read"] }
path "database/creds/pharma-runtime" { capabilities = ["read"] }
```

OpenBao PostgreSQL database role `pharma-runtime` 的 creation statement 必须创建带过期时间的登录角色，并执行 `GRANT pharma_runtime TO <lease-role>`。固定 `pharma_runtime` 是 `NOLOGIN` 最小权限组角色；默认租约 60 分钟，最大租约 24 小时。ESO 续租/刷新后 Reloader 只滚动在线工作负载。迁移 URL 位于独立 KV 路径，只挂载到一次性 migration Job。

应用 KV 必需键以 `deploy/kubernetes/secret-contract.env.example` 为准。密钥轮换后检查：

```bash
kubectl -n pharma-intelligence get externalsecret,vaultdynamicsecret
kubectl -n pharma-intelligence rollout status deploy/pharma-api
kubectl -n pharma-intelligence rollout status deploy/pharma-jobs
kubectl -n pharma-intelligence logs deploy/pharma-api --since=10m | rg -i 'password|token|secret'
```

最后一条不应出现明文凭据。租约撤销测试必须先在预生产执行：撤销旧租约、确认旧连接在宽限期后失败、确认新 Pod 使用新租约恢复且没有跨租户读取。

## 网关与观测验收

`BackendTrafficPolicy` 只提供边缘第一层保护；MCP 商业额度、账户级速率、反枚举和账本仍由应用服务端执行。目标 overlay 必须替换 `MCP_TRUSTED_PROXY_CIDRS` 占位值，且 Envoy 必须丢弃客户端 forwarding 头并根据受信链重建 `X-Forwarded-For`。上线前检查 Gateway/Route `Accepted=True`、证书有效、HTTP 自动跳转 HTTPS、内部 Service 无公网 LoadBalancer，并通过绕过代理、伪造转发头和错误代理跳数的拒绝测试。

Collector 必须有 3 个副本和 PDB。中心观测平台至少配置 API 5xx、MCP 拒绝率、Temporal backlog、投影失败、OpenBao/ESO 同步失败、数据库连接耗尽和账本差异告警。日志不得记录完整查询正文、原始证据、令牌或密钥。

指标、SLO、错误预算、告警、角色责任和 runbook 的版本化契约位于 `deploy/operations/operations-contract.yaml`。每次构建执行 `pharma-operations-verify`；本地真实 OTLP 链路执行 `make observability-acceptance`。目标观测平台必须逐项实现等价规则并完成通知失败、确认和升级演练，仓库内角色引用不能替代实际值班表或 Production `operations_approval`。

## 可重复验证

在装有 Docker、kubectl 和锁定 Python 环境的 WSL 或 Linux 构建节点执行：

```bash
./scripts/validate-kubernetes.sh --uv-path uv
```

构建网络不能直接访问上游发布站点时，只允许使用企业批准的 HTTPS 传输镜像：

```bash
./scripts/validate-kubernetes.sh \
  --asset-mirror-prefix https://approved-mirror.example/ \
  --uv-path uv
```

`--asset-mirror-prefix` 必须以 `https://` 开头并以 `/` 结尾。镜像只改变下载传输路径；脚本仍按上游发布的固定 SHA-256 校验 kind 和全部 CRD，校验不一致即失败。默认不配置镜像并直接访问上游。

脚本校验 kind 下载 SHA-256，在一控制面、两 worker 的临时 Kubernetes API Server 中安装官方 CRD，再对生产清单执行 server-side dry-run；ClamAV 实测要求两个副本跨 worker 和测试 zone 分布，完成单 Pod 替换后仍保持布局、PVC 与 Service 可用性，最后删除临时集群。它不等同于真实云集群的存储、证书、DNS、KMS、负载和节点/可用区故障转移验收。
