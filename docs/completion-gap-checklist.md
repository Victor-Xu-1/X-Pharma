# 项目完整缺口与验收清单

| 字段 | 内容 |
|---|---|
| 文档 ID | `PIP-GAP-001` |
| 权威目标 | [`GOAL.md`](../GOAL.md) |
| 适用范围 | Code Complete、Pilot、Commercial Production、Scale Production 条件项 |
| 当前判断 | 本地代码基线已具备；修复后的真实 Google Chrome/Playwright 串行全量为 `124/124`，四视口各 `31/31`；后端非集成全量为 `1176 passed`、覆盖率 `84.54%`；4-worker `119/124` 仅作为并发资源争用历史基线；Commercial Production 未完成 |
| 更新规则 | 只有完成判据全部满足且证据可定位时，才把 `[ ]` 改为 `[x]`；部分实现、测试替身、本地通过或口头批准均不得勾选 |

本表是项目剩余工作的单一勾选入口。详细技术状态仍由外部/内部能力矩阵、`docs/commercial-readiness.md` 和 `docs/release-evidence.md` 管理；发生冲突时，以 `GOAL.md` 的完成标准和更严格证据为准。任何新发现的生产缺口必须先增加稳定 ID，再开始关闭。

2026-08-03 当前工作台增量已让全局检索结果表和实体快速详情消费服务端 `identity_identifiers`；真实库缺失标识时明确显示空状态，未用展示层补造数据。前端 `60 files / 363 tests`、生产构建、Biome 和真实 Chrome 桌面/移动复核通过；不改变商业生产完成状态，正式来源绑定、数据授权、生产 RUM 和专业用户 UAT 仍未关闭。

2026-08-04 当前代码收口批次修复了审计持久化的请求会话生命周期、遥测 401 不得清空
有效登录态、取消请求后的陈旧 401、同视图导航覆盖新输入，以及内部入库运行记录分页
定位。后端 API `18/18`、Compose `16/16`、RUM `4/4`、生成传输 `5/5`、工作台 `16/16`、
前端 `60/60` 个测试文件 `371/371`、TypeScript、Biome、后端定向 `187 passed` 和生产
镜像构建均通过。修复后的真实 Google Chrome 串行全量为 `124/124`，四视口各 `31/31`，
快照未更新，临时账号、实体、结构、活性、治理和入库夹具均为 `0`。默认 4-worker 全量
`119/124` 仅保留为并发负载下的历史资源争用基线。验收脚本支持经校验的
`PHARMA_BROWSER_WORKERS=1..16`，默认仍为 4。该批不改变正式数据授权、人工辅助技术/系统
缩放、生产 RUM P75、专业用户 UAT 和 Commercial Production 门禁状态。

2026-08-05 真实 Google Chrome 串行全量再次通过 `124/124`（四视口各 `31/31`）。本次
修复的是验收夹具在真实大库存下只查源对象第一页的问题，已改为逐页定位并验证恢复流程；
不更新视觉快照，临时账号、实体、结构、活性、治理和入库夹具均为 `0`。这加强了当前候选
的浏览器证据，不把人工辅助技术、系统缩放、生产 RUM、正式授权或专业用户 UAT 勾选完成。

2026-08-05 同批后端质量门禁重跑通过 `1176 passed, 35 deselected`，覆盖率 `84.54%`；
`make lint typecheck` 通过（318 个文件格式检查、Ruff、317 个源码文件 mypy）。本批修正了
ClinicalTrials.gov 输入边界测试与增量重扫中误重复加入普通 `SNAPSHOTTED` 版本的问题；
失败治理版本仍会自动重试，普通快照不会因未出现在增量 manifest 中被重复入队。该证据仍属于
本地代码候选，不改变正式来源授权、生产自动入库、生产基础设施、客户 UAT 或 Commercial
Production 的未完成状态。

2026-08-09 运行态与数据边界复核：当前运行线只保留 ClinicalTrials.gov 与 PubMed 两个官方来源，
当前资产为 `649 + 107`；`628/628` 个实体都有 `governed_ai_extraction` 来源文档引用，`668/668`
条证据都有原始文档绑定，`pharma-runtime-hygiene` 为 `0 finding`。删除前确认无 alias 指向后，
已清理 `60` 个 browser/旧 acceptance OpenSearch 临时索引，权威 alias 恢复指向 runtime recovery
索引；API/worker/parser 及基础依赖 healthy，MCP 匿名边界为 `401`。这只加强 D-02/D-03 的本地
真实运行证据，不关闭正式授权、目标环境、MCP 生产互操作、专业 UAT 或 Commercial Production 门禁。

2026-08-04 质量运营增量已补齐来源/数据集级覆盖报告代码：内部工作台现在可以读取解析覆盖、
事实发布/冲突、运行成功率、新鲜度、失败 SLA、授权状态、数据分类和责任人，并已接入
OpenAPI、生成客户端和真实 PostgreSQL 回归；当前运行库只读核验得到来源数为 `0`，所以
没有把 D-05 勾选。固定分母为 78 项，当前 `[x]` 22 项、`[ ]` 56 项；其中 Core Commercial
（排除 S 类规模扩展项）仍有 51 项未完成。代码基线的新增证据不等于正式授权、生产覆盖或
责任方签字。

