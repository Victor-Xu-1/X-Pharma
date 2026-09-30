# 自动数据源接入手册

## 1. 准备来源

- 给 worker 只读权限；禁止 API、MCP 和浏览器直接访问原盘。
- 将允许的最高根目录挂载到容器，例如 `Y:/` -> `/sources/knowledge`。
- 不要把数据库、对象卷或临时目录放在被扫描根目录内。
- 先确认空间、文件数、最大文件、字符集、符号链接和许可范围。

## 2. 注册数据源

通过人员工作台的数据工厂页面注册，或在首次引导时使用：

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm \
  -v "$PWD/deploy/licensing:/licensing:ro" api pharma-bootstrap \
  --tenant-slug default \
  --tenant-name "Default Tenant" \
  --skip-api-key \
  --dataset literature \
  --dataset-license "literature=/licensing/evidence-license.schema-example.json" \
  --source "文献库|/sources/knowledge/文献收集|literature" \
  --source-owner "R&D Intelligence Operations" \
  --source-authorization-scope "contract:internal-rd-2026" \
  --source-authorization-valid-from "2026-01-01T00:00:00+08:00" \
  --source-authorization-valid-until "2027-01-01T00:00:00+08:00" \
  --source-data-classification confidential \
  --source-freshness-seconds 86400
```

root 必须为绝对路径并位于 `SOURCE_ROOTS` 允许范围内。dataset key 是租户逻辑名，不是 RAGFlow 私有 ID。

注册前必须明确：

- 具名数据负责人，不能使用 `unassigned` 或迁移占位值。
- `public/internal/confidential/restricted` 数据分级。
- 至少一个合同、授权单或内部政策范围编号；这里只保存引用，不保存合同原文或凭据。
- 授权生效时间必须包含时区；结束时间可空表示长期授权。结束时间为不包含边界，未生效或已到期来源会在发现和快照前阻断，30 天内到期会持续告警。
- 已注册、启用且当前许可允许至少一个交付渠道的数据集。
- 期望 freshness 和扫描周期。工作台会区分 `pending/stale/unavailable/blocked`，不会把从未成功扫描的来源显示为 ready。

`SOURCE_ROOTS` 是强制白名单，不是文档约定。API 注册、手动触发、调度器和 worker 均 fail closed；路径逃逸、根目录符号链接逃逸、空白名单和未知连接器都会阻止扫描并保留发现项。文件在发现后还会先生成有界、同步落盘并核对前后状态的临时不可变副本，源文件在快照阶段发生变化时本次对象失败，不会发布不一致版本。迁移前已存在的来源会以 `migration-unassigned` 和空授权范围回填，因此必须补齐治理信息后才能恢复自动调度。

### NCBI PubMed 官方 E-utilities

PubMed 使用固定的 NCBI ESearch/EFetch History 端点，不接受租户自定义 URL 或 v1 凭据。注册命令会创建或复用 `literature` dataset，并把查询、上限、页大小和摘要策略固定在版本化 routing rule：

```bash
docker compose exec worker pharma-ingest register-pubmed \
  --tenant-slug default \
  --query-term 'EGFR' \
  --max-records 100 \
  --page-size 100
```

默认 `include_abstract=false`，仅保存 PMID、标题、期刊、日期、作者、文献类型、MeSH、化学词和 DOI。启用 `--include-abstract` 前必须增加 `public:ncbi-pubmed-abstracts` 授权范围并更新 dataset license。连接器限制为无 API key 每分钟最多 180 次请求，生产环境应配置 `SOURCE_NCBI_TOOL` 和可联系的 `SOURCE_NCBI_EMAIL`。模型只允许生成有原文引用的 claim；单个 malformed fact 被拒绝并写 warning，不能中断同文档其他有效事实或同批其他记录。

真实试点证据见 `manifests/real-source-pilot/official-sources-egfr-200-20260730.json`。该证据只证明本地双公开源链路，不替代正式数据授权和生产 UAT。

### HTTP Manifest API

供应商 API 必须实现 [HTTP Manifest v1](../docs/http-manifest-v1.md)。上线前由平台运维完成：

1. 在 OpenBao/External Secrets 的应用 secret 中写入独立 Bearer token 环境变量。
2. 将变量名加入 `SOURCE_CREDENTIAL_ENV_ALLOWLIST`，将供应商精确 Origin 加入 `SOURCE_HTTP_ALLOWED_ORIGINS`。
3. 在工作台选择 `HTTP Manifest API`，填写 manifest URL 与 `env://VARIABLE_NAME` 引用。
4. 用供应商测试租户执行首次全量、分页、增量、token 轮换、429/5xx、损坏 hash 和断点重放验收。

