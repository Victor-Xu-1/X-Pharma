# S3 Snapshot v1 来源协议

`s3-snapshot-v1` 将批准 bucket/prefix 视为只读权威清单。它适用于供应商 S3 交付区、企业数据湖导出区和 S3 兼容对象存储，不承担平台内部不可变证据仓的写入职责。

## 注册合同

- 工作台来源类型：`S3 只读快照`。
- root URI：`s3://bucket/canonical/prefix/`；bucket 必须在部署级 `SOURCE_S3_ALLOWED_BUCKETS` 精确白名单中。
- endpoint、region、path-style 和超时由部署配置固定，不能由租户或来源记录覆盖。
- `stable_seconds` 必须为 `0`；一致性依赖对象存储清单元数据与条件 GET，不使用本地文件稳定等待。
- include/exclude glob、单文件上限、数据集许可、owner、分级、授权范围和 freshness 沿用数据工厂治理合同。

默认凭据引用为 `env://VARIABLE_NAME`。变量必须列入 `SOURCE_CREDENTIAL_ENV_ALLOWLIST`，值是单行紧凑 JSON：

```json
{"access_key_id":"temporary-access","secret_access_key":"temporary-secret","session_token":"optional-session-token"}
```

来源记录、API 和运行日志只保存引用，不返回 JSON。生产优先使用云工作负载身份；只有部署 overlay 已绑定最小权限角色时才启用 `SOURCE_S3_ALLOW_DEFAULT_CREDENTIAL_CHAIN=true`。静态长期 access key 不属于推荐生产配置。

## 扫描与快照

1. 连接器使用 `ListObjectsV2` 完整分页枚举 prefix，限制每页和总页数，并拒绝重复或缺失 continuation token。
2. 对象 key 转换为规范相对 POSIX 路径；目录标记、不支持类型、超限和 glob 排除项不进入处理。
3. ETag、大小、LastModified、bucket 和 key 生成来源指纹。指纹未变化时不下载；即使大小与修改时间相同，ETag 变化仍会触发新快照。
4. 下载使用 `If-Match` 条件 GET，并再次核对 ETag、LastModified、ContentLength 和实际流式字节数。发现后发生变化的对象使本项失败，不会发布混合版本。
5. 平台对临时快照计算 SHA-256，再写入自己的不可变证据仓。供应商 ETag 只做来源并发控制，不冒充内容 SHA-256。
6. 完整且零失败的清单是权威 inventory；上次存在、本次消失的对象标记为 `missing`。任一发现或快照失败时不执行缺失标记，也不推进成功 inventory cursor。

连接器不调用 Put/Delete/Copy，不修改供应商 bucket。IAM/STS 策略至少限制到目标 bucket/prefix 的 List/Get；生产还必须限制网络出口、KMS 解密范围、凭据时效和审计日志。

## 配置

```dotenv
SOURCE_CREDENTIAL_ENV_ALLOWLIST=SUPPLIER_S3_CREDENTIALS
SOURCE_S3_ALLOWED_BUCKETS=licensed-supplier
SOURCE_S3_ENDPOINT_URL=
SOURCE_S3_REGION=us-east-1
SOURCE_S3_ALLOW_DEFAULT_CREDENTIAL_CHAIN=false
SOURCE_S3_FORCE_PATH_STYLE=false
SOURCE_S3_CONNECT_TIMEOUT_SECONDS=10
SOURCE_S3_READ_TIMEOUT_SECONDS=60
SOURCE_S3_MAX_PAGES=10000
SOURCE_S3_PAGE_SIZE=1000
```

AWS 公有 S3 使用空 endpoint。私有 S3 兼容服务填写固定 HTTPS origin；生产拒绝 HTTP。`SOURCE_S3_ALLOW_INSECURE_LOOPBACK=true` 只允许非生产环境访问 loopback 测试服务。

## 验收

```bash
make s3-source-acceptance
```

该命令启动固定 digest 的临时 S3 兼容服务，通过真实 SigV4 HTTP 请求验证分页、条件 GET、幂等扫描、同元数据内容变化和权威删除，再销毁测试容器。它证明协议实现，不替代真实供应商 bucket、合同、KMS、网络和容量验收。
