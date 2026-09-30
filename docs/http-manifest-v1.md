# HTTP Manifest v1 数据源协议

`http-manifest-v1` 用于从授权供应商或内部发布服务自动增量入库。它是数据工厂内部连接器协议，不是第三个产品入口；人员仍通过工作台管理来源，Agent 仍只通过 MCP 获取已发布数据。

## 请求

平台对已登记的 manifest URL 执行 `GET`，发送 `Authorization: Bearer <token>`。首次请求没有 cursor；后续请求携带上次完整成功批次返回的 `cursor`。分页请求同时携带相同 cursor 与 `page_token`。

```http
GET /v1/manifest?cursor=opaque-cursor&page_token=opaque-page HTTP/1.1
Authorization: Bearer <secret>
Accept: application/json, application/octet-stream;q=0.9
```

cursor 和 page token 都是供应商定义的不透明字符串，最大 4096 字符。供应商不得要求把 token、签名或凭据写入 manifest URL。

## 响应

```json
{
  "schema_version": "1.0",
  "items": [
    {
      "operation": "upsert",
      "logical_path": "literature/egfr-review.pdf",
      "download_url": "./objects/egfr-review.pdf",
      "file_name": "egfr-review.pdf",
      "size_bytes": 123456,
      "modified_at": "2026-07-17T12:00:00Z",
      "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "next_page_token": null,
  "next_cursor": "opaque-next-cursor"
}
```

- 每页最多 1000 个 item；未知字段会导致整页失败。
- `operation` 为 `upsert` 或 `delete`。`delete` tombstone 只包含 `operation`、`logical_path` 和带时区的 `modified_at`。
- `logical_path` 必须是规范的相对 POSIX 文件路径，不能包含 `..`、反斜杠或重复路径。
- `file_name` 必须等于 `logical_path` 的 basename。
- `modified_at` 必须带时区，`content_sha256` 必须是小写 64 位十六进制。
- HTTP 来源的 `stable_seconds` 必须为 `0`；供应商只能发布已完成、可按 hash 重放的对象。
- 非末页提供 `next_page_token` 且不得提供 `next_cursor`；末页必须提供 `next_cursor`。
- `download_url` 可为相对或绝对 URL，但解析后必须与 manifest 使用完全相同的 scheme、host 和有效 port。

## 提交语义

平台将增量页视为变更集，不会把未出现的历史对象误判为删除；删除必须发送显式 `delete` tombstone。只有在所有 manifest 页和所有纳入范围的对象均完成不可变快照后，平台才应用 tombstone，并原子更新来源 cursor 与 `last_success_at`。解析、AI 治理和发布在后续版本化工作流中执行，不影响供应商快照提交。发现、下载、大小或 hash 校验任一失败时，批次标记为 partial/failed，cursor 保持不变，后续运行必须可重放。

## 安全边界

- 生产仅允许 HTTPS，不跟随 3xx 重定向。
- manifest Origin 必须在部署级 `SOURCE_HTTP_ALLOWED_ORIGINS` 精确白名单内。
- Bearer token 只从 `SOURCE_CREDENTIAL_ENV_ALLOWLIST` 允许的 `env://VARIABLE_NAME` 解析。
- 数据源表、API、日志、错误、发现项和持久化 source URI 都不得包含 token。
- manifest 响应、页数、对象大小和读取时间均有硬上限；对象实际大小与 SHA-256 必须匹配。
- 连接器执行本地单进程速率预算；生产还必须在出口网关和供应商账户配置全局限流、审计与告警。