GOAL v1.11.0 已将近期最高优先级改为三角色真人体验与根因修复循环：执行 Agent 轮流
扮演外部医药小白、内部平台管理员和第三方 MCP Agent，只通过真实产品入口完成逐模块
任务；先黑盒体验，再建立回归、追踪根因、修复并以同一任务复验。原 `ACC-EXT`、
`ACC-A11Y-PERF`、`ACC-DATA`、`ACC-INGEST`、`ACC-LLM`、`ACC-OPS` 和 `ACC-MCP`
七条商业主线继续作为不可降级边界。该方向调整不改变固定分母、正式授权、目标环境、
外部/UAT 或 Commercial Production 的完成口径。

2026-08-04 自动入库复核增量：PubMed 官方来源已通过一次真实 Temporal scheduler
幂等复核，105 个当前版本完成安全扫描、解析、远程 `mimo-v2.5` 治理、引用定位和
OpenSearch 投影；报告位于 `manifests/automatic-ingestion/pubmed-egfr-temporal-20260804.json`。
验收脚本已区分历史失败与当前有效失败，数据工厂也会在自然扫描中自动重试治理失败版本。
ClinicalTrials.gov 当前快照为 `583` 个治理成功、`1` 个真实供应商 `content_filter` 失败；
3 个历史失败样本中 2 个已由远程 `mimo-v2.5` 重处理成功，剩余样本已再次进入正式
Temporal 治理工作流但尚未通过。当前失败路径已具备普通/紧凑/身份最小投影三级重试和
30 分钟重处理 heartbeat/cancel；来源仍未通过完整生产门禁。本批不改变固定分母 `78`、
已完成 `22`、未完成 `56`，也不关闭 D-01、D-02、D-03、D-05 或 Commercial Production。

v1.9.100 已将化学检索保存与刷新回放改为服务端版本化 `chemistry_search` 保存检索，URL 只携带经授权的保存检索 UUID，结构原文不进入 URL、保存摘要或监控摘要；真实保存检索 API 会恢复模式、阈值、上限和结构条件并重新执行查询。组件 `5/5`、前端全量 `362/362`、后端监控/OpenAPI `21/21` 通过，真实 Chrome 四视口化学回放每次 `4/4` 通过。该批明确不开放化学检索监控，因为结构事件匹配语义尚未实现；全球 Chrome 完整套件两次均为 `123/124`，故 C-02、C-05、C-06、C-07 和 Commercial Production 继续保持未关闭。

v1.9.85 已将 `VirtualDataTable` 的视图设置失败统一为 `role=alert`，新增定向组件回归 `7/7`；真实 Chrome 全量 `124/124`，INP `16–48ms`、LCP `104–136ms`、CLS `0`，报告见 `docs/release-evidence.md`。该批继续不关闭 C-02、C-05、C-06 或 C-07，正式数据授权、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.84 已将 `PipelineLandscape` 与 `DealLandscape` 的真实空维度和按需图表加载态统一为可播报状态，新增定向组件回归 `2/2`；真实 Chrome 全量 `124/124`，INP `16–32ms`、LCP `76–116ms`、CLS `0–0.00245`，报告见 `docs/release-evidence.md`。该批继续不关闭 C-02、C-05、C-06 或 C-07，正式数据授权、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.83 已将 `DomainLandscape` 与 `ClinicalTrialLandscape` 的真实空结果和按需图表加载态统一为可播报状态，新增定向组件回归 `3/3`；真实 Chrome 全量 `124/124`，INP `16–40ms`、LCP `68–124ms`、CLS `0`，报告见 `docs/release-evidence.md`。该批继续不关闭 C-02、C-05、C-06 或 C-07，正式数据授权、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.82 已补充空状态播报、侧栏 `aria-current`、SPA 标题焦点和同工作域 URL 状态同步提交，真实比较列表密集操作在四视口通过；定向组件回归 `16/16`，真实 Chrome 全量 `124/124`，报告见 `docs/release-evidence.md`。这些批次不关闭 C-02、C-05、C-06 或 C-07，正式数据授权、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.81 已将搜索、分页、排序和跨域导航的非紧急路由更新交给 React transition，并以真实 Google Chrome 全量四视口 `124/124` 验证 INP `16–40ms`、LCP `92–128ms`、CLS `0` 和视觉回归；报告见 `docs/release-evidence.md`。v1.9.80 已补充监控子页统一 `monitor_tab` URL、刷新和浏览器历史连续性，并以真实 Chrome 专项四视口 `4/4` 验证。v1.9.79 已补充监控主题条件摘要和已有数据错误重试；v1.9.78 已补充所有专业保存检索的受控组合条件摘要；v1.9.77 已补充所有专业保存检索的列表/统计图/统计表/时间线标签；v1.9.76 已补充已保存检索的中文实体类型、多类型固定顺序和列表/统计展示标签；v1.9.75 已补充全局实体统计视图的保存、监控中心回放和稳定 URL 连续性；v1.9.74 已补充真实 facet 驱动的全局检索统计、列表/统计稳定 URL 和统计表回筛证据；v1.9.73 已补充真实靶点活动/结构/SAR 与受治理知识/证据投影证据。这些批次不关闭 C-02、C-05、C-06 或 C-07，正式数据授权、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

## 已完成基础

