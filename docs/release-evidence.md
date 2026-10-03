# 发布证据链

## 当前架构候选与证据使用边界（2026-10-02）

软件显示版本为 `X-Pharma v0.1.0`，当前工程分支为 `refactor/architecture`；原 `main`、原业务数据库和原预览未被此次架构迁移覆盖。以下旧日期的测试计数和运行状态仅用于历史追溯，不可冒充当前提交的完整门禁结果。

本轮按受影响模块验证，不主动执行全局测试或手动调度全量 CI。共用来源返回、同实体失败缓存恢复、Portal 预览和 URL 模块化有四尺寸真实 Chrome、相关单元、类型与资源预算证据；治理辅助、领域材料化和确定性来源适配有相关行为、无循环/单一归属检查、策略指纹不漂移及独立 PostgreSQL 原子发布/结构权威验证。各项定向结果不能相加成全站场景覆盖或生产验收。

三张研究页基线已逐张审阅并更新清单哈希，20 张已提交资产的哈希一致；这不表示 20 张截图都在本轮重拍。既有 140 场景、像素、性能、源安全和 CI 门禁保留，不为部分运行降低覆盖门槛。私有配置、合成身份凭据及可能含令牌的失败 trace 只保留在本地 E 盘，不随公开仓库交付。

架构 HTML 已自包含；完整离线迁移还需要容器运行时、所有镜像、持久数据、所需签名与模型文件以及断网启动/恢复验证。代码开源、精确镜像部署或依赖缓存不能代替该整体交付；正式数据许可、客户 IdP、真实计费、HA/SLO、人工 UAT 和上线批准仍是独立外部条件。

## 2026-08-10 内部数据工厂失效保护

- 隔离单进程 `pharma-gateway` 使用临时 SQLite，管理员通过真实 Google Chrome 在内部工作台登记
  PubMed `EGFR AND lung cancer` 来源，抓取上限为 `3` 且启用摘要授权。该运行态明确关闭 Temporal；
  基线页面一边显示“调度未启用”，一边仍开放“立即扫描”，点击后直接暴露英文
  `Durable workflow service is not enabled`。
- 根因是来源按钮只检查忙碌态和来源治理 readiness，没有检查同一快照中的
  `durable_workflows_enabled`。修复后能力缺失或 readiness 未确认时扫描失败关闭，按钮标题解释
  当前原因；来源非通过检查转为面向管理员的中文处置提示，接入弹窗不再承诺立即调度。
- 行为红测先得到 `1 failed/19 passed`；完成实现并更新既有英文断言后，`DataFactoryView` `20/20`。
  两个 owner 文件的 Biome、完整 typecheck、production build/build-boundary 和 scoped
  `git diff --check` 均通过，初始 CSS 保持 `196132/196608` bytes。
- 当前构建在同一隔离运行态完成真实 Chrome 复验：来源卡片显示“尚未完成首次扫描”和工作流
  启用指引，“立即扫描”不可操作；接入弹窗准确说明服务启用后才进入调度；原始英文 readiness
  消息和旧 `503` alert 均不再出现，浏览器控制台条目为 `0`。清理前 SQLite 为 `1` 个登记来源、
  `0` 个 ingestion run、`0` 个 ingestion asset、`0` 个 source asset、`0` 个 source version；
  网关日志没有 traceback/exception/error/warning/warn 命中。
- Chrome 会话、隔离数据库、运行目录和指针已销毁，`18580` 已关闭。脱敏报告
  `${PHARMA_RUNTIME_ROOT}/evidence/browser/data-factory-durable-scan-guard-20260810.json`，
  SHA-256 `ac9f8336b9362671f596849bd3a0ed18d1756ffbef0a61348244c2da5fc51b68`，权限 `0600`，
  `production_claim=false`。本项只证明工作流服务不可用时的 fail-closed 管理员体验；成功 PubMed
  抓取、Temporal 自然调度、正式来源授权、远程模型治理和生产验收继续使用既有独立门禁。

## 2026-08-10 双工作台登录失败焦点恢复

- 正式候选 `18181` 的真实 Google Chrome 基线稳定复现共享登录缺陷：外部鼠标点击、内部从
  密码框 Tab 到提交按钮后回车，以及 `390×844` 外部移动端提交，在真实 `401`、密码清空和
  中文 `alert` 出现后，焦点均落到 `BODY`；只有直接从密码框回车的路径仍保留输入焦点。
- 根因位于 `LoginScreen` 失败状态机：认证失败只清空密码，提交按钮进入禁用/加载态后失去的
  焦点没有恢复。修复为密码输入建立稳定 ref，并在失败关闭路径清空后主动恢复焦点，不改变
  成功登录、错误脱敏、按钮禁用、OIDC 或双工作台身份边界。
- 双工作台行为红测先得到 `2 failed/9 passed`，修复后 `LoginScreen` `11/11`；与入口路由组合
  回归共 `28/28`。两个 owner 文件的 Biome、完整 typecheck、production build 和
  build-boundary 均通过，初始 CSS `196132/196608` bytes。
- 当前构建在隔离单进程 `pharma-gateway` 和临时 SQLite 上提供真实 HTTP：认证配置 `200/local`、
  外部/内部入口 `200`、错误凭据 `401`。Google Chrome 复验外部鼠标、内部 Tab+Enter 和移动端
  三条路径均聚焦到已清空的密码框；中文 `alert`、外部内部术语隔离和 390px 无横向溢出保持
  正确。隔离数据库、日志和进程已销毁，`18580` 已关闭；日志 `4` 次预期 `401`，error/warning、
  测试凭据载荷和完整 API Key 命中均为 `0`。
