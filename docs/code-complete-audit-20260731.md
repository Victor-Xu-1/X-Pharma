# Code Complete 审计报告

| 字段 | 内容 |
|---|---|
| 审计日期 | 2026-07-31 |
| 目标基线 | `PIP-GOAL-001` v1.9.59 |
| Git 基线 | `635988967f6345efd21f5fd27676bf5c942a2f38` 加当前未提交候选 |
| 结论 | 代码级审计完成；候选不是干净提交、签名制品或 Commercial Production |

## 需求与证据

| 审计面 | 当前事实 | 结论 |
|---|---|---|
| 外部能力矩阵 | 12 个工作域均已登记；10 个代码级 `implemented`，全局搜索与个人/团队效率因正式数据和业务 UAT 保持 `partial` | 映射完整，外部证据未冒充代码完成 |
| 体验门禁 | 8 项均有证据；4 项 `implemented`，密集结果、个人效率、人工辅助技术/响应式、生产性能/视觉证据保持 `partial` | 映射完整，人工与生产门禁仍开放 |
| 专业组合查询 | 专利、交易、监管、流行病学、新闻/会议已贯通草稿、稳定 URL、真实 API、结果、保存/订阅和刷新恢复 | C-01 已关闭 |
| 真实浏览器 | Chrome `151.0.7922.71`、Edge `150.0.4078.105`、Edge `149.0.4022.98` 各 `112/112`，四视口、WCAG、键盘重排和只读视觉基线通过 | 本地受控浏览器证据成立，不是生产 UAT |
| 运行候选 | API、parser、worker 使用镜像 `4e99391e214d...`，非 root、只读根文件系统且 healthy；研究入口资产为 `research-main-D3KIKnSC.js` | 当前 `8080` 与已验证前端产物一致，但镜像未绑定干净 commit/tag |

## 实际门禁

- `make check`：Ruff 315 个文件、严格 Mypy 314 个源文件、`1149 passed / 35 deselected`、覆盖率 `84.56%`、OpenAPI 352 个生成文件、Biome、TypeScript、前端 `336/336`、生产构建、运维合同、59 份 YAML 文档、Compose 配置和 Kubernetes 渲染通过。
- `make container-backend-check`：独立测试镜像通过 Ruff、严格 Mypy 311 个源文件、OpenAPI 漂移检查、`1149 passed / 35 deselected` 和覆盖率 `84.56%`。
- 三浏览器报告均为 `status=passed`、`professional_news_query=true`、`production_claim=false`；验收命令报告临时账号、实体和入库夹具清理后为 0。
- `pharma-runtime-hygiene`：`finding_count=0`。
- `git diff --check`：通过。

## 审计发现

1. 首次容器门禁在 `tests/test_runtime_cleanup.py` 发现 pytest `session` 夹具缺少 `Session` 类型；补齐精确类型后，未放宽 Mypy，容器和原生全仓门禁均通过。
2. 生产源码扫描未发现 TODO、FIXME、XXX、空 `pass`、`NotImplemented` 或 mock 成功路径。`placeholder` 命中为表单提示、加载态和显式配置校验，不是业务空壳。
3. 能力矩阵为有效 UTF-8 JSON；Windows PowerShell 5.1 读取时必须显式使用 `-Encoding UTF8`，Python 标准 JSON 解析器和仓库测试均通过。

## 未关闭边界

- 审计时工作树有 150 个状态项并含并行 Agent 工作；后续已在同日完成敏感信息、安全门和所有权收束，形成代码提交 `50374913c5bfd7e5b427df0af98c36d3227b6575`，C-09 已关闭。
- 审计时镜像来自未提交源码；后续已从 `50374913c5bfd7e5b427df0af98c36d3227b6575` 构建 OCI revision 一致的 `ff1dbfc64357...` 并通过部署后 Chrome `112/112`，C-10 已关闭。受控 remote、签名 tag 与 R-01 至 R-05 仍未完成。
- 审计时 Redis/Temporal 使用历史 Compose 标签且存在 3 个退出 orphan；后续已完成原子备份、隔离恢复、当前仓库重建、运行状态验证和逐个 orphan 删除，C-11 已关闭且未删除任何卷。
- `make check` 按项目合同排除 35 个 integration 标记测试；最新候选尚未在干净源码和签名候选上重跑数据库集成、clean-source、安全 release-mode、迁移回环与离线验包。
- 正式数据授权、目标服务器、企业 IdP/TLS、远程 MCP、多副本、容量/灾备、独立安全评估、人工辅助技术和专业用户 UAT 均不属于本次代码审计通过范围。
