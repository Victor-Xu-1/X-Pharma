# Agent MCP 数据访问契约

## 入口与认证

- 唯一 Agent 入口：`https://mcp.example.com/mcp`；本地为 `http://127.0.0.1:8090/mcp`。
- 生产必须使用 OIDC access token，校验签名、issuer、audience、tenant claim 和 `mcp:connect` scope。
- 生产令牌必须以 RFC 9449 DPoP 绑定公钥：每个 MCP HTTP 请求使用 `Authorization: DPoP` 和独立签名 proof；服务端校验 `jkt`、`ath`、`htm`、`htu`、`iat` 与 `jti`，并通过共享 Valkey `SET NX` 重放窗口失效关闭。普通 Bearer、重复 proof、私钥 JWK、过期/未来 proof、错误 URI/方法/令牌摘要和重放缓存故障均在 MCP SDK 前拒绝。
- 本地 API key 只供 MCP verifier 使用，随后交换为 60 秒内部 JWT；内部 API 不接受原始 key。
- 每次工具调用都携带独立 Agent 身份、租户、scope 和审计 request ID。
- 商业生产只接受预注册 client；服务端从身份与合同绑定 customer、billing account、subscription 和 tenant，调用者不得自行声明。
- 发布协议门禁必须同时使用固定版本的官方 Inspector CLI 与锁定的官方 Python MCP SDK，针对同一隔离租户、受限研究身份和查询完成初始化、工具发现、schema 校验、两页实体遍历、篡改游标拒绝、错误后恢复、靶点/双靶点竞品管线/证据读取及真实计费结算；竞品管线必须校验完整靶点集合、角色和稳定组合键，任何一个客户端失败都不得生成通过证据。普通研究身份对异步导出工具只做能力发现。独立高权限 `mcp_async_tasks` 门禁为两个隔离 `data:export` client 分别验证创建、审批等待、状态、取消、真实完成、签名结果分页、篡改游标拒绝与恢复和唯一结算，并强制销毁数据库与临时对象存储；未授权导出拒绝仍由反搬运门独立验证。

## 设计规则

1. 名称不明确时先 `resolve_entity`，不能静默选择实体。
2. 领域查询使用稳定 entity ID，不允许调用者传 OpenSearch index、迁移 adapter dataset 或其他内部存储 ID。
3. limit 在服务端有硬上限；大结果必须分页、分域查询或使用受控异步数据任务。
4. 事实型输出返回来源文档、locator、quote 或明确的数据缺口。
5. 工具错误区分输入错误、scope/授权拒绝、来源不可用和内部失败。
6. 平台只负责返回治理后的数据、证据和质量元数据，不规定 Agent 的分析流程或下游产物。
7. 每个生产工具调用在读取商业数据前完成 entitlement、数据许可、风险、配额和额度预留，成功交付后追加幂等 settlement。
8. 付费不等于全库权限；交互式查询、原始证据和批量导出必须使用不同 scope、权益、结果上限和累计覆盖限额。
9. 网关 QPS 只负责流量保护，不能代替领域层的分页深度、唯一记录覆盖、导出和跨 client 风险控制。

## 商业访问与计量契约

当前已实现 PostgreSQL 权威账本、预注册 client/subject 绑定、订阅、权益、不可变 rate card、额度授予、同步预留/结算/释放、租约、幂等结果重放、客户账户级精确日覆盖、请求窗口/client/脱敏网络/凭据确认键扩散与分片协同策略事件、14 个可分页 MCP 工具统一签名游标、受审批异步导出、不可变冲正、过期清算、三方对账、签名账期快照和 DPoP sender constraint。网络只保存规范网段 HMAC，凭据只保存签名 `cnf` 或 API key 实例的 HMAC；目标 IdP/网关的真实 DPoP 客户端联调和真实 billing provider 仍属于 Production 阻断项。Valkey 仅保存短时 DPoP 重放键与流量状态，不是余额或结算权威。

所有 billable 工具共享以下请求控制字段：

| 字段 | 规则 |
|---|---|
| `idempotency_key` | 客户端稳定幂等键；同一主体/client/工具/规范化参数重复提交返回既有结果，不重复扣费 |
| `max_billable_units` | 精确十进制字符串；调用方允许的硬上限，最坏情况预估超过上限时在查询前拒绝 |

