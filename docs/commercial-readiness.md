# 商业交付门禁

本文件只记录当前版本相对于 [项目总目标](../GOAL.md) 的实现证据和上线缺口，不改变或降低目标本身。

## 当前结论

2026-09-30：项目以 X-Pharma / Apache-2.0 建立公开源码基线。当前源码验证与发布状态以 GitHub 的精确提交、CI 和本次交付结果为准。下列旧 WSL 表格及 v1.x 数字是历史开发基线，不能用于证明新提交已部署或达到生产条件。开源 remote 的建立不替代签名发布、正式授权数据或商业批准。

当前候选按 GOAL v1.11.0 记录：最新隔离 WSL 真实 Google Chrome/Playwright 串行四视口完整套件为 `124/124`，后端非集成全量为 `1176 passed`、覆盖率 `84.54%`；这些仍只是本地候选证据。v1.11.0 将近期研发主线改为外部医药小白、内部平台管理员和第三方 MCP Agent 三种角色的逐模块黑盒体验、问题发现、根因修复和同任务复验；原七条商业主线继续作为不可降级边界。正式授权数据、生产 RUM P75、人工辅助技术、操作系统缩放、专业用户 UAT、目标 MCP 网关和 Commercial Production 仍未完成。

本仓库已经是可安装、可迁移、可测试的企业平台基础，不再是 RAG/Obsidian 演示项目。但在真实客户生产环境完成数据授权、托管基础设施、IdP/模型联调、容量测试、安全评估和恢复演练前，不能宣称达到医药魔方级别的覆盖面、并发或 SLA。

“代码具备能力”和“商业服务已验收”必须分开判定。

下一阶段所需的正式数据、授权、UAT、生产指标和责任人输入统一登记在 [正式验收输入包](formal-acceptance-inputs.md)，未满足前不勾选商业缺口。

## WSL 验收基线（2026-07-29）