2026-08-04 自动入库真实来源复核：ClinicalTrials.gov 与 PubMed 均由自然 Temporal
scheduler 触发，未人工触发、未修改调度配置；两个来源均观察到 `SUCCEEDED` 的 unchanged
运行，3/3 版本完成安全扫描、解析、远程 `mimo-v2.5` 治理、引用定位和 OpenSearch 投影，
失败对象与投影积压为 0。该记录只加强本地/试点证据，D-01、D-02、D-03、D-05 仍需正式
授权、生产环境和责任方批准，报告摘要见 `docs/automatic-ingestion-evidence-20260804.md`。
随后将自动入库验收脚本改为显式绑定 `COMPOSE_PROJECT_NAME`/`--project-name` 并尊重
`COMPOSE_FILE`，用 `pharma-acceptance` 运行线重跑两条来源均通过；这只修复验收工具的
运行身份可诊断性，不改变 D-01、D-02、D-03、D-05 的生产门禁状态。
同一 project 下 ClinicalTrials.gov 的完整 pilot（自然调度加两次幂等扫描）也通过，
仍保持 `production_claim=false`。
内部质量运营脚本在同一 project 的临时 PostgreSQL 数据库上完成最新迁移和真实质量
回归 `1 passed`，但 D-05 仍需正式覆盖率、freshness SLA、失败 SLA 和责任人报告。

v1.9.100 已将化学保存检索纳入受控 URL 回放和敏感结构边界：服务端保存版本承载结构条件，浏览器只携带 UUID；刷新、错误和错误类型均有显式状态，监控中心拒绝不支持的结构监控。组件、后端 API/OpenAPI、生产构建和前端全量回归通过；真实 Chrome 化学路径四视口回放通过，但完整套件存在既有非化学失败，因此该批只关闭代码级结构保存/回放缺口，不关闭正式数据、人工辅助技术、生产 RUM、UAT 或 Commercial Production。

v1.9.99 已将结构检索结果的实体入口改为稳定 `entity_id`，并以真实结构 API/Chrome 验证正确档案恢复；`ChemistryView` 定向回归 `3/3`、真实 Chrome `124/124`、前端全量 `358/358` 均通过，报告与 SHA-256 见 `docs/release-evidence.md`。该批关闭代码级结构检索实体 ID 连续性缺口，但不关闭 C-02、C-05、C-06、C-07 或 Commercial Production，正式授权数据、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.98 已将通用实体、公司和疾病档案的交易分区接入真实 `DealSearchItemRead`，并补充参与方/资产的类型化专业档案跳转；真实 Chrome `124/124`、全量 `make check` 后端 `1152 selected / 35 deselected`、前端 `358/358` 均通过，报告与 SHA-256 见 `docs/release-evidence.md`。该批关闭代码级交易档案跨域导航缺口，但不关闭 C-02、C-05、C-06、C-07 或 Commercial Production，正式授权数据、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.97 已将药物专业档案中的已治理关系、获批适应症、交易参与方、交易资产和权益持有人按真实类型直达靶点、疾病、公司或药物专业档案；`DrugView` 定向回归 `8/8`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，真实 Chrome 全量 `124/124`，INP `24–32ms`、LCP `84–124ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.96 已将交易结果、参与方、资产和权益持有人按真实类型直达公司、药物、靶点或疾病专业档案，并将交易结果“档案”入口统一进入交易专业档案；`DealsView` 定向回归 `9/9`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，真实 Chrome 全量 `124/124`，INP `24ms`、LCP `88–112ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.95 已将专利专业结果的关联实体按真实类型直达药物、靶点、疾病和研发机构档案，并将结果表“档案”入口统一进入专利族专业档案；专利与监管/新闻/流行病学/疾病/共享实体导航定向回归 `40/40`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，真实 Chrome 全量 `124/124`，INP `16–32ms`、LCP `92–164ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.89 已将靶点档案实体关系、转化证据和竞品管线中的药物、疾病、靶点及研发机构按真实类型直达专业档案，化合物活性记录保留通用实体入口；`TargetView` 定向回归 `7/7`，全量 `make check` 后端 `1151/1151`、前端 `357/357`，真实 Chrome 全量 `124/124`，INP `24–40ms`、LCP `80–180ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.88 已将药物档案概览、研发管线和临床结果中的靶点、适应症、研发机构及角色药物按真实类型直达专业档案，未知或未充分类型化实体保留通用实体兜底；`DrugView` 定向回归 `7/7`，真实 Chrome 全量 `124/124`，INP `16–40ms`、LCP `80–168ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.87 已将临床试验列表与试验档案中的药物、靶点、疾病和机构链接按真实类型直达专业档案，未知类型保留通用实体兜底；`TrialsView` 定向回归 `5/5`，真实 Chrome 全量 `124/124`，INP `16–48ms`、LCP `76–156ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

v1.9.86 已将管线结果中明确类型的靶点、疾病和研发机构链接改为直接进入专业档案，未知类型保留通用实体兜底；`PipelineView` 定向回归 `8/8`，真实 Chrome 全量 `124/124`，INP `16–104ms`、LCP `76–200ms`、CLS `0`，报告与 SHA-256 见 `docs/release-evidence.md`。该批不关闭 C-02、C-05、C-06 或 C-07，正式授权数据、人工辅助技术/系统缩放、生产 RUM 和专业用户 UAT 仍须单独签字。