- 脱敏报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/login-failure-focus-20260810.json`，
  SHA-256 `4396e3b4f459722d35629f938c81887356e0eb5b1b16e7530cf10b9f84d5545a`，权限 `0600`。
  `credentials_recorded=false`、`production_claim=false`；企业 OIDC 成功登录、目标环境和客户 UAT
  仍是独立门禁。

## 2026-08-10 商业 MCP API Key 生命周期

- 修复托管 Agent API Key 的真实收费 MCP 查询参数漂移：`search_entities` 与 `resolve_entity`
  现在在计费预留参数和内部领域查询中统一使用 `review_status=verified`，非 `verified`
  请求失败关闭。此前默认空值会被内部 API 补成 `verified`，导致商业反篡改校验返回 `403`。
  行为红测先复现该差异，随后 `tests/test_mcp_server.py` 完整 `23/23`、Ruff、格式检查和
  `mypy src/pharma_intel/mcp_server.py` 通过。
- 在持久的隔离 SQLite 上启动单进程 `pharma-gateway`，真实 Google Chrome 管理员工作台完成
  Agent API Key 创建、轮换和撤销。创建/轮换后的完整密钥均只显示一次、自动获得焦点，关闭
  后从 DOM 移除；页面在 MCP 调用后显示最近使用时间和商业 client 绑定，撤销后 API-key 主体
  数量从 `1` 变为 `0`。Chrome 页面控制台 error/warning 为 `0`。
- 官方 Python MCP SDK 真实协商协议 `2025-11-25`、发现 `30` 个工具，并以创建 Key 和轮换
  Key 分别调用数据库 `search_entities`；两次均生成独立 settlement，每次扣费
  `1.00100000`。轮换后旧 Key 被 SDK 拒绝，轮换 Key 调用成功，主动撤销后轮换 Key 立即被
  拒绝。SQLite 终态为两把 Key 均撤销、不同的 64 位哈希、两次结算总额 `2.00200000`，商业
  client 指向轮换 Key，唯一 API-key subject 已失效，`security.api_key.create/rotate/revoke`
  审计顺序完整；审计和网关日志均无完整密钥，网关 error/warning 为 `0`。
- 隔离网关、SQLite、Chrome 会话和临时日志已精确销毁；脱敏报告保留在
  `${PHARMA_RUNTIME_ROOT}/evidence/mcp/api-key-lifecycle-20260810.json`，
  SHA-256 `9220a31b02e9c1d815b7189461985ab58e5836d42b27ad32dcc27f7d15fc0f5d`，权限
  `0600`。`credentials_recorded=false`、`production_claim=false`；该证据不关闭目标服务器
  TLS、企业 OAuth/OIDC、DPoP、多副本、生产账单对账、真实授权数据、五类 Agent 互操作或
  客户 UAT 门禁。

## 2026-08-04 增量证据

- 2026-08-05 质量门禁复核：后端非集成全量 `1176 passed, 35 deselected`，覆盖率 `84.54%`；
  `make lint typecheck` 通过。ClinicalTrials.gov 输入边界与增量重扫重复入队回归已修复，
  失败治理版本仍可自然重试，普通快照不会被错误重复加入后台任务。该结果属于本地候选，
  `production_claim=false`。
- 真实自动入库复核补充：PubMed `EGFR` 来源由 Temporal scheduler 自然触发，未调用手工扫描、未修改来源调度配置；官方 NCBI ESearch/EFetch 均 HTTP 200。第二次验收结果为 `SUCCEEDED`，105 个当前版本全部 malware scanned、processed、governed、projected、traceable，当前有效 AI 治理运行 `268/268` 使用远程 `mimo-v2.5`，token/segment accounting 完整，`713` 条 staged facts 中 `697` 条 quote verified，OpenSearch 3.7.0 为 green，dead/processing/retry 均为 `0`。持久报告与 SHA-256 位于 `manifests/automatic-ingestion/pubmed-egfr-temporal-20260804.json`。`production_claim=false`，该证据不替代正式授权、生产环境、覆盖率 SLA 或责任方签字。
- 自动入库验收脚本修复历史失败误报：保留失败 extraction run 作为审计记录，只从当前有效运行集排除已被同一 immutable source version 后续 `SUCCEEDED` 运行解决的历史失败；若最新有效运行仍失败，门禁仍失败。自动/手工幂等脚本 Bash 语法、契约回归 `4 passed`。数据工厂新增治理失败版本在下一次自然扫描自动重试，数据工厂回归 `15 passed`，Ruff 和 mypy 通过。该修复不删除历史失败、不伪造成功，`production_claim=false`。

- ClinicalTrials.gov 真实运行修复复核：Worker/API 已部署同一新镜像且健康，源中 `583` 个当前版本治理成功、`1` 个仍因远程供应商 `content_filter` 失败；3 个历史模型失败样本已有 2 个经 `mimo-v2.5` 重处理成功。源恢复后资产状态会从 `SOURCE_UNAVAILABLE` 恢复为 `ACTIVE`，已看到路径的治理失败版本也会在自然扫描中重新入队；专门的 Temporal 重排队工作流已真实触发剩余样本治理。该来源仍未达到完整通过门槛，`production_claim=false`。
- ClinicalTrials.gov 边界重试增强：模型网关对连续 `content_filter`/长度边界采用普通、紧凑、身份/结构字段最小投影三级有界请求；`SourceVersionReprocessWorkflow` 增加 30 分钟 heartbeat 和等待取消。跨层回归 `57 passed`，Ruff/mypy 通过；真实样本仍最终保留 1 个 `content_filter` 失败，fail-closed 语义保持不变。部署后 readiness 为 `ready`，MCP 匿名请求 `401`、protected-resource metadata `200`，全部仍属于 `production_claim=false`。
- 真实 Google Chrome 回归复核（2026-08-05）：由于 ClinicalTrials.gov 真实库存使源对象超过第一页，验收夹具新增真实分页定位；不更新快照、`PHARMA_BROWSER_WORKERS=1` 下四视口全量 `124/124`，桌面 1440/1920、平板 1024、移动 390 各 `31/31`。临时账号、实体、化学、活动、治理和入库夹具均为 `0`；报告 `/tmp/pharma-browser-acceptance-20260805-chrome-rerun.json`，运行产物 `/tmp/pharma-browser-acceptance-2964819`。这只证明当前候选的真实 Chrome 路径，`production_claim=false`，不关闭 C-05/C-06/C-07 的人工/生产门禁。
- MCP 异步互操作复核（2026-08-05）：官方 MCP Inspector `0.22.0` 与 Python MCP SDK `1.28.1` 两个独立客户端在隔离 PostgreSQL/对象存储中均通过异步任务创建、状态读取、分页、签名游标篡改拒绝、取消、错误恢复、批准门控、导出 manifest 验签、结算幂等和零活动预留；客户端 `2/2`，settlement `2`，临时数据库与对象存储已销毁，`credentials_recorded=false`、`production_claim=false`。报告 `/tmp/mcp-async-task-20260805.json`。该证据不关闭 A-01/A-02/A-03/A-04/A-06/A-07/A-08/A-09 的生产网络、IdP、DPoP、真实账单、反搬运和客户 UAT 门禁。

- Telemetry overlay 已修复为目录挂载 `./deploy/otel:/etc/otelcol-contrib:ro`，collector 使用
  `collector.dev.yaml`；真实 Windows Docker Desktop + WSL Compose 启动成功。完整 overlay 下
  `otel-collector`、API、worker 均运行，API/worker 健康，`/health/ready` 返回 HTTP 200，collector
  日志持续收到真实 Traces，API 无 OTEL 导出错误；MCP `/mcp` 返回 401，protected-resource
  metadata 返回 200。Compose 合同回归更新为 `17 passed`。该证据只证明本地候选的跨平台启动和
  OTLP 发送链路，`production_claim=false`，不关闭 I-08 的中心可观测性生产联调、指标/SLO、
  HA、告警和长期稳定性门禁。
- 远程 ModelGateway 新增严格 `AI_FALLBACK_PROVIDERS_JSON` 配置和显式 provider 追踪：只对有界
  `408/429/5xx` 或网络故障切换，不对 4xx、schema 或引用治理失败静默降级，禁止本地模型回退。
  配置/网关回归 `152 passed`、Ruff 和 mypy 通过；新镜像 `sha256:59adde909b4d1af764dffa6378b9887a0412a72a3268b367aa1670b99970c2ae`
  已部署，真实 NCBI EFetch → worker → Mimo `mimo-v2.5` 返回 3 条治理事实、`stop`、usage、provider
  request ID 和 `provider_name=primary`。这是本地候选和主 provider 证据，第二真实 provider、付费文档、
  成本对账和生产审批仍未完成，D-07 保持未关闭。
- [MCP live boundary evidence](mcp-live-boundary-evidence-20260804.md)：8080/8090 双入口的 metadata、匿名 401 和 readiness 实测；仅为本地候选运行证据。
- [Third-party LLM provider live evidence](llm-provider-live-evidence-20260804.md)：真实 PubMed `42549034` 经项目模型网关和 `mimo-v2.5` 完成 5 条结构化事实抽取；仍不关闭付费文档、提示注入、成本恢复和第二供应商门禁。
- MCP gateway 和独立 `pharma-mcp-health` 探针现在都验证 API readiness（gateway）、匿名 MCP 401 和 protected-resource metadata；定向回归 `17 passed`，对当前真实 `8080` 与 `8090` 服务的命令行探针均返回退出码 `0`。该修复只强化本地发现边界，`production_claim=false`。
- Mimo response-format 兼容模式已同步到 Kubernetes 配置契约：基础 ConfigMap 明确默认为 `json_schema`，Mimo 生产 overlay 必须显式选择 `prompt_only`；Kubernetes 合同测试 `10 passed`。
- 内部质量运营新增受保护的 `GET /api/v1/governance/quality/coverage` 与“来源覆盖与授权”表格，按来源/数据集聚合解析覆盖、缺失资产、事实发布覆盖、冲突率、运行成功率、新鲜度、失败 SLA、授权状态、数据分类和责任人，不使用逐来源 N+1 查询，也不暴露原始错误文本。OpenAPI 合同 `4 passed`，质量/API 定向测试 `6 passed, 1 skipped`，真实 PostgreSQL 迁移与质量回归 `1 passed`，前端 Governance 定向测试 `7/7`、Biome、TypeScript 和生产构建通过；最终 API/worker 镜像 `sha256:707f7dd0e837598c02dd7d6756fb0979b5f1d84965beb9df670b2db258e3f1ab` 已部署，readiness 返回 200。
- 对当前运行中的真实 PostgreSQL 做只读运行时核验，默认租户来源数为 `0`，覆盖接口因此返回空集合；这确认正式来源注册、授权和覆盖报告输入仍未进入生产样本库。该批只闭合内部质量覆盖的代码与运行接口基线，`production_claim=false`，不关闭 D-05、D-01、D-02、D-03 或 Commercial Production。
- 同批修复 OpenAPI 生成 transport 的取消竞态：请求在取消后收到迟到的 401 响应时，不再广播陈旧的会话失效事件；修复写入 `apps/web/openapi/request.ts` 模板并重新生成 354 个客户端文件。前端全量回归最终为 `60 files / 371 tests passed`，`pnpm api:check`、Biome 和 TypeScript 均通过；Google Chrome 未登录入口烟测确认 `/workspace/research` 与 `/workspace/internal` 标题、登录边界和页面宽度正常。该项仍只属于本地候选运行证据，认证后的管理员 UAT 和生产浏览器矩阵未完成。

## v1.10.2 当前代码收口与真实 Chrome 复核（2026-08-04）

本批修复了五个跨层问题：审计写入不再依赖已由 FastAPI 依赖清理的请求会话；`web-vitals`
401、取消请求后的陈旧 401 不再清空有效用户会话；同视图侧栏导航同步提交，避免覆盖新输入；
内部入库运行记录验收按现有分页逐页定位。定向证据实际通过：后端 API `18/18`、Compose
合同 `16/16`、RUM `4/4`、生成传输 `5/5`、工作台 `16/16`、前端 TypeScript、Biome 和
生产镜像构建；容器启动健康，日志无 `audit_write_failed`。

真实 Google Chrome/Playwright 全量结果必须区分运行模式：

| 模式 | 结果 | 解释 |
|---|---:|---|
| `PHARMA_BROWSER_WORKERS=1` | `124/124` | 修复后的真实四视口全量通过；桌面 1440、桌面 1920、平板 1024、移动 390 各 `31/31` |
| `PHARMA_BROWSER_WORKERS=4` | `119/124` | 5 项失败为本机并发资源争用下的 INP/页面等待，不能作为生产通过证据 |

验收脚本现在对 `PHARMA_BROWSER_WORKERS` 做 `1..16` 边界校验，默认仍为 `4`。修复后的串行
全量已在真实 Google Chrome 中重跑通过，结果文件保留在本次运行的受限临时目录
`/tmp/pharma-browser-acceptance-23382`；快照未更新，临时账号、实体、结构、活性、治理和
入库夹具均为 `0`。本地性能观测为：桌面 1440 `LCP 168ms / INP 56ms / CLS 0`，桌面 1920
`116ms / 24ms / 0`，平板 `108ms / 16ms / 0`，移动 `88ms / 32ms / 0`。所有本地证据保持
`production_claim=false`；正式授权数据、人工辅助技术/系统缩放、生产 RUM P75、专业用户
UAT、TLS/OIDC/DPoP、真实账单和 Commercial Production 仍未完成。

同日对两个真实官方来源执行了自然调度复核，详见
`docs/automatic-ingestion-evidence-20260804.md`。ClinicalTrials.gov 和 PubMed 均未使用
人工触发，Temporal scheduler 观察到 `SUCCEEDED` 的 unchanged 运行，3/3 版本完成安全
扫描、解析、远程 `mimo-v2.5` 治理、quote 定位、OpenSearch 投影和可追溯链路，失败对象
与投影积压均为 0。该证据仍固定为 `production_claim=false`，不能关闭 D-01、D-02、D-03、
D-05 或 Commercial Production。

随后使用修复后的验收脚本，以 `--project-name pharma-acceptance` 和
`COMPOSE_FILE=compose.yaml:compose.dev.yaml:compose.telemetry.yaml` 重新复核两条来源；
ClinicalTrials.gov 观察耗时 58 秒、PubMed 观察耗时 11 秒，两个报告仍为
`status=passed`、`manual_trigger_used=false`、`source_schedule_mutated=false`，且
OpenSearch delivery 的 dead/processing/retry 均为 0。脚本现在不会在漏掉项目名时静默探测
另一套 Compose 运行线。

同一显式 project 还完成了 ClinicalTrials.gov 的完整 pilot 复核：自然调度报告和随后两次
幂等扫描均为 `SUCCEEDED`，3/3 版本保持安全、治理、可追溯和投影完成，失败对象为 0；
报告分别为 `/tmp/automatic-ingestion-pilot-clinicaltrials-20260804-v2.json` 和
`/tmp/ingestion-pilot-clinicaltrials-20260804-v2.json`。这仍是 `local-wsl`、
`production_claim=false` 的试点证据。

内部质量运营验收脚本也已显式绑定同一 Compose project，并在临时 PostgreSQL 数据库上
完成最新迁移、数据质量快照、阈值、freshness、事件和处置回归，结果为 `1 passed`；
临时数据库由脚本退出清理。该证据证明质量运营代码和真实数据库链路可执行，不代表正式
数据覆盖率、freshness SLA 或责任方批准已经完成。

## v1.10.1 加速执行实测（2026-08-04）

在隔离 WSL `pharma-acceptance` 运行线使用真实 Google Chrome/Playwright 执行四视口完整套件，结果为 `123/124` 通过，`1` 项失败；本轮未更新视觉快照。失败为：

1. 流行病学刷新场景的幂等 GET 在 Playwright `route.fetch()` 阶段收到一次 `socket hang up`；同一接口的应用日志返回 HTTP 200，已补一次有界传输重试，修复后必须重跑完整套件。

该失败仍需在同一四视口套件重跑并关闭；不得通过更新快照、放宽超时、降低断言、注入静态数据或跳过视口消除。当前结果只证明本地候选的 `123` 条路径通过，不能覆盖人工辅助技术、系统级 200%/400% 缩放、生产 RUM、正式授权数据或专业用户 UAT。

## v1.10.0 加速收口当前验收（2026-08-04）

本轮之前在隔离的 WSL `pharma-acceptance` 运行线使用真实 Google Chrome/Playwright 执行
四视口完整套件，结果为 `117/124` 通过，未更新视觉快照。该结果是历史基线；当前有效结果以
v1.10.1 的 `123/124` 和 1 个传输/验收竞态失败为准。
该报告不是通过证据，也不能覆盖人工辅助技术、系统级 200%/400% 缩放、生产 RUM 或专业
用户 UAT。

同一隔离运行线已用真实官方网络源验证自动入库：ClinicalTrials.gov API v2 与 NCBI
PubMed E-utilities 各注册 1 个来源，真实 HTTP 返回 200，Temporal scheduler 自动触发，
未使用人工触发，远程 `mimo-v2.5` 治理成功，PubMed 手工重复扫描幂等通过。当前运行证据
明确为 `production_claim=false`，只证明本地候选的跨层链路，不代表正式授权覆盖或生产来源
验收。证据文件保存在运行时临时目录，需在发布归档时绑定候选 SHA、数据许可和审批记录。

## v1.9.100 当前修复验收（2026-08-04）

本次修复将总览页“数据目录”改为直接消费同一认证请求返回的真实
`entity_type` 与 `review_status` facets，不再显示固定或演示计数。当前默认租户
快照为 366 个实体，其中药物 147、靶点 40、疾病 122、机构 8、临床试验 25、
专利 5；治理状态为已确认 292、待治理 74。该快照只代表当前租户，不代表全球
市场覆盖量。

真实 Windows Google Chrome `150.0.7871.188` 全量四视口验收已通过 `124/124`，
四个项目各 `31/31`；报告为
`C:\\Users\\Victor\\AppData\\Local\\Temp\\pharma-e2e-real-20260804\\apps\\web\\browser-report.json`，
并记录 `credentials_recorded=false`、`production_claim=false`、所有临时数据清理
为 `0`。本证据关闭的是当前租户计数真实性和该批前端回归，不关闭正式授权数据、
生产基础设施、生产 RUM、人工辅助技术验收或专业用户 UAT。

## v1.9.100 外部工作台候选批次

本批将化学检索的保存/刷新回放改为服务端版本化 `chemistry_search` 保存检索，URL 只携带经授权的保存检索 UUID；结构原文不进入 URL，保存检索摘要不泄露结构原文。真实读取 API 恢复模式、阈值、上限和结构条件后重新执行结构查询；监控中心明确不提供尚未实现结构事件匹配的化学检索订阅。

代码与协议门禁：`ChemistryView` 定向回归 `5/5`，`MonitoringView` `15/15`，路由 `21/21`，后端监控与 OpenAPI 回归 `21/21`；前端全量 `60` 个测试文件、`362/362`，Biome、TypeScript、OpenAPI 漂移、生产构建、Ruff 均通过。

真实 Google Chrome `151.0.7922.71` 在隔离真实 PostgreSQL/RDKit 运行线执行完整四视口套件两次，每次 `123/124`；本批化学保存、刷新、UUID-only URL 与回放场景四视口每次 `4/4`，两次合计 `8/8`。全套件尚未通过：第一次失败为既有平板密集结果路径 INP `408ms > 200ms`，第二次失败为既有桌面管线药物实体候选组合框在 `apps/web/e2e/workspace.spec.ts:3122` 超时；两次失败点不一致，全球性能/稳定性门禁保持 partial。由于完整套件未达到通过条件，本批没有生成 `pharma.browser-acceptance.v9` 发布报告，也不能宣称商业发布或生产验收。

## v1.9.99 外部工作台批次

结构检索结果的实体入口现在使用稳定 `entity_id`，通过研究工作台实体路由打开正确专业档案，避免显示名称歧义。`ChemistryView` 定向回归 `3/3`，前端全量 `358/358`，Biome、TypeScript、生产构建和构建边界检查通过。

真实 Google Chrome `151.0.7922.71` 四视口完整套件 `124/124`，四视口各 `31/31`；INP `16–32ms`、LCP `84–204ms`、CLS `0`，320/360/720 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/chemistry-entity-id-v1.9.99-final.json`，SHA-256 `d122a4ad75686b8aa9feb57e9d5ad1dfa8f5b1d196c5b9aac767a03f8b88ec2c`。临时账号、实体、结构夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级结构检索跨域入口和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.98 外部工作台批次

