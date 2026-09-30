# SMB Snapshot v1 来源协议

`smb-snapshot-v1` 将批准的企业 SMB3/NAS 共享目录视为只读权威清单，适用于内部研发文件服务器和受控交付区。连接器只执行目录枚举、属性读取和文件读取，不创建、改名、删除或写回远端对象。

## 信任与注册合同

- 工作台来源类型：`SMB / NAS 只读快照`。
- root URI：`smb://host:port/share/absolute/path/`；第一段必须是共享名，URI 不得包含用户名、密码、query 或 fragment。
- origin 必须精确匹配部署级 `SOURCE_SMB_ALLOWED_ORIGINS`。当前版本支持 DNS 名称和 IPv4；不接受 IPv6 literal。
- 生产强制 `SOURCE_SMB_REQUIRE_ENCRYPTION=true`，会话同时要求 SMB 签名。loopback 只可在非生产环境显式启用。
- `stable_seconds` 必须为 `0`；连接器依赖完整清单、下载前后属性核对和平台内容摘要，不使用本地文件等待。

凭据使用 allowlist 中的 `env://VARIABLE_NAME` 引用。变量值是单行紧凑 JSON，密码只存在于 Secret Manager 注入的进程环境，不进入来源记录、API 响应、日志或 URI：

```json
{"username":"source-reader","password":"secret-manager-value","domain":"RESEARCH","auth_protocol":"negotiate"}
```

`domain` 可省略，`auth_protocol` 只允许 `negotiate` 或 `ntlm`。服务端账户必须限制到目标共享和目录的只读权限；部署网络出口应只允许批准的 host/port。

## 发现与快照

1. 连接器为每次扫描创建隔离会话缓存，以明确端口、签名、加密和凭据建立 SMB 会话，结束后主动清除连接缓存。
2. 通过 `scandir` 有界递归目录；限制总条目和深度，不跟随 symlink/reparse point，忽略非普通文件。
3. 规范化相对路径，执行扩展名、glob 和大小策略。路径、大小和 mtime 形成清单指纹，但不作为内容身份。
4. SMB 共享没有统一可靠的内容摘要，因此每次扫描都重新物化文件并计算 SHA-256；同大小、同 mtime 的内容覆盖仍会产生新版本。
5. 下载前后分别用不跟随链接的 `stat` 验证普通文件、大小和 mtime，并限制实际读取字节数。文件在发现后变化时本次对象失败。
6. 只有完整且零失败的权威清单才允许推进 cursor 和标记缺失对象。认证失败、共享断开或根目录不可读只会把来源标记为不可用，已保存的不可变版本继续保留。

## 配置

```dotenv
SOURCE_CREDENTIAL_ENV_ALLOWLIST=ENTERPRISE_SMB_CREDENTIALS
SOURCE_SMB_ALLOWED_ORIGINS=smb://fileserver.example:445
SOURCE_SMB_REQUIRE_ENCRYPTION=true
SOURCE_SMB_ALLOW_INSECURE_LOOPBACK=false
SOURCE_SMB_CONNECT_TIMEOUT_SECONDS=10
SOURCE_SMB_MAX_ENTRIES=1000000
SOURCE_SMB_MAX_DEPTH=64
```

Kubernetes 中通过 External Secrets 或同等级 Secret Manager 注入凭据变量，并把变量名加入 allowlist。不要把密码写入 ConfigMap、Helm values、来源表单或 Git 仓库。生产上线还必须验证账户锁定/轮换、域控不可用、网络分区、NAS failover、ACL 拒绝、容量和扫描带宽。

## 验收

```bash
make smb-source-acceptance
```

该命令启动固定 digest 的 Samba 4.23.8 临时服务器，强制 SMB3 传输加密和只读共享。真实协议测试覆盖幂等扫描、同元数据内容变化、发现后竞态、权威删除、错误凭据导致来源不可用、历史版本保留及凭据恢复，然后销毁服务器和测试凭据。该本地验收不能替代客户 NAS、域控、企业 PKI/网络和真实数据规模的上线验收。