| ID | 状态 | 已完成能力 | 当前证据边界 |
|---|---|---|---|
| B-01 | [x] | 人员 Web 与 Agent MCP 两个公开入口，外部/内部人员工作台隔离 | 本地 Compose、API、浏览器和 MCP 测试；不等于公网生产部署 |
| B-02 | [x] | 三条常驻应用进程线：gateway、jobs、parser | 当前 Compose/部署合同已收束；基础设施进程不计入应用进程线 |
| B-03 | [x] | 文件夹、HTTP manifest、S3、SFTP、SMB 自动发现与入库编排代码 | 真实协议和本地运行时已验证；获批生产来源仍见 D 类缺口 |
| B-04 | [x] | PostgreSQL/RDKit 权威层、OpenSearch 投影、十类医药结构化治理和可追溯知识层 | 本地真实数据库、迁移、RLS、查询和治理测试已通过 |
| B-05 | [x] | 人员 HTTP、收费 MCP、计量账本、配额、签名游标、审批导出和反枚举应用边界 | 本地真实协议与数据库通过；外部 IdP、账单和攻击演练仍见 A 类缺口 |
| B-06 | [x] | LLM 只通过 provider-neutral 第三方 HTTPS API；核心栈不含 vLLM、本地权重或本地模型回退 | 源码、Compose、Kubernetes 和运行配置边界已有检查 |
| B-07 | [x] | RAGFlow 退出在线核心路径，仅保留只读离线迁移能力 | 架构、Compose、Kubernetes 和新入库链路已收束 |
| B-08 | [x] | WSL 主源码目录统一为 `${REPO_ROOT}` | 运行证据和外部 runtime 目录不作为源码提交 |

## 代码与外部产品

| ID | 状态 | 缺口 | 完成判据 | 证据/责任 |
|---|---|---|---|---|
| C-01 | [x] | 全局专业查询已覆盖本阶段专业页高价值条件 | 专利、交易、监管、流行病学和新闻/会议切片均按现有领域合同贯通草稿、URL、API、刷新和三浏览器 | 产品/前端；新闻批次通过前端 `336/336`、专项后端 `6/6`、运行合同 `27/27`；Chrome、Edge current、Edge previous 四视口各 `112/112`，合计 `336/336`，三份报告均 `professional_news_query=true` 且临时数据残留为 `0` |
| C-02 | [ ] | 批准参考产品的真实任务差异审计未全部关闭 | 12 个外部工作域、8 个体验门禁、10 个核验面均有版本锁定的 submitted/verified 证据 | 产品/专业用户；对标矩阵和授权审计记录 |
| C-03 | [ ] | 密集结果操作仍缺正式数据和专业用户 UAT | 分页、五级排序、列偏好、跨页选择、比较和受控导出在正式数据上签字 | 产品/UAT；外部矩阵 `dense_result_operations` |
| C-04 | [ ] | 个人与团队效率仍缺业务验收 | 保存/订阅、共享、集合、比较、导出、最近访问和知识连续性完成正式 UAT | 产品/UAT；外部矩阵 `personal_productivity_and_delivery` |
| C-05 | [ ] | 人工辅助技术和操作系统缩放未验收 | 自动化已覆盖 `320/360/720 CSS px` 等效视口、键盘路径和具名可聚焦表格 region；仍需屏幕阅读器、真实浏览器/操作系统 200%/400% 缩放及支持设备矩阵通过人工验收 | 可访问性负责人；v1.9.70 Chrome 报告仅作为自动化补充证据，人工报告和批准记录仍缺失 |
| C-06 | [ ] | 生产真实用户性能证据缺失 | 目标环境形成批准观察窗的 LCP/INP/CLS/TTFB P75，达到 SLO 且无敏感维度 | 产品/平台；生产 RUM 报告 |
| C-07 | [ ] | 外部工作台正式状态矩阵仍未完成 | 八个专业查询已统一覆盖首次加载、显式刷新、保留旧结果、取消、部分可用、403 失败关闭与恢复；真实 Chrome 四视口已逐域验证真实 API 刷新/取消，并在每次真实上游 `200` 后受控注入 `503/403`；v1.9.71 用真实 `VIEWER` 验证外部读取 `200`、企业运营 `403` 和双工作台界面隔离；v1.9.72 用真实 dossier/SAR API 验证靶点跨域档案标签；v1.9.73 进一步验证真实活动、结构、SAR 结果和受治理知识/证据投影连续性；v1.9.74 验证全局检索统计、空结果深链和真实 facet 回筛；v1.9.80 验证监控子页 URL、刷新和历史恢复；v1.9.81 验证 transition 后全量四视口性能与视觉回归；v1.9.82 验证空状态播报、路由焦点、当前导航语义和同域密集比较操作；v1.9.83 验证统计全景空态和按需图表加载态播报；v1.9.84 验证管线与交易全景空维度和按需图表加载态播报；v1.9.85 验证密集结果表视图设置错误播报和重试恢复。仍须在正式数据和真实授权策略上完成逐专业任务错误/权限组合，并完成人工辅助技术、操作系统缩放和专业用户 UAT | QA/UAT；v1.9.64、v1.9.71、v1.9.72、v1.9.73、v1.9.74、v1.9.80、v1.9.81、v1.9.82、v1.9.83、v1.9.84 和 v1.9.85 报告；C-07 保持未勾选直到正式矩阵和签字齐全 |
| C-08 | [x] | 最新累计候选已完成 Code Complete 审计 | 全仓需求逐项映射到权威证据，无关键 TODO、空壳、mock 成功或未验证声明；外部/生产证据缺口继续显式保持 partial | 工程负责人；`docs/code-complete-audit-20260731.md`，原生 `make check`、容器后端门禁和三浏览器报告 |
| C-09 | [x] | 主工作树累计候选已形成干净提交 | 154 个文件变更经全仓、三浏览器、Gitleaks、Semgrep 与镜像门禁审阅后提交；无敏感/构建残留，工作树干净 | 工程负责人；代码提交 `50374913c5bfd7e5b427df0af98c36d3227b6575`，`git status --short` 为空；本轮交付文档在其上独立提交 |
| C-10 | [x] | 最新代码候选已部署到当前 `8080` | 从确定 SHA 构建并启动候选，版本身份、API 和真实浏览器烟测一致 | 发布负责人；镜像 `ff1dbfc64357...` 的 OCI revision 为 `50374913c5bf...`，三条应用进程 healthy；部署后 Chrome 四视口 `112/112`，报告 SHA-256 `3e1bd897dc2559df3cb18f6a9e6712cbfd42877c7b9ccc5c3fee1af578b9b610` |
| C-11 | [x] | 本地 Compose 运行身份已收束到当前仓库 | 保留命名卷和权威数据，由当前仓库 Compose 重建 Redis/Temporal；3 个已退出旧服务容器已逐个删除，服务标签、配置来源、健康、备份与恢复均完成验证 | 平台负责人；备份 `runtime-20260731-021522`，恢复报告 `7d3218f1...`，runtime status `155077e3...`，pre/post inspect `9d6f75fa...`/`64660301...`；未使用 `down -v` |