本批已实现通用实体、公司和疾病档案交易分区的真实交易投影与类型化跨域入口。真实 Google Chrome `151.0.7922.71` 四视口完整套件 `124/124`，四视口各 `31/31`；INP `16–32ms`、LCP `112–820ms`、CLS `0`，320/360/720 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/entity-dossier-deal-links-v1.9.98-final.json`，SHA-256 `91b103ef9f8247e11bd39923561177fcec93c29fb1285f0e83ca801368ce1d96`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。

全量 `make check` 通过：后端 `1152 selected / 35 deselected`、前端 `358/358`，并通过格式、静态类型、OpenAPI、生产构建、Compose、Kubernetes 和运营契约检查。该证据证明代码级真实链路，不替代正式授权数据、人工辅助技术、生产 RUM 或专业用户 UAT。

## v1.9.97 外部工作台批次

药物专业档案中的已治理关系、获批适应症、交易参与方、交易资产和权益持有人现在按真实 `entity_type` 直达靶点、疾病、公司或药物专业档案；权益持有人遵循后端组织类型契约，未知类型继续使用通用回退。`DrugView` 定向回归 `8/8`，真实 e2e 新增药物交易资产回跳，代码门禁、生产 API 镜像构建和运行契约通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `24–32ms`、LCP `84–124ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/drug-dossier-links-v1.9.97-final.json`，SHA-256 `a06750c32ec2a550ba2782c59b78e3f79932fa947c5b2ac854e1cf29d93cf642`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级药物档案跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.96 外部工作台批次

交易结果、参与方、资产和权益持有人现在按真实 `entity_type` 直达公司、药物、靶点或疾病专业档案；权益持有人遵循后端组织类型契约。交易结果“档案”入口与交易标题统一进入交易专业档案并保留 `deal` 深链接，缺少阶段细节时保留类型化资产候选回退。`DealsView` 交易导航定向回归 `9/9`，全量代码门禁、生产 API 镜像构建和运行契约通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `24ms`、LCP `88–112ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/deal-specialized-links-v1.9.96-links-final.json`，SHA-256 `5d610e17b4ddc863819117d3975fa0807e39d3ed06c12f66a4b10a7bbd24490b`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级交易结果跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.95 外部工作台批次

专利专业结果的关联实体现在按真实 `entity_type` 把药物、靶点、疾病和研发机构直达对应专业档案；结果表“档案”入口与专利族标题统一进入专利族专业档案，不再落到通用实体页。`PatentsView` 与监管/新闻/流行病学/疾病/共享实体导航定向回归 `40/40`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–32ms`、LCP `92–164ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/patent-specialized-links-v1.9.95-final.json`，SHA-256 `98ecd796d2d3304cddb0852c90d4928a88baac3f966262fead8caa7d4a25686a`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级专利结果跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.94 外部工作台批次

监管专业结果表和事件详情现在按真实实体类型把主题实体、适应症及申办方直达对应专业档案，未知类型继续使用通用实体兜底。`RegulatoryView` 与新闻/流行病学/疾病/共享实体导航定向回归 `34/34`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `24–48ms`、LCP `92–136ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/regulatory-specialized-links-v1.9.94-final.json`，SHA-256 `a478edc7c1228768e098e120f2255770901afd43925caa61c3ff123ffd06abfb`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级监管结果跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.93 外部工作台批次

新闻/会议专业结果的列表、研究发布时间线和详情抽屉现在按真实实体类型把发布机构及关联药物、靶点、疾病和研发机构直达对应专业档案，未知类型继续使用通用实体兜底。`NewsView` 与疾病/流行病学/共享实体导航定向回归 `25/25`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–32ms`、LCP `72–160ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/news-specialized-links-v1.9.93-final.json`，SHA-256 `a8191e05752bff8c26778533270cf5fb493955b7835c0f66534358db8365dbee`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级新闻/会议结果跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.92 外部工作台批次

流行病学专业结果表中的疾病和发布机构现在按真实实体类型直达对应专业档案；已知疾病进入疾病档案，发布机构按 `entity_type` 导航，未知类型继续使用通用实体兜底。`EpidemiologyView` 定向回归与疾病/共享实体导航回归 `19/19`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–56ms`、LCP `92–208ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/epidemiology-specialized-links-v1.9.92-final.json`，SHA-256 `f02228a085af170ef090ee4b2601a468dd40c4a7a22b1780bcea33ed195d8636`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级流行病学结果跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.91 外部工作台批次