| 验收面 | 本次结果 |
|---|---|
| 当前应用镜像 | API、worker、isolated parser、search projector、monitoring worker 和 MCP 必须由同一不可变摘要镜像启动；不可变 digest 由每个安全证据 manifest、gate statement 和离线候选包的 `subject.targets` 绑定。2026-07-29 源码和本地健康运行时均位于唯一迁移 head `e2b7c4a1f639`，隔离 PostgreSQL 迁移回环、运行健康和 RLS 验证通过；三组 OpenSearch alias 使用 v2。AI 治理运行以不可变 `policy_sha256` 绑定模型、提示词、结构化 schema、预算和发布策略；固定研究包、报告页和 PPTX 输出契约已退出 Web、HTTP API、MCP、领域模型及权威 schema，PPTX 仅保留为输入解析格式。v1.9.28 起每个最终检查点均从提交源码独立构建生产镜像；当前仍没有签名 tag 或受控 remote，未获风险接受时不得运行或冒充 release-mode 安全批准 |
| 运行时终态 | 候选开始时只部署安全门禁从确定性 staged source 构建并扫描的镜像；末尾必须生成 `pharma.local-runtime-acceptance.v3`，核对 telemetry profile 下 9 个常驻容器及每个容器 image ID 与 gate statement 的 API/PostgreSQL digest 一致。业务面只允许 gateway、unified jobs 与 isolated parser 三条常驻应用进程线；PostgreSQL、Valkey、OpenSearch、Temporal、ClamAV 和 OTel Collector 是基础设施/安全依赖，`migrate` 与 `storage-init` 为一次性任务。报告同时验证 Web live/ready、查询与内部工作台各自独立 HTML 文档、入口标记、不同 SHA-256、GET/HEAD/SPA shell/安全头、未认证 MCP 401、独立 parser、统一 jobs 同 PID 心跳、Alembic/PostgreSQL/RDKit、OpenSearch alias/投影队列和零持久测试残留。除 Collector 外所有必需容器必须具有真实 `healthy` 状态；不能再以仅有 Running 状态通过。发布捕获、组包与离线验包均重新解析，报告固定 `production_claim=false` |
| 后端/前端 | 当前精确测试数和覆盖率由每个候选的 `quality` 与 `source_reproducibility` statement 绑定，不在手写文档中固化易漂移数字；WSL 宿主和独立非 root 测试镜像均执行 Ruff、严格 Mypy、后端回归、Biome、TypeScript、前端组件、OpenAPI 契约、Vite production build、Compose 与 Kubernetes 渲染。容器和本地模型协议结果仍不能替代真实来源、付费模型、目标 IdP/网关与外部审批 |
| 真实浏览器 | 当前候选必须使用真实 Google Chrome、Microsoft Edge 当前主版本和 Edge 前一主版本，在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 四个视口分别通过外部查询登录、内部管理登录、双工作台隔离、真实认证导航、稳定检索/深链接、会话恢复、Viewer 权限边界、状态恢复、监控、计费争议、监管情报和浏览器 RDKit 场景；同一套件还必须在每个 project 内以 `320 CSS px` 验证键盘登录、移动导航、核心研究入口和页面级无横向溢出。`pharma.browser-acceptance.v9` 要求严格记录浏览器产品/channel/四段版本号，用 axe 对公开登录页及全部 14 个外部工作域执行 WCAG 2.2 A/AA 自动审计，并执行 LCP `<=2500 ms`、INP `<=200 ms`、CLS `<=0.1` 门禁；Chrome 同时生成逐视口空结果全页、205 条真实投影密集表格 shell、临床结构化终点、专利时间线和交易地域权益五组像素基线及 SHA-256，Edge 只读比较且不能更新基线。发布捕获、组包与离线验包均重新解析。该证据不等于人工辅助技术测试、操作系统级缩放、生产 RUM P75、Windows 企业策略验证或外部业务 UAT。 |
| 视觉对标证据 | `pharma.reference-visual-pair.v1` 已提供外部内容寻址登记与复验机制：第三方参考 PNG 只能留在仓库外证据存储，本仓库只维护自有 Chrome 基线、schema、工具和测试；清单拒绝凭据、Cookie、查询参数、生产数据、第三方二进制入库及自动等价声明，并将工作流、同一 CSS viewport、两侧摘要和授权工单绑定到 `pair_id`。机制代码已验证，但真实批准参考流程的人工差异结论、产品签字和业务 UAT 尚未完成，因此该项不构成商业同级批准。 |
| MCP 协议 | 官方 Inspector 0.22.0 与官方 Python MCP SDK 1.28.1 必须通过 `pharma.mcp-interoperability-acceptance.v3` 协议 `2025-11-25`，发现同一 28 工具合同和 14 个统一游标工具；两者都必须完成同一查询的两页实体遍历、实体集合摘要、篡改游标拒绝及恢复、靶点与非空竞品管线读取、证据检索，并各自产生 5 个有效收费调用。普通身份只发现四个异步导出工具；独立 `pharma.mcp-async-task-interoperability.v1` 以两个隔离高权限 client 验证审批等待、状态、取消、真实完成、签名结果分页、错误恢复和两条唯一 settlement，且数据库与制品全部销毁。未授权导出仍由反搬运门拒绝；发布捕获、组包和离线验包均重新解析当前候选报告，不接受历史计数 |
| 双入口一致性 | 同一租户临时管理员经 Web 创建实体后，Web 与收费 MCP 的规范读取及同过滤搜索对 9 个权威字段完全一致；2 个 MCP 调用产生 2 个唯一 settlement，临时账号、实体、outbox 和 OpenSearch 文档均精确清理；当前候选必须生成 `entry_consistency/report.json` |
| 权威记录一致性 | 一次性迁移 PostgreSQL 中的受控活性事实通过 Web、收费 MCP 和签名 `fact_provenance` 标准导出返回同一权威记录、源版本、源文档与原文 locator；3 项收费操作对应 3 个唯一 settlement，临时 API/MCP 与数据库强制清理；当前候选必须生成 `record_consistency/report.json`，报告固定 `production_claim=false`，不能替代真实授权靶点数据或生产 UAT |
| MCP 并发/计量 | 当前候选的 `mcp_commercial` 门禁执行真实有界并发并记录 P50/P95/P99、唯一 settlement 和活动 reservation；schema 2.0 进一步验证幂等重放、参数冲突、领域失败释放、额度拒绝、客户端取消竞态以及 settlement/扣费/余额恒等式。结果只以当前候选的机器附件为准，不在源码中保留会漂移的本机报告 |
| Kubernetes | 加固候选使用 `pharma.local-kubernetes-validation.v3` 在 kind 0.31.0 / Kubernetes 1.35.0 的一控制面、两 worker 真实 API Server 安装 3 组固定摘要 CRD，对包含独立 mTLS parser、分离 Secret、HPA/PDB、NetworkPolicy 和只读根文件系统的生产清单执行 server-side dry-run；同一受控集群实际启动双副本 ClamAV StatefulSet，强制证明副本跨两个 worker 和两个测试 zone 分布，并验证两块独立持久卷、签名 freshness、干净/EICAR 扫描、单 Pod 删除期间至少一个 Ready endpoint、原 PVC 数据及跨节点布局保留，最后要求临时集群清理。报告仍不替代目标集群、真实存储/CNI、容量与运维审批。 |
| 恢复 | 加固候选使用 `pharma.local-backup-restore-acceptance.v1` 绑定完整备份 manifest/checksum，在隔离卷恢复 PostgreSQL、两套 Temporal 数据库、RDKit、RLS、对象与 Markdown 归档，并证明主运行时未修改；报告不替代生产 PITR、区域切换和非开发人员演练 |
| 安全供应链 | Secret/SAST/依赖/SBOM/API、PostgreSQL/RDKit 与 OCR 三类镜像可修复 High/Critical 门禁通过；Grype v6 库由官方 HTTPS 元数据发现、归档 SHA-256 校验并离线导入固定扫描器；每次候选的完整报告只归档在仓库外证据包，无修复版本的 High/Critical 仍须真实风险审批 |
| 发布证据链 | 已实现干净提交/源码树/镜像绑定、仅从 `HEAD` 执行锁定安装/测试/构建/迁移回环/非 root 镜像烟测的源码复现门禁、分级证据策略、原子不可覆盖组包、完整 SHA-256 清单、Ed25519 外部签名接口和离线篡改校验；Production 额外强制真实能力矩阵/UAT 与十类数据 coverage/freshness v2 语义报告，所有测试工件和逐角色审批实物必须随候选包携带并校验摘要，缺失外部门禁、虚构摘要、release-mode 安全报告或签名 tag 均失败关闭，详见 [发布证据链](release-evidence.md) |
| GOAL 完成矩阵 | `deploy/release/goal-section-19-matrix.json` 固定映射未发生结构变化的 GOAL `v1.9.9` 第 19 节 24 条完成条件；外部 capability matrix 当前绑定 Goal `v1.9.98`，内部矩阵仍绑定其最后一次结构性基线 `v1.9.9`。外部矩阵记录 `41` 项代码级 `implemented`；12 个工作域中 10 个为 `implemented`、2 个因正式数据/UAT 保持 `partial`；8 项体验门禁中 4 项为 `implemented`、4 项因正式数据、人工辅助技术、生产 RUM 或 UAT 保持 `partial`。v1.9.98 以真实 Google Chrome 全量四视口验证通用实体/公司/疾病档案交易分区的真实交易投影和类型化跨域导航；v1.9.97 以真实 Google Chrome 全量四视口验证药物档案关系、获批适应症和交易实体类型化导航及视觉回归；v1.9.96 以真实 Google Chrome 全量四视口验证交易结果实体类型化、交易专业档案入口和视觉回归；v1.9.95 以真实 Google Chrome 全量四视口验证专利结果实体类型化和视觉回归；v1.9.84 以真实 Google Chrome 全量四视口验证管线与交易全景空维度、按需图表加载态和视觉回归；v1.9.83 以真实 Google Chrome 全量四视口验证统计全景空态、按需图表加载态和视觉回归；v1.9.82 以真实 Google Chrome 全量四视口验证空状态播报、路由焦点、当前导航语义、同域比较操作和视觉回归；v1.9.81 以真实 Google Chrome 全量四视口验证 transition 后搜索、分页、排序和跨域导航性能与视觉回归；v1.9.80 以真实 API/数据库/Chrome 验证监控子页 URL、刷新和历史连续性；v1.9.79 以真实 API/数据库/Chrome 验证监控主题条件摘要、已有数据错误重试及所有专业保存检索摘要连续性；v1.9.78 以真实 API/数据库/Chrome 验证所有专业保存检索组合条件摘要、列表/统计图/统计表/资讯时间线展示标签；v1.9.77 以真实 API/数据库/Chrome 验证所有专业保存检索的列表/统计图/统计表/资讯时间线展示标签；v1.9.76 以真实 API/数据库/Chrome 验证已保存检索中文实体类型、多类型固定顺序和列表/统计视图标签；v1.9.75 以真实 API/数据库/Chrome 验证全局统计视图保存与监控中心回放连续性；v1.9.74 以真实 facet 驱动的全局检索统计、列表/统计稳定 URL 和统计表回筛强化结果视图连续性；v1.9.73 以真实 dossier/SAR API、活动/结构记录和受治理知识/证据投影强化靶点跨域档案标签；v1.9.72 以真实 dossier/SAR API 和真实人员浏览器逐一走通靶点跨域档案标签；v1.9.71 以真实 `VIEWER` 账户验证外部读取 `200` 与企业运营 `403` 的 admin/viewer 基础边界，并确认两个工作台的真实界面隔离；v1.9.70 在等效缩放视口下把密集表格具名 region 和键盘入口纳入真实 Chrome 重排门禁；v1.9.69 扩展等效视口重排并明确不等同于系统缩放；v1.9.68 删除化学浏览器场景的静态业务响应，以真实 PostgreSQL/RDKit 结构、真实人员登录和真实 HTTP API 完成四视口闭环；v1.9.67 保持编辑器按需激活，v1.9.66 继续约束两个工作台首屏静态闭包。上述本地审计强化不改变完成分母，也不替代目标环境 P75、批准负载、正式化学数据规模、真实系统缩放或 UAT。正式数据和真实权限组合、最终权利时间线、操作系统/人工辅助技术验证、授权参考人工评审和业务 UAT 尚未闭合；无受控 remote、签名 tag、release-mode 风险批准或目标生产拓扑，因此不能把本地源码检查点提升为发布候选或商业证明。 |
| 外部证据交接 | 可从干净提交生成 requirements-only 交接目录，向责任方提供策略定义的全部权威检查、审批角色、工件门槛、策略快照和 schema；正式跨组织交接支持 Ed25519 清单签发和脱离源码仓库的可信公钥离线验签，未签名模式只允许本机草拟。完整 intake 可在 release-mode 安全证据下原子批量登记，任一类别失败则整个暂存批次回滚。Production 审计/组包拒绝仓库外策略覆盖，并可从本地候选和外部批次目录有界发现 statement；工具仍不生成 UAT、合同、渗透测试或审批事实。 |
| 运营合同与本地观测 | 低基数 MCP、入库、OpenSearch 投影、billing delivery 和外部工作台 Web Vitals 指标已形成稳定代码契约；版本化 SLO/错误预算/告警/角色/runbook 由构建验证，Development/Pilot 候选强制真实协议流量经 OTLP 到达本地 Collector。RUM 只保留五类有界维度并已有 LCP/INP/CLS/TTFB P75 目标；目标中心观测、真实用户样本量/观察窗、分页路由、值班表和通知/升级演练仍须外部审批 |
| MCP 防提取验收 | `anti_extraction_baseline` 现为所有候选必选语义门禁；隔离 PostgreSQL 的真实协议链覆盖正常计费查询、深分页/游标篡改、字母/数字分区、跨客户端协同、网络/凭据轮换、未授权导出、人员风险台和客户端撤销，并核对持久拒绝事件、零活动预留、零非法导出、原始分片/网络值不落库及数据库销毁。报告固定 `production_oidc_covered=false`，不能冒充目标 IdP/网关/外部告警与审批的 Production `anti_extraction` 证据 |
| 入库恶意内容门禁 | 真实 ClamAV INSTREAM 与隔离 Data Factory 链通过：干净 Markdown 正常解析，EICAR 在解析和科学资产登记前阻断，只保留不可变快照且不生成 extracted text。持久运行线还必须通过 `pharma.quarantine-workflow-acceptance.v1`：人员留置、强制 ClamAV/Temporal 复扫、再次阻断、永久拒绝、通用重放拒绝、幂等、审计、append-only 历史、强制 RLS 和夹具清零；目标环境批准恶意文档 corpus 与安全运营 UAT 仍是生产门禁 |
| 不可信文档解析边界 | worker 不加载第三方文档解析器；独立 parser 容器只允许 worker 入站、无主动公网出站、无业务凭据，并对每文件子进程限制 CPU/内存/PID/输出/墙钟。真实 MD/HTML/DOCX/PPTX/XLSX/PDF/SDF/MOL/PDB/CIF/mmCIF、401、摘要篡改、ClamAV 前置阻断和 mTLS 双向身份通过；真实慢请求饱和时并发请求明确返回 `429`，释放后恢复，子进程墙钟超时后零直接子进程残留且后续解析成功。九类临时对抗样本通过真实 HTTP parser 链证明 Office 路径、重复成员、符号链接、成员爆炸、压缩比、加密、PDF 加密、XML 实体和损坏 SDF 均失败关闭且服务恢复。SDF/MOL 使用 RDKit，PDB/mmCIF 使用 Gemmi。精确依赖版本和结果由当前候选附件绑定，不复制到手写文档；外部批准 corpus 和目标环境渗透测试仍是生产门禁。 |
| 自动入库验收 | Development 候选强制生成机器可读平台准备度证据：精确核对五类连接器、Temporal worker/scheduler、来源根、ClamAV、隔离 parser、关键服务和全部已注册来源治理状态；零来源只标记 `ready_for_source_registration`，不能冒充真实入库。Pilot `ingestion_pilot` 使用 scheduler-first 双报告，以 workflow 时间水位和治理策略指纹区分新不可变版本的 `new_version`、同版本新策略重治理的 `policy_reprocess` 与静态真实源的 `unchanged`；并要求同一来源全部可治理版本具有批准的第三方 API 模型、成功 extraction run、usage/request ID/响应哈希/逐段 token 核算、staged fact 和服务端原文 locator。历史本地模型样本不能作为当前 Pilot 或 Production 证据；必须重新完成真实第三方模型 API 与授权数据验收。 |