## 数据、AI 与内部运营

### 真实来源试点（不替代 D 类生产门禁）

| ID | 状态 | 已验证能力 | 本次证据边界 |
|---|---|---|---|
| P-DATA-01 | [x] | ClinicalTrials.gov 官方 API v2 固定端点连接器、分页、限流、不可变快照和来源链接 | `manifests/real-source-pilot/clinicaltrials-gov-egfr-20260730.json`；单一公开源 |
| P-DATA-02 | [x] | EGFR 查询抓取 100 条真实记录，路径、URL、内容 SHA-256 均为 100 个唯一值 | 100 个真实 NCT 记录；大小 4,976-342,911 字节 |
| P-DATA-03 | [x] | 100/100 ClamAV、JSON 解析和远程 `mimo-v2.5` AI 治理成功 | 本地 WSL Compose；未使用本地模型；不等于生产模型验收 |
| P-DATA-04 | [x] | 月/年日期精度、超长字段、权威身份和单记录失败隔离按真实异常修复 | 专项测试、迁移 `7b5f1e9c2d48`、Temporal 完成运行 |
| P-DATA-05 | [ ] | ClinicalTrials.gov 试点事实全部审核并正式发布 | 当前最新事实：89 待审、7 冲突、4 因引用未对齐拒绝；不得伪装为已发布 |
| P-DATA-06 | [x] | NCBI PubMed ESearch/EFetch History 专用连接器、固定官方端点、分页/限流、不可变快照和无摘要默认许可边界 | `pubmed-eutilities-v1`；迁移 `8c6d2e4f1a90`；真实来源 ID 与运行统计见 200 条 manifest |
| P-DATA-07 | [x] | PubMed `EGFR` 抓取 100 条真实元数据，路径、URL、内容 SHA-256 均为 100 个唯一值 | `manifests/real-source-pilot/official-sources-egfr-200-20260730.json`；reported total 152,118 |
| P-DATA-08 | [x] | PubMed 100/100 ClamAV、Markdown 解析、远程 `mimo-v2.5` 专用治理和 OpenSearch 投影成功 | 100 个当前策略成功 run；332 claim；本地模型为 0；失败事实逐条隔离并审计 |
| P-DATA-09 | [x] | 首批双官方来源达到 200 条且运行时虚拟数据为 0 | ClinicalTrials.gov 100 + PubMed 100；200 个唯一内容 SHA-256；`pharma-runtime-hygiene` 0 finding |
| P-DATA-10 | [x] | 外部工作台不再依赖虚拟 `DeepEGFR` 证据，真实双来源引用路径通过 Chrome | `EGFR` 返回 20 个 `clinical_trials`/`literature` 引用片段；Google Chrome 四视口 `112/112`；双 Docker daemon 串线在创建 fixture 前失败关闭 |

| ID | 状态 | 缺口 | 完成判据 | 证据/责任 |
|---|---|---|---|---|
| D-01 | [ ] | 十类正式数据授权未齐全 | 文献、专利、靶点、结构、活性、管线、临床、公司、交易、监管逐类具备合同、字段、渠道、地域、期限和用途批准 | 数据许可/法务；`data_licensing` 证据 |
| D-02 | [ ] | 正式供应商/公开来源连接器未全部联调 | 每个批准来源完成增量、限流、失败游标、许可、freshness、去重和撤回测试 | 数据工程；真实来源报告 |
| D-03 | [ ] | 自动入库生产门禁未完成 | 非本地环境证明发现、快照、恶意扫描、解析、AI 治理、发布、投影、通知、幂等与恢复 | 数据/运维；`ingestion` 生产证据 |
| D-04 | [ ] | 内部十个运营域仍为生产 `partial` | 数据管理员只用 UI 完成来源接入、失败处置、治理审核、发布、回放、质量和审计，完成越权/恢复演练 | 数据运营/UAT；内部能力矩阵签字 |
| D-05 | [ ] | 正式覆盖率、时效和质量基线缺失 | 每个领域发布覆盖率、缺失率、冲突率、freshness、失败 SLA 和责任人 | 数据负责人；质量与 freshness 报告 |
| D-06 | [ ] | 真实付费 LLM 医药文档验收不足 | 获批文档验证 strict schema、引用对齐、prompt injection、usage/request ID、成本、限流、超时和恢复 | AI/安全；`external_services` 报告 |
| D-07 | [ ] | 多供应商模型兼容未验收 | 至少两个供应商或独立兼容端点通过同一 provider 契约和故障切换测试 | AI 平台；兼容矩阵和真实调用报告 |
| D-08 | [ ] | Embedding 医药金标和生产容量未验收 | 获批远程 embedding API 达到排序指标，完成目标规模容量、滚动升级和恢复 | 搜索/数据科学；金标和压测报告 |
| D-09 | [ ] | 化学检索批准规模验证未完成 | RDKit exact/substructure/similarity 在批准数据规模完成相关性、并发、容量和 HA/PITR 验收 | 化学信息/平台；v1.9.68 已证明单条受控 PostgreSQL/RDKit 记录经真实人员 API 与 Chrome 闭环，不能替代规模基准和恢复报告 |