所有成功数据工具响应包含 `data` 和 `usage`；`usage` 至少包含：

| 字段 | 语义 |
|---|---|
| `reservation_id` | 本次额度预留标识 |
| `settlement_id` / `usage_event_id` | 可对账的不可变结算与使用事件标识 |
| `billing_class` | 不可临时改变价格语义的工具类别 |
| `charged_units` | 按不可变费率卡的基础、实际结果、响应字节和计算量计算的精确单位 |
| `compute_units` | 本次服务端结算的计算单位；无计算费率的工具为零 |
| `result_count` / `response_bytes` | 服务端复核后的交付量 |
| `unique_record_count` / `new_unique_record_count` | 当前响应唯一记录数及本订阅当日首次交付数 |
| `page_depth` | 服务端验证后的游标链页深度 |
| `replayed` | 是否由既有幂等结算返回持久化结果 |

响应可以公开客户可操作的额度、重试时间和上限，但不得暴露内部风险特征权重、跨客户信号或足以规避检测的精确安全阈值。

标准商业错误至少包括 `ENTITLEMENT_REQUIRED`、`DATA_LICENSE_DENIED`、`BUDGET_GUARD_EXCEEDED`、`INSUFFICIENT_CREDIT`、`RATE_LIMITED`、`COVERAGE_LIMITED`、`EXPORT_APPROVAL_REQUIRED` 和 `RISK_POLICY_BLOCKED`。这些拒绝不产生收费 settlement，但计入安全速率与风险审计。

MCP 工具拒绝以 `isError=true` 返回，文本以稳定错误码和安全提示开头（例如 `ENTITLEMENT_REQUIRED: ...`）。网关不得把内部 API URL、原始 HTTP 响应体、内部 scope 名称或堆栈回传给 Agent；request ID 只通过审计和服务端日志关联。

计费规则：

- 每次成功交付至少产生 invocation settlement；result、compute 和 export 单位按版本化 rate card 追加。
- 初始化、能力发现、权益/报价读取和异步状态轮询默认使用 zero-rated billing class，但仍产生审计计量并受速率/滥用限制；不得在这些工具中夹带领域数据。
- 鉴权/授权/风险/配额拒绝和平台 `5xx` 不收费；异步取消只结算已完成分片。
- entitlement、预留或权威账本不可用时默认 fail closed；任何 grace 模式必须由合同显式启用并有硬额度、持久化待结算事件和告警。
- 价格调整、退款和争议通过 adjustment/reversal 追加记录处理，不能修改历史 settlement。
- 同步结果与 settlement 在响应发送前持久化；连接中断后以相同幂等键读取既有结果，不再次收费。无持久化结果的失败必须释放预留。
- reservation 具有租约和 `reserved/settled/released/expired` 状态；异步任务续租或分片预留，reconciler 只能在确认无结果/结算后回收悬挂额度。

目标商业控制工具：

| Tool | 用途 | 主要 scope |
|---|---|---|
| `get_commercial_access` | 已实现；查询当前 client 的订阅、余额和启用权益，不交付领域数据 | `mcp:connect` |
| `estimate_usage` | 已实现；按绑定订阅和生效 rate card 对有界调用报价，不读取结果、不预留额度；响应字节费用在实际结算时确定 | `mcp:connect` |
| `get_usage_summary` | 已实现；查询绑定 client 当前月结算、交付量、余额和最近账单引用 | `mcp:connect` |

## 防枚举与数据搬运目标契约