该基线证明当前 WSL 工程可运行、可测试、可迁移，不代表 Production 已获批准。未修复操作系统漏洞必须按 [镜像漏洞风险登记](security-risk-register.md) 取得真实审批引用；外部 IdP、真实模型、数据许可、目标云 HA/PITR、账单 provider、容量和灾备仍是正式商用阻断项。


真实 Chrome 的发布场景还必须在桌面和移动项目中覆盖企业管理；缺少 `enterprise_administration` 场景会使 browser 证据失败关闭。

## 已有交付能力

| 领域 | 当前证据 |
|---|---|
| 产品入口 | 只有工作台与 MCP 两个 Ingress；内部 API/存储不公开 |
| 人员身份 | OIDC Code + PKCE、state/nonce、JWKS、预绑定/受控自动开户；本地密码仅开发 |
| Agent 身份 | MCP OIDC protected resource、本地 key 交换短期内部 JWT、scope/tenant/audit |
| 租户隔离 | 服务过滤 + PostgreSQL RLS + 签名 tenant context + 非特权 runtime role |
| 自动入库 | `folder-v1`、通用 `http-manifest-v1`、`s3-snapshot-v1`、`sftp-snapshot-v1` 与 `smb-snapshot-v1` 连接器；强制目录/Origin/bucket/环境凭据白名单、SFTP `known_hosts`、SMB3 签名/加密、owner/分级/授权/许可/freshness、失败不推进游标或误删、不可变快照、ClamAV 失败关闭扫描、隔离 parser 真实解析和 Temporal 有界重试；独立 scheduler 使用固定 workflow ID 防重。Development 准备度与 Pilot 真实来源报告使用不同 schema 和发布门禁，避免把“平台已准备”写成“来源已自动入库”；S3、SFTP 与 SMB 已通过真实协议验收，付费供应商合同与专用字段适配仍未完成 |
| AI 治理 | schema 2.5 约束、模型原始/规范载荷、分段输入/响应哈希、provider/client request ID、token/费用审计；quote 必须属于生成事实的精确分段，文档/分段/响应/token/费用超限失败关闭，确定性政策失败不由 Temporal 重试；包含冲突/置信度策略、人工审核、RDKit 结构权威校验、临床试验设计/队列/终点/结果/状态历史、监管事件、流行病学观测和新闻/公告事件在内的十类领域表物化 |
| 知识层 | PostgreSQL 版本页、claim 引用、typed links、确定性 Markdown/Obsidian 导出 |
| 人员领域档案 | 药物、公司、疾病、临床试验、专利族与交易使用独立页面级专业档案：药物聚合全球/中国阶段、适应症与地区进度、当前版本靶点/机构集合及角色、研发/商业化权益、项目分类与历史、结构化临床结果和登记、获批适应症/监管、标准结构和来源；公司聚合项目、资产、靶点、适应症、交易、模态、阶段分布和时间线；疾病聚合研发格局、规范靶点、靶点证据、试验、专利及按稳定疾病 ID 查询的流行病学与患者人群；临床试验按稳定试验 ID 展示概览、设计与入组、终点与结果、状态历史和中心；专利族按稳定族 ID 展示优先权、法律事件、独立权利要求和关联资产；交易按稳定交易 ID 展示概览、参与方角色、资产阶段、地域权益、金额条款和来源。靶点使用独立全景。所有档案保持受控 URL 分区、刷新与历史连续性，关键记录继续通过许可感知的来源抽屉查证；正式授权数据和专业客户 UAT 仍是独立商业门禁 |
| Agent 数据访问 | MCP 共 28 个工具：21 个同步收费领域/证据工具返回稳定实体、来源、quote、locator、coverage 和 warnings，4 个受审批、额度、许可、所有权游标和签名 manifest 约束的数据导出生命周期工具，以及 3 个零费率商业控制工具；`get_entity_dossier`、`get_clinical_trial` 与 `get_company_timeline` 分别执行独立权益或跨域 scope 校验，公司时间线同时要求管线和交易读取权限并使用独立费率类；流行病学与新闻事件分别使用独立 `epidemiology:read`、`news:read` scope、套餐权益和费率类，不能借基础实体读取绕过领域权益；记录溯源按稳定 UUID 返回同一权威记录的 claim、源文档和源版本 |
| MCP 计量核心 | 预注册 client/subject、订阅/权益、不可变 rate card、额度授予、预留/结算/释放、幂等结果和 PostgreSQL 追加账本 |
| 账户级反枚举 | 14 个可分页 MCP 工具统一使用短时签名游标、逐页预授权与结算、分页深度/并发/响应上限、服务端稳定 ID 复核、客户级精确日覆盖、请求窗口/client 扩散/跨 client 分片关联与不可变策略事件 |
| 商业财务闭环基础 | 不可变调整/双层冲正、过期预留清算、余额/账本/凭证三方对账、签名账期快照、带负责人/SLA/版本控制/不可变事件的计费争议状态机，以及固定目的地 HTTPS billing adapter、幂等 outbox worker、有限重试/死信/审计/人工重放；争议退款决议与负向账本调整同事务提交，且只进入人员工作台，不暴露给 MCP |
| 商业工作台契约 | 管理员同源 API 返回客户/订阅/rate card、余额、权益、活跃预留、当日结算和唯一覆盖，不暴露内部风险权重 |
| 企业管理契约 | 同一人员工作台提供租户概况、用户/角色/状态、用户组成员和审计日志；仅人员管理员可调用，使用版本冲突、最后管理员保护、复合租户外键、签名 RLS 和过滤绑定审计游标 |
| 搜索投影 | OpenSearch 3.7 严格向量 mapping、版本化 alias/pipeline、实体/证据/知识 embedding、原生 BM25/k-NN hybrid、固定分页候选深度、租户 routing/filter、facet、联想、locator、outbox 重试/死信和全量原子重建；readiness 对单活动 alias、schema/向量维度及评分 pipeline 完整契约失效关闭；embedding 密钥只进入 API/projector，OpenSearch query/projector 凭据使用独立 OpenBao 路径并分别只挂载 API/projector，均在消费边界强校验 |
| 数据库运行线 | Compose PostgreSQL 18.4 + RDKit 2026.03.3 固定源码供应链；逐库 dump/restore、精确行数、独立新卷和 16→18→16→18 回切演练 |
| 工程交付 | Python 3.13.14、uv 单一锁、Biome 2、Node 锁、Docker 非 root 镜像、Alembic、CI、Kubernetes HA 基线 |

