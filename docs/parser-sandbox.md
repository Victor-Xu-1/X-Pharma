# 隔离文档解析服务

本服务处理来源不可信的 PDF、Office、HTML、文本及科学结构文件。ClamAV 是前置门禁，但不能识别所有畸形文件或解析器漏洞，因此格式解析不能在持有数据库、对象存储、Temporal、模型和租户凭据的 ingestion worker 进程内执行。

## 信任边界

运行顺序固定为：

1. worker 从已治理来源生成不可变 SHA-256 快照。
2. worker 通过 ClamAV INSTREAM；检出、超时、协议错误或超限均停止。
3. worker 以流式 `application/octet-stream` 请求调用内部 parser 服务。
4. parser 核对认证、声明长度、文件类型和 SHA-256，再写入私有临时目录。
5. 每个文件在新的 Python `-I` 子进程中解析；子进程清空业务环境变量并限制地址空间、CPU 时间、输出文件、文件描述符和墙钟时间。
6. parser 返回协议版本、原文件摘要、文本摘要、解析器名称/版本和 locator 元数据；worker 重新计算两个摘要后才写 extracted text。

parser 服务不加载平台 `.env`，不取得数据库、对象存储、模型、OIDC、MCP、OpenSearch、Valkey 或 Temporal 凭据。服务只取得独立 `PARSER_SERVICE_TOKEN`、服务端 TLS 私钥和客户端 CA；worker 只取得客户端 TLS 私钥和服务端 CA，双方看不到对方私钥。生产 token 至少 32 字节且不能复用任何平台签名密钥。

## 协议边界

内部接口为 `POST /internal/v1/parse`，不属于公开产品入口。请求必须包含：

- `Authorization: Bearer <parser-service-token>`
- `Content-Type: application/octet-stream`
- 精确 `Content-Length`
- `X-Content-SHA256`
- 查询参数 `filename` 和 `max_chars`

路径型文件名、HTTP 压缩请求体、未知扩展名、空文件、长度或摘要不一致都会在解析前拒绝。响应使用 `parser_protocol.py` 的封闭 Pydantic schema；未知字段、协议版本、摘要或空文本不符合契约时 worker 失败关闭。

服务默认每 Pod 同时只启动一个高内存解析子进程。容量耗尽返回 `429` 和 `Retry-After`，由 Temporal 有界退避重试；不会为了吞吐同时突破内存上限。支持的格式与精确 parser 版本由应用锁文件和镜像共同锁定。

## Compose

本地 Compose 的 `parser` 和 `worker` 只共享 `parser-sandbox` internal 网络。parser 不加入默认网络，不能访问公网或数据库服务；容器只读、drop all capabilities、`pids_limit=64`、2 CPU、3 GiB 内存。开发环境使用该隔离网络上的 HTTP 和开发 token，不能把这套 token 或明文传输复制到生产。

真实验收：

```bash
make parser-sandbox-acceptance \
  PARSER_EVIDENCE=manifests/runtime/acceptance-smoke/parser-sandbox.json
make malware-scan-acceptance \
  MALWARE_EVIDENCE=manifests/runtime/acceptance-smoke/malware-parser-chain.json
```

第一项验证十一种真实格式（MD/HTML/DOCX/PPTX/XLSX/PDF/SDF/MOL/PDB/CIF/mmCIF）、401、摘要篡改、容器资源、最小环境和公网阻断，并启动真实 Uvicorn mTLS 服务证明合法证书成功、无客户端证书/伪造客户端/错误服务端 CA 均握手失败。它还用慢请求占满唯一解析槽，要求并发请求返回 `429 parser_capacity_exhausted` 和 `Retry-After`，释放后立即恢复；另在真实容器中触发子进程墙钟超时，要求完整进程组回收、零直接子进程残留并成功解析后续文件。验收期间临时生成九类对抗样本，经过真实 HTTP parser 链逐一证明 Office 路径穿越、大小写重复成员、符号链接、成员数量爆炸、异常压缩比、加密成员、加密 PDF、XML 外部实体及损坏 SDF 均返回 `422 document_parse_rejected`，随后健康文件和就绪探针必须恢复。语料仅存在于临时目录，报告不记录内容或解析错误正文。科学格式在子进程中执行记录数、原子数、链、残基、配体类型和输出大小硬限制；损坏记录明确失败，不登记为解析成功。第二项用临时 SQLite 权威库证明 Data Factory 的干净文件确实使用 `parser_backend=service`，而 EICAR 在 parser 前被阻断。两项均不修改持久运行数据库。

## Kubernetes

`pharma-parser` 是独立 Deployment/Service，不是 worker sidecar，避免共享 worker 的网络身份。默认 NetworkPolicy：

- 只允许 `pharma-jobs` 到 parser 的 8070/TCP 入站；
- parser 被排除在 DNS 和平台通用 egress 策略之外，因此没有主动出站权限；
- 其他 Pod 不能调用 parser。

生产 base 强制：

- `PARSER_SERVICE_URL=https://pharma-parser:8070`
- parser 从 `pharma-parser-server-tls` 挂载服务端 `tls.crt`/`tls.key`，从 `pharma-parser-client-tls` 只挂载 `ca.crt`
- worker 从 `pharma-parser-client-tls` 挂载客户端 `tls.crt`/`tls.key`，从 `pharma-parser-server-tls` 只挂载 `ca.crt`
- `PARSER_SERVICE_VERIFY_CERTS=true`
- `PARSER_SERVICE_CLIENT_CERT` 与 `PARSER_SERVICE_CLIENT_KEY` 必须为绝对路径
- token 由 OpenBao/ESO 的 `pharma-document-processing-secrets` 注入；平台 API、MCP 和 scheduler 不挂载该 Secret

目标 overlay 必须由企业 PKI 或 cert-manager 分别创建带 `pharma-parser` 服务 DNS SAN 和 `serverAuth` 的服务端证书，以及带 `clientAuth` 的 worker 证书。不得把私钥或自签证书提交到 Git。证书轮换后必须验证 parser/worker rollout、双向 CA 信任和在途 Temporal 重试。Kubelet 使用 TCP probe，避免用不带客户端证书的 HTTP probe 绕过或误判 mTLS；应用级就绪由 worker synthetic check 和发布验收覆盖。

## 故障与运营

| 故障 | 行为 |
|---|---|
| token/mTLS/CA 错误 | TLS 握手或应用认证失败，worker 记录解析失败，不回退进程内 parser |
| parser 429/不可用 | Temporal 按有限预算退避；不推进来源成功游标 |
| 文档拒绝/加密/空文本 | 记录不可重试版本失败，保留原始快照 |
| CPU、内存或墙钟超限 | 终止完整子进程组，记录隔离解析失败 |
| 响应 schema/摘要异常 | worker 拒绝响应，不写 extracted text |

生产上线仍需在批准数据量下完成 parser 队列容量与吞吐基准、外部批准恶意样本库、超大文件、Pod 驱逐、企业 PKI 证书轮换和多副本故障演练。本地证据只证明内建对抗样本、有界饱和拒绝、子进程回收和恢复语义，不能替代外部 corpus、目标负载、渗透测试或目标云 CNI/PKI 验收。