来源记录和 API 响应均不得包含 token。生产只允许 HTTPS；开发时只有显式启用 `SOURCE_HTTP_ALLOW_INSECURE_LOOPBACK` 才能访问本机 HTTP。manifest 与下载均禁止重定向，下载必须与 manifest 同 Origin。任一对象失败时不提交供应商 cursor，下次扫描从上一个成功 cursor 重放。

### S3 只读快照

供应商对象存储使用 [S3 Snapshot v1](../docs/s3-snapshot-v1.md)。运维先把 bucket 加入 `SOURCE_S3_ALLOWED_BUCKETS`，固定 endpoint/region，并通过工作负载身份或 allowlist 中的 `env://` JSON 凭据授予 prefix 级 List/Get 权限。工作台只填写 `s3://bucket/prefix/`、治理字段和可选凭据引用，不填写 endpoint 或密钥。

首次上线必须执行 `make s3-source-acceptance`，再对真实供应商 bucket 验证多页清单、同名覆盖、条件 GET、删除、KMS、STS 轮换、403/429/5xx、网络中断和对象规模。连接器使用 ETag/LastModified/大小形成来源指纹，但最终内容身份始终由平台快照 SHA-256 决定。任一对象失败时不会把未见对象标记为缺失，也不会推进成功 inventory。

### SFTP 只读快照

供应商交付目录使用 [SFTP Snapshot v1](../docs/sftp-snapshot-v1.md)。运维先把规范 origin 加入 `SOURCE_SFTP_ALLOWED_ORIGINS`，通过合同联系人或其他带外渠道核验服务器主机密钥，再把固定 `known_hosts` 作为只读 secret 挂载给 API/worker。禁止在生产启动脚本中自动运行 `ssh-keyscan` 并信任结果。

来源凭据使用 allowlist 中的 `env://` JSON 引用，生产默认只接受私钥。供应商账户必须限制为目标目录只读 SFTP，关闭 shell、端口转发和远端写入；网络出口同时限制到批准 host/port。首次上线执行 `make sftp-source-acceptance`，再在真实交付区验证主机密钥/私钥轮换、递归目录、symlink、权限拒绝、连接中断、同名覆盖、删除、限流和容量。

### SMB / NAS 只读快照

企业研发共享目录使用 [SMB Snapshot v1](../docs/smb-snapshot-v1.md)。运维先把规范 origin 加入 `SOURCE_SMB_ALLOWED_ORIGINS`，保持 `SOURCE_SMB_REQUIRE_ENCRYPTION=true`，再通过 Secret Manager 注入 allowlist 中 `env://` JSON 凭据。来源记录只填写 `smb://host:port/share/path/`、治理字段和凭据引用，禁止在 URI、表单备注、ConfigMap 或 Git 中写密码。

服务端账户必须只允许目标共享和目录的 List/Read，拒绝 Create/Write/Delete/Rename；网络出口限制到批准 host/port。首次上线执行 `make smb-source-acceptance`，再对客户 NAS/域控验证凭据轮换、ACL、递归目录、reparse point、同大小同 mtime 覆盖、连接中断与恢复、NAS failover、删除、限流和容量。共享不可达只允许把来源标记为不可用，不能删除平台不可变快照或权威记录。

`--dataset-license` 文件是受版本控制的交付许可，不是备注。它定义许可编号/版本、Web 或 MCP 渠道、可返回字段、单片段最大字符数、有效期和归属声明。策略缺失、格式无效、过期或不允许当前渠道时检索会 fail closed；截断和字段省略必须在响应 `warnings` 中显式报告。示例文件只提供 schema 和安全结构，投产前必须替换为经法务与数据负责人批准的真实合同范围。

## 3. 默认内容策略

解析：PDF、DOCX、PPTX、XLSX、CSV、TXT、MD、HTML。

资产登记：CDX、SDF、MOL、PDB、CIF、MOE、MDB。它们保留路径、hash、MIME/扩展名和版本，不生成伪文本。

建议排除：回收站、系统目录、软件/安装包、发票、考勤、视频和无研发价值的大文件。排除策略在数据源记录中显式保存，不靠隐藏脚本。

## 4. 小样本验收

入库安全门禁先执行：

```bash
make malware-scan-acceptance \
  MALWARE_EVIDENCE=manifests/runtime/acceptance-smoke/malware-$(date -u +%Y%m%dT%H%M%SZ).json
```

