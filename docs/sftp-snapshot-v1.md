# SFTP Snapshot v1 来源协议

`sftp-snapshot-v1` 将批准服务器上的绝对目录视为只读权威清单，适用于供应商定期交付区和企业隔离交换区。它不执行远程命令，不上传、改名或删除供应商文件。

## 信任与注册合同

- 工作台来源类型：`SFTP 只读快照`。
- root URI：`sftp://host:port/absolute/path/`；URI 不得包含用户名、密码、query 或 fragment。
- origin 必须精确匹配部署级 `SOURCE_SFTP_ALLOWED_ORIGINS`，租户不能指定任意网络目标。
- `SOURCE_SFTP_KNOWN_HOSTS_PATH` 必须指向部署挂载的 OpenSSH `known_hosts`；未知或变化的主机密钥一律拒绝。
- 生产 `known_hosts` 必须由运维通过供应商合同渠道或带外指纹核验后配置，不能在应用启动时用 `ssh-keyscan` 自动信任。
- `stable_seconds` 必须为 `0`；连接器依赖清单属性与下载前后 `lstat` 一致性，不使用本地文件等待。

凭据使用 allowlist 中的 `env://VARIABLE_NAME` 引用。变量值是单行紧凑 JSON，生产默认只接受私钥：

```json
{"username":"source-user","private_key_pem":"<REDACTED_PRIVATE_KEY>","private_key_passphrase":"optional"}
```

密码认证只用于受控兼容环境，并须显式启用 `SOURCE_SFTP_ALLOW_PASSWORD_AUTH=true`；production profile 会拒绝该配置。SSH agent 和本机默认密钥查找始终关闭。

## 发现与快照

1. 连接器建立带 connect/banner/auth/channel 超时的 SSH 会话，使用显式 `known_hosts` 和拒绝未知主机策略。
2. 通过 SFTP `listdir_attr` 有界递归目录；限制总条目和目录深度，不跟随 symlink，忽略非普通文件。
3. 规范化相对 POSIX 路径，执行扩展名、glob 和文件大小策略；路径、大小和 mtime 形成清单指纹，但不被当作内容身份。
4. 标准 SFTP 没有通用 ETag/checksum，因此每次扫描都会重新流式计算内容 SHA-256；内容相同不会创建新版本。下载前后分别执行 `lstat`，要求对象始终是同一大小和 mtime 的普通文件。
5. 平台计算 SHA-256 后写入自己的不可变证据仓。远程 mtime 只是并发与增量信号，不是内容身份。
6. 完整且零失败的目录清单才允许标记缺失对象并推进 inventory cursor；目录不可读、连接中断或文件变化时失败关闭。

## 配置

```dotenv
SOURCE_CREDENTIAL_ENV_ALLOWLIST=SUPPLIER_SFTP_CREDENTIALS
SOURCE_SFTP_ALLOWED_ORIGINS=sftp://supplier.example:22
SOURCE_SFTP_KNOWN_HOSTS_PATH=/run/secrets/supplier_known_hosts
SOURCE_SFTP_ALLOW_PASSWORD_AUTH=false
SOURCE_SFTP_CONNECT_TIMEOUT_SECONDS=10
SOURCE_SFTP_READ_TIMEOUT_SECONDS=60
SOURCE_SFTP_MAX_ENTRIES=1000000
SOURCE_SFTP_MAX_DEPTH=64
```

网络策略还应只允许 worker 访问批准 endpoint；账户应被服务端限制为目标目录只读 SFTP，不能获得 shell、端口转发或写权限。凭据和 `known_hosts` 通过 Secret Manager/Kubernetes Secret 或批准的动态密钥系统挂载，不提交仓库。

完整内容复核保证同大小/同 mtime 覆盖不会漏检，但会消耗 SFTP 带宽。大规模高频来源应优先采用带 ETag/checksum 的 S3 或 HTTP Manifest；SFTP 上线时必须按合同带宽设置扫描周期、文件上限和来源速率。

## 验收

```bash
make sftp-source-acceptance
```

该命令启动固定 digest 的 OpenSSH 10.2p1 临时服务器，以真实公钥认证和 SFTP 协议验证主机密钥、递归清单、幂等扫描、发现后竞态、新版本和权威删除，再销毁服务器。测试中的 `ssh-keyscan` 只针对 loopback 临时容器，不是生产信任流程。真实供应商上线还须验证带外主机指纹、密钥轮换、目录权限、限流、网络中断和容量。