- `limit`、字段集、日期范围、查询复杂度、证据长度、响应字节、并发、分页深度和累计唯一实体/claim 数均由服务端设硬上限。
- 只返回短时、签名、不透明游标。游标绑定 subject、tenant、client、tool、规范化 query hash、page size 和 expiry；不提供任意 offset 或内部 ID 扫描。
- `search_entities`、`resolve_entity`、证据、活性、管线、结构、化学、临床、专利、交易、监管、流行病学、新闻和知识页共 14 个可分页工具均执行该游标契约；响应只公开 `next_cursor` 与 `page_depth`，不公开任意 offset 或 total。
- 每个后续页必须使用新幂等键重新预授权并独立结算；跨 tenant、subject、client、tool、查询或 page size 复用游标均在读取数据前拒绝，达到 entitlement 的 `max_page_depth` 后不再签发下一页。
- 每个 entitlement 的 `max_page_depth`、`daily_unique_record_limit` 和 `max_response_bytes` 均由合同配置；活跃预留也占用保守覆盖预算，防止并发越界。
- 普通领域工具不返回原始文件或无限全文。证据检索响应同时返回 `license_scopes` 与显式 `warnings`；服务端只接受租户授权的逻辑 dataset key，并按数据集许可裁剪内容/字段。大结果进入独立 `data:export` scope、套餐权益、审批策略和异步导出任务。
- `create_data_export` 只接受包含监管事件和事实溯源清单在内的九类结构化权威数据集的平台白名单与客户许可字段/过滤字段的交集；任务固化许可版本、SHA-256 和 attribution。`fact_provenance` 导出只包含权威记录、claim、源资产、源版本、源文档和 locator 标识，不绕过证据正文的 dataset 字段许可。`get_data_export`、`cancel_data_export` 和 `read_data_export` 分别提供状态、取消和所有者绑定的签名游标读取；许可变更后执行和读取均拒绝，已被导出任务引用的许可版本不可复用，避免旧制品因策略回退而重新激活。导出执行使用 `export.data` rate card，在批准后预留，按实际记录数和制品字节一次结算；状态轮询和后续分块读取不重复扣费。
- 导出制品与 manifest 均按 SHA-256 不可变寻址；manifest 使用独立 HMAC 密钥，包含 job、数据集、字段、过滤摘要、时点、记录数、字节数、制品摘要和有效期。生产对象存储必须使用 S3 服务端加密和生命周期策略；本地文件系统后端只允许开发测试。
- 风险策略跨请求关联连续 ID、字母/数字分片、深分页、低选择性轮询、快速扩大时间范围、异常唯一记录覆盖、凭据/网络轮换和多 client 协同。
- 风险处置必须明确返回限速、冷却、step-up、复核或拒绝原因；禁止通过伪造记录、修改数值或无提示截断来追踪客户。
- 客户支付更多额度不能绕过数据许可、导出许可或累计覆盖限制。

## 已实现工具