该命令连接真实 clamd，在临时 SQLite 权威库与临时文件对象存储中执行完整 Data Factory，必须同时证明干净 Markdown 能解析、EICAR 在解析前被阻断、原始不可变快照保留且不生成 extracted text。证据文件以 `0600` 权限原子创建且拒绝覆盖；验收不会向长期运行库写测试租户或凭据。

所有来源类型都在不可变快照校验后、解析或科学资产登记前执行扫描。默认最大扫描文件为 256 MiB；恶意内容、clamd 不可用/超时、协议异常和文件超限均记录为 `malware_scan_status=FAILED`，不得退化为 `SKIPPED`。生产必须设置 `MALWARE_SCAN_ENABLED=true` 并把 `CLAMAV_HOST` 指向内部服务，同时监控病毒库更新时间、扫描延迟、拒绝数和服务可用性。

隔离处置链在已启动的完整 Compose 运行线上验收：

```bash
make quarantine-workflow-acceptance \
  QUARANTINE_WORKFLOW_EVIDENCE=manifests/runtime/acceptance-smoke/quarantine-$(date -u +%Y%m%dT%H%M%SZ).json
```

命中案件必须在内部工作台“恶意文件隔离”队列处理。`留置待审` 保持阻断，`永久拒绝` 不允许再通过标准复扫或通用版本重放恢复，`重新安全扫描` 只从 `malware_scan` 启动 Temporal 工作流并继续强制调用 ClamAV。没有人工“强制释放”动作；只有完整复扫返回清洁结果才会自动转为 `CLEARED` 并继续后续阶段。每次处置必须填写原因并形成递增版本、不可变决策记录和审计事件；状态冲突时刷新案件后使用新操作键，禁止直接修改数据库状态或删除历史。

Kubernetes 中 `pharma-clamav` 是双副本起步的 StatefulSet；每个副本使用独立持久卷，避免多个 freshclam 进程并发改写同一病毒库。新卷先由固定摘要镜像种入缺失的内置签名并保留原始时间戳，已有签名绝不覆盖，随后由 freshclam 增量更新；这只减少冷启动依赖，不允许跳过 freshness。readiness 在 clamd 不可达或 36 小时内没有更新签名文件时失败，Service 自动摘除该副本；应用侧仍按 fail closed 记录版本失败，不允许绕过扫描。拓扑约束要求副本尽量跨主机和 zone 分布；目标 overlay 必须替换 `replace-with-rwo-storage-class`，并确认签名更新 HTTPS 只能到企业批准的镜像或由目标 CNI 执行 FQDN 限制。

预生产切换演练至少执行：

```bash
kubectl -n pharma-intelligence get statefulset,pod,pvc,pdb,hpa -l app.kubernetes.io/name=pharma-clamav
kubectl -n pharma-intelligence delete pod pharma-clamav-0 --wait=true
kubectl -n pharma-intelligence wait --for=condition=Ready pod/pharma-clamav-0 --timeout=15m
kubectl -n pharma-intelligence exec pharma-clamav-0 -- freshclam --version
kubectl -n pharma-intelligence exec pharma-clamav-1 -- freshclam --version
```

演练期间提交干净样本和 EICAR，要求至少一个副本持续 Ready、干净样本可扫描、EICAR 仍被阻断、历史不可变快照未改变，且告警完成触发、确认和恢复。删除 Pod 后原 ordinal 必须重新挂载同一 PVC；不得通过删除 PVC 或关闭 readiness 恢复服务。

每类数据集先选至少 3 个真实 PDF/PPTX/DOCX/XLSX/专利 PDF：

1. 文件稳定后创建且只创建一个 SourceVersion。
2. raw snapshot、恶意文件扫描记录与 extracted text URI 均存在，SHA-256 正确，扫描状态为 `SUCCEEDED`。
3. page/slide/sheet locator 与原文一致。
4. AI 候选 quote 可在解析文本中找到；低置信度进入 review。
5. 批准后结构化表、evidence claim 和 knowledge page 更新。
6. 第二次扫描记录 unchanged，不重复版本。
7. 拔掉来源后状态为 unavailable，数据库仍可查询；恢复后自动继续。
8. 活动运行需要停止时，只能在内部数据工厂打开运行详情并提交取消原因；平台会校验精确 Temporal workflow/run 身份并在阶段边界停止。不得使用 `tctl terminate` 作为日常取消路径；该命令只用于受控应急处置并必须补录审计。
9. 解析、AI 治理或检索投影失败时，版本详情只显示服务端判定合法的恢复点。选择恢复起点并填写原因后，系统保留不可变原始快照，只重置所选阶段及其下游状态；请求仍受租户权限、当前版本状态、当前错误码或失败阶段、幂等键和审计约束。
10. 调整模型、提示词、结构化 schema、预算或自动发布策略后，下一次自然扫描重新排队同一 SourceVersion，创建新的 ExtractionRun；旧运行不可变保留，策略未变化时不得再次调用模型。