疾病专业档案概览、流行病学观测、研发格局、靶点证据和关系网络现在按真实实体类型把药物、靶点、疾病和研发机构直达对应专业档案；流行病学发布机构按 `publisher_entity.entity_type` 导航，未知类型继续使用通用实体兜底。`DiseaseView` 与共享实体导航定向回归 `13/13`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `32–40ms`、LCP `96–144ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/disease-specialized-links-v1.9.91-final.json`，SHA-256 `bcebaa1d429deb490949a91a405a4008aab9cfca5d5771f2ff602e2da6965fa7`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级疾病跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.90 外部工作台批次

公司专业档案概览、研发管线、公司时间线和关联网络现在按真实实体类型把药物、靶点、疾病和研发机构直达对应专业档案；共享管线表补齐靶点列，未知类型继续使用通用实体兜底。公司、共享实体和疾病档案定向回归 `13/13`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `32–40ms`、LCP `100–124ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/company-specialized-links-v1.9.90-final.json`，SHA-256 `0a26468a79e5575d8fae295c551efbb2860f02c640ff9caf575c09ed0346ac53`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级公司跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.89 外部工作台批次

`TargetView` 的实体关系、转化证据和竞品管线现在按真实实体类型把药物、疾病、靶点和研发机构直达对应专业档案；化合物活性记录因当前类型契约不足继续使用通用实体兜底。定向 `TargetView` 回归 `7/7`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，前端类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `24–40ms`、LCP `80–180ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/target-specialized-links-v1.9.89-final.json`，SHA-256 `873e19a789de0878beef750c82f686eec65ad563db92591ae2f6c011b2c6e73f`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级靶点跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.88 外部工作台批次

`DrugView` 的药物概览、研发管线和临床结果现在按真实实体类型把靶点、适应症、研发机构和角色药物/靶点直达对应专业档案；缺少充分类型信息的交易、监管链接继续使用通用实体兜底。定向 `DrugView` 回归 `7/7`，全量 `make check` 后端 `1151/1151`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–40ms`、LCP `80–168ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/drug-specialized-links-v1.9.88-final.json`，SHA-256 `adb0ede3ee11b5bf0a4eef518cf2b9cf13d305480dfc31661336177ec1151b74`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级药物跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.87 外部工作台批次

`TrialsView` 的列表和临床试验专业档案现在按真实 `entity_type` 将药物、靶点、疾病和研发机构链接直达对应专业档案，未知类型继续使用通用实体兜底。定向 `TrialsView` 回归 `5/5`，全量 `make check` 后端 `1151/1151`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–48ms`、LCP `76–156ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/trial-specialized-links-v1.9.87-final.json`，SHA-256 `4ceff4e1845eb524b83281b1160a642f0ab2274463ddf3d5f658896a07563cea`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级临床跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## v1.9.86 外部工作台批次

`PipelineView` 与 `PipelineLandscape` 对已知靶点、疾病和研发机构使用类型化导航，直接打开专业档案；未知实体类型继续使用通用实体兜底。定向 `PipelineView` 回归 `8/8`，全量 `make check` 后端 `1151/1151`、覆盖率 `84.57%`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–104ms`、LCP `76–200ms`、CLS `0`，320 CSS px 重排和视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/pipeline-specialized-links-v1.9.86-final.json`，SHA-256 `4b31843a210369743ea92093e3d48349e72433832948d6d49c1b7e63996d5876`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明代码级跨域导航和本地受控真实链路，不替代正式授权数据、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。
`scripts/release_evidence.py` 是 WSL 内唯一的版本证据收口工具。它不替代测试、安全审批或生产变更审批，而是证明各项证据属于同一个 Git 提交、源码树和镜像集合。

## v1.9.85 外部工作台批次

`VirtualDataTable` 的视图设置同步失败和保存失败统一使用 `role=alert`，与公共查询错误契约一致；原有重试和恢复路径保持不变，定向组件回归 `7/7`。

镜像 TypeScript 构建和 `make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–48ms`、LCP `104–136ms`、CLS `0`，视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/table-error-semantics-v1.9.85-final.json`，SHA-256 `8acd61173981efd115f5ab58653704eb6bc0e1b51785091a85d9a0981fddb918`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据不替代目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术或专业用户 UAT。

## v1.9.84 外部工作台批次

`PipelineLandscape` 与 `DealLandscape` 的真实空维度状态统一使用 `role=status`、`aria-live=polite` 和 `aria-atomic=true`，按需图表加载态同样可播报；新增定向组件回归 `2/2`。

镜像 TypeScript 构建和 `make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–32ms`、LCP `76–116ms`、CLS `0–0.00245`，视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/landscape-state-v1.9.84-final.json`，SHA-256 `bea2f33e61942d3fc1b17cd3ed3eebfdcbf0c4b04fe61ef540ddb76f27172103`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据不替代目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术或专业用户 UAT。

## v1.9.83 外部工作台批次

`DomainLandscape` 与 `ClinicalTrialLandscape` 的真实空结果状态统一使用 `role=status`、`aria-live=polite` 和 `aria-atomic=true`，按需图表加载态同样可播报；新增定向组件回归 `3/3`。

`make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，四视口各 `31/31`，INP `16–40ms`、LCP `68–124ms`、CLS `0`，视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/landscape-state-v1.9.83-final.json`，SHA-256 `9a6d1c51589439a03a4013a279e3357b95442bf75b3bd29b187ce391fc3623b6`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据不替代目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术或专业用户 UAT。

## v1.9.82 外部工作台批次

`EmptyState` 现在以状态播报语义呈现空结果；`WorkspaceShell` 为当前导航项提供 `aria-current=page`，并在 SPA 视图切换后将焦点移到页面标题。`ResearchWorkspace.navigate` 保留跨页面 transition，但同一工作域内的 URL 状态提交同步完成，修复真实比较列表复选框在非紧急队列中的受控状态竞争。`ProfessionalQueryState`、`WorkspaceShell` 与 `CollectionsView` 定向回归 `16/16`。

`make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。真实 Google Chrome `151.0.7922.71` 固定隔离端口全量 `124/124`，四视口各 `31/31`，INP `16–24ms`、LCP `84–100ms`、CLS `0`，视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/accessibility-state-v1.9.82-final2.json`，SHA-256 `8158aa20508ef04e0e6c0aa3c4438ee38f1b3b7fe17ad96e8e6f0a225da5fd3d`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据不替代目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术或专业用户 UAT。

## v1.9.81 外部工作台批次

`ResearchWorkspace.navigate` 现在将搜索、分页、排序和跨域导航的非紧急状态更新交给 React transition，保持 URL、刷新、分享和浏览器历史语义不变。`ExplorerView` 组件回归 `28/28`；`make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端类型/构建、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 固定隔离端口全量 `124/124`，四视口各 `31/31`，INP `16–40ms`、LCP `92–128ms`、CLS `0`，视觉回归通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/research-transition-v1.9.81-chrome.json`，SHA-256 `7E1675FF576B98F81D42B827FC2E842542C027EE2379A31A4C0E73986EAC2B8A`。临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据关闭本地受控导航性能失败，但不替代目标环境生产 RUM P75、批准负载、正式授权数据或专业用户 UAT。

## v1.9.80 外部工作台批次

监控页的提醒中心、监控主题和已保存检索现在由统一 `monitor_tab` URL 状态驱动；点击、刷新、分享和浏览器后退恢复同一子视图，未知值规范化到提醒中心。路由契约与受控 `MonitoringView` 组件测试通过；`make check` 后端 `1151/1151`、前端 `350/350`、类型、构建、OpenAPI、Compose、Kubernetes 和运营契约均通过。

真实 Google Chrome `151.0.7922.71` 专项四视口 `4/4`、失败 `0`，报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/monitoring-route-v1.9.80-chrome-focused.json`，SHA-256 `AD23A1C68533CF18093CF5BFCAE9BDED0FDCC59D1FA20BD8FF5F2AAA8F6E693D`，JSON 统计 `expected=4、unexpected=0、flaky=0`，临时账号和实体恢复为 `0`。固定隔离端口的全量 `124` 用例最近一次为 `123` 通过、`1` 失败，唯一失败为桌面主导航 INP `224ms > 200ms`；该次未生成全量发布报告，因此性能体验门禁保持 `partial`，不能以专项 `4/4` 替代全量性能证据。`credentials_recorded=false`、`production_claim=false`。

## v1.9.79 外部工作台批次

监控主题表现在复用已保存检索的受控条件摘要；已有数据的监控操作失败保留原数据并提供重试入口，重试成功后清除错误。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/monitoring-context-v1.9.79-chrome-20260802-final1.json`，SHA-256 `feb1ffb063ad656a9ab077ee1bd06113457cabdfb8a4405cd3df69aa2d86ee19`，测试 `124/124`，浏览器版本 `151.0.7922.71`，四视口各 `31/31`，快照未更新，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明本地候选的真实监控上下文与错误恢复行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

## v1.9.78 外部工作台批次

所有专业已保存检索现在统一显示受控组合条件摘要：实体条件显示已选状态/数量，枚举条件显示已设置，文本和日期保留原值，分析维度、范围、阶段口径和聚合口径均可扫描；不改变事实查询或监控匹配。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/saved-search-conditions-v1.9.78-chrome-20260802-final1.json`，SHA-256 `958a4d216b4d26a03c739076ad66e0d07881cd3a4a9a391f542666f0152e69b0`，测试 `124/124`，浏览器版本 `151.0.7922.71`，四视口各 `31/31`，快照未更新，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明本地候选的真实保存检索摘要和回放行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

## v1.9.77 外部工作台批次

所有专业已保存检索现在统一显示列表、统计图、统计表或资讯时间线；标签来自受控保存查询展示状态，不改变事实查询或监控匹配。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/saved-search-view-labels-v1.9.77-chrome-20260802-final1.json`，SHA-256 `691c1e18916ded6d4ad3c83f76bcb37bd696d434bc9cf94de1a1a00bebc5eeb5`，测试 `124/124`，浏览器版本 `151.0.7922.71`，四视口各 `31/31`，快照未更新，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明本地候选的真实保存检索展示与回放行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

## v1.9.76 外部工作台批次