| Tool | 用途 | 主要 scope |
|---|---|---|
| `search_entities` | 按名称、别名和外部 ID 搜索实体；兼容单个 `entity_type`，多个 `entity_types` 去重排序后按 OR 检索并进入计费查询身份；结果返回规范名、别名、外部标识、描述或语义命中解释；支持相关性、名称、实体类型和更新时间受控升降序并与签名游标绑定 | `entities:read` |
| `resolve_entity` | 将自然语言名称解析为候选稳定 ID；使用与 `search_entities` 相同的单类/多类规范化和计费身份 | `entities:read` |
| `get_entity` | 读取一个规范实体 | `entities:read` |
| `get_entity_dossier` | 有界读取一个实体的关系、活性、管线、临床、专利、交易、监管、结构及逐域覆盖/缺口；最多 100 条/域 | `dossiers:read` |
| `search_evidence` | 在授权逻辑数据集中检索原文证据 | `evidence:read` |
| `get_record_provenance` | 将一个权威记录追溯到授权源版本、原文位置和已验证引用 | `evidence:read` |
| `get_target_profile` | 靶点基本信息和结构化 profile | `targets:read` |
| `get_bioactivity_landscape` | assay 和活性值、单位、关系、来源 | `activities:read` |
| `compare_target_sar` | 按兼容 Assay 上下文分组的标准化活性、组内排名、ΔpChEMBL、结构和不可比原因 | `activities:read` |
| `get_competitive_pipeline` | 按任一主/联合靶点、适应症、机构、模态、全球/中国阶段及日期、研发/商业化权益、项目标签和里程碑查询项目；支持药物、靶点、适应症、机构、模态、全球/中国阶段和状态日期的受控升降序，排序进入计费查询身份；返回当前权威版本的完整靶点集合、角色、稳定组合键、区域阶段、权益、里程碑与来源。该 MCP 工具保持有界分页项目读取；同查询的聚合竞争格局由 HTTP `GET /api/v1/pipelines` 返回，不把大聚合结果隐式塞入收费 MCP 响应 | `pipelines:read` |
| `search_structures` | entity/InChIKey 精确结构查询 | `structures:read` |
| `search_chemical_structures` | 真实 RDKit exact SMILES、SMARTS substructure 或 SMILES similarity 查询；exact 每次最多 20 条，其他模式最多 50 条 | `structures:read` |
| `get_clinical_trials` | 临床试验和关联实体；支持最近更新、注册号、结果状态/评价、招募状态、入组量和研究类型的受控升降序，排序进入计费查询身份 | `trials:read` |
| `get_clinical_trial` | 按稳定试验 ID 读取设计、队列、入组条件、终点、结果、状态历史和关联实体 | `trials:read` |
| `get_patent_landscape` | 专利族和关联实体；支持最早优先权、专利族号、法律状态和预计到期的受控升降序，排序进入计费查询身份 | `patents:read` |
| `get_deals` | 按稳定参与机构、参与角色/分类、状态、方向、交易时与当前阶段、权益、三类时间和披露金额区间查询许可、合作、并购和交易；支持披露日期、名称、类型、状态、方向、地区和同币种披露金额的受控升降序，排序进入计费查询身份 | `deals:read` |
| `get_company_timeline` | 公司管线当前状态与已披露交易公告的统一可分页时间线 | `pipelines:read` + `deals:read` |
| `get_regulatory_events` | 按机构/辖区/事件、认定资格、标签变更、黑框警告、安全信号/严重程度/状态及决定/来源更新时间读取监管事件；支持决定日期、标题、机构、辖区、事件类型、状态、主题和来源更新的受控升降序 | `regulatory:read` |
| `get_epidemiology_observations` | 按规范患者人群稳定 ID、地区、时间和统计口径读取带疾病/靶点关系、方法学与来源的疾病负担观测；支持观察期、疾病、指标、估计值、地区、单位、发布方和样本量的受控升降序 | `epidemiology:read` |
| `get_news_events` | 受治理的新闻、新闻稿和公司公告，含发布方、关联实体、时间与来源；支持发布日期、标题、事件类型、发布方和会议场景的受控升降序，排序进入计费查询身份 | `news:read` |
| `search_knowledge_pages` | 搜索已发布版本化知识页 | `knowledge:read` |
| `get_knowledge_page` | 读取知识页当前版本、事实和引用 | `knowledge:read` |

`entity.dossier` 按实际返回的实体及各领域记录逐条结算并计入日唯一记录覆盖。`limit` 是每个领域的预览上限，结算预留上限为 `1 + 8 * limit`，组合响应不能绕过计费和反批量抽取策略。

`search_structures` 保留 entity/InChIKey 规范记录读取；`search_chemical_structures` 使用 PostgreSQL 18 RDKit cartridge、物化 mol/Morgan 指纹和 GiST 索引执行真实化学检索。化学调用固定预留计算单位，内部 Domain API 校验 billing class、完整参数、结果上限和计算单位后才执行；结果按结构稳定标识计入每日唯一覆盖。当前真实功能与索引路径已通过，但生产规模相关性、延迟和容量压测仍是上线门禁。

早期 `build_research_bundle`、`get_research_bundle` 和 PPTX 渲染器已从 MCP、Web、HTTP API 和权威 schema 全部退出。Agent 只获得受治理数据与证据，并自行决定下游用途。

## Agent 推荐调用链

用户提出“查看某靶点最新数据、活性、结构和竞品”时：

1. `resolve_entity` 确认靶点。
2. `get_entity_dossier` 读取有界跨域概览、覆盖和缺口，再按需要并行调用 target、activity、structure、pipeline、trial、patent、deal、regulatory 分页工具深入检查。
3. `search_evidence` 补充原文上下文，并用 `get_record_provenance` 校验关键结构化记录的权威来源和版本。
4. 根据分页游标继续读取，或为超大结果创建受控异步数据任务。
5. 向 Agent 返回 coverage、warnings、数据截止时间和未授权/未覆盖数据源。

Agent 不应把“数据库没有记录”解释为“全球没有项目”，也不能隐藏检索和授权范围。Agent 后续生成何种内容由其宿主应用决定，不属于本契约。
