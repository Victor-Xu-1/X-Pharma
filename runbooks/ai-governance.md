# AI 入库治理运行手册

AI 网关是自动入库的内部处理边界，不是第三个产品入口。生产资料只能发送到经过数据授权、安全评审和合同审批的模型网关。

平台的 LLM、embedding 和 reranker 推理只允许调用获批准的第三方 HTTPS API。仓库不包含本地模型权重、vLLM/Ollama 服务或本地回退；远程 API 未配置或不可用时请求必须明确失败，不能改走本机推理。

## 配置门禁

- `AI_BASE_URL` 接受服务根地址或以 `/v1` 结尾的 OpenAI-compatible 根地址；应用确定性生成一个 `/v1/chat/completions` 路径。
- 所有环境都要求远程 HTTPS，URL 不得指向 localhost/loopback，也不得携带账号、密码、query 或 fragment。`AI_API_KEY` 只由 secret manager 注入。
- `AI_MODEL` 可以是批准的网关别名，但 provider 返回的实际模型 ID 必须命中 `AI_ALLOWED_RESPONSE_MODELS_JSON`；模型切换先更新审批和 allowlist，不能静默漂移。
- `AI_INPUT_COST_PER_MILLION_TOKENS`、`AI_OUTPUT_COST_PER_MILLION_TOKENS` 和 `AI_MAX_DOCUMENT_COST` 必须由已批准 rate card 设置为正数。Kubernetes base 中的零值是故意的失败关闭占位，生产 overlay 必须覆盖。
- `AI_MAX_DOCUMENT_CHARS`、`AI_MAX_SEGMENTS_PER_DOCUMENT`、`AI_MAX_OUTPUT_TOKENS_PER_SEGMENT`、文档 token 上限和响应字节上限按获批模型 context、成本和数据分级设置，不得通过截断规避失败。
- Production 不允许关闭 usage metadata 或 provider request ID 要求。
- 网关发送可移植的 `json_schema` 响应格式，但不声明某一家 provider 的 strict dialect。获批准的第三方 provider 负责生成约束；平台随后执行大小、深度、集合、Pydantic 领域 schema、引用和政策校验，任一失败均不进入暂存区。新增或更换 provider 必须用真实协议测试证明结构化输出、usage、request ID、限流和错误行为，不能仅凭“OpenAI-compatible”名称放行。

## 运行行为

每个分段请求带稳定 client request ID；网络、超时、429 和指定 5xx 在网关内有界重试。只接受单个 `finish_reason=stop` choice。拒答、截断、多 choice、缺失 usage/request ID、超大响应和 schema 错误均不会进入暂存区。

普通自然语言分段的模型 schema 不允许 `structure` 事实。只有原文明确标注 `SMILES`、`InChI`、molfile/mol block 或 V2000/V3000 表示时才开放结构候选；平台仍用 RDKit 独立解析、标准化和验证。SDF/MOL 等结构文件应走确定性化学解析链路，不能让模型凭药物名称生成结构。

每个模型运行记录配置/响应模型、system fingerprint、provider/client request ID、输入与响应 SHA-256、token、估算费用和事实 key。引用必须存在于生成该事实的精确输入分段中。重复事实优先保留引用有效的候选，再比较置信度。

`model_gateway_error` 在模型网关完成内部重试后可由 Temporal 按活动策略恢复。`governance_budget_error` 和 `governance_policy_error` 是确定性失败，在 Temporal 边界标记为 non-retryable，防止重复费用。结构权威校验等发布期政策错误会回滚本次候选并写入失败运行，不保留半发布事实。

## 生产验收

发布证据必须来自真实获批模型和真实资料样本，并至少包含：

1. 正常 schema 抽取及 provider usage/request ID 对账。
2. 文档、分段、响应、input/output token 和费用上限分别失败关闭。
3. 文档 prompt injection、跨分段伪引用、拒答、截断和畸形 JSON 不发布。
4. 429、超时和暂时 5xx 的有界恢复；确定性政策错误不重复调用。
5. `ExtractionRun`、`StagedFact`、原文对象、来源版本和最终权威记录可相互追溯。
6. 实际 provider 账单与 `estimated_cost` 的 rate card 抽样核对。

本地 `respx` 契约测试只证明客户端边界，不是上述真实模型验收证据。