监控中心的全局实体已保存检索现在将受控实体类型映射为中文并按固定顺序展示，统计视图额外显示“统计图/统计表”，不改变查询 JSON 或事实匹配。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-saved-labels-v1.9.76-chrome-20260802-final2.json`，SHA-256 `abe737f113d50cb03e60ad34fe1ea6cf141a58f7213886673071fe46fc69d48d`，测试 `124/124`，浏览器版本 `151.0.7922.71`，四视口各 `31/31`，快照未更新，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明本地候选的真实保存检索展示和回放行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

## v1.9.75 外部工作台批次

全局实体检索的统计展示状态已进入版本化保存合同：从真实统计视图保存后，监控中心运行检索可恢复 `display=landscape&analysis_view=table`，并继续执行真实 facet 回筛；监控匹配不使用展示状态。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-saved-view-v1.9.75-chrome-20260802-final5.json`，SHA-256 `5e96fce651fbb6fd479440ecae2f6f744c76be8a29e5605245c72fba460e0186`，测试 `124/124`，浏览器版本 `151.0.7922.71`，四视口各 `31/31`，快照未更新，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该证据只证明本地候选的真实 API/数据库/Chrome 保存与回放行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

## v1.9.74 外部工作台批次

全局实体检索的服务端 facets、列表/统计切换、稳定 `display`/`analysis_view` 路由、统计表回筛和空结果深链状态已通过真实 Google Chrome 四视口验收。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-landscape-v1.9.74-chrome-20260802-final5.json`，SHA-256 `9d376654568dd60f58d9c7ee9739263ed1217e024e2715c1a4847a7fc41926ca`，测试 `124/124`，浏览器版本 `151.0.7922.71`，临时账号、实体、化学结构、活动、治理和入库夹具为 `0`，`credentials_recorded=false`、`production_claim=false`。该报告只证明本地候选的真实 API/Chrome 行为，不能替代正式数据授权、参考产品人工差异评审或商业发布门禁。

MCP 防提取控制可先在 WSL 隔离数据库中执行 `make mcp-anti-extraction-acceptance`。该门禁使用真实 PostgreSQL、迁移、RLS、API、MCP 协议和商业计量链路，验证深分页、游标篡改、字母/数字分区、跨客户端协同、网络与凭据轮换、人员风险台、凭据撤销与未授权导出；临时数据库在出具报告前强制销毁。`anti_extraction_baseline` 是 Development、Pilot 和 Production 都必须携带的本地实现基线，发布工具会重新解析全部场景、数据库终态和清理断言。报告明确标记 `production_claim=false` 和 `production_oidc_covered=false`，不能代替 Production 的真实 OIDC、网关、跨 client 关联、外部告警及安全/数据负责人审批类别 `anti_extraction`。

Agent 商业入口的本地门禁使用版本化语义合同。`pharma.entry-consistency-acceptance.v1` 绑定同一租户夹具的 Web 与收费 MCP 实体字段、筛选结果、协议、唯一结算和清理终态；`pharma.mcp-interoperability-acceptance.v3` 要求固定版本的官方 Inspector 与 Python SDK 发现同一 28 工具合同，并分别完成两页实体遍历、相同实体集合、篡改游标拒绝、错误后恢复、靶点与非空竞品管线读取、证据检索和五次有效收费调用。普通研究身份只发现四个异步导出工具；独立 `pharma.mcp-async-task-interoperability.v1` 在一次性 PostgreSQL 和对象存储中为 Inspector 与 Python SDK 分配两个独立 `data:export` client，分别验证审批等待、状态、取消、真实完成、签名 manifest、两页结果、游标篡改拒绝与恢复和唯一 settlement，随后销毁进程、数据库及制品。`anti_extraction` 仍单独证明未授权导出被拒绝。`pharma.mcp-commercial-acceptance.v2` 校验有界并发、分位延迟、逐成功调用唯一 settlement、无悬挂 reservation，以及幂等、参数冲突、领域失败、额度不足、取消、超时和余额恒等式。发布捕获、审计、组包和离线验包都会重新解析这些字段，额外字段、版本漂移、假结算或失败清理不能只靠退出码进入候选。
MCP 互操作验收脚本现在显式绑定 `COMPOSE_PROJECT_NAME`/`--project-name` 并尊重 `COMPOSE_FILE`，避免在多套本地或预生产 Compose 运行线之间误探测；该脚本契约修复已完成静态检查，但本轮共享 WSL 通道未恢复，真实 Inspector/Python SDK 运行结果仍待补验。

宿主机真实 Google Chrome/Playwright 在 `desktop-1440`、`desktop-1920`、`tablet-1024` 和
`mobile-390` 四个视口完成登录入口烟测：HTTP `200`、邮箱/密码字段和登录按钮各存在 1 个，
四个视口均无横向溢出。对本地 MCP `/mcp` 端点的真实未认证 GET 返回 HTTP `401`、
`invalid_token`；这证明认证边界 fail closed，但不替代带批准凭据的 Inspector/Python SDK
工具发现、计量、分页和互操作证据。

同一真实 Chrome 烟测还验证了双工作台入口：`/workspace/research` 返回
`data-workbench=research` 与“医药情报工作台”，`/workspace/internal` 返回
`data-workbench=internal` 与“内部管理工作台”；两条路由均保持独立登录壳和 200 响应。

`database`、`operations_contract`、`parser_sandbox` 与 `ocr` 同样不能只靠命令退出码。`pharma.local-database-acceptance.v1` 固定核对 PostgreSQL/RDKit/Alembic、签名租户上下文 RLS、持久数据卫生、OpenSearch 3.7 alias 和投影队列，并明确本地确定性 embedding 不是生产模型证明；`pharma.local-observability-acceptance.v1` 要求四次真实收费调用有四个唯一 settlement，且调用数与延迟指标经 OTLP-gRPC 到达 Collector；`pharma.local-parser-sandbox-acceptance.v3` 锁定十一种真实格式及解析器版本、容器 CPU/内存/PID/只读根目录/最小 secret scope/内部网络、真实并发饱和 `429`/恢复、子进程墙钟超时回收，以及九类临时对抗文档经真实 HTTP 链失败关闭后的恢复，并验证 mTLS 双向信任和外网阻断。独立 `pharma.local-ocr-acceptance.v1` 必须使用固定 PP-OCRv5 检测/识别模型，通过真实 HTTP 服务识别中英文 PNG 与扫描 PDF，校验模型目录摘要、Paddle 版本、逐页区域定位、置信度和文本摘要。四类报告都标记 `production_claim=false`，不能代替托管数据库、生产监控、外部恶意样本库或目标集群演练。

候选末尾的 `runtime` 门禁必须附带 `pharma.local-runtime-acceptance.v3`。报告从实际 Compose 状态、健康检查、两个受治理人员工作台、MCP/parser 入口、Alembic、PostgreSQL/RDKit、OpenSearch 投影和持久数据卫生命令生成，以 `0600` 原子独占写入；两个工作台必须分别通过 GET/HEAD、HTML 类型、SPA shell、CSP 和防嵌入响应头验证，并记录匹配的入口文档、`data-workbench` 标记和互不相同的 HTML SHA-256。发布工具会拒绝缺少任一必需服务或工作台、两个路由返回相同文档、未认证 MCP 不再返回 401、迁移或版本漂移、搜索队列积压、测试残留以及主运行时修改。验证器保留对历史 `v1`、`v2` 候选的读取能力，但新候选只生成 `v3`。该证据证明当前本地运行线在候选结束时仍健康，不等于目标环境可用性或 SLO 证明。

内部平台运营页只读取受控证据根目录，不生成或改写发布证据。部署方可将仓库外目录以只读方式挂载并设置 `PLATFORM_EVIDENCE_ROOT`；读取器只接受 `backup_restore/report.json` 的 `pharma.local-backup-restore-acceptance.v1`、`candidate-summary.json` 和 `production_topology/report.json` 的 `pharma.production-topology-live-probe.v1`，同时执行文件类型、大小、JSON schema、状态和摘要边界检查。目录未配置、文件缺失、无效或只含本地证据时，UI 必须分别显示 `not_configured`、`missing`、`invalid` 或非生产结论，不能把它们折算为生产健康。API 不执行报告命令，也不需要 Docker socket 或写入证据目录。

## 信任边界

- `capture` 仅在工作树干净、当前提交与安全报告的源码树摘要一致时启动命令；命令结束后再次核对，源码变化会使记录失败。
- 门禁命令使用 argv 直接执行，不经过 shell。令牌和密码必须从受控环境注入，禁止放在命令参数、附件或证据 JSON 中。
- `assemble` 拒绝失败、过期、跨提交、跨镜像、附件被修改或类别缺失的 statement；目标目录已存在时拒绝覆盖。
- Pilot 可以使用无签名包，但它只能校验目录内的一致性，不能证明发布者身份，也不能抵御攻击者整体重写后重算摘要；Production 强制 release-mode 安全报告、已验证的签名 Git tag、全部生产类别和外部 Ed25519 签名密钥及可信公钥验证。
- `verify` 不访问网络，可检查完整文件集合、SHA-256、manifest 交叉引用和签名。签名包必须显式提供组织信任库中的公钥，包内不得自带并信任公钥。
- 证据包始终记录 `production_claim=false` 和 `approval_status=pending_deployment_approval`；完整证据只能进入审批，不能自行授予上线资格。

证据策略位于 `deploy/release/evidence-policy.json`。Development 只覆盖干净提交复现、质量、数据库、浏览器、Web/MCP 实体一致性、Web/MCP/标准导出记录一致性、MCP 反提取实现基线、MCP、双入口性能基线、隔离解析与真实 OCR、自动入库平台准备度和运行线，不代表 Pilot；Pilot 额外要求真实入库、备份恢复和 Kubernetes 清单；Production 类别与 `docs/commercial-readiness.md` 的正式商用阻断面一一对应，不能通过删除策略项绕过。`ingestion_readiness` 在没有注册来源时只允许报告 `ready_for_source_registration`，并强制 `real_source_automatic_ingestion_verified=false`；一旦运行控制缺失或已注册来源被治理门禁阻断，候选直接失败。`mcp_commercial` 使用报告 schema `2.0`，除有界并发、P50/P95/P99 和逐成功调用唯一 settlement 外，还真实验证幂等重放不重复扣费、参数冲突拒绝、领域失败释放、额度不足拒绝、客户端取消竞态及余额恒等式。`performance_baseline` 使用 `pharma.local-performance-baseline.v1`，真实执行 Web/MCP 持续与峰值混合流量、协议层并发幂等争用和取消/超时恢复，并显式保留长稳、目标基础设施故障和生产批准缺口；这些报告都只能独占创建且权限为 `0600`。

GOAL 第 19 节的 24 条条件由 `deploy/release/goal-section-19-matrix.json` 逐条绑定到上述类别；其结构由同目录 JSON Schema 描述，运行时还校验固定文档 ID、GOAL 版本、顺序、分组、策略类别和完整包覆盖。`audit` 输出 `goal_section_19`：`proven` 表示该条件的生产类别及附加控制已满足，`baseline_only` 表示仅有 Pilot 级实现证据，`missing` 表示连该条件的本地/试点基线仍不完整。签名发布包携带矩阵与 schema 快照；离线验包会在摘要和 Ed25519 验签后重新计算逐条状态，拒绝手工改写计数或结论。即使 24 条都显示 `proven`，只要整个发布审计存在重复类别、主体绑定、签名或其他 blocker，`production_complete` 仍为 `false`。

## WSL Development 候选

在本地服务已经启动、当前提交已有安全证据时，可以一次性记录全部本地必选门禁、审计并组装无签名 Development 包。运营合同门禁会执行真实收费 MCP 请求，并确认业务指标经 OTLP 到达本地 Collector；OCR 门禁运行固定真实模型识别中英文 PNG 与扫描 PDF；自动入库准备度门禁会精确核对五类连接器、Temporal 调度、来源根、恶意内容扫描、隔离解析器、已注册来源治理状态和所需运行服务：

```bash
make release-candidate \
  SECURITY_EVIDENCE=manifests/runtime/security/20260717T011730Z
