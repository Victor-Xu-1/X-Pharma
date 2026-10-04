# 真实公开来源的持续自动入库

软件版本为 X-Pharma v0.1.0。本文描述 ClinicalTrials.gov 和 ChEMBL 目标/机制数据的自动处理，不把公开接口可达、空来源 readiness 或模拟测试称为真实入库，也不代替商业 Production 验收。

## 唯一处理链

来源注册与许可 → Temporal 自然调度 → 有界发现与不可变快照 → ClamAV → 隔离 parser → 确定性/模型治理 → 同一暂存与发布事务 → outbox → OpenSearch → 人员查询。

`DETERMINISTIC_GOVERNANCE_ENABLED=true` 允许已识别、已授权的 ClinicalTrials.gov/ChEMBL 结构化快照独立治理。`AI_GOVERNANCE_ENABLED` 只控制需要模型的抽取；关闭模型不会让官方结构化记录跳过治理。确定性路径仍校验来源、摘要、字段、引用、实体身份和冲突，不调用本地或未批准模型。

来源识别和策略身份由 `governance/source_policy.py` 唯一拥有。适配器、重复处理检查与治理重放使用同一策略摘要。模型配置变化不重复治理确定性官方数据；真正政策变化保留旧运行并创建新的审计运行。

同一原始记录的新确定性版本可以替代自己的旧事实，旧快照与治理历史保留。迟到旧版本不能覆盖已经接受的新版本。该规则只适用于同一来源资产及版本向前推进；跨来源、跨记录、身份和规范化冲突仍进入审核。发布阶段锁定来源记录，并重新读取当前事实，避免并发旧视图覆盖。

## 明确的同步范围

旧 `snapshot` 模式仍只抓取最多 `max_records` 的当前查询窗口。新增 `continuous` 模式把这个值作为单批工作预算，不作为永久总量上限。

- ClinicalTrials.gov：必须指定 `start_date`，按 `LastUpdatePostDate` 冻结日期分区并分页，保存查询绑定的检查点；整个冻结周期完成后才推进覆盖水位。正常更新回看 2 天，每 30 天从配置起点完整复核；可在来源配置中调整分区、回看与复核周期。
- ChEMBL：范围是一个明确的 `target_chembl_id` 的目标/机制记录，不是整个 ChEMBL 数据库。使用升序 `mec_id` keyset 跨批续跑，完整周期结束后的下一次扫描从头复核，因此较早记录的修改也会重新检查。
- 未完成的范围由 scheduler 以 `PUBLIC_SYNC_CATCHUP_INTERVAL_SECONDS`（默认 30 秒）有界续跑；完成后恢复来源正常扫描周期。固定活动 workflow ID 防止同源任务重叠，外部失败继续走有限退避。
- 只有快照登记成功才推进发现检查点；格式、治理和检索投影拥有独立持久化阶段和恢复点。批次异常不跳过对象、不推进游标，不把有限窗口之外记录当作删除。
- 上游接口是可变服务，不承诺跨请求的数据库级一致快照。重叠回看和周期复核减少更新遗漏；异常分页、重复标识、无进展或错误检查点明确失败并进入运营处理，不掩盖为成功。
- 官方 API 响应由共同 HTTP 边界流式读取，检查声明长度和实际字节数后才解析。`SOURCE_HTTP_MAX_API_RESPONSE_BYTES` 默认 32 MiB、硬上限 64 MiB，与来源工作预算取更小上限；超限关闭响应并失败，不先把整个响应放入内存，也不截断成成功记录。

来源 readiness 与工作台区分“等待调度”“分批同步中”“本周期完成”以及仅限配置查询的完成日期。浏览器不读取 opaque page token、对象 URI 或凭据。

## 注册与运行

先创建自己的活跃组织并确认来源条款、数据集许可与展示渠道。以下参数是示例，部署时必须明确替换组织、查询、范围和靶点，不使用隐式的默认科研主题：

```bash
docker compose exec worker pharma-ingest register-clinicaltrials-gov \
  --tenant-slug YOUR_ORGANIZATION \
  --query-term 'YOUR_APPROVED_QUERY' \
  --sync-mode continuous --start-date 2026-01-01 \
  --max-records 50 --page-size 50 --scan-interval-seconds 86400

docker compose exec worker pharma-ingest register-chembl \
  --tenant-slug YOUR_ORGANIZATION \
  --target-chembl-id YOUR_CHEMBL_TARGET_ID \
  --sync-mode continuous --max-records 25 --page-size 25 \
  --scan-interval-seconds 86400
```

注册复用已有数据集时会检查活跃状态和当前许可；配置变动写审计，重复相同注册不新增来源或审计。查询/历史范围在已经取得资产后变动需要受治理迁移，不能把旧检查点用于另一个查询。预算和复核策略等操作参数可以单独调整并安全重启检查点。

不必逐文件操作或调用 `once`：scheduler 会自然启动采集。运营人员在同一个内部数据工厂查看运行、版本、异常、重放及发布状态；研究工作台只展示已发布且有许可的数据。

## 数据与模型的独立边界

ClinicalTrials.gov 注册记录不是对试验安全性、科学性或疗效的认可；不从自由文本猜测靶点或生成疗效结论。ChEMBL 目标/机制中的阶段、结构和监管信息只按已有明确字段能力处理，不宣称同步了所有生物活性和化学结构。

PubMed 仍为有界元数据快照，默认不含摘要，不把标题索引称为完整文献知识抽取。全文/摘要再利用、商业数据库、付费模型、资料外发、OCR 与语义检索各自需要真实授权和配置。第一方 Apache-2.0 不替代第三方数据许可；ChEMBL 数据保留 CC BY-SA 3.0，来源归属与限制随记录交付。

## 验收和恢复

只针对改动的连接器、治理、来源写入/重放、scheduler 和页面执行定向回归；原 GitHub 必需 CI 不减少。真实证明必须来自自然调度、真实来源、真实 PostgreSQL/ClamAV/parser/OpenSearch 和正常人员 API/Chrome，并包含原始 SHA-256、版本、策略、已发布记录与来源引用对账。

单元协议夹具、状态探测、只有截图或旧版本记录都不代替当前数据链路证据。公开文档只说明可复现实现；本机查询参数、组织、数据和完整运行证明保留在外部私有证据目录，不进入 Git。

升级前保留权威备份、私有配置和上一镜像。应用回滚不执行数据库 downgrade，也不删除已经采集的原始版本；检索是可重建投影。更换 source query 或清除历史数据需要单独的治理操作，不用于通过验收。

官方参考：[ClinicalTrials.gov 使用条款](https://clinicaltrials.gov/about-site/terms-conditions)、[ChEMBL 数据与许可](https://www.ebi.ac.uk/chembl/)、[NCBI 使用政策](https://www.ncbi.nlm.nih.gov/home/about/policies/)。