## 正式商用阻断项

以下任一未完成，都只能标记为“预生产/受限试点”：

1. **外部产品同级能力**：当前查询、跨域档案、证据抽屉、化学检索、监控和受控导出只是已实现基础；仍须完成第 5.1.1 节 12 个外部工作域的版本化功能对标矩阵、全部 P0/P1 真实数据路径、桌面/平板/移动状态矩阵和专业用户 UAT。任何缺域、空壳或 mock 驱动页面都不能进入 Production。
2. **内部运营闭环**：第 5.1.2 节十个域的 20 条代码能力已实现并进入同一内部工作台，包括主数据回滚、发布撤回/投影重建、质量处置、会话撤销、数据集许可和平台运营读模型；仍须以获批真实来源和外部服务完成数据管理员端到端 UAT、越权/失败恢复演练和运维签字，才能把十个域从 `partial` 提升为生产证明。
3. **远程 Agent 互操作**：当前本地 MCP 协议、计量、异步任务和两类官方客户端证据不能替代远程生产能力；仍须在真实 TLS 域名、多副本 Gateway、企业 IdP 和非开发机网络上完成五类客户端、至少两个供应商的 OAuth、发现、调用、取消、重连、分页和错误恢复测试，并发布版本化 Python/TypeScript SDK 与兼容矩阵。
4. **数据内容**：证据检索已按数据集强制许可编号/版本、渠道、有效期、字段、片段长度和归属声明，结构化导出已按账户强制字段/过滤字段许可并固化策略哈希；仍须完成合法授权的文献、专利、临床、药物、公司、交易和结构数据连接器，并将真实合同逐项录入和审批。
5. **目标运行线**：本地 Python 3.13.14、固定 uv 0.11.28、单一 `uv.lock`、Biome 2、TypeScript 7/Vite 8 和 PostgreSQL 18.4/RDKit 2026.03.3 迁移已完成并进入 CI/容器验证。生产 PostgreSQL 18 + RDKit 仍必须完成托管 HA/PITR 与主备切换演练。
6. **检索体验**：OpenSearch 3.7 多语言全文、联想、facet、证据定位、provider-neutral embedding API 端口、原生向量/混合检索和受限稳定分页已实现，并通过真实 OpenSearch 3.7 协议测试；仍需用获批准的第三方 HTTPS embedding API 完成医药金标排序评估、目标数据量容量测试、滚动升级和故障恢复验收。仓库不提供本地模型或回退；不能用确定性测试向量、PostgreSQL substring 或 RAGFlow 私有索引替代这些生产证据。
7. **化学能力**：PostgreSQL 18 / RDKit cartridge、权威 mol/Morgan 指纹列、版本化标准化、exact/substructure/similarity、复合租户 GiST 索引、强制 RLS、人员 API 与收费 MCP 计算量结算均已用真实数据库验证；仍需完成批准数据规模下的相关性基准、并发/容量压测和生产 HA/PITR 验收。
8. **真实外部链路**：在客户 IdP、真实模型网关、OpenSearch 证据索引、S3 对象存储和生产 Temporal 上完成验收；模型验收必须使用真实获批文档和付费 endpoint，证明 strict schema、usage/request ID、费用率、分段引用、防 prompt injection、限流退避和失败恢复，不能用 mock 响应替代。历史 RAGFlow 只验证隔离的只读离线导出，不进入生产验收拓扑。
9. **基础设施**：Envoy Gateway 双入口/本地与全局限流清单、OpenBao/ESO 动态数据库租约、密钥轮换滚动更新和 OpenTelemetry 四类进程 OTLP 链路已实现，并通过 Kubernetes 1.35 API Server 与本地真实 Collector 验证；仍须在目标云完成 PostgreSQL/RDKit 多可用区/PITR、OpenSearch、版本化对象存储、Temporal、Valkey、证书/DNS/KMS、中心观测后端和区域故障演练。
10. **MCP 商业计量余项**：已完成权威 ledger、客户/订阅/rate card、额度预留结算、幂等重放、失败释放、额度拒绝、客户端取消竞态、冲正、周期对账、签名账期快照和 provider-neutral 异步投递链；本地发布门禁会核对 settlement、扣费、余额和零遗留 reservation。仍须完成客户真实账单/ERP 账户联调、税务/收款/贷项和状态同步，以及真实预生产环境的 provider 中断、跨系统恢复与财务签字演练。
11. **防数据搬运余项**：已实现 14 个可分页 MCP 工具统一签名游标、逐页预授权/结算、结果/分页/响应/并发门禁、客户级精确日唯一覆盖、请求窗口、client/脱敏网络/凭据确认键扩散及跨 client 分片风险检测、Envoy 本地/全局边缘限流，以及独立 `data:export` scope、账户级限额/审批、Temporal 异步执行、签名 manifest、所有者游标和记录/字节结算。相关性信号进入幂等摘要和风险事件，不记录原始 IP/确认键；证据与导出字段许可均 fail closed，策略轮换会使旧任务和制品失效且留下审计/outbox；工作台已支持风险确认/关闭、客户端即时停用、预留释放和导出取消。应用边界现已按 RFC 9449 校验 DPoP 公钥绑定、方法/URI/令牌摘要、时间窗和共享 Valkey 防重放，缓存不可用时失败关闭。仍须在目标 IdP/网关以两类真实 Agent 客户端验收 DPoP token issuance、精确代理 CIDR、真实合同审批同步和外部告警联动。
12. **性能**：本地发布候选现已强制执行 Web/MCP 双入口的有界持续与峰值混合负载，记录 P50/P95/P99，并通过真实协议证明逐成功调用唯一 settlement、扣费/额度一致、并发同幂等键只生成一个结算、取消/超时终态和零遗留 reservation。该报告固定标记非生产且不覆盖长稳或托管依赖故障；仍须按批准的并发、真实数据量和 query mix 完成目标环境持续负载、峰值、长稳、服务端背压及多依赖故障注入，并验证风险门禁不会被高并发绕过，取得产品和平台批准。
13. **安全与合规**：SAST/依赖/镜像扫描、解析前 ClamAV 和无业务凭据/无主动出站的隔离 parser 已有 Development 证据；本地 Kubernetes v3 门禁已经真实证明双副本 StatefulSet 跨两个 worker/测试 zone 分布、独立持久卷、签名 freshness、干净/EICAR 扫描和单 Pod 删除期间至少一个 Ready endpoint，且原 PVC 数据与布局保留；parser v3 门禁补充了九类内建临时对抗样本、真实有界饱和、超时进程组回收和后续恢复。仍须完成未修复镜像漏洞风险审批、目标存储类/镜像源/CNI/企业 PKI、真实节点/可用区故障切换、外部批准恶意文档 corpus、批准规模 parser 吞吐与 Pod 驱逐故障注入、渗透测试、权限矩阵、审计留存、隐私、数据生命周期和计费争议流程评审。
14. **灾备**：执行数据库 PITR、对象恢复、区域切换、usage ledger/账单对账和 OpenSearch/其他投影重建演练，达到批准 RPO/RTO。
15. **运营**：告警、值班、升级、数据质量 SLA、模型/调用成本配额、账单支持、滥用响应、客户支持和变更审批流程。

