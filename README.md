# X-Pharma

<img src="apps/web/src/assets/brand/X-Pharma-logo-128.png" width="96" height="96" alt="X-Pharma logo" />

[Apache-2.0](LICENSE) · [架构](docs/architecture.md) · [可离线打开的项目总览 HTML](docs/project-overview.html) · [账号与组织](docs/accounts-and-organizations.md) · [源码导航](docs/codebase-guide.md) · [设计系统](docs/design-system.md) · [贡献指南](CONTRIBUTING.md) · [安全](SECURITY.md)

X-Pharma is an open-source pharmaceutical intelligence platform for people and
agents. It combines a research workbench, governed evidence, structured drug and
target data, durable ingestion workflows, and a standard MCP interface.

X-Pharma 是面向人员与 Agent 的医药情报平台：人员通过研究工作台查询药物、靶点、临床、专利、交易和证据；Agent 通过 MCP 使用相同领域服务和权限口径。PostgreSQL 保存权威事实，检索与知识页由这些事实投影产生。

这是开发版本。源码可以独立安装、测试和构建；目标环境的数据许可、自动入库、真实 LLM/OCR、企业身份和商业生产条件需分别验收。完整产品目标见 [GOAL.md](GOAL.md)，商业边界见 [商业就绪说明](docs/commercial-readiness.md)。

## 能力与模块

| 模块 | 能力 | 源码 |
| --- | --- | --- |
| 研究工作台 | 多领域查询、实体档案、结构检索、对比、收藏和受控导出 | `apps/web/src` |
| 数据与证据 | 规范实体、版本、来源定位、审计、组织隔离 | `src/pharma_intel/models/`、`intelligence/`、`repository.py` |
| 数据工厂 | 文件夹、HTTP、S3、SFTP、SMB 与公共来源连接器，快照、扫描、解析和 Temporal 工作流 | `src/pharma_intel/ingest` |
| AI 治理 | 批准的 HTTPS 模型接口、严格结构化输出、引用、预算、审核与发布 | `src/pharma_intel/governance` |
| 检索与知识 | OpenSearch 投影、事务 outbox、版本知识页、Markdown 导出 | `search`、`knowledge` |
| Agent MCP | Streamable HTTP、鉴权、许可、配额、计量与异步导出 | `mcp_server.py`、`commercial` |
| 运维与恢复 | Compose、Kubernetes 基线、迁移、RLS 验证、备份与恢复 | `deploy`、`scripts`、`runbooks` |

```mermaid
flowchart LR
  Sources["获授权来源"] --> Factory["Temporal 数据工厂"]
  Factory --> Scan["杀毒与隔离解析"]
  Scan --> Evidence["不可变原始证据"]
  Scan --> Governance["AI 暂存与治理审核"]
  Governance --> PG["PostgreSQL + RDKit 权威数据"]
  PG --> Search["OpenSearch 可重建投影"]
  PG --> Knowledge["知识页与 Markdown"]
  PG --> Domain["统一领域服务与授权"]
  Search --> Domain
  Evidence --> Domain
  Domain --> Web["人员 Web"]
  Domain --> MCP["Agent MCP"]
```

业务进程保持统一：`pharma-gateway` 提供 Web/API/MCP，`pharma-jobs` 监督后台角色，`pharma-parser-service` 隔离不可信文件。内部 Python 包名 `pharma_intel`、现有 `pharma-*` 管理命令、数据库标识与存储合同保持稳定，方便已有数据升级；公共产品和 Python 发行包名为 X-Pharma / `x-pharma`。

## 安装

支持 Linux x86-64 或 Windows WSL2 的 Linux 环境。需要 Linux Docker Engine/Compose、Python 3.13.14、uv 0.11.28、Node.js 24.14、Corepack/pnpm 11.7。版本由 `pyproject.toml`、`uv.lock`、`apps/web/package.json` 和 `pnpm-lock.yaml` 锁定。

E 盘 WSL 工作区使用以下位置：

| 内容 | 位置 |
| --- | --- |
| 源码 | `/srv/wsl/projects/x-pharma` |
| 环境 | 源码内 `.venv` 或 `/srv/wsl/envs` |
| 运行数据 | `/srv/wsl/data` |
| 缓存与临时文件 | `/srv/wsl/cache`、`/srv/wsl/tmp` |

这些 Linux 路径属于 E 盘的 WSL ext4；Windows 可通过 `\\wsl.localhost\WSL\srv\wsl\projects\x-pharma` 访问。先确认目标发行版的磁盘位置，命令不能保证一个未经核对的 WSL 环境位于 E 盘。