```

MCP 测试令牌默认从 `~/.config/pharma-intelligence/agent-gateway.key` 读取；文件必须属于当前用户、不是符号链接且权限不宽于 `0600`。也可以通过 `MCP_TOKEN_FILE=/secure/path` 指定。候选输出位于被 Git 忽略的 `manifests/runtime/release-candidates`，命令参数、日志和 statement 均不保存令牌。Development 包只证明当前本地运行线可复现，不能对外宣称 Pilot 或 Production 就绪。

需要在同一个 Development 候选中额外证明全量隔离恢复和真实 Kubernetes API Server 清单校验时，显式启用加固门禁：

```bash
make release-candidate \
  SECURITY_EVIDENCE=manifests/runtime/security/<stamp> \
  RELEASE_CANDIDATE_ARGS="--include-backup-restore --include-kubernetes"
```

该候选在普通 Development 基础上额外记录恢复和 Kubernetes 两类门禁。`backup_restore` 会在 `backups/release-candidates` 保留一份完整备份，发布包仅收录 `pharma.local-backup-restore-acceptance.v1` 摘要；Pilot 候选在快照期间会短暂停顿 API、MCP、后台写入服务及 Temporal，并通过退出清理保证恢复，避免自动调度写入破坏跨存储快照的一致性。WSL systemd 同时注册独立的十分钟恢复守卫，即使采集进程被强制终止也不会无限期保留暂停状态。`kubernetes` 使用可销毁的三节点 kind 集群和固定摘要资产，发布包仅收录 `pharma.local-kubernetes-validation.v3` 报告；除 server-side dry-run 外，v3 还实际启动双副本 ClamAV StatefulSet，验证跨两个 worker/测试 zone 分布、独立 PVC、签名 freshness、干净/EICAR 扫描和单 Pod 删除期间至少一个 Service endpoint 持续 Ready。两类报告都会被捕获、审计、组包和离线验包重新做语义校验，但仍是 `production_claim=false` 的本地工程证据，不能代替目标云环境的 HA/PITR、灾备演练、容量或变更审批。普通 Development 默认不生成完整备份；Pilot 仍无条件要求备份恢复。

Pilot 的 AI 治理必须由部署环境注入已批准的第三方 HTTPS 模型 API 配置。发布工具不启动、不下载也不缓存本地模型；provider 的真实协议、费用、限流、usage、request ID 和失败关闭行为必须作为独立验收证据。

自动入库报告 v4 区分 `new_version`、`policy_reprocess` 和 `unchanged`：三者分别证明自然调度发现并治理了新的不可变版本、同一不可变版本按新 AI 治理策略重新治理、以及未变更真实源的幂等扫描。报告只允许从无处理中版本的静止快照开始，并同时绑定开始前最新 workflow 的 `(created_at, id)` 水位、实际观察到的新 workflow 时间、治理策略 SHA-256 及该策略成功运行数增量，不能把更早的历史任务或其延迟下游结果误报为本次验收。所有结果都要求已有版本具备完整快照、病毒扫描、模型计量、原文定位事实和 OpenSearch 投影，并禁止手工触发、修改扫描周期或由测试创建源内容。

`initial_due_in_seconds` 是观察边界处的调度快照，不作为运行出现时间的下限：调度器可能已在数据库观测边界并发启动、尚未创建 ingestion run。验收仍要求基线之后出现新的 `source-ingest-<source-id>-*` workflow、成功且计数语义与 `outcome` 一致，从而不会把手工扫描或旧运行误认为自动调度。

`source_reproducibility` 不复用当前工作目录的忽略文件。它从干净 `HEAD` 导出无 `.git` 的临时源码树，校验源码摘要后使用 `.env.example`，真实执行锁定 Python/Node 安装、后端和前端测试、前端 production build、Compose/Kubernetes 渲染、一次性 PostgreSQL/RDKit 升降级回环、最终运行镜像构建和无网络非 root 容器烟测。临时源码、随机数据库容器和唯一镜像标签结束后强制清理。捕获、审计、组包和离线验证都会重新解析报告的全部契约检查、6 项命令及镜像身份；空报告不能满足类别。该门禁证明工程可复现，不替代目标环境部署、PITR 或非开发人员恢复演练。

`browser` 门禁不接受只有 Playwright 退出码或测试总数的报告。`pharma.browser-acceptance.v9` 必须记录严格配对的真实 `chrome/Google Chrome` 或 `msedge/Microsoft Edge` channel、产品和四段版本号，并证明 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四个项目都执行外部查询登录、内部管理登录、两侧品牌与导航双向隔离、查询与运营工作台、认证导航、检索与深链接、会话恢复、权限拒绝、真实 viewer/admin 权限边界、完整状态、监控、计费争议、监管情报和 RDKit 场景。候选兼容性要求分别执行 Chrome、Edge 当前主版本和 Edge 前一主版本；每个项目还必须用 axe 对公开登录页及全部 14 个外部工作域执行 WCAG 2.2 A/AA 自动审计，并执行 `320 CSS px` 键盘登录、导航和核心研究页重排场景；当前自动化还以 `720/360 CSS px` 等效视口补充 200%/400% 缩放布局代理，报告必须将该范围标记为 `system_zoom_verified=false`。报告缺少 `reflow_keyboard` 或 `real_permission_boundary` 时失败关闭。报告必须包含逐视口受控导航 LCP/INP/CLS、交互计数、像素比较阈值、视口尺寸，以及空结果全页、真实密集结果表格 shell、临床结构化终点、专利时间线和交易地域权益五种状态的基线 SHA-256，并确认临时账号、实体与凭据残留为零。Chrome 基线更新是显式审查操作，`--update-snapshots` 不得与证据输出同时使用；Edge 运行始终禁止更新基线。Playwright Chromium 或 Codex 内置浏览器不能替代该门禁；自动 axe、等效视口重排和本地受控指标仍不替代操作系统级缩放、人工辅助技术测试、Production RUM P75、能力矩阵和真实用户 UAT。

`real-target-dossier` 是上述 browser 合同的独立真实数据证据：必须先通过真实 `GET /api/v1/targets/{target_id}/dossier` 返回 `200` 并核对靶点实体及非空跨域集合，再通过真实 `GET /api/v1/targets/{target_id}/sar-comparison` 返回 `200`，逐一验证 dossier 的关系、证据、活性、管线、临床、专利、交易、监管、新闻和结构标签可进入；该场景不得用业务 API 响应 mock，且仍不替代正式授权数据和 UAT。

参考产品与本平台的同视口留证使用 `deploy/release/reference-visual-pair.schema.json` 和 `scripts/reference_visual_pair.py`，不把第三方截图提交到源码仓库。登记时必须给出外部只读图片、无查询参数的 HTTPS 页面、版本、外部制品 ID、授权工单、工作流、视口和捕获时间；工具校验 PNG、摘要、本平台权威基线、视口及安全声明，只在仓库外以 `0600` 创建内容寻址清单。复验使用 `make reference-visual-pair-verify REFERENCE_VISUAL_PAIR=<manifest> [REFERENCE_VISUAL_IMAGE=<external-png>]`；提供外部图片时同时复核二进制摘要，不提供时仍复核清单身份和仓库自有基线。该机制固定保持人工审查 `pending` 且不产生自动等价结论，真实参考证据和批准记录由外部发布证据包管理。

## 记录门禁

v1.9.73 的 `real-target-dossier` 证据还必须证明 dossier 的 `activities` 与 `structures` 集合非空，活性表包含真实 `IC50` 记录，结构页包含真实 InChIKey，且 SAR 响应的 `total` 与 `items` 均大于 0；知识/证据连续性必须来自真实 PostgreSQL/OpenSearch 投影，清理报告必须记录受治理夹具为 `0`。

`entry_consistency` 使用持久本地运行线验证同一实体在 Web 与收费 MCP 的读取、检索和清理一致。`record_consistency` 另建一次性 PostgreSQL 数据库并执行全部迁移，在临时 API/MCP 上发布一条带源资产、源版本、原文位置和 claim 的活性事实；随后通过 Web、收费 MCP 和 `fact_provenance` 标准导出读取，要求同一权威 ID、源版本、源文档和 locator 完全一致，三项收费操作各有唯一 settlement，导出 manifest 已签名，进程和数据库全部销毁。

`pharma.record-consistency-acceptance.v1` 固定标记 `controlled_fixture=true`、`production_claim=false`。发布捕获、审计、组包和离线验证都会重新解析字段清单、协议操作、摘要、结算数、导出及清理断言；它证明跨入口实现一致，不能替代合法授权数据覆盖、真实靶点查询、生产账单或业务 UAT。

`mcp_async_tasks` 是 Development、Pilot 和 Production 证据策略中的独立必需类别。它证明两个官方客户端在隔离本地边界内完成高权限异步任务协议互操作，但固定声明 `production_claim=false`，不能替代目标 IdP sender constraint、生产对象存储、合同审批、真实账单或外部 Agent UAT。

可单独运行：

```bash
make record-consistency-acceptance
```

## WSL Pilot 候选

本地候选开始时只部署安全门禁已经从 staged source 构建和扫描的镜像，不在候选阶段重新构建 mutable tag。运行时报告记录每个必需容器的不可变 image ID，并与 gate statement 中的 API/PostgreSQL target digest 交叉校验；OCR 由独立真实模型门禁验证，安全报告和生产拓扑分别绑定 OCR 镜像 digest。任一旧容器、未扫描镜像或 OCR 模型版本漂移都会阻止相应候选。

Pilot 必须指定工作台中已注册、当前可访问且有有效 Web/MCP 许可策略的真实只读来源。候选首先在不调用手工扫描、不修改来源调度元数据的情况下等待 Temporal scheduler 自然启动严格晚于起始水位的新 workflow，并生成自动入库报告；随后连续手工复扫两次，只验证不可变快照、真实解析或资产登记、来源追溯、失败记录、幂等与 OpenSearch 投影。两份入库附件都存在后，才创建全量权威备份，并在隔离容器和临时卷中恢复 PostgreSQL、Temporal、RDKit、RLS、对象存储和 Markdown 归档。

```bash
make release-candidate \
  RELEASE_LEVEL=pilot \
  SECURITY_EVIDENCE=manifests/runtime/security/20260717T011730Z \
  RELEASE_CANDIDATE_ARGS="--ingestion-source-id <registered-source-uuid>"