## 远程 Agent 与商业控制

| ID | 状态 | 缺口 | 完成判据 | 证据/责任 |
|---|---|---|---|---|
| A-01 | [ ] | MCP 尚未在真实 TLS 多副本网关验收 | 非开发机网络通过发现、初始化、调用、取消、重连、分页和错误恢复 | Agent/平台；远程互操作报告 |
| A-02 | [ ] | 企业 IdP OAuth 生产联调未完成 | 真实 issuer、resource metadata、PKCE/客户端授权、scope/租户、吊销和审计通过 | IAM/安全；`external_services` 证据 |
| A-03 | [ ] | DPoP/持有证明生产证据缺失 | 两类真实 Agent 验证 jkt/ath/htm/htu/iat/jti、重放失败关闭、轮换和吊销 | IAM/安全；`mcp_sender_constraint` 报告 |
| A-04 | [ ] | 五类 Agent、两个供应商互操作未完成 | 批准客户端矩阵全部通过，不依赖本地桥接私有行为 | Agent 产品；兼容矩阵 |
| A-05 | [ ] | 版本化 Python/TypeScript SDK 未正式发布 | SDK 锁定协议、错误、游标、取消和认证，具备版本/兼容/升级说明 | SDK 负责人；包、tag、测试 |
| A-06 | [ ] | 真实账单/ERP/税务系统未联调 | settlement、冲正、贷项、发票、状态同步、幂等、provider 中断恢复和财务签字通过 | 财务/商业；`billing_provider` 证据 |
| A-07 | [ ] | 目标环境反数据搬运演练未完成 | 分页深度、唯一覆盖、跨 client 分片、凭据/网络扩散、审批导出和绕过攻击均被阻断 | 安全/商业；`anti_extraction` 报告 |
| A-08 | [ ] | 外部风险告警与处置联动未完成 | 风险事件进入中心告警，完成确认、停用、预留释放、导出取消和审计 | SOC/商业运营；演练记录 |
| A-09 | [ ] | 真实客户合同权益同步未完成 | 套餐、字段许可、额度、费率、数据范围和到期撤回与合同系统一致 | 商业/法务；对账和批准记录 |

## 目标基础设施、安全与可靠性

| ID | 状态 | 缺口 | 完成判据 | 证据/责任 |
|---|---|---|---|---|
| I-01 | [ ] | 目标 Kubernetes 拓扑未部署/探测 | 至少 3 个 Ready 节点、2 个可用区，工作负载/PDB/HPA/NetworkPolicy/Gateway 全部通过只读探针 | 平台；`production_topology` |
| I-02 | [ ] | 正式 DNS、TLS、WAF、企业 CA/KMS 未完成 | 人员与 MCP 两个 HTTPS 主机、HSTS、WAF、证书轮换和边缘策略通过 | 平台/安全；实时探测和批准 |
| I-03 | [ ] | 生产 secret manager 和动态租约未联调 | OpenBao/ESO、数据库动态凭据、最小权限、轮换、吊销和故障恢复通过 | 安全/平台 |
| I-04 | [ ] | 托管 PostgreSQL/RDKit HA/PITR 未验收 | 主备切换、时间点恢复、RLS/扩展/迁移一致，达到 RPO/RTO | DBA/平台 |
| I-05 | [ ] | 生产 OpenSearch 未完成容量和恢复验收 | HA、快照、滚动升级、alias 重建、投影回放和故障恢复通过 | 搜索/平台 |
| I-06 | [ ] | 版本化对象存储未完成生产验收 | 加密、版本、保留、恶意隔离、对象恢复和跨区策略通过 | 存储/安全 |
| I-07 | [ ] | Temporal 与 Valkey HA 未完成 | 多副本、持久性、任务恢复、重放存储和依赖故障演练通过 | 平台 |
| I-08 | [ ] | 中心可观测性未联调 | 指标、日志、追踪、审计、脱敏、保留和告警在目标后端可用 | SRE/安全 |
| I-09 | [ ] | 目标负载、峰值和长稳未完成 | 批准并发、真实数据量/query mix 下达到 SLO，结算和配额无漂移 | 性能/产品；`performance` |
| I-10 | [ ] | 背压和多依赖故障注入未完成 | 数据库、搜索、对象存储、Temporal、模型和账单故障均有界恢复且不绕过安全门 | SRE/安全 |
| I-11 | [ ] | 漏洞风险和供应链生产批准未完成 | 最新 SAST/SCA/镜像/SBOM 无未处置可修复高危，其余风险有正式接受 | 安全；release-mode 报告 |
| I-12 | [ ] | 独立渗透测试未完成 | 独立执行方覆盖 Web、API、MCP、租户、导出、SSRF/注入/越权并关闭问题 | 安全；`penetration_test` |
| I-13 | [ ] | Parser 外部恶意 corpus 与批准规模未验收 | 企业批准恶意文档、吞吐、饱和、超时回收、Pod 驱逐和恢复通过 | 安全/数据平台 |
| I-14 | [ ] | 隐私、留存、删除、法律保留和审计评审未完成 | 数据生命周期、最小化、留存、删除证明、法律保留和争议流程获批 | 隐私/法务/安全 |
| I-15 | [ ] | 灾备和区域切换未完成 | 数据库 PITR、对象恢复、usage ledger/账单对账、区域切换和索引重建达到 RPO/RTO | SRE/DBA；`disaster_recovery` |