## 5. 运行监控
对已注册来源执行当前版本的真实门禁：

```bash
make ingestion-acceptance INGESTION_SOURCE_ID=<registered-source-uuid>
make automatic-ingestion-acceptance INGESTION_SOURCE_ID=<registered-source-uuid>
make source-stage-replay-acceptance
```

第一条命令显式执行两次受控扫描，验证解析、追溯、投影和幂等。第二条命令不调用手工扫描，不修改 `last_scanned_at`/扫描周期，也不创建源文件；它会在有界时间内等待正在运行的 Temporal scheduler 自然发起一个新 workflow，并核对入库、恶意文件扫描、原文追溯和 OpenSearch 队列。来源下次到期时间超出默认 900 秒时会失败关闭，可直接运行脚本并用 `--timeout-seconds` 扩大观察窗口，不允许为通过验收而在脚本内篡改调度元数据。

第三条命令使用受控真实 Markdown 完成解析、第三方 LLM API 治理、事务 outbox 和 OpenSearch 首次入库，再注入解析、治理和投影阶段失败并从人员 HTTP API 触发 Temporal 恢复；验收结束必须确认临时账号、数据库记录、原始文件、对象和检索文档均无残留。


持续观察：扫描耗时、发现/未变/失败数量、解析吞吐、失败扩展名、模型延迟/成本、review backlog、投影失败和知识 freshness。

AI 治理变更必须作为受审计的批次发布。`policy_sha256` 不包含 API 密钥，但绑定模型 ID、模型端点哈希、允许的响应模型、系统提示词、普通/结构事实 JSON schema、输入输出边界、token/成本预算和自动发布策略。任一绑定项变化时，scheduler 会在来源下一次到期扫描时只重新治理当前不可变版本，不重新复制原文件；相同策略的成功或失败运行不会被自动重复。模型或策略升级前先估算当前资产数和最大成本、限制 worker 并发并监控 governance backlog；需要重试同一失败策略时使用受审计的人工重试流程，不得通过修改策略制造新指纹绕过失败记录。

工作台的来源 readiness 同时展示连接器能力、Web/MCP 许可渠道、增量游标、freshness 和阻断原因。目录连接器标识为 `folder-v1`，通用供应商协议标识为 `http-manifest-v1`，对象存储标识为 `s3-snapshot-v1`，文件交换区标识为 `sftp-snapshot-v1`，企业共享标识为 `smb-snapshot-v1`。具体付费供应商仍须完成真实合同、字段映射、主机密钥/凭据和限流回放；事件流和供应商专用 API 适配器仍须按实际合同实现，不能把五种通用协议冒充全部连接器已完成。

失败必须保留 `IngestionFinding`、source/version/run ID 和可诊断原因。不要以空文本、跳过验证或无限重试隐藏失败。自动调度对 `UNAVAILABLE` 来源使用 `SOURCE_RETRY_BASE_SECONDS` 与 `SOURCE_RETRY_MAX_SECONDS` 的有界指数退避；恢复后回到来源自身的 `scan_interval_seconds`，不会在每个 scheduler poll 重复打上游，也不会因一次瞬时失败等到下一个日周期。内部工作台的人工重试仍是显式操作，不修改成功游标。

授权续期在工作台编辑来源治理配置：更新授权范围、生效时间和可选结束时间后，系统写入 `data_source.authorization.update` 审计事件并递增配置版本。来源路径、数据集绑定、历史资产和增量游标不变；readiness 通过后调度器会自动恢复。来源授权时间窗负责“能否继续抓取”，dataset license 仍独立负责“能否通过 Web/MCP 交付”，两者任一失效都 fail closed。

## 6. 变更和下线

- 改挂载路径时先停 scheduler，更新 source root，执行 checksum 对账后恢复。
- 目录重命名不会自动删除历史；应创建受审计的来源迁移记录。
- 下线来源只停扫描，不删除不可变版本和已经发布的带来源事实。
- 删除原始资料、对象或 canonical 记录需要单独的数据保留/法律审批流程。