```

若来源的真实扫描周期长于默认 900 秒，在不修改来源调度元数据的前提下向同一个参数串添加 `--automatic-ingestion-timeout <60..86400>`。候选会真实等待该来源到期；不提供“立即置为到期”的测试后门。

也可以单独运行：

```bash
make ingestion-acceptance INGESTION_SOURCE_ID=<registered-source-uuid>
make backup-restore-acceptance
```

入库验收不创建或上传任何来源文件，也不接受空目录；真实来源不可访问、许可缺失/过期、解析失败、第二次扫描重复建版或投影队列未清空都会失败关闭。备份保留在 Git 忽略的 `backups/release-candidates`，证据包只包含无敏感数据的摘要和 checksum 绑定，不复制数据库 dump 或对象归档。无签名 Pilot 包仍不能证明发布者身份，也不等于 Production。

Pilot 类别固定为 `ingestion_pilot`，并且必须恰好包含 `pharma.automatic-ingestion-evidence.v4` 与 `pharma.ingestion-pilot-evidence.v2` 两份报告。自动报告必须先观察严格晚于捕获水位的自然 Temporal 调度，证明新版本治理、当前策略重治理或 unchanged 幂等之一；随后手工复扫只能证明 unchanged 幂等，不能预先消费来源对象。发布捕获、审计、组包和离线验包会重新核对同一 source/license/dataset、连接器身份、非空稳定对象、两个不同成功 run、治理策略指纹与运行增量、全部可治理版本已完成 AI 治理和搜索投影、实际响应模型、成功 extraction run、token/费用元数据、provider request ID、响应哈希、逐段核算、至少一个 staged fact 和服务端从原文计算的 quote locator，以及零投影积压。任何禁用 AI、零事实、模型自报 locator、旧 workflow 冒充本次调度、手工触发、调度修改、测试创建来源内容、跨来源拼接或时间顺序错误都会失败。

Production 另要求外部 `ingestion` 门禁，不能复用 `ingestion_pilot` 冒充目标环境。它必须在非本地预生产或生产环境证明许可来源清单、自动发现、不可变快照、恶意扫描、真实解析、AI 治理、权威发布、搜索投影、通知、幂等重扫、失败恢复和事实追溯，并绑定至少两项客观工件以及 data_owner/operations 审批。

先在当前干净提交上生成安全证据，再用同一个目录记录其他门禁。附件必须位于 statement 输出目录之下。命令成功时，每个声明附件都必须已生成，否则捕获失败关闭；命令失败时，statement 保留原始退出码、已有日志以及 `missing_attachments` 清单，避免缺失报告掩盖门禁的真实失败原因。失败 statement 不能进入证据包。需要保留命令输出时显式使用 `--log-attachment`；日志以 `0600` 独占创建、最大 64 MiB 并计入摘要，操作员必须先确认输出不包含令牌、密码、客户数据或其他敏感载荷。

```bash
SECURITY_DIR=manifests/runtime/security/20260717T011730Z
EVIDENCE_DIR=manifests/runtime/release-captures/candidate-1

uv run python scripts/release_evidence.py capture \
  --category quality \
  --security-dir "$SECURITY_DIR" \
  --output "$EVIDENCE_DIR/quality.statement.json" \
  --log-attachment "$EVIDENCE_DIR/quality.log" \
  -- make check
```

需要保留机器报告时，把报告写到同一目录并声明为附件：

```bash
uv run python scripts/release_evidence.py capture \
  --category mcp_protocol \
  --security-dir "$SECURITY_DIR" \
  --output "$EVIDENCE_DIR/mcp-protocol.statement.json" \
  --attachment "$EVIDENCE_DIR/mcp-interoperability.json" \
  -- ./scripts/verify-mcp-interoperability.sh \
     --mcp-url http://127.0.0.1:8090/mcp \
     --output "$EVIDENCE_DIR/mcp-interoperability.json"
```

### MCP 持有证明生产证据

`mcp_sender_constraint` 只属于 Production，不能用本地 DPoP/Valkey 自测充数。其 statement 必须同时附带通用 `production-evidence-report.json`、名为 `mcp-sender-constraint-report.json` 的详细语义报告、至少一份其他客观工件，以及 security/platform 两个角色的审批实物。详细报告必须作为通用报告的 `artifacts[]` 成员绑定；发布工具在捕获后和离线验包时都会重新解析，而不是只检查 `status=passed`。

详细报告必须符合 `deploy/release/mcp-sender-constraint-report.schema.json` 中的 `pharma.mcp-sender-constraint-evidence.v2`，绑定当前 statement 的 commit、源码树和镜像主体，并记录非本地 `environment_id`。它还必须记录两个独立且支持 DPoP 的 Agent 客户端、真实 HTTPS IdP 与 MCP resource URL、共享 TLS replay store，以及 IdP、网关和安全审批引用。签名校验、`jkt/ath/htm/htu/iat/jti`、普通 Bearer 拒绝、重放缓存失败关闭、密钥轮换和令牌吊销必须全部为真；缺少任一项都会阻止 Production 审计和离线验证。

仓库内真实 JWKS、OIDC 签名、DPoP 和 Valkey 集成测试只证明实现边界可运行，仍不能生成上述生产类别。

### 外部生产门禁证据

`ingestion`、`product_uat`、`data_licensing`、`external_services`、`infrastructure_ha_pitr`、`billing_provider`、`mcp_sender_constraint`、`anti_extraction`、`performance`、`penetration_test`、`disaster_recovery`、`operations_approval` 和 `change_approval` 不再接受“命令返回 0”作为生产证据。每个类别必须附带 `production-evidence-report.json`，并使用附件绑定的 `pharma.production-gate-evidence.v2`。结构参考 `deploy/release/production-evidence-report.schema.json`；策略中的 checks、审批角色和最少工件数仍是更严格的运行时权威。

`product_uat` 至少绑定两项独立工件，必须覆盖批准的同级能力矩阵、核心用户流程、支持浏览器、加载/空/错误/无权限/恢复状态、检索/对比/监控、标准数据导出、管理流程和业务 UAT 批准。`data_licensing` 除合同、字段和渠道权利外，还必须分别证明文献、专利、靶点、结构、活性、管线、临床、公司、交易和监管十类数据的实际覆盖范围及 freshness/coverage 报告；用一个泛化 `domain_coverage` 布尔值不能通过 Production 审计。`external_services` 中的真实模型网关还必须分别验证 strict schema、usage/request ID、成本计量、引用对齐、prompt injection 防护、限流退避和失败恢复，不能用单一 `model_gateway=true` 代替。

`production_topology` 独立证明 GOAL 第 11、19 节要求的生产架构与版本矩阵，必须绑定批准架构和真实部署清单，明确 PostgreSQL/RDKit 兼容版本、对象存储、OpenSearch、Temporal、Kafka/Debezium、Valkey、网关、Kubernetes 以及 RAGFlow 迁移退出计划，并由 architecture/platform/operations 批准。它不能由本地 Compose、通用 Kubernetes render 或变更工单替代；拓扑声明与目标集群实时观测是两份不同证据，任一缺失都会失败关闭。

详细拓扑报告必须命名为 `production-topology-report.json` 并符合 `pharma.production-topology-evidence.v1`。Core Commercial profile 使用 PostgreSQL transactional outbox，不被错误强制部署 Scale 组件；Scale Production profile 才要求 Kafka `4.x`、Debezium `3.x`、ClickHouse 和 Iceberg。两种 profile 都要求两个不同 HTTPS 公共入口、PostgreSQL `18.x`（或带 ADR 的 `17.x`）、RDKit `2026.03.x`、OpenSearch `3.7.x`、Temporal HA、Valkey `9.x`、企业身份/密钥、Gateway/Kubernetes、集中可观测性和权威数据边界，并明确拒绝 PostgreSQL 16 或 RAGFlow 进入关键路径。

目标集群探测报告必须命名为 `production-topology-live-probe.json` 并符合 `pharma.production-topology-live-probe.v1`。它由只读探针直接读取目标 Kubernetes API，要求至少三个 Ready 且可调度节点分布在两个可用区，核对九个固定工作负载的副本、generation、当前发布镜像 digest、PDB/HPA、双向 default-deny NetworkPolicy、已 Programmed Gateway 和恰好两个路由主机；随后通过系统 CA 或显式企业 CA 真实访问人用 HTTPS 工作台并要求 `200 + HSTS`，以无凭据 MCP initialize 请求验证 Agent 入口返回 `401/403 + HSTS`。报告只保存上下文哈希、证书哈希和非敏感观测，不保存 kubeconfig、令牌、证书内容或响应正文。

在批准的预生产或生产操作机执行；本地、development、test、kind、minikube 或 Docker 上下文会在访问集群前被拒绝。输出必须位于仓库外且拒绝覆盖：

```bash
make production-topology-live-probe \
  PRODUCTION_SECURITY_EVIDENCE=/secure/release-security/20260722T062209Z \
  PRODUCTION_TOPOLOGY_REPORT=/secure/intake/production-topology-report.json \
  PRODUCTION_TOPOLOGY_OUTPUT=/secure/intake/production-topology-live-probe.json \
  PRODUCTION_ENVIRONMENT_KIND=preproduction \
  PRODUCTION_ENVIRONMENT_ID=preprod-us-east-1 \
  PRODUCTION_KUBE_CONTEXT=company-preprod \
  PRODUCTION_NAMESPACE=pharma-intelligence