## 发布、运营与商业上线

| ID | 状态 | 缺口 | 完成判据 | 证据/责任 |
|---|---|---|---|---|
| R-01 | [ ] | 缺受控 Git remote、保护分支和审查流程 | 最新源代码推送到受控仓库，required checks、CODEOWNERS 和审查策略生效 | 仓库管理员 |
| R-02 | [ ] | 最新候选缺干净源码复现 | `git archive`/干净克隆完成锁定安装、全量检查、迁移回环、镜像构建和运行烟测 | 发布工程 |
| R-03 | [ ] | 最新候选缺 SHA 绑定安全制品 | commit/tag、镜像 digest、SBOM、依赖审计、测试和源码树哈希一致 | 发布/安全 |
| R-04 | [ ] | 生产外部证据类别未全部登记 | ingestion、product_uat、data_licensing、external_services、HA/PITR、billing、DPoP、anti-extraction、performance、pen-test、DR、operations、change 全通过 | 各责任方 |
| R-05 | [ ] | 缺签名 tag 和不可变发布包 | 签名 tag、镜像/包 checksum、来源、版本、回滚点和离线验包通过 | 发布负责人 |
| R-06 | [ ] | 生产变更与回滚未演练 | 升级、数据库迁移、回滚/前向恢复和版本兼容在预生产通过 | 平台/DBA |
| R-07 | [ ] | 告警、值班和事故响应未批准 | on-call、升级、P0 响应、滥用、数据质量、账单和客户支持流程可执行 | 运营/SRE |
| R-08 | [ ] | SLA/SLO、模型预算和数据质量 SLA 未批准 | 产品、平台、数据和商业负责人签字，仪表盘与告警阈值一致 | 业务/运营 |
| R-09 | [ ] | 客户 UAT 与上线批准未完成 | 专业用户、客户管理员、数据管理员和 Agent 用户全部签字 | 客户/产品；`product_uat` |
| R-10 | [ ] | 上线后验证与观察窗未完成 | 目标版本身份、健康、关键 Web/MCP 路径、账单、告警、数据时效和回滚信号通过 | 发布/SRE |
| R-11 | [ ] | Commercial Production 最终审计未完成 | 本表所有 Core Commercial 必需项为 `[x]`，证据包审计和离线验包通过 | 业务/安全/运维共同批准 |

## 条件规模化项

以下项目不阻断 Core Commercial profile；达到 1 亿事实、1,000 万文档或批准的 Scale Production 包络前必须完成。

| ID | 状态 | 条件缺口 | 完成判据 |
|---|---|---|---|
| S-01 | [ ] | Kafka/Debezium 变更流 | 真实回放、顺序、幂等、灾备和对账通过 |
| S-02 | [ ] | ClickHouse 分析投影 | 与 PostgreSQL 权威事实对账，完成容量、恢复和权限验收 |
| S-03 | [ ] | Parquet/Iceberg 数据湖 | schema 演进、快照、删除、授权和恢复通过 |
| S-04 | [ ] | 经资格评审的 OpenMeter 投影 | 与权威 usage ledger 双向对账，不能成为计费权威 |
| S-05 | [ ] | 多区域与受监管 profile | 区域故障、数据驻留、电子记录、验证和变更控制通过 |

## 最新权限边界复核（2026-08-09）

- 新增公共实体审核可见性回归：普通用户/API key/Agent 的搜索、draft 显式筛选、建议、已知 ID、通用 dossier、药物/疾病/靶点/公司档案入口均由服务端钳制到 verified；治理主体保持显式未发布权限。
- API/搜索回归实际结果为 30 passed；当前 API 镜像重建并部署后 readiness 200，匿名 API/MCP 仍为 401。
- 该修复只关闭代码级入口越权，不勾选 C-07、A-01/A-02/A-03、D-04 或 I-12；正式授权租户、真实身份矩阵、TLS/DPoP、多副本和独立渗透测试仍需外部证据。
- 详细记录：docs/security-boundary-evidence-20260809.md。

## 勾选审计

每次关闭项目必须同时更新本表、对应能力矩阵/运行文档和证据索引。勾选提交至少包含：稳定候选 SHA、实际命令或外部报告、通过数量、环境身份、数据/凭据清理结果、未覆盖边界和批准人。若证据过期、目标版本变化或依赖重新进入关键路径，必须取消勾选并重新验收。
## Incremental security closure (2026-08-09)

