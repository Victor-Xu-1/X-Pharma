# 隔离 OCR 服务

OCR 是自动数据工厂的内部解析能力，不是第三个产品入口。内部运营工作台注册目录或供应商来源后，Temporal worker 自动扫描、快照、杀毒并调用 parser；只有有效图片或完全没有机器文本层的 PDF 才会以 `document_ocr_required` 转交 OCR。外部信息查询工作台和 MCP 只能消费已治理发布的数据，不能调用 OCR 或提交文件。

## 信任边界

- 服务仅接受 PNG、JPEG、TIFF 和 PDF 的 `application/octet-stream`，要求 Bearer token、精确长度、文件名后缀和源 SHA-256。
- 图片在推理前验证格式和像素上限；PDF 使用严格模式验证加密状态与页数。
- PaddleOCR `3.5.0`、PaddlePaddle `3.3.1`、`PP-OCRv5_server_det` 和 `PP-OCRv5_server_rec` 被固定；启动时重新计算两个模型目录摘要，漂移立即失败。
- 输出只接受结构完整、坐标有界、置信度在 `[0,1]` 的结果；低置信度行丢弃，文本、行数、页数和并发均有硬上限。
- worker 重新验证响应 schema、源摘要和文本摘要。结果携带 `[[page:n]]` 与 `[[region:x1,y1,x2,y2;confidence:s]]`，供后续引用回溯。
- 损坏、加密、恶意或普通解析失败不会进入 OCR fallback；OCR 不作为错误吞噬或伪解析机制。

## 本地 Compose

模型不提交 Git。先把官方模型复制到仓库外、由平台管理的只读目录；不要直接挂载个人用户的 PaddleX 缓存目录，因为其中的元数据文件可能只有下载用户可读。模型目录内所有文件必须能由容器 UID `10001` 读取，且内容必须与 `deploy/ocr/models.json` 的摘要一致。例如：

```bash
install -d -m 0750 /srv/pharma-intelligence/models/ocr
cp -a ~/.paddlex/official_models/PP-OCRv5_server_det /srv/pharma-intelligence/models/ocr/
cp -a ~/.paddlex/official_models/PP-OCRv5_server_rec /srv/pharma-intelligence/models/ocr/
find /srv/pharma-intelligence/models/ocr -type d -exec chmod 0555 {} +
find /srv/pharma-intelligence/models/ocr -type f -exec chmod 0444 {} +
```

然后配置受管模型根目录：

```dotenv
OCR_MODEL_ROOT=/srv/pharma-intelligence/models/ocr
OCR_SERVICE_TOKEN=replace-with-an-independent-random-token
```

```bash
docker compose -f compose.yaml -f compose.dev.yaml -f compose.ocr.yaml build ocr
docker compose -f compose.yaml -f compose.dev.yaml -f compose.ocr.yaml up -d ocr worker
```

`ocr` 只加入 `ocr-sandbox` internal 网络，不读取平台 `.env`，只读挂载模型，使用只读根文件系统、tmpfs、drop-all capabilities、单请求推理槽和 CPU/内存/PID 上限。默认构建从官方 PyPI 下载哈希锁定 wheel；受控企业环境可通过 `OCR_PYPI_INDEX_URL` 指向只读制品代理，但 `--require-hashes` 仍强制校验内容。

本机存在完全相同的 Python 3.13/Paddle 运行时和模型时，可运行真实 TCP、typed fallback 和中英文扫描件验收：

```bash
make ocr-acceptance OCR_EVIDENCE=/absolute/private/evidence/ocr-acceptance.json
```

证据记录模型摘要、运行时版本、PNG/PDF 源摘要、文本摘要、页/区域定位、置信度和耗时，不保存扫描图。Mock 测试不能替代该门禁。

## Kubernetes

`pharma-ocr` 是 3 副本独立 Deployment，模型来自 `pharma-ocr-models` ReadOnlyMany PVC。默认 NetworkPolicy 只允许 `pharma-jobs` 访问 8071/TCP；OCR 被排除在 DNS 和平台通用 egress 之外。企业 PKI 必须分别创建 `pharma-ocr-server-tls` 和 `pharma-ocr-client-tls`，私钥方向与 parser 相同；`OCR_SERVICE_TOKEN` 必须独立保存于 OpenBao/ESO。

生产 overlay 必须完成以下替换和验证：

- 将 OCR 镜像标签替换为 CI 生成、签名并扫描的不可变 digest。
- 用受控模型制品流程填充只读 PVC，校验 `deploy/ocr/models.json` 的目录摘要和许可证清单。
- 替换模型 storage class，并验证 3 Pod 跨节点挂载、冷启动、PDB、证书轮换和 worker 有界重试。
- 在批准的真实扫描资料上评测中文、英文、混排、旋转、低质量、表格和多页 PDF；记录召回率、字符错误率、吞吐、峰值内存与失败分类。

当前服务提供文本检测/识别和区域定位，不宣称已完成复杂版面还原、表格结构重建或手写体生产质量。此类能力必须通过独立模型、版本、评测与字段映射进入，不能把普通 OCR 文本冒充结构化表格。

## 故障处理

| 故障 | 行为 |
|---|---|
| token、mTLS 或摘要错误 | 请求失败，不写解析文本 |
| 模型目录或运行时版本漂移 | Pod 启动失败，readiness 不通过 |
| OCR 容量耗尽 | 返回 429/Retry-After，Temporal 有界退避 |
| OCR 无高置信文本 | 版本失败并保留原始快照，进入运营处置 |
| OCR 服务不可用或超时 | 不回退空文本或伪内容，不推进来源成功游标 |
| wheel/镜像下载失败 | 构建失败；使用经批准制品代理，不关闭哈希校验 |