## 建议首版 SLO

这些是待压测和业务审批的目标，不是当前承诺：

| 指标 | 初始目标 |
|---|---|
| 工作台/MCP 月可用性 | 99.9% |
| 结构化查询 P95 | 小于 800 ms |
| MCP 单工具 P95 | 小于 2 s，不含外部语义检索 |
| 证据检索 P95 | 小于 5 s |
| 文件发现延迟 | 正常来源小于 5 min |
| RPO | 小于等于 5 min |
| RTO | 小于等于 30 min |
| 跨租户泄漏 | 0，任何一次即 P0 |
| MCP 事实型响应缺少来源 | 0 |
| 成功商业 MCP 调用缺少 settlement | 0 |
| 幂等重试重复扣费 | 0，任何一次即财务 P0 |
| 未解释账单对账差异 | 0 |

## 发布分级

| 等级 | 允许范围 | 必需条件 |
|---|---|---|
| Development | 单机研发 | 单元/集成测试通过，不接真实敏感数据 |
| Pilot | 少量受控用户 | OIDC、真实数据样本、RLS、备份、审计、人工值守 |
| Production | 商业客户 | 全部阻断项关闭，性能/安全/恢复报告批准 |
| Regulated | 受监管工作流 | 在 Production 上增加验证、电子记录、审计和变更控制要求 |

## 交付证据包

每个商业版本应归档：

- Git commit/tag、镜像 digest、SBOM 和依赖审计结果。
- Alembic head、配置清单和密钥版本引用（不含明文）。
- 后端、PostgreSQL/RLS、前端、浏览器、MCP、入库和真实模型测试报告。
- MCP 正常研究、计量预留/结算/冲正、并发余额、失败策略、深分页、分片枚举、跨 client 协同和批量导出绕过测试报告。
- 负载、渗透、备份恢复和故障演练报告。
- 数据源授权清单、字段级限制和 freshness/quality 报告。
- usage ledger 到聚合/发票的对账报告、价格版本、异常调整、已知限制、回滚方案、值班人和变更审批。

生产外部证据现可通过 `release_evidence.py production-requirements/register-production` 受控登记：工具从仓库外真实工件和逐角色审批文件原子生成绑定当前 commit、源码树、镜像和安全 manifest 的 Production report/statement，并拒绝空文件、符号链接、重复源、覆盖、路径穿越和不完整策略检查。该工具不生成外部事实或批准，不能减少现有真实商用阻断项。

只有上述证据齐全并由业务、安全和运维共同签字，版本才可标记为商业生产可交付。
