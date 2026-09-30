# X-Pharma 源码梳理

## 模块职责与调用关系

| 边界 | 权威模块 | 职责 |
| --- | --- | --- |
| 应用进程 | `gateway.py`、`jobs.py`、`job_roles.py` | 单网关和受监督后台角色 |
| Web/API | `api.py`、`security.py`、`human_oidc.py` | 人员/Agent 身份、租户、scope 与会话 |
| 领域查询 | `intelligence.py`、`repository.py`、`dossier.py` | Web 与 MCP 共用的事实查询 |
| 数据库 | `models.py`、`schemas.py`、`db.py`、`migrations/` | 数据模型、事务和签名 RLS |
| 数据工厂 | `ingest/` | 来源、快照、安全解析、Temporal 和恢复 |
| AI 治理 | `governance/`、`enterprise/llm_providers.py` | 模型访问、暂存、验证、审核与发布 |
| 检索与知识 | `search/`、`knowledge/` | outbox delivery、搜索投影和版本知识 |
| 商业与协作 | `commercial/`、`comparison/`、`monitoring/` | 账本、权益、导出和团队工作流 |
| 前端 | `apps/web/src/lib/contracts`、`components`、`views` | 状态、传输、共享组件和专业工作域 |
| 部署与工具 | `deploy/`、`services/`、`scripts/`、`runbooks/` | 安装、隔离组件、门禁、恢复与运维 |

入口、领域、持久化和适配器各自负责一层。新增规则进入对应领域模块，不能在 UI、路由和 MCP 重复实现。数据流见 [architecture.md](architecture.md)。

## 本次整理

公共名称集中在后端 `product.py` 与前端 `lib/product.ts`；API、MCP、来源请求、登录和导航复用该定义。API 版本读取发行包元数据。内部数据库、协议和 CLI 标识保持稳定，已有业务数据不因品牌变动而迁移。

原 10,431 行集中样式按职责拆为 16 个模块：基础、登录、导航、共享数据表面、研究、用户中心、靶点、档案、商业、企业、知识、数据工厂、治理、化学、临床和监管。`styles.css` 保持领域布局顺序；`design-system.css` 只导入五个主题模块，分别拥有 token、控件、排版、业务表面和第三方适配。所有领域色值已改为语义 token，415 条被主题覆盖的重复声明已删除。设计权威见 [design-system.md](design-system.md)。

`configure-development.py` 生成独立密钥、数据库 URL 和 0600 私有配置，保护已有环境，默认关闭远程 AI。生产凭据仍由部署环境注入。

公开目录包含完整应用、迁移、生成客户端、测试、配置、容器、Kubernetes 和运维源码。私有环境、业务数据、运行证据、缓存、历史快捷链接和一次性空文件保留在原私有环境。

## 已识别的维护风险

`api.py`、`intelligence.py`、`schemas.py` 和部分专业视图仍承载较多职责。后续拆分需受现有查询、授权、RLS 与浏览器回归约束，不能按长度机械拆业务规则。本次公开整理没有宣称已完成这些模块的全面重构。

历史 CI 的双入口任务引用了已退出统一拓扑的 `mcp` 和 `search-projector` 服务。验证应使用当前 API/jobs/parser 拓扑、独立配置和真实夹具，同时保留既有门禁。

恢复镜像与新源码是不同候选。每个候选的源码摘要、测试、镜像和实际验收须绑定同一身份；恢复时的成功结果不计为新代码部署证据。