- [x] Explicit linked entity IDs are checked against tenant ownership and the `VERIFIED` publication boundary before public domain reads.
- [x] Agent domain routes apply the check after paid reservation authorization, covering target evidence, activity, SAR, pipeline, structure, trial, patent, deal, company timeline, regulatory, epidemiology and news filters.
- [x] Public domain routes apply the same check for explicit entity IDs, including target activity/SAR/pipeline and all major linked-data search families.
- [x] Regression evidence: 33 API/commercial tests passed; 39 MCP/security tests passed with one external-credential skip; Ruff and mypy passed; API image build passed.
- [ ] Live HTTP recheck of the rebuilt image remains open because the shared 8080/8090 ports are currently owned by another acceptance runtime.
## Reservation safety follow-up (2026-08-09)

- [x] Agent draft-ID visibility checks run before commercial reservation authorization, so denied domain filters cannot leave a new paid reservation active.

## Domain query publication boundary (2026-08-09)

- [x] Public and Agent domain services receive an explicit verified-only mode for ordinary principals, while governance review retains draft access.
- [x] Generic pipeline free-text search has a regression proving a draft-linked record is hidden from ordinary users and visible to governance review.
- [ ] Full runtime pytest/ruff/mypy recheck for this service-layer change is still pending while the shared WSL client is unavailable.

## Continuation verification status (2026-08-09)

- [x] Service-level publication boundary regression: the relevant search/API suite passed 86 tests.
- [x] Commercial, MCP, security-boundary, anti-extraction, and automatic-ingestion contract suite passed 68 tests.
- [x] Ruff check, Ruff format check, and mypy passed for the modified source and test files.
- [ ] Current source image rebuild: blocked by Docker Desktop Linux engine BuildKit EOF; no image digest was recorded for this source revision.
- [ ] Live HTTP/MCP recheck of the current source image: remains open; the existing 8080/8090 runtime must not be treated as rebuilt-source evidence.

## Historical volume migration risk (2026-08-09)

- [x] A clean isolated volume completed the current Alembic chain and reached API readiness with OpenSearch initialized by the unified jobs process.
- [ ] The existing core volume records unknown revision `a7d2e9f4c160`; source provenance and an audited forward migration or isolated data restore are still required before reusing that volume.
- [x] Recovery guidance explicitly forbids `alembic stamp` or editing `alembic_version` without the original migration definition and reconciliation evidence.

## Automatic ingestion cursor integrity (2026-08-09)

- [x] ClinicalTrials.gov, PubMed, S3, and SFTP persisted cursors now reject malformed SHA-256 digests and JSON booleans masquerading as integer object counts.
- [x] Affected connector regressions passed 15 tests; the complete automatic-ingestion, source, replay, cancellation, and run-read-model suite passed 83 tests.
- [x] Parser, malware, quarantine, AI governance, publication, recovery, and search-projection suites passed 144 tests.
- [x] Ruff, Ruff format, mypy, and diff whitespace checks passed for the cursor-integrity change.
- [ ] Real S3, SFTP, and SMB protocol integration remains open because `TEST_S3_SOURCE_ENDPOINT`, `TEST_SFTP_SOURCE_ORIGIN`, and `TEST_SMB_SOURCE_ORIGIN` are not configured; the three tests were skipped and are not counted as production evidence.

## MCP internal client boundary (2026-08-09)

- [x] The MCP internal HTTP client now rejects absolute/external URLs, query or fragment-bearing paths, non-application prefixes, control characters, encoded slashes, and dot-segment traversal before network I/O.
- [x] Four path-abuse regressions plus MCP authentication, anti-extraction, and security tests passed 45 tests; Ruff and mypy passed.
- [ ] Remote TLS gateway, enterprise OAuth/DPoP, standard-client interoperability, and live cross-network abuse tests remain open; unit and local transport tests do not close those production gates.

## Backend non-visual gate and validation runtime (2026-08-09)

- [x] MCP's privileged internal HTTP client now rejects every percent-encoded path before network I/O. This closes single- and double-encoded traversal, encoded slash, encoded backslash, and encoded control-character ambiguity across proxies and application servers.
- [x] MCP path, authentication, health, anti-extraction, and security-boundary regressions passed 49 tests; Ruff check, Ruff format check, and mypy passed for the changed MCP files.
- [x] The non-visual backend gate passed 1,190 tests with 35 integration tests deselected and 84.46% coverage. `tests/test_reference_visual_pair.py` was deliberately excluded because the separate frontend task owns the concurrently changing visual baselines; this result is not represented as a fully green repository `make test`.
- [x] The rebuilt validation runtime at `127.0.0.1:18080/18090` returned readiness 200 with OpenSearch ready; anonymous personnel API and anonymous MCP requests returned 401. The validation image ID observed by the frontend deployment starts with `9db2ea365742`; this is local validation evidence, not a signed release digest.
- [ ] The second unchanged full browser run remained non-green: Playwright recorded 122 expected and 2 unexpected results. Evidence identified one stale trial visual baseline after the current typography/line-height change and one `ERR_NETWORK_CHANGED` dynamic-chunk failure. No baseline was updated and neither failure is hidden by the backend gate.
- [ ] Production TLS/OAuth/DPoP, real remote Agent interoperability, licensed S3/SFTP/SMB sources, the historical unknown Alembic revision, signed release evidence, and target-environment load/long-run testing remain open.
