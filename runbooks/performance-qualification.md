# 性能与故障验收

## 证据分层

`performance_baseline` 是 Development/Pilot 的本地协议基线，不能满足 Production 的 `performance` 类别。它使用同一租户的临时人员账号和预注册 MCP 客户端，真实访问两个公开入口，并验证：

- 有节奏的持续混合流量和更高并发的峰值混合流量；
- Web 与 MCP 的 P50/P95/P99、吞吐量、失败明细和协议版本；
- 每个成功 MCP 调用的唯一 settlement、扣费/额度一致和零遗留 reservation；
- 同一幂等键并发争用只产生一个 durable settlement，终态重放不重复扣费；
- 客户端取消、短超时、领域失败、额度拒绝和恢复终态。

报告固定声明 `production_claim=false`、`long_running=false`、`target_infrastructure_faults=false` 和 `production_approvals=false`。发布证据校验器会拒绝删除这些缺口或把本地结果改写为生产证据。

## 本地运行

服务必须通过 WSL Compose 启动，MCP token 文件必须由当前 WSL 用户所有且权限不高于 `0600`：

```bash
export PHARMA_REPO="${PHARMA_REPO:-/srv/wsl/projects/x-pharma}"
export PHARMA_RUNTIME_ROOT="${PHARMA_RUNTIME_ROOT:-/srv/wsl/data/x-pharma-runtime}"
cd "$PHARMA_REPO"
export TEST_MCP_ACCESS_TOKEN="$(cat ~/.config/pharma-intelligence/agent-gateway.key)"
make performance-baseline-acceptance \
  PERFORMANCE_BASELINE_EVIDENCE="$PHARMA_RUNTIME_ROOT/evidence/performance-baseline.json"
```

验收脚本根据 MCP key 的服务端绑定解析租户，创建随机临时人员账号后立即把权限降为只读 Viewer，运行负载后删除账号并核对残留为 0。报告独占创建、权限为 `0600`，不记录 token、邮箱或密码。存在同命名空间残留时脚本失败关闭，运维必须先调查上次执行是否被强杀，不能盲目删除生产账号。

## Production 资格

Production 必须另外在批准的预生产环境运行并提交 `pharma.production-gate-evidence.v2`，至少覆盖策略中的九项检查：持续负载、峰值、长稳、背压、故障注入、Web SLO、MCP SLO、计量完整性和风险控制。执行前由产品与平台负责人批准以下参数：

- 真实数据量、query mix、租户数、Agent client 数和授权组合；
- 正常、峰值和突发并发，测试时长及允许错误率；
- PostgreSQL/RDKit、OpenSearch、Valkey、Temporal、对象存储、IdP、网关和模型服务故障矩阵；
- P50/P95/P99、吞吐、队列深度、连接池、资源水位、settlement 差异和风险告警阈值；
- 停止条件、客户影响隔离、恢复步骤和证据保留位置。

故障注入必须在隔离环境进行，包含依赖超时/断连、Pod 驱逐、节点或可用区丢失、限流、队列积压和恢复。任何跨租户结果、成功调用缺少 settlement、重复扣费、遗留 reservation 或风险门禁绕过都按 P0 处理，不能用提高阈值继续测试。
