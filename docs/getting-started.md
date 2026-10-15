# X-Pharma：开始使用

使用 Linux x86-64 或 WSL2 Linux 环境，并将源码放在 Linux 原生文件系统。准备 Linux Docker Engine/Compose、Python 3.13.16、uv 0.11.28、Node.js 24.14、Corepack/pnpm 11.7.0、Git 与 Make。

```bash
git clone https://github.com/Victor-Xu-1/X-Pharma.git
cd X-Pharma
uv sync --locked --dev
corepack pnpm@11.7.0 --dir apps/web install --frozen-lockfile
make configure
make up-observed
make status
```

首次启动需要网络下载或构建镜像。`make configure` 创建独立随机密钥与私有配置，不覆盖已有配置。没有预设账号或密码；AI 默认关闭。WSL 用户还需按 [环境准备说明](wsl-development.md)完成工具安装与预检。

创建自己的开发账号：

```bash
read -rsp "Admin password: " ADMIN_PASSWORD; printf '\n'
docker compose -f compose.yaml -f compose.dev.yaml run --rm api pharma-bootstrap \
  --tenant-slug default --tenant-name "Default Tenant" --skip-api-key \
  --admin-email admin@example.com --admin-password "$ADMIN_PASSWORD"
unset ADMIN_PASSWORD
```

将示例邮箱与组织信息替换为自己的信息，使用至少 12 个字符的独立强密码。密码通过命令参数传给本地容器，请在可信开发主机执行。

- 研究工作台：<http://127.0.0.1:18380/workspace/research>
- 内部管理工作台：<http://127.0.0.1:18380/workspace/internal>，需要相应权限
- MCP：<http://127.0.0.1:18390/mcp>，需另行配置客户端身份与许可

仓库不包含业务数据库、模型或商业数据。新环境需要自行接入获授权的来源。


## 数据与安全

这是开发环境启动流程。真实生产环境需另行配置企业身份、TLS、租户隔离、备份恢复和容量控制，参阅[部署说明](deployment.md)和[安全策略](../SECURITY.md)。

只接入有权使用的数据。商业数据、模型权重与在线服务不包含在开源授权内。AI 默认关闭，启用前需明确批准第三方 HTTPS 服务、模型、费用与资料外发权限。

升级前先备份并按迁移说明操作；不要关闭鉴权、校验或删除数据卷来绕过故障。

## 接下来

- [账号、组织与登录](accounts-and-organizations.md)
- [来源接入](../runbooks/source-onboarding.md)与[公共数据同步](automatic-public-source-ingestion.md)
- [Agent MCP 接入](mcp-contract.md)
- [备份与恢复](../runbooks/recovery.md)