```bash
git clone https://github.com/Victor-Xu-1/X-Pharma.git /srv/wsl/projects/x-pharma
cd /srv/wsl/projects/x-pharma
export UV_CACHE_DIR=/srv/wsl/cache/uv
export COREPACK_HOME=/srv/wsl/cache/x-pharma/corepack
export npm_config_cache=/srv/wsl/cache/npm
export TMPDIR=/srv/wsl/tmp
uv sync --locked --dev
corepack pnpm@11.7.0 --dir apps/web install --frozen-lockfile
make configure
```

`make configure` 从 `.env.example` 生成权限为 0600 的私有 `.env`，每个安全边界使用独立随机密钥，数据库身份与连接 URL 一致；已有配置会保留并报错。AI 治理默认关闭，不提供预设账号或密码。其他 Linux 主机可使用自己的 Linux 原生目录和缓存位置。

```bash
make wsl-tools
make wsl-check
make up-observed
make status
```

首次启动会构建或下载锁定的容器镜像，需要网络。源码仓库不包含 Docker 引擎、镜像、模型或业务数据库；已有离线迁移包属于单独交付物，不能用 `git clone` 替代它。

创建自己的开发账号（将密码替换为独立的强密码）：

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm api pharma-bootstrap \
  --tenant-slug default --tenant-name "Default Tenant" --skip-api-key \
  --admin-email admin@example.com --admin-password "your-own-unique-long-password"
```

默认入口：

- 研究工作台：http://127.0.0.1:18380/workspace/research
- 内部工作台：http://127.0.0.1:18380/workspace/internal
- MCP：http://127.0.0.1:18390/mcp

内部工作台只向有权限的人员开放。数据库、缓存、搜索和 Temporal 不是公开产品入口。MCP 客户端仍需身份、数据许可与商业合同配置，见 [MCP 契约](docs/mcp-contract.md)。

### 注册、登录和退出

两套工作台的登录页都有“登录 / 注册 / 加入组织”入口，登录后的侧栏都有“组织与账号”和“退出账号”。一个账号可以加入多个组织，每个会话只选择一个组织；角色、事实、私人研究与偏好按组织隔离。退出成功会撤销服务端会话、清除当前工作台缓存并返回本工作台登录页；失败时保留会话并提示重试。

- 外部研究工作台：本地密码模式下，`HUMAN_SELF_REGISTRATION_ENABLED=true` 开放独立账号注册。每个新账号创建自己的空租户，只有 `viewer` 权限，不自动获得其他企业数据或内部管理权限。设置默认关闭；开发配置示例明确开启。
- 内部管理工作台：管理员在“企业管理 → 注册邀请”生成绑定邮箱的一次性邀请码。有效期默认 24 小时，可设置 1–168 小时，并可在使用前撤销。受邀新账号以内部分析员身份加入发码管理员所在企业，不自动获得管理员权限；需要额外权限时由管理员在现有用户管理中明确授权。
- 邮箱全局唯一，已有账号不重复注册。管理员可以邀请已有账号，由本人验证身份并明确确认后加入新组织；不会移动原组织、分享原数据或自动授予管理员。注册密码至少 12 个字符，注册后回到登录页自行登录。
- 切换组织撤销当前设备旧会话并重新确认服务端身份；组织级停用或降权不影响其他组织。改密会使其他组织的旧会话失效。既有账号、凭据、业务归属和偏好保留；迁移和安全回退约束见[账号与组织](docs/accounts-and-organizations.md)。
- 企业 OIDC 模式继续使用组织身份系统，不开放本地密码注册或邀请码发放。这里的本地邮箱只作为登录标识，未发送验证邮件，不应当作已验证的组织身份。

匿名注册请求体最多 16 KiB，在解析 JSON 前同时检查声明长度和实际流量；每个直接连接来源每 10 分钟最多 10 次有效格式的注册尝试。失败尝试也计入数据库预算，不能通过多进程绕过；部署到代理后仍需配置入口级限流和身份策略，不把本地开发注册当作已验收的生产身份方案。

升级已有环境前先备份，再以迁移身份执行 `uv run alembic upgrade head`，随后执行 `uv run pharma-db-provision` 和正常 RLS 验证，确认完成后更新应用。迁移 `b8d22d9a1ef3` 新增注册预算和强制租户隔离的邀请表，不改已有用户、密码或业务数据。已有邀请记录时禁止直接降级删除；生产应用回滚不自动降级数据库。

安装本机 Google Chrome 后，`make account-browser-acceptance` 为每个视口启动仅绑定回环地址的临时网关与独立 SQLite 数据库，以随机测试账号验证注册、登录、刷新、权限拒绝、邀请确认、组织切换、多标签会话一致性、私人研究隔离和退出，然后关闭进程并清理自己的临时环境。它不读取业务数据库，不依赖私有开发账号，不记录邀请码截图或浏览器 trace，也不关闭注册滥用预算。自定义 Chrome 可执行文件可通过 `E2E_BROWSER_EXECUTABLE` 指定；PostgreSQL 的迁移、强制 RLS 和并发领取另由数据库门禁验证。

## 数据接入与 AI

管理员注册来源后，数据经不可变快照、ClamAV、隔离解析、治理审核和投影进入平台。只有实际获授权的数据才能接入或交付。连接器、来源许可与注册操作见 [来源接入](runbooks/source-onboarding.md)，数据工厂调用关系见 [架构说明](docs/architecture.md)。

AI 使用批准的第三方 HTTPS API。启用前在私有配置中设置 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` 与明确的响应模型 allowlist，确认费用、usage、输出 schema 和资料外发权限。模型不能直接写入权威事实。OCR 是独立可选组件，见 [OCR 服务](docs/ocr-service.md)。