```

通用生产报告必须把详细拓扑报告、实时探测报告及至少两项独立部署/版本工件绑定为 artifact，因此该类别最少四项工件；缺少任一 architecture/platform/operations 审批均失败关闭。实时报告必须与详细拓扑报告的 SHA-256、环境、时间、发布源码树和镜像主体完全一致，登记、审计、组包及离线验包都会重新解析这些约束。

报告必须标识非本地的 `preproduction`/`production` 环境，完整绑定 statement 中的 commit、源码树和镜像，且提供策略中精确定义的全部检查项、执行机构和真实工件。每个 `artifacts[]` 项必须声明候选目录内的 `path`、`size`、`sha256` 和外部追踪 `reference`；文件必须作为同一 gate statement 的附件进入发布包。每个 `approvals[]` 项除角色、组织、时间和工单引用外，还必须通过 `artifact_path`、`artifact_size`、`artifact_sha256` 绑定一份独立审批记录。报告不能自引用，同一附件不能复用为多个工件/审批，额外的未引用附件也会失败。

渗透测试还强制执行方 `independent=true`。检查项缺失/为假、摘要伪造、附件缺失或篡改、本地环境、跨提交报告、证据过期、审批未附实物或非独立渗透测试都会在 `capture`、`audit`/`assemble` 和离线 `verify` 三个阶段失败关闭。类别所需的精确 checks/审批角色以 `deploy/release/evidence-policy.json` 为权威定义。审批记录可以是客户批准的签名 PDF、工单导出或不可变审计 JSON；其 `approved_at` 不得早于本次 `tested_at`，仅允许五分钟跨系统时钟偏差，也不得晚于证据登记时间五分钟以上。发布系统不生成这些记录，也不允许复用旧审批或用仓库内自签样例代替真实审批。

### 生产证据受控登记

外部团队不需要手写带摘要和 release subject 的最终报告。先读取某一类别的权威要求：

```bash
uv run python scripts/release_evidence.py production-requirements \
  --category performance
```

`production-requirements` 当前返回 `pharma.production-evidence-requirements.v2`；`detail_reports` 会机器可读地列出 `mcp_sender_constraint` 的一份额外报告，以及 `production_topology` 的拓扑声明和实时探测两份报告，包括文件名、schema ID 与仓库 schema 路径，其余类别返回空数组。

按 `deploy/release/production-evidence-intake.schema.json` 创建 intake request。`checks[]` 必须与上述输出完全一致；`artifacts[]` 和 `approvals[]` 分别声明真实源文件的绝对路径、证据目录内目标路径和外部工单或报告引用。审批角色、最少工件数、独立执行方要求和有效期均来自策略，不能由 request 降低。

```bash
uv run python scripts/release_evidence.py register-production \
  --security-dir /secure/release-security/20260719T115640Z \
  --request /secure/intake/performance.json \
  --output /secure/release-evidence/performance
```

登记器只接受仓库外的绝对路径普通文件，拒绝符号链接、空文件、重复源、路径穿越和覆盖已有目录。单文件上限 1 GiB、单类别附件总量上限 4 GiB；附件在读取期间发生变化也会失败。普通工件目标必须位于 `artifacts/`，审批文件必须位于 `approvals/`；`mcp_sender_constraint` 的详细报告使用策略要求的顶层 `mcp-sender-constraint-report.json`，`production_topology` 的两份详细报告分别使用顶层 `production-topology-report.json` 和 `production-topology-live-probe.json`。Intake JSON Schema 按 `category` 限定这三类专用路径，不能把某一类别的详细报告路径复用到其他生产门禁。

工具把真实文件复制为 `0600`，不在最终报告保留操作机源路径；随后自动计算大小和 SHA-256、绑定当前 clean commit、源码树、镜像与安全证据，生成 `production-evidence-report.json` 和 `gate-statement.json`，并在原子发布目录前运行同一 Production 语义验证器。任一步失败都会删除暂存目录，成功目录拒绝覆盖。intake request 本身不会进入证据包，以免泄露操作机路径。输入应是最小化后的测试报告、合同清单或审批记录，不能把客户原始数据、密钥或令牌作为证据附件。

该命令只登记外部证据，不生成 UAT、授权、渗透测试、审批或生产事实，也始终返回 `production_claim=false`。真实审批文件和客观报告仍必须由对应责任方提供。

不要直接向多个外部团队分发仓库副本。先从干净提交生成不可覆盖的 requirements-only 交接目录：

```bash
make production-evidence-handoff \
  PRODUCTION_HANDOFF_OUTPUT=/secure/handoffs/release-2026-07 \
  PRODUCTION_HANDOFF_SIGNING_KEY=/secure/release-ed25519.pem \
  PRODUCTION_HANDOFF_SIGNING_KEY_ID=production-release-2026-v1

make production-evidence-handoff-verify \
  PRODUCTION_HANDOFF=/secure/handoffs/release-2026-07 \
  PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY=/secure/release-ed25519.pub

# 外部责任方无需源码仓库即可执行
make production-evidence-handoff-offline-verify \
  PRODUCTION_HANDOFF=/secure/handoffs/release-2026-07 \
  PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY=/secure/release-ed25519.pub
```

交接目录绑定 commit、源码树和权威策略摘要，包含全部外部生产类别的独立 requirements JSON、策略快照、GOAL 第 19 节矩阵及 JSON Schema，但不包含 intake 占位、通过结论、客户数据或审批。正式跨组织分发必须使用权限为 `0600` 的 Ed25519 私钥签发，并通过独立可信渠道分发公钥；外部责任方可脱离源码仓库核对完整文件清单、策略、目标矩阵、逐类别 requirements 和清单签名。本机未签名模式只用于草拟，不能作为正式签发物。Production 的 `audit` 和 `assemble` 强制使用当前提交内的 `deploy/release/evidence-policy.json`；`--policy` 不能用仓库外删减策略覆盖正式门禁。

当权威策略定义的全部外部类别真实 intake request 都已由责任方提供后，使用 `pharma.production-evidence-batch-intake.v1` 清单一次登记。清单只列出类别和各 intake request 的仓库外绝对路径；类别集合必须与权威策略完全一致：

```bash
make production-evidence-batch \
  SECURITY_EVIDENCE=/secure/release-security/20260719T115640Z \
  PRODUCTION_BATCH_MANIFEST=/secure/intake/batch-intake.json \
  PRODUCTION_BATCH_OUTPUT=/secure/release-evidence/external-production
```

批量登记要求 release-mode 安全证据，逐类别复用同一严格语义验证器，并在最后重新核对源码和安全 manifest。任何较晚类别失败时，已暂存的较早类别也会全部删除；目标目录只在全部类别均成功后通过 Linux no-replace 原子发布。输出的 `batch-manifest.json` 记录每个 statement 的相对路径和摘要，仍固定 `production_claim=false`。

企业管理属于 browser 语义合同的必选场景，桌面和移动项目都必须验证管理员可见、当前管理员自保护和带版本号的角色变更；只增加测试总数不能满足该场景。

## 审计与组包

`audit` 返回 `0` 表示类别和绑定满足该等级，返回 `3` 表示仍有真实缺口，输入或证据结构无效则返回 `2`。下面的 Production 审计在外部门禁未完成时必须返回 `blocked`：

```bash
uv run python scripts/release_evidence.py audit \
  --level production \
  --security-dir "$SECURITY_DIR" \
  --output manifests/runtime/releases/production-gap.json \
  --statement "$EVIDENCE_DIR/quality.statement.json"
```

候选目录和外部批次目录可通过 `--statement-dir` 传入。工具只发现该目录下一层合法类别目录中的 `gate-statement.json`，拒绝符号链接、重复路径、空目录和超过 128 个 statement，不会递归吸入历史 bundle：

```bash
make release-audit \
  RELEASE_LEVEL=production \
  SECURITY_EVIDENCE=/secure/release-security/20260719T115640Z \
  RELEASE_STATEMENT_DIRS="/secure/local-candidate /secure/release-evidence/external-production" \
  RELEASE_TAG=v0.1.0
```

Pilot 组包需要策略列出的全部 Pilot statement。路径可以重复传入 `--statement`：

```bash
uv run python scripts/release_evidence.py assemble \
  --level pilot \
  --security-dir "$SECURITY_DIR" \
  --statement "$EVIDENCE_DIR/quality.statement.json" \
  --statement "$EVIDENCE_DIR/database.statement.json" \
  --output manifests/runtime/releases/candidate-1
```

Production 还必须传入指向当前提交且能被 `git verify-tag` 验证的 tag，以及仓库外权限为 `0600` 的 Ed25519 私钥。加密 PEM 的口令只能通过 `RELEASE_SIGNING_KEY_PASSWORD` 注入。

```bash
uv run python scripts/release_evidence.py assemble \
  --level production \
  --release-tag v0.1.0 \
  --security-dir "$SECURITY_DIR" \
  --signing-key /secure/release-ed25519.pem \
  --signing-key-id production-release-2026-v1 \
  --statement ... \
  --output manifests/runtime/releases/v1.0.0
```

## 离线校验

```bash
make release-verify RELEASE_BUNDLE=manifests/runtime/releases/candidate-1

make release-verify \
  RELEASE_BUNDLE=manifests/runtime/releases/v1.0.0 \
  TRUSTED_PUBLIC_KEY=/trusted/release-ed25519.pub.pem
```

归档时必须保存整个目录，不能只保存 `release-manifest.json`。`SHA256SUMS` 不允许缺文件或存在未登记文件；任何修改都会使离线校验失败。私钥、环境变量、客户凭据和真实数据不得进入证据包。