## 验证与构建

```bash
make check
uv run pharma-openapi --check
uv build
make container-check
```

`make check` 覆盖格式、静态检查、严格类型、后端测试与覆盖率、生成客户端一致性、前端交互测试、生产构建、运维合同及部署清单。真实数据库、浏览器、安全扫描和协议验收由 CI 与相应脚本完成；完整目录见 [贡献指南](CONTRIBUTING.md)。

修改 API 后从权威 schema 重新生成客户端：

```bash
uv run pharma-openapi
corepack pnpm@11.7.0 --dir apps/web api:generate
corepack pnpm@11.7.0 --dir apps/web api:check
```

不要手工修改生成客户端。后端、前端、数据库、协议和容器采用同一版本的实现与迁移；验收结果必须属于本次实际候选。

## 部署、迁移与故障排查

- [WSL 开发与运维](docs/wsl-development.md)：工具、预检、启动与目录要求。
- [生产部署](docs/deployment.md)：企业 OIDC、TLS、Secrets、托管依赖与安全边界。
- [备份与恢复](runbooks/recovery.md)：权威数据、隔离恢复、校验与回滚。
- [发布证据](docs/release-evidence.md)：候选身份、门禁、分级与签名。
- [交接](docs/project-handoff.md)：当前源码治理与恢复后的运行边界。

启动失败时先检查 `make status`、容器健康和缺失的环境变量；数据库错误先核对迁移 head 与运行身份；查询为空时检查来源许可、已发布数据与搜索投影。不要通过关闭鉴权、校验或删除数据卷来绕过失败。

API 构建默认从 ECR Public 读取 Docker Official Images 的固定摘要。
遇到该镜像服务的配额限制，可显式使用相同摘要的 Docker Hub 官方副本：

```bash
DOCKER_LIBRARY_REGISTRY=docker.io/library docker compose build api worker
```

此参数只改变镜像传输位置，不改变 Node/Python 版本或 SHA-256；没有自动静默 fallback。
原生 WSL 构建仍可保留默认来源，GitHub CI 显式使用已核对摘要的 Docker Hub 来源。
OpenSearch 使用相同的显式策略：`OPENSEARCH_REGISTRY=docker.io` 只切换传输仓库，版本和摘要保持固定。
SMB 实协议验收须以非 root 主机用户运行；它会保持私有夹具权限并映射相同 UID，
需要独立 Docker 网络时可设置 `SMB_TEST_DOCKER_NETWORK`，不会停用加密或开放共享。

容器还应用共享的 Debian 安全包锁；固定版本、基础摘要、供应商安全补丁和 SBOM
必须一起审阅与更新。`scripts/verify_cpython_tarfile.py` 在构建中验证真实解析器，
不能通过忽略可修复漏洞或提高扫描阈值完成发布。

## 许可证

自有源码和文档使用 [Apache License 2.0](LICENSE)，署名见 [NOTICE](NOTICE)。第三方库、CPython 安全回补、容器、模型和数据保留各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。Apache-2.0 不授予第三方医药数据、模型权重或在线服务的访问与再分发权。
