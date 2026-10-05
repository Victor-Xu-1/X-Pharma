# Design QA: X-Pharma 工作台

## Current iteration: comprehensive preview fidelity

The user explicitly requested a closer, page-by-page match after the earlier
lightweight adaptation. The earlier acceptance does not waive this iteration's
typography, spacing, density or layout findings.

Source truth: the three unchanged `AI-*-design-target.png` references under
`E:\WSL\management\x-pharma\deliverables\design-fidelity\before`.
Fresh baseline: exact main `0c12132967df7a0e29a84eb072e6b46ae371fab9`,
28 actual screens at each of four CSS viewports. Desktop comparison is
1440x1024/DPR1; source 1487x1058 is proportionally normalized to width1440,
never stretched. The combined `comparison-{explorer,company,factory}.png`
and corresponding `*-header.png` were opened and inspected together.

Initial findings (closed by the post-fix evidence below):

- P1 typography: 24px research title overrides shared26px; internal descendant
  and query blanket12px rules compress readable body and controls far below
  the concepts. Fix one 32/26px title hierarchy and 16/14/12px text scale.
- P2 company: 46px identity, unbounded single-line title truncation, and no
  source-summary surface. Fix shared identity, wrapping and 20px panel inset;
  preserve the correct generic organization icon rather than the concept's
  inaccurate X-Pharma company mark.
- P2 explorer: recent-research and instruction occupy competing rows; object
  controls are too small and crowded. Unify the instruction's ownership and
  let genuine type controls wrap, retaining all counts/query semantics.
- P2 target: six metrics in five columns and four cards in three columns
  leave orphaned rows. Use responsive auto-fit within existing sections.
- P2 factory: tight stage nodes, collapsed inter-panel rhythm and four-column
  projection details. Increase genuine icon slots and readable spacing;
  reflow actual status fields without manufacturing concept-only timestamps.

Iteration1 (`4be11414f6d3d56585625541345995bde998cc21`) captured all112
screens successfully; combined/focused reference comparisons were inspected.
It resolved the initial desktop hierarchy and wrapping, but revealed P2
mobile company title compression and a tablet3+1 card row. Iteration2 removes
the redundant second entity-type control rail, retains all counts in the
original primary controls, and reflows mobile record status beneath text.
The responsive selectors now target the actual `.badge` component; obsolete
`.status-badge` selectors were corrected rather than retained as dead paths.
The private wide-screen check was corrected: a complete untruncated single
line at1920px is valid, while narrower views must wrap. Tablet checks now
require2+2 card occupancy, not merely two rows (which could hide3+1).

Required fidelity surfaces: fonts and wrapping, layout rhythm, semantic
color tokens, original asset sharpness/provenance, and factual copy are all
in scope. Existing permissions, public-data gaps, table densities, query
state and progressive disclosures must remain functional.

### Post-fix comparison and focused verification

Final UI candidate `d9031a11f9a1504d9dc2b8681af85459fe007182`:
`E:\WSL\management\x-pharma\deliverables\design-fidelity\iteration-3`.
All28 routes/entrances at1440x1024,1920x1080,1024x768 and390x844 rendered
successfully (112 actual PNGs, no page errors or document horizontal overflow).
The generic entity entry correctly resolves to its typed target dossier; it
is not counted as a distinct invented product screen. Mobile raster1024x2216
uses the original DPR2.625; desktop/tablet use DPR1.

The three combined full views and focused headers were reopened after the
fixes. Company/mobile detail and four-viewport dossier sheets were inspected:
long titles now use the available reading width, status appears below the
title on mobile, and tablet cards occupy2+2 rather than3+1. Original company
trial/provenance actions remain real and accessible.

The new focused Chrome registration passed4/4 (24.4s): actual32/26px title,
14px standard rows, one research instruction, non-scrolling type controls,
recent-research disclosure, full title visibility, real trial navigation,
responsive card occupancy, dossier tab actions and source-dialog open/cancel.
All-page capture passed4/4 (35.3s). Neither registration executes a global
manual suite or creates an account/source/scientific fact.

Five fidelity surfaces reviewed:

- Fonts: existing offline sans-serif family preserved;32/26px page titles,
  30px identity,16px body,14px controls/standard rows,12px metadata/compact
  rows. No replacement font download; wrapping has actual browser evidence.
- Rhythm:32px desktop gutter, consistent heading/navigation space,20px
  source panel inset,72px identity slots,48px factory icons and20px section
  gaps. Responsive rails/lists remain scrollable in their own containers.
- Colors: unchanged restrained teal/white/neutral authority; warning/danger
  and healthy status retain independent semantics and AA contrast contracts.
- Assets: original orange logo and derived icons unchanged,48px display
  remains sharp with128px asset; library domain icons are not fake corporate
  logos. No generated figure/copy was rasterized into interactive UI.
- Copy: one research instruction, corrected stacked-mobile knowledge copy,
  actual registry titles/counts/status and explicit data-coverage caveats.

Expected functional differences from the concepts: the real explorer retains
selection, safe export, sort/density/column tools, target handoff and full
catalogue (not six illustrative records); factory keeps authorized source
cards with scan/edit/pause/checkpoint operations. Actual source fields and
query time replace illustrative dates; the generic organization icon avoids
false X-Pharma affiliation. These are not unresolved visual regressions.
No actionableP0/P1/P2 remains in the compared states. Screenshot evidence
does not imply scientific completeness or global WCAG/product certification.

Release gate history: the first controlled12-registration reference update
had9 passes and3 loading timeouts (5.0m). Failure images show pending company/
facet reads, not accepted blank states. Trace includes7.15s pipeline reads,
5.90s identity reads and18.54s telemetry; these do not establish a product
performance pass. Its original cleanup completed. The subsequent six-case
single-worker rerun was interrupted during the shared WSL outage; neither
that run nor its partial local PNG updates is counted as acceptance.

Independent [refresh run37324706734](https://github.com/Victor-Xu-1/X-Pharma/actions/runs/37324706734)
on exactd903 completed all six mandatory gates. Original Chrome registration
passed144/144 (22.5m) for the explicit update, then144/144 (22.2m) strictly
readonly; the latter reports snapshots_updated=false and all temporary
fixture counts zero. All20 generated PNGs and their original-generator
manifest were downloaded, hash-verified and visually reviewed. They replace
the incomplete local update, which remains in the external evidence store.
Masks, budgets, browser/font profile and0.001 pixel tolerance are unchanged.

Once native access returned, bounded recovery found239 entities and five
accounts belonging to this task's isolated test organization. An ingestion
run referencing its temporary evidence source exposed an existing foreign-key
cleanup omission; the transaction rolled back. Evidence and replay sources
now share one selected-ID cleanup path, removing ingestion/version children
before their parents. The new regression fails with the old SQL; all11
related cleanup/runtime checks, scoped lint and strict typing pass. Actual
PostgreSQL recovery removed only these fixtures, restored authoritative
search/readiness and preserved the preview organization's2698 entities and
910 source versions. Verified pre-recovery/pre-change backups remain.

Offline gallery Chrome checks retain the initial desktop pass and mobile
114/115 image-load failure; the bounded mobile-only rerun passes with all115
images, original timeout and no external requests. These are artifact checks,
not product performance certification. Mandatory ordinary PR/main CI and
exact-main deployment remain separate release evidence from this visual pass.

final result: passed

## Previous completed iteration (historical evidence)

## 2026-10-05: clean biomedical workbench adaptation

Visual source: native Image Generation explorer, company and factory concepts.
The backend model identifier is not exposed by the tool. This is a restrained
adaptation of the existing product, not a pixel-perfect clone of generated
copy, invented data or inaccurate brand marks. The existing design system
remains the single implementation authority.

Local evidence root (private runtime captures are not committed):
`E:\WSL\management\x-pharma\deliverables\biomedical-visual-preview`.
Source images: `AI-explorer-design-target.png`, `AI-company-design-target.png`,
`AI-factory-design-target.png`, each 1487×1058 pixels. Implementation:
`real-pages/desktop-1440/research-explorer.png`, `research-company.png` and
`internal-factory.png`, each 1440×1024 at CSS viewport 1440×1024 and DPR 1,
from exact candidate `c7c42fddd19647f0489b5c0f415c0f0d8bc8e5d5`.
The concepts are proportionally width-normalized to 1440 pixels; the remaining
one-pixel height difference is retained rather than stretched away.

Full comparisons place both artifacts in one image:
`comparison-explorer.png`, `comparison-company.png`, `comparison-factory.png`.
Focused comparisons cover navigation, title/toolbar, company identity/tabs and
factory status/stages: `comparison-explorer-navigation.png` and the three
`comparison-*-header.png` images. These images were opened and visually
compared; filenames or passing compilation were not used as visual evidence.

### Findings and comparison history

- **P2, resolved: mobile knowledge list overlapped the document empty state.**
  Initial real capture `knowledge-mobile-before-fix.png` showed list rows
  extending past the index's 300px bound into the document. The list retained
  its 550px bound. The mobile height limit now belongs to the scrollable list;
  the parent follows normal document flow. Governance list bounds and parent
  borders remain. `comparison-knowledge-mobile.png` compares initial and fixed
  states at the same empty selection, 500 records and CSS 390×844 viewport.
  Both are 1024×2216 raster pixels at the original Pixel 7 DPR 2.625; no density
  mismatch was treated as a defect. The real-browser containment test failed
  before the fix and passed after it, including keyboard focus/visibility for
  record 21. The initial-state post-fix image and the keyboard-focused image
  were separately inspected. No other actionable P0/P1/P2 finding remains.
- **Accepted adaptation: readable dense-workbench typography.** Generated
  text is larger and more approximate than its prompt. The product retains
  its system/Noto Sans CJK font stack, readable 12px metadata, 13–14px controls,
  26px page heading and existing table density. No remote or proprietary font
  is added. Full-size images and focused crops were checked for alignment,
  optical weight, wrapping and truncation rather than judged only as thumbnails.
- **Accepted adaptation: actual data and professional controls.** The explorer
  keeps real relationship matching, selection, sorting and professional
  filters rather than the concept's illustrative six-row table. Company
  registration provenance and actual trial links remain; the building icon
  is intentionally retained instead of the concept's incorrect product logo
  as a company logo. Factory sources, statuses and authorization notices remain
  real and can change over time. Empty domains are not filled with invented
  scientific, commercial, patent or licensed coverage.

### Required fidelity surfaces

- Fonts/typography: shared system stack, compact optical weights and hierarchy
  are coherent across the 24 views and account forms; intentional density
  differences are documented above. Existing full-title/detail affordances
  remain for compact result text.
- Spacing/layout: desktop navigation is 224px, headings use consistent 28px
  top spacing and 24px separation. Existing mobile drawer, tab scrolling,
  labelled horizontal data-table scrolling and pane reflow are retained.
  The one observed overlapping pane was fixed and compared again.
- Colors/tokens: white canvas, near-white navigation, subdued teal active
  states and charcoal primary actions match the selected direction. Focus and
  emphasis use `#08656d`; success, warning and error semantics are unchanged.
  The component contrast contracts and original WCAG routes own accessibility
  acceptance; no contrast or pixel threshold was reduced.
- Image/asset fidelity: the supplied orange logo and favicon are unchanged
  repository assets, not generated replacements. Icons remain the existing
  library. No CSS art, handcrafted SVG decoration, DNA background, screenshot
  renderer or concept bitmap is introduced into the application.
- Copy/content: original Chinese workflows and domain-specific caveats remain.
  Concept captions, illustrative dates and generated assertions were not
  copied into the application. The preview gallery explicitly distinguishes
  three concepts from 112 actual page captures and does not claim a model ID.

### Implemented checks and remaining acceptance boundaries

- Final shared design, brand, controls, navigation and knowledge selection:
  61/61 tests across eight related files passed. Visual manifest/profile
  contracts passed 22/22 and e2e TypeScript passed. Earlier overlapping runs
  are not summed as independent coverage. Production assets remain bounded:
  research JS473307, internal JS360666, CSS196589 bytes.
- Fixed candidate's real page capture registrations passed 4/4 in 1.7 minutes:
  28 pages at 1440×1024, 1920×1080, 1024×768 and 390×844; zero page errors or
  document horizontal overflow. This is a page-render gate, not exhaustive
  business or scientific acceptance.
- Original 12 accessibility/17-stage navigation registrations passed during
  explicit reference review. A later local readonly attempt was interrupted
  after WSL startup failures and health-request timeouts, not counted as a
  pass. Its bounded EXIT cleanup restored the authoritative search projection
  and readiness. Mandatory automatic CI owns the remaining strict readonly
  comparison without snapshot updates. Readonly references, CI, normal merge
  and exact-main deployment are independent release gates. No manual global
  suite was run and no gate was relaxed.

Implementation checklist: shared tokens/hierarchy applied; original branding
preserved; all page surfaces captured; mobile overlap fixed; full and focused
comparisons completed; real keyboard access verified. Professional-user UAT,
assistive-technology review, paid-provider validation and production RUM are
not established by these visual previews.

final result: passed

## 历史私有平台记录

> 本文保留旧私有平台 v1.x 的历史检查记录，不是当前 X-Pharma 的验收报告。
> 旧深色侧栏与浅蓝视觉结论已由用户的新要求取代；当前权威为
> [design-system.md](design-system.md)。实际新主题证据以本次运行和精确候选为准。

## 2026-08-03 当前工作台增量：规范身份标识可见性

- 外部全局检索结果表和快速实体详情现在复用 API 已返回的 `identity_identifiers`；当 `external_ids` 为空时，结果表显示规范命名空间和值，详情显示可信命名空间和来源文档绑定状态，不再用空白单元格掩盖真实数据缺口。
- `ExplorerView` 定向回归新增身份标识场景；前端单 worker 全量 `60 files / 363 tests`、TypeScript、生产构建和 Biome 通过。真实 Google Chrome 复核 `1600x775` 与 `390x844`，检索结果、详情空状态和移动端无横向溢出通过。
- 当前真实租户的 EGFR 结果没有 `external_ids` 或规范身份标识，页面明确显示缺口；本批不伪造来源，也不关闭正式来源绑定、数据授权、生产 RUM、人工辅助技术、操作系统缩放或专业用户 UAT。

## 2026-08-03 v1.9.100：化学检索保存与受控回放

- 化学检索保存为服务端版本化 `chemistry_search` 保存检索，浏览器 URL 只携带经授权的保存检索 UUID；刷新通过真实保存检索 API 恢复模式、阈值、上限和结构条件并重新执行查询，结构原文不进入 URL、保存摘要或监控摘要。结构事件匹配尚未实现，因此监控中心明确不提供化学保存检索订阅。
- `ChemistryView` 定向回归 `5/5`，`MonitoringView` `15/15`，路由 `21/21`，后端监控/OpenAPI `21/21`，前端全量 `362/362`；Biome、TypeScript、OpenAPI、生产构建和 Ruff 通过。
- 真实 Google Chrome `151.0.7922.71` 隔离真实 PostgreSQL/RDKit 运行线中，化学保存/刷新/回放四视口每次 `4/4` 通过；完整套件两次均为 `123/124`，第一次为既有平板密集结果 INP `408ms > 200ms`，第二次为既有桌面管线药物实体候选组合框超时。全球性能/稳定性门禁保持 partial，本批不构成 Commercial Production 批准。

## 2026-08-03 v1.9.99：结构检索实体 ID 连续性

- 结构检索结果的“查看实体”入口现在传递服务端返回的稳定 `entity_id`，由研究工作台既有实体路由恢复正确的药物/靶点/公司/疾病专业档案；不再用显示名称触发可能歧义的全局搜索。
- 真实 Google Chrome `151.0.7922.71` 四视口完整套件 `124/124`，各视口 `31/31`；INP `16–32ms`、LCP `84–204ms`、CLS `0`，320/360/720 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/chemistry-entity-id-v1.9.99-final.json`，SHA-256 `d122a4ad75686b8aa9feb57e9d5ad1dfa8f5b1d196c5b9aac767a03f8b88ec2c`；临时账号、实体、结构夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- `ChemistryView` 定向回归 `3/3`；前端全量 `358/358`，Biome、TypeScript、生产构建和构建边界检查通过。本批关闭结构检索结果到实体档案的代码级 ID 连续性缺口，不关闭正式数据授权、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT。

## 2026-08-03 v1.9.98：档案交易分区实体链接

- 本批将通用实体、公司和疾病档案的交易分区接入真实 `DealSearchItemRead`，补充交易名称、方向、参与方、资产、阶段和金额，并按服务端 `entity_type` 进入专业档案；组件、API、生成客户端和真实跨域导航均已验证。
- 真实 Google Chrome `151.0.7922.71` 四视口完整套件 `124/124`，各视口 `31/31`；INP `16–32ms`、LCP `112–820ms`、CLS `0`，320/360/720 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/entity-dossier-deal-links-v1.9.98-final.json`，SHA-256 `91b103ef9f8247e11bd39923561177fcec93c29fb1285f0e83ca801368ce1d96`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 全量 `make check` 通过：后端 `1152 selected / 35 deselected`、前端 `358/358`，并通过 Ruff、Mypy、OpenAPI、Biome、TypeScript、生产构建、Compose、Kubernetes 和运营契约门禁。本批不关闭 C-02、C-05、C-06 或 C-07，也不等同于 Commercial Production 批准。

## 2026-08-02 药物档案关系/交易实体直达专业档案及 v1.9.97

- 药物专业档案中的已治理关系、获批适应症、交易参与方、交易资产和权益持有人现在依据服务端真实 `entity_type` 进入靶点、疾病、公司或药物专业档案；权益持有人遵循后端组织类型契约，未知类型继续使用通用回退。
- `DrugView` 定向回归 `8/8`；新增真实 e2e 交易资产回跳断言，Biome、TypeScript、生产 API 镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `24–32ms`、LCP `84–124ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/drug-dossier-links-v1.9.97-final.json`，SHA-256 `a06750c32ec2a550ba2782c59b78e3f79932fa947c5b2ac854e1cf29d93cf642`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级药物档案关系与交易实体类型化导航缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 交易/公司/资产实体直达专业档案及 v1.9.96

- 交易结果、参与方、资产和权益持有人现在依据真实 `entity_type` 进入公司、药物、靶点或疾病专业档案；权益持有人遵循后端组织类型契约。交易结果“档案”图标与交易标题进入交易专业档案，保留 `deal` 深链接；缺少阶段细节时使用类型化资产候选回退。
- `DealsView` 交易导航定向回归 `9/9`；Biome、TypeScript、生产 API 镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `24ms`、LCP `88–112ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/deal-specialized-links-v1.9.96-links-final.json`，SHA-256 `5d610e17b4ddc863819117d3975fa0807e39d3ed06c12f66a4b10a7bbd24490b`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级交易域实体类型化和交易专业详情入口缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 专利结果实体直达专业档案及 v1.9.95

- 专利专业结果的关联实体现在依据真实 `entity_type`，将药物、靶点、疾病和研发机构直达对应专业档案；结果表“档案”图标与专利族标题统一进入专利族专业档案，不再落到通用实体页。
- `PatentsView` 与监管/新闻/流行病学/疾病/共享实体导航定向回归 `40/40`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–32ms`、LCP `92–164ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/patent-specialized-links-v1.9.95-final.json`，SHA-256 `98ecd796d2d3304cddb0852c90d4928a88baac3f966262fead8caa7d4a25686a`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级专利结果实体类型化和专利族详情入口缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 监管结果实体直达专业档案及 v1.9.94

- 监管专业结果表和事件详情现在依据真实实体类型，将主题实体、适应症及申办方直达对应专业档案；缺少类型信息的实体继续使用通用回退。
- `RegulatoryView` 与新闻/流行病学/疾病/共享实体导航定向回归 `34/34`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `24–48ms`、LCP `92–136ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/regulatory-specialized-links-v1.9.94-final.json`，SHA-256 `a478edc7c1228768e098e120f2255770901afd43925caa61c3ff123ffd06abfb`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级监管结果实体类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 新闻/会议结果实体直达专业档案及 v1.9.93

- 新闻/会议专业结果的列表、研究发布时间线和详情抽屉现在依据真实实体类型，将发布机构及关联药物、靶点、疾病和研发机构直达对应专业档案；缺少类型信息的实体继续使用通用回退。
- `NewsView` 与疾病/流行病学/共享实体导航定向回归 `25/25`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–32ms`、LCP `72–160ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/news-specialized-links-v1.9.93-final.json`，SHA-256 `a8191e05752bff8c26778533270cf5fb493955b7835c0f66534358db8365dbee`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级新闻/会议结果实体类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 流行病学结果实体直达专业档案及 v1.9.92

- 流行病学专业结果表中的疾病和发布机构现在依据真实实体类型直达对应专业档案；已知疾病进入疾病档案，发布机构按服务端 `entity_type` 导航，缺少类型信息的实体继续使用通用回退。
- `EpidemiologyView` 定向回归与疾病/共享实体导航回归 `19/19`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–56ms`、LCP `92–208ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/epidemiology-specialized-links-v1.9.92-final.json`，SHA-256 `f02228a085af170ef090ee4b2601a468dd40c4a7a22b1780bcea33ed195d8636`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级流行病学结果实体类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 疾病档案实体直达专业档案及 v1.9.91

- 疾病专业档案概览、流行病学观测、研发格局、靶点证据和关系网络现在依据真实实体类型，将药物、靶点、疾病和研发机构直达对应专业档案；流行病学发布机构按真实 `publisher_entity.entity_type` 解析，缺少类型信息的实体继续使用通用回退。
- `DiseaseView` 与共享实体导航定向回归 `13/13`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `32–40ms`、LCP `96–144ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/disease-specialized-links-v1.9.91-final.json`，SHA-256 `bcebaa1d429deb490949a91a405a4008aab9cfca5d5771f2ff602e2da6965fa7`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级疾病档案类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 公司档案实体直达专业档案及 v1.9.90

- 公司专业档案概览、研发管线、公司时间线和关联网络现在依据真实实体类型，将药物、靶点、疾病和研发机构直达对应专业档案；共享管线表补齐靶点列，缺少类型信息的实体继续使用通用回退。
- 公司、共享实体和疾病档案定向回归 `13/13`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `32–40ms`、LCP `100–124ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/company-specialized-links-v1.9.90-final.json`，SHA-256 `0a26468a79e5575d8fae295c551efbb2860f02c640ff9caf575c09ed0346ac53`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级公司档案类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 靶点档案实体直达专业档案及 v1.9.89

- 靶点档案的实体关系、转化证据和竞品管线现在依据真实 `entity_type` 或固定业务字段，将药物、疾病、靶点和研发机构直达对应专业档案；化合物活性记录因当前类型契约不足继续使用通用实体入口。
- `TargetView` 定向回归 `7/7`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、前端全量 `357/357`，OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `24–40ms`、LCP `80–180ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/target-specialized-links-v1.9.89-final.json`，SHA-256 `873e19a789de0878beef750c82f686eec65ad563db92591ae2f6c011b2c6e73f`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级靶点档案类型化跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 药物档案实体直达专业档案及 v1.9.88

- 药物概览中的靶点、适应症和研发机构，研发管线中的疾病、靶点和机构，以及临床结果中的角色药物/靶点，现在依据真实 `entity_type` 或固定业务语义直接进入对应专业档案；缺少充分类型信息的交易、监管和其他关联继续使用通用实体兜底。
- `DrugView` 定向回归 `7/7`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–40ms`、LCP `80–168ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/drug-specialized-links-v1.9.88-final.json`，SHA-256 `adb0ede3ee11b5bf0a4eef518cf2b9cf13d305480dfc31661336177ec1151b74`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级药物档案跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 临床试验实体直达专业档案及 v1.9.87

- 临床试验列表的规范药物/靶点角色链接、关联实体链接，以及试验详情概览中的相同链接，现在依据真实 `entity_type` 直接进入药物、靶点、疾病或公司专业档案；临床试验、专利、交易等其他类型仍走通用实体兜底。
- `TrialsView` 定向回归 `5/5`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–48ms`、LCP `76–156ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/trial-specialized-links-v1.9.87-final.json`，SHA-256 `4ceff4e1845eb524b83281b1160a642f0ab2274463ddf3d5f658896a07563cea`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级临床试验实体直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 管线结果直达专业档案及 v1.9.86

- `PipelineView` 的管线表格与 `PipelineLandscape` 的目标、疾病和研发机构关系现在分别接收类型化打开回调；已知实体直接进入 `view=target`、`view=disease` 或 `view=company`，未知类型仍由通用实体回调兜底，避免先请求通用实体再重定向。
- 组件定向回归 `PipelineView` `8/8`；Biome、TypeScript、生产镜像构建和全量 `make check` 通过，后端 `1151 passed / 35 deselected`、覆盖率 `84.57%`，前端全量测试/类型/构建、OpenAPI、Compose、Kubernetes 和运营契约通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–104ms`、LCP `76–200ms`、CLS `0`，320 CSS px 重排和视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/pipeline-specialized-links-v1.9.86-final.json`，SHA-256 `4b31843a210369743ea92093e3d48349e72433832948d6d49c1b7e63996d5876`；临时账号、实体、化学/活动/治理/入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批关闭代码级管线跨域直达缺口，不等于正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02、C-05、C-06、C-07 继续保持未关闭。

## 2026-08-02 密集结果表错误状态语义及 v1.9.85

- `VirtualDataTable` 的视图设置同步失败和保存失败现在统一使用 `role="alert"`，与公共查询错误契约一致；原有重试和恢复路径保持不变。定向组件回归 `7/7`。
- 镜像 TypeScript 构建和 `make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–48ms`、LCP `104–136ms`、CLS `0`，视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/table-error-semantics-v1.9.85-final.json`，SHA-256 `8acd61173981efd115f5ab58653704eb6bc0e1b51785091a85d9a0981fddb918`；临时账号、实体、化学/活动/治理/入库夹具均清理为 `0`。
- 该批只收束密集结果表的错误播报语义，不等于目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术、操作系统缩放或专业用户 UAT；对应体验门禁仍保持 `partial`。

## 2026-08-02 管线与交易全景空态语义及 v1.9.84

- `PipelineLandscape` 与 `DealLandscape` 的真实空维度状态现在统一使用 `role="status"`、`aria-live="polite"` 和 `aria-atomic="true"`；按需图表加载态也可被辅助技术播报。新增定向组件回归 `2/2`。
- 镜像 TypeScript 构建和 `make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–32ms`、LCP `76–116ms`、CLS `0–0.00245`，视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/landscape-state-v1.9.84-final.json`，SHA-256 `bea2f33e61942d3fc1b17cd3ed3eebfdcbf0c4b04fe61ef540ddb76f27172103`；临时账号、实体、化学/活动/治理/入库夹具均清理为 `0`。
- 该批只收束管线和交易统计分区的真实状态语义，不等于目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术、操作系统缩放或专业用户 UAT；对应体验门禁仍保持 `partial`。

## 2026-08-02 统计全景空态与加载态语义及 v1.9.83

- `DomainLandscape` 与 `ClinicalTrialLandscape` 的真实空结果状态现在统一使用 `role="status"`、`aria-live="polite"` 和 `aria-atomic="true"`；按需图表加载态也可被辅助技术播报。新增定向组件回归 `3/3`。
- `make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端全量测试/类型/构建、Compose、Kubernetes 和运营契约均通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–40ms`、LCP `68–124ms`、CLS `0`，视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/landscape-state-v1.9.83-final.json`，SHA-256 `9a6d1c51589439a03a4013a279e3357b95442bf75b3bd29b187ce391fc3623b6`；临时账号、实体、化学/活动/治理/入库夹具均清理为 `0`。
- 该批只收束统计分区的真实状态语义，不等于目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术、操作系统缩放或专业用户 UAT；对应体验门禁仍保持 `partial`。

## 2026-08-02 状态可访问性、密集操作与 v1.9.82

- 空状态统一使用 `role="status"`、`aria-live="polite"` 和 `aria-atomic="true"`；侧栏当前页使用 `aria-current="page"`，SPA 视图切换将焦点移动到新的页面标题。`ProfessionalQueryState`、`WorkspaceShell` 与 `CollectionsView` 定向回归 `16/16`。
- `ResearchWorkspace.navigate` 对同一工作域内的 URL 状态提交同步更新，跨页面导航仍交给 React transition；真实比较列表复选框在四个视口中完成真实勾选、URL 回写、刷新恢复和矩阵展示。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–24ms`、LCP `84–100ms`、CLS `0`，视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/accessibility-state-v1.9.82-final2.json`，SHA-256 `8158aa20508ef04e0e6c0aa3c4438ee38f1b3b7fe17ad96e8e6f0a225da5fd3d`；临时账号、实体、化学/活动/治理/入库夹具均清理为 `0`。
- 该批只补强本地状态播报、路由焦点和密集结果操作，不等于目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术、操作系统缩放或专业用户 UAT；对应体验门禁仍保持 `partial`。

## 2026-08-02 路由 transition 与真实性能门禁及 v1.9.81

- `ResearchWorkspace.navigate` 将搜索、分页、排序和跨域导航的非紧急状态更新交给 React transition；URL、刷新、分享和浏览器历史保持原有语义，避免整个研究工作台在交互事件内同步重渲染。
- `ExplorerView` 组件回归 `28/28`；`make check` 后端 `1151/1151`、覆盖率 `84.56%`、OpenAPI 352 文件、前端类型/构建和运行契约均通过。
- 真实 Google Chrome `151.0.7922.71` 固定隔离端口全量四视口 `124/124`，各 `31/31`；INP `16–40ms`、LCP `92–128ms`、CLS `0`，视觉回归通过。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/research-transition-v1.9.81-chrome.json`，SHA-256 `7E1675FF576B98F81D42B827FC2E842542C027EE2379A31A4C0E73986EAC2B8A`；临时账号、实体、化学/活动/治理/入库夹具均清理为 `0`。
- 该批关闭本地受控导航性能失败，但不等于目标环境生产 RUM P75、批准负载、正式授权数据、人工辅助技术、操作系统缩放或专业用户 UAT；对应体验门禁继续保持 `partial`。

## 2026-08-02 监控子页 URL 与历史连续性及 v1.9.80

- 监控页的提醒中心、监控主题和已保存检索统一使用 `monitor_tab` URL 状态；点击写入浏览器历史，刷新、分享和后退恢复同一子视图，非法值回到提醒中心。
- 真实 Google Chrome `151.0.7922.71` 专项四视口 `4/4`、失败 `0`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/monitoring-route-v1.9.80-chrome-focused.json`，SHA-256 `AD23A1C68533CF18093CF5BFCAE9BDED0FDCC59D1FA20BD8FF5F2AAA8F6E693D`。临时账号和实体均清理为 `0`，未更新视觉快照。
- `make check` 后端 `1151/1151`、前端 `350/350`、类型/构建/契约门禁通过；全量 Chrome 最近一次 `123/124`，唯一失败为桌面主导航 INP `224ms > 200ms`，因此性能体验门禁仍未闭合。
- 该批证明本地真实 API 路由连续性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-06/C-07 继续未关闭。

## 2026-08-02 监控主题研究连续性与可恢复错误及 v1.9.79

- 监控主题表复用已保存检索的受控条件摘要，人员无需离开监控中心即可识别主题绑定的实体、枚举、文本、日期和分析口径。
- 已有监控数据发生操作失败时，页面保留旧提醒/主题/检索数据，在原上下文显示错误并提供明确 `重试`；重试成功后错误提示消失，未引入静态或缓存事实。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/monitoring-context-v1.9.79-chrome-20260802-final1.json`，SHA-256 `feb1ffb063ad656a9ab077ee1bd06113457cabdfb8a4405cd3df69aa2d86ee19`。未更新快照，临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批只证明本地候选的真实监控上下文展示和可恢复错误交互，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 保存专业检索组合条件可扫描性及 v1.9.78

- 监控中心的已保存检索现在显示受控条件摘要：实体条件只显示已选状态/数量，枚举条件显示已设置，文本与日期保留原值；统计维度、范围、阶段口径和聚合口径不再被隐藏在查询 JSON 中。
- 条件摘要只读取保存查询中的白名单字段，不从实体名称、结果行或浏览器本地状态推断事实，也不改变保存 JSON、监控匹配或回放 URL。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/saved-search-conditions-v1.9.78-chrome-20260802-final1.json`，SHA-256 `958a4d216b4d26a03c739076ad66e0d07881cd3a4a9a391f542666f0152e69b0`。未更新快照，临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批只证明本地候选的真实保存检索摘要、展示和回放兼容性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 专业保存检索展示形态连续性及 v1.9.77

- 监控中心现在对所有专业已保存检索统一显示 `列表`、`统计图`、`统计表` 或资讯 `时间线`，标签来自受控保存查询合同，不在浏览器生成事实。
- 真实管线统计检索和资讯研究时间线检索均通过真实 API/数据库保存并从监控中心回放；原有全局实体统计保存/回放路径保持稳定。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/saved-search-view-labels-v1.9.77-chrome-20260802-final1.json`，SHA-256 `691c1e18916ded6d4ad3c83f76bcb37bd696d434bc9cf94de1a1a00bebc5eeb5`。未更新快照，临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批只证明本地候选的真实保存检索展示与回放兼容性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 已保存检索摘要可扫描性及 v1.9.76

- 监控中心的全局实体保存检索将 `target`、`organization` 等受控实体类型显示为中文标签，并按固定顺序合并多类型条件；保存查询的实体 ID、过滤条件和回放合同不变。
- 保存检索的展示列会明确标记 `列表`、`统计图` 或 `统计表`，真实统计视图仍可从监控中心运行并恢复稳定 URL；该层只改善用户识别，不在浏览器生成事实或查询结果。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-saved-labels-v1.9.76-chrome-20260802-final2.json`，SHA-256 `abe737f113d50cb03e60ad34fe1ea6cf141a58f7213886673071fe46fc69d48d`。未更新快照，临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批只证明本地候选的真实保存检索展示和回放兼容性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 全局检索统计视图保存与回放及 v1.9.75

- 全局实体检索保存合同现在携带非默认统计展示状态：`display_mode=landscape` 与 `analysis_view=table` 进入版本化 `EntitySearchQuery`，监控变更匹配只读取事实筛选条件，不把展示状态误当作数据条件。
- 真实人员从统计视图保存检索后，在监控中心运行该检索，页面恢复统计区域、表格分析、稳定 `display=landscape&analysis_view=table` URL，并继续通过真实 facet 回筛；覆盖 API、PostgreSQL 持久化、生成客户端和真实 Chrome。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-saved-view-v1.9.75-chrome-20260802-final5.json`，SHA-256 `5e96fce651fbb6fd479440ecae2f6f744c76be8a29e5605245c72fba460e0186`。未更新快照，临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，`credentials_recorded=false`、`production_claim=false`。
- 该批只证明本地候选的真实保存/回放连续性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 全局检索统计与结果视图连续性及 v1.9.74

- 全局实体检索现在直接使用真实搜索响应中的 `entity_type` 与 `review_status` facets，提供实体类型和治理状态统计；统计表的“筛选”动作复用当前已执行查询和排序条件回写真实 URL，不在浏览器本地拼接数据。
- 列表/统计视图通过 `display=landscape` 与 `analysis_view=table|chart` 进入稳定路由，刷新和分享链接恢复相同视图；空结果继续保持原有全页视觉基线，避免统计工具栏改变空态布局。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`，统计切换、表格切换、靶点 facet 回筛、空结果深链和真实结果恢复通过；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/global-search-landscape-v1.9.74-chrome-20260802-final5.json`，SHA-256 `9d376654568dd60f58d9c7ee9739263ed1217e024e2715c1a4847a7fc41926ca`。临时账号、实体、化学结构、活动、治理和入库夹具均为 `0`，凭据未记录。
- 该证据补强全局检索的真实统计与连续性，不代表正式授权数据、参考产品人工差异评审、人工辅助技术、操作系统缩放、生产 RUM 或专业用户 UAT；C-02/C-05/C-07 继续未关闭。

## 2026-08-02 真实靶点活性/结构与治理证据闭环及 v1.9.73

- 靶点 dossier 的活动与结构集合现在由真实 target-linked activity/program 关系投影产生；真实浏览器验收为目标写入 assay、IC50 和 pChEMBL 活性记录后，核对 dossier 活性表、结构 InChIKey 和 SAR API 的非空 `total/items`，不拦截业务 API。
- 验收运行器在真实 PostgreSQL 中建立受治理证据、知识专题、引用和 OpenSearch 投影，四视口真实 Google Chrome `151.0.7922.71` 各 `31/31`、合计 `124/124`；`real_target_dossier=true`、`chemistry_real_api=true`，移动端证据操作布局通过，账号、实体、化学结构、活性和受治理知识/证据夹具清理为 `0`。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/real-target-activity-structure-v1.9.73-chrome-20260802-final2.json`，SHA-256 `a70991caffd56c539aabcd866826cfc0e6140baae61a3c0d11832bae1b7f117a`，未记录凭据且 `production_claim=false`。
- 该证据证明受控真实数据的 dossier、活动/结构和知识/证据投影闭环，不代表正式授权数据、规模化学活性、字段/租户权限、系统缩放、生产 RUM 或专业用户 UAT；C-02/C-07 继续保持未关闭。

## 2026-08-02 真实靶点全景档案跨域链路及 v1.9.72

- 正式浏览器运行器通过真实人员登录打开受控靶点 dossier，先核对真实 dossier API 的靶点实体、竞品管线、临床试验、专利、交易和新闻集合，再逐一进入关系、证据、活性、管线、临床、专利、交易、监管、新闻和结构标签；SAR 标签额外通过真实 SAR API 返回 `200`。
- Google Chrome `151.0.7922.71` 四视口各 `31/31`、合计 `124/124`，`real_target_dossier=true`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/real-target-dossier-v1.9.72-chrome-20260802.json`，SHA-256 `80b33050de30b6fc9b0c0c6a0335eb741d2d4bbb05123ad83f0aa6f56dc81c59`。临时账号、实体和化学结构清零，未记录凭据。
- 该证据证明当前受控数据的人员到跨域 dossier/SAR 页面链路，不代表正式授权数据、规模化学活性、字段/租户权限或专业用户 UAT；C-02/C-07 保持未关闭。

## 2026-08-02 真实 viewer 权限边界及 v1.9.71

- 正式浏览器运行器创建受控 `VIEWER` 数据库账户，测试不接管业务 API。viewer 的外部实体读取返回 `200`，企业运营读取返回 `403`；真实浏览器进入内部工作台显示无权状态并隐藏内部入口，进入外部检索工作台正常加载。
- Google Chrome `151.0.7922.71` 四视口各 `30/30`、合计 `120/120`，`real_permission_boundary=true`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/real-permission-boundary-v1.9.71-chrome-20260802.json`，SHA-256 `ba02bbb80be88ea0ae679de30ad110479166c60119b4b5db0fc03dcfbf08ee2c`。临时账号、实体、化学结构和入库夹具清零。
- 该证据覆盖本地 admin/viewer 基础角色边界，不代表正式 IdP、字段级/租户级权限策略或专业用户 UAT；C-07 保持未关闭。

## 2026-08-02 缩放视口密集表格可达性及 v1.9.70

- 在 `320/360/720 CSS px` 等效视口重排检查中，六条真实研究深链现在同时验证所有 `.table-frame` 具备业务名称、`region/section` 语义和 `tabIndex=0` 键盘入口。
- Google Chrome `151.0.7922.71` 四视口各 `29/29`、合计 `116/116`，`reflow_keyboard=true`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/zoom-table-reflow-v1.9.70-chrome-20260802.json`，SHA-256 `e9f77e3adf47b82628335766066845f64050d3d2367724563fb33d13649c4502`。临时账号、实体、化学结构和入库夹具清零，视觉基线未更新。
- 这是自动化密集结果可达性证据，不是人工屏幕阅读器、操作系统缩放或专业用户 UAT；C-05 保持未关闭。

## 2026-08-02 等效缩放与研究路径重排及 v1.9.69

- 既有 `320 CSS px` 键盘登录、移动导航和研究路径重排继续保留；同一真实 Chrome 项目现在额外以 `720` 和 `360 CSS px` 等效视口覆盖 200%/400% 缩放代理。
- 全局检索、靶点、临床结果、专利时间线、交易权益和化学结构六条真实深链均重新加载并检查页面级 `scrollWidth <= clientWidth`；不以 CSS 视口代理宣称操作系统缩放或辅助技术验收。
- Google Chrome `151.0.7922.71` 四视口各 `29/29`、合计 `116/116`，`reflow_keyboard=true`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/zoom-reflow-v1.9.69-chrome-20260802.json`，SHA-256 `1666f84274adbd262780f9588c5e5bbc549474cdfc0a9c0e833fc0c84a1cd9d0`。临时账号、实体、化学结构和入库夹具清零，视觉基线未更新。
- 该证据只强化自动化布局回归，C-05 仍需人工屏幕阅读器/辅助技术、真实 Chrome 系统 200%/400% 缩放和专业用户 UAT。

## 2026-08-01 化学真实 API 闭环及 v1.9.68

- 化学 E2E 不再拦截全部 `/api/v1/**` 或返回静态 Aspirin 对象。正式运行器创建隔离账号、规范药物实体和 PostgreSQL/RDKit 结构记录；页面完成真实登录、Ketcher 按需激活、结构应用和真实 `POST /api/v1/chemistry/search` exact 查询。
- 测试核对 `200`、`mode=exact`、规范化 SMILES、唯一稳定实体 UUID、夹具隔离名称、InChIKey，以及页面唯一 RDKit 描绘；证据合同新增 `chemistry_real_api=true`。结束后按本次结构 UUID 查询 `compound_structures`，临时账号、实体、化学结构和入库夹具必须全部归零。
- Biome、TypeScript 与浏览器/发布证据契约 `307/307` 通过。Google Chrome `151.0.7922.71` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 四视口各 `29/29`、合计 `116/116`；视觉基线未更新，`production_claim=false`。
- 报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/chemistry-real-api-v1.9.68-chrome-20260801.json`，SHA-256 `d02ff24dfe56cc7193ed76e1ea0f8f84951d5a638ee1b45a78374751cc7165de`。该受控单记录闭环不证明正式化学数据规模、并发容量、HA/PITR、目标网络或专业药化用户 UAT，D-09 保持未关闭。

## 2026-08-01 化学编辑器按需激活及 v1.9.67

- `ChemistryView` 初始保持“绘制结构”标签语义，但只呈现稳定的“结构画板尚未打开”区域；用户点击“打开结构画板”或重新选择绘制标签后才加载 `StructureEditor`。高级 SMILES/SMARTS 输入不等待 Ketcher，加载失败仍可回退高级输入。
- 组件红测先复现初始即渲染编辑器，修复后 `3/3`；生产构建继续证明 `StructureEditor` 为独立动态 entry，research 首屏 JS `400951 B`/gzip `115145 B`，CSS `167710 B`/gzip `28579 B`，均在 v1.9.66 预算内。
- 首次 Google Chrome 全量运行中，页面已显示编辑器，但四个化学场景等待页面 Resource Timing 中的 `.wasm` 超时，得到 `112/116`。原因是 Ketcher worker 的 WASM 请求不属于页面 Resource Timing；证据断言改为激活前不存在 `.wasm`/RDKit/Indigo/Ketcher/StructureEditor 页面资源，激活后出现 `StructureEditor` 动态 chunk，并继续操作真实 Ketcher 苯环控件、应用结构和验证 RDKit 描绘。定向四视口 `4/4` 后，最终全量四视口各 `29/29`、合计 `116/116`。
- 运行镜像为统一应用镜像 `sha256:604e44f6b441474f13615690117ea70e9fbfece6e05cd9832b28b4efbcc657bc`；报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/chemistry-on-demand-v1.9.67-chrome-20260801.json`，SHA-256 `e1741ad9eaf23fc2c0dac0eaed47775ee849ca90d38c476ce191bd78fe25d8bd`。视觉基线未更新，临时数据清零；正式数据规模、目标网络和专业用户 UAT 仍未完成。

## 2026-08-01 首屏资源性能边界及 v1.9.66

- `verify-workbench-build.mjs` 现在从生产 manifest 递归计算入口静态 import 闭包及关联 CSS，分别约束原始体积与 gzip 体积；research 预算为 JS `512 KiB`/gzip `180 KiB`、CSS `192 KiB`/gzip `40 KiB`，internal 预算为 JS `384 KiB`/gzip `140 KiB`、CSS `192 KiB`/gzip `40 KiB`。
- RDKit、Ketcher、`StructureEditor`、`TrendLineChart` 和 `LandscapeBarChart` 被明确禁止进入首屏闭包；化学编辑器和专业图表仍保留按需加载，门禁不会通过删除结构编辑能力缩小产物。当前 production build 的 research 首屏为 JS `400951 B`/gzip `115143 B`、CSS `167438 B`/gzip `28539 B`；internal 为 JS `307307 B`/gzip `94824 B`、CSS `167438 B`/gzip `28539 B`。
- Google Chrome `151.0.7922.71` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 四视口各 `29/29`、合计 `116/116`。真实登录后的 Resource Timing 未出现 `.wasm`、RDKit、Indigo、Ketcher 或结构编辑器首屏资源，最大单资源解码体积受 `600 KiB` 门限制约；`initial_load_boundary=true`，视觉基线未更新，临时账号、实体和入库夹具清零。
- 报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/initial-load-boundary-v1.9.66-chrome-20260801.json`，SHA-256 `8e6622dae67aa3de75bcc651f3fcd49e5fffab7b7b8029bced02afedff3ceef2`，`production_claim=false`。本地构建和受控导航不替代目标环境 P75、批准负载、长稳和专业用户 UAT，因此 `performance_and_visual_regression` 继续保持 `partial`。

## 2026-08-01 八域错误与权限恢复矩阵及 v1.9.64

- 新增独立 `professional-error-permission-matrix`，覆盖全局实体、药物与管线、临床试验、专利、交易、监管、流行病学和新闻八个专业域。每个域先通过受治理夹具、稳定 URL 和真实 API 呈现命中结果；测试不提供静态业务结果，也不绕过 PostgreSQL/OpenSearch 查询。
- 对每次目标请求先用 `route.fetch()` 执行真实 API 并断言上游为 `200`，然后只在浏览器传输边界受控注入错误。`503` 连续三次覆盖现有有界重试，页面必须显示“最新结果刷新失败”、保留旧结果，并通过“重新刷新”再次取得真实 API；`403` 必须显示“当前账号无权读取这组结果”、隐藏旧结果，并通过“重新校验权限”再次取得真实 API。
- 实现与证据合同提交 `ee22be0db31bd5ae89dcd0020c7dc41581591987`。最终 `make check` 通过 Ruff 315 文件、严格 Mypy 314 文件、后端 `1149/1149`、前端 `343/343`、OpenAPI、生产构建和运维/Compose/Kubernetes 门禁；浏览器/发布证据合同 `307/307`。
- Google Chrome `151.0.7922.71` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 四视口各完成 `29/29`、合计 `116/116`。`professional_query_state_matrix=true`、`professional_error_permission_matrix=true`、`query_cancellation=true`，视觉基线只读且未更新；临时账号、实体和入库夹具清零。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/professional-error-permission-v1.9.64-chrome-20260801.json`，SHA-256 `8d81983ab3c6974ddd6ca04f8623bb682f22a0478e171ba573bfcf0a78cb4719`，`production_claim=false`。
- 该证据只证明本地受控前端错误/权限恢复合同。正式数据上的真实角色、字段和数据授权组合，人工辅助技术、操作系统缩放、生产故障演练及专业用户签字仍未完成，因此 `state_accessibility_and_responsive_quality` 和 C-07 继续保持 `partial`。

## 2026-07-31 八域查询状态连续性及 v1.9.63

- 全局实体、药物与管线、临床试验、专利、交易、监管、流行病学和新闻八个专业页现在复用 `ProfessionalQueryState`。首次加载、刷新、取消、瞬态刷新失败、403 权限拒绝、空闲与成功不再由 `isPending` 的间接组合猜测；403 会隐藏任何缓存结果，刷新和瞬态失败则继续显示上次成功结果并给出明确恢复动作。
- 每个专业域都有“刷新当前结果”命令，仍使用当前稳定 URL、类型化 query key 和生成客户端 AbortSignal。取消首次请求显示“查询已取消”；取消已有结果刷新显示“刷新已取消”，保留筛选、排序、分页和上次成功结果，可重新刷新或关闭提示。零结果全页和密集表格 shell 的仓库视觉基线保持原尺寸，不为新增操作放宽 `0.001` 阈值或更新快照。
- 组件/状态测试新增 `ProfessionalQueryState.test.tsx` 6 项，八域专项与 Explorer 共 `80/80`；最终 `make check` 为 Ruff 315、严格 Mypy 314、后端 `1149/1149`、前端 `343/343`、OpenAPI 352 文件、生产构建和运维/Compose/Kubernetes 门禁全部通过。
- 真实 Google Chrome `151.0.7922.71` 在四个强制视口完成 `112/112`，每视口 `28/28`。`professional_query_state_matrix=true` 对八个域逐一先读取真实后端 `200`，再延迟浏览器交付，验证刷新期间结果仍可操作、取消后保留、重新刷新回到真实 API；原有视觉基线只读，临时账号、实体和入库夹具均为 `0`。报告 `${PHARMA_RUNTIME_ROOT}/evidence/browser/professional-state-v1.9.63-chrome-20260731.json`，SHA-256 `496095117f4141a5f2ed477f5ae02d63d66aa34732f9ad8b801088aee61fa47a`，`production_claim=false`。
- 累计实现提交为 `21aec9e8a281f0076a4ea6ed52da9bee94ff0545`，当前三条应用进程运行镜像 `sha256:417c8d9dc1f88b909d10692bdec90efff3cd4c85c25b55636e7bc3acf2570848`，OCI revision 一致且 healthy。该证据不替代正式数据上的逐任务错误/权限矩阵、人工辅助技术、操作系统缩放或专业用户签字，因此 `state_accessibility_and_responsive_quality` 和 C-07 继续保持 `partial`。

## 2026-07-31 专业查询取消与恢复及 v1.9.62

- 全局实体、管线、临床、专利、交易、监管、流行病学和新闻八个专业查询现在在加载状态提供一致的“取消查询”操作。共享 Hook 按完整查询键调用 React Query cancellation，生成客户端已有的 AbortSignal 继续终止真实 fetch；没有增加平行请求层、无界轮询或静默错误。
- 初次请求取消后页面显示“查询已取消”，保留 URL 与筛选，并提供“重新查询”；已有成功结果的后台刷新取消后回到上一成功状态。加载、取消和恢复使用稳定 `role=status`，查询按钮在请求期间保持禁用，避免重复提交。
- 组件回归实际触发 AbortSignal 并重试成功；前端门禁通过 OpenAPI 352 文件漂移检查、Biome 190 文件、TypeScript、`337/337` 和生产构建。浏览器/发布证据契约 `307/307`，新增 `query_cancellation` 为所有强制视口必需场景。
- Google Chrome `151.0.7922.71` 四视口 `112/112`。真实浏览器链先从 PostgreSQL/OpenSearch/API 取得 `200` 响应，只延迟向页面交付，然后由按钮终止浏览器请求、核对取消终态与保留筛选，最后解除延迟并重新查询 205 条真实结果；报告 SHA-256 `41f406f64fcb31a7b3b7a53d2653b9b3d83d26507cf8a5801bb78db1b009f123`，所有临时账号、实体和入库夹具清零。
- 实现提交为 `2ed812a7a1ff7c406787df32410ba7c0887d80f6`，部署镜像 ID 为 `sha256:b2938b22843fd8145d3922845c44a19941a06b49ae46e31e73dd7ae71c854492`，三条应用进程均绑定该 revision、非 root、只读且 healthy。该批仍不替代完整关键任务状态矩阵、人工辅助技术、操作系统缩放、正式数据、生产 RUM 或专业用户 UAT，因此 `state_accessibility_and_responsive_quality` 和 C-07 保持 `partial`。

## 2026-07-29 隐私有界 Web Vitals RUM 及 v1.9.41

- 外部 research workbench 在认证完成后按需加载固定 `web-vitals@6.0.1`，采集 CLS、INP、LCP、TTFB；内部工作台不加载。浏览器将导航映射为固定工作域，只提交指标、数值、服务端可复算评级、导航类型/序号和设备类别，完整 URL、查询、实体/文档/租户/人员标识及 Web Vitals client ID 不进入载荷。每页最多 32 个样本、每批最多 8 个，普通发送复用生成 OpenAPI client，隐藏/离开页面使用同源 CSRF keepalive，失败只有一次有界重试。
- `/api/v1/workspace/web-vitals` 只允许人员会话和 `entities:read`，仍强制 CSRF；Agent/API key 失败关闭。高频 RUM 不写逐请求业务审计，但认证、授权和输入校验不豁免。服务端限制枚举、大小、有限数值、CLS 上界、同导航指标唯一性并复算评级，然后写入现有 OTel duration/CLS histogram；只导出 `device.class`、`navigation.type`、`web_vital.name`、`web_vital.rating`、`workspace.view` 五类维度。
- Duration 与 CLS 使用分别覆盖 LCP/INP/TTFB 和 CLS 正式阈值的显式 bucket。现有 `workspace` 运维责任域新增 LCP `2500 ms`、INP `200 ms`、CLS `0.1`、TTFB `800 ms` 的 28 天 P75 目标和告警，复用 gateway、OTel Collector 与既有值班/runbook，不新增第四条业务进程。
- 本地 telemetry profile 实际保持 9 个常驻容器：3 个应用工作负载为 gateway、unified jobs、isolated parser，6 个基础设施/安全依赖为 PostgreSQL、Valkey、OpenSearch、Temporal、ClamAV、OTel Collector；migrate/storage-init 为一次性任务。Parser 不并入 jobs，因为不可信文件的网络、只读文件系统、CPU/内存/PID 与子进程超时隔离属于安全边界。
- 完整 `make check` 通过后端 `1129 passed / 35 deselected`、前端 `294/294`、Ruff、严格 Mypy `307` 个源文件、OpenAPI 漂移、Biome、TypeScript、生产构建、Compose 和 Kubernetes 契约。`web-vitals` 延迟块为 `8.60 kB`（gzip `3.21 kB`），内部入口哈希和四视图边界保持独立。
- Google Chrome `150.0.7871.128` 在四个强制视口完成 `104/104`；浏览器真实 POST 均返回 `202`，样本没有查询、夹具键、UUID 或 URL。本地指标为 LCP `92-144 ms`、INP `16-24 ms`、CLS `0`，报告位于 runtime root 下 `evidence/browser/v1.9.41-web-vitals-rum-chrome-final.json`。独立真实 gateway→OTLP→Collector 验收先读累计基线，再证明专用低基数序列增加 `1`，并确认业务审计和临时账号残留为 `0`；封存报告位于 `evidence/observability/v1.9.41-web-vitals-rum-sealed.json`。
- 实现提交 `9583fa3dd4138957b97a9d4e122ad79e89d3f1f3` 通过 Gitleaks、Semgrep `634` 个目标/`243` 条规则、Python/Node 依赖审计和源码/API/PostgreSQL/OCR SBOM；SAST 与可处置 High/Critical 均为 `0`，API/OCR 门禁清单仍分别保留 `3/15` 个 Medium/Low 项，不把“当前不可处置”误写为“无漏洞”。证据位于 runtime root 下 `evidence/security/v1.9.41-9583fa3-rum`。
- 同一提交从 `git archive` 隔离完成锁定安装、完整质量门、PostgreSQL 迁移升降级、生产镜像构建和非 root 运行烟测；报告绑定 `1104` 个提交源码文件、内容树 SHA-256 `91721eade04b04dcf4371558831c926b50a10153b18185bd4b70330c4129d487` 和镜像 digest `sha256:afb10f7652b2f19e1b9e50d21d965721efd595edaa65c1b3ad71a254d5bfca27`，位于 `evidence/clean-source/v1.9.41-9583fa3.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批闭合本地生产可接入的采集、传输、聚合和运维合同，不等于目标环境已有中心观测、足量真实用户/设备/地区/版本观察窗或批准 P75；正式数据、专业用户 UAT、参考人工差异结论和 Commercial Production 也未完成，因此 `performance_and_visual_regression` 继续保持 `partial`。

## 2026-07-29 账户级结果表偏好连续性及 v1.9.40

- 八个结构化工作域原先把列显隐、列顺序和密度保存在浏览器 `localStorage`，只能在单一浏览器配置中连续，无法满足企业共享终端、跨设备使用、账户注销和浏览器存储清理后的身份边界。本批新增固定八领域键的 `workspace_table_preferences`，以租户/人员复合外键、唯一约束、乐观版本和 PostgreSQL 强制 RLS 持有展示状态；排序、筛选和分页仍只属于稳定 URL 与服务端查询。
- 人员 API 只接受已认证 human session 和 `entities:read`；默认偏好以版本 `0` 返回，更新要求精确期望版本。共享表在首次同步时禁用展示控件，450 ms 合并连续操作，冲突最多进行一次有界重基；读取、保存或恢复默认失败均在表格上下文显示并可重试，不吞掉错误。API 响应和列 ID 在边界处校验，未知、重复或超限列不会进入状态。
- 真实 PostgreSQL 验收完成迁移升级、降级、重升级、同版本并发单胜、同租户用户隔离和跨租户 RLS；后端定向测试 `3/3`、PostgreSQL `1/1`，完整 `make check` 通过后端 `1123 passed / 35 deselected` 与前端 `291/291`，以及 Ruff、严格 Mypy、OpenAPI 漂移、Biome、TypeScript、生产构建、Compose 和 Kubernetes 契约。
- 当前源码安全门通过 Gitleaks、Semgrep `630` 个目标/`243` 条规则、Python/Node 依赖审计、源码与 API/PostgreSQL/OCR 镜像 SBOM、完整漏洞清单和可处置 High/Critical 门禁；密钥泄漏、SAST finding 与可处置项均为 `0`。报告位于 runtime root 下 `evidence/security/20260729T042228Z`；未修复或无上游修复的基础镜像风险仍受既有风险接受门禁约束，本批不据此声称 Commercial Production 已批准。
- 实现提交 `81072093fe9288253a1100fc0dd380063e03d1ec` 从 `git archive` 隔离完成锁定 Python/前端安装、同一全量门禁、PostgreSQL 迁移升级/回滚、生产镜像构建以及非 root、只读、无网络烟测；报告绑定 `1097` 个提交源码文件和内容树 SHA-256 `12a9daf8170ccddddbe13f290d42b93b93d72db373e6eff5a34340940f3dd1cf`，位于 runtime root 下 `evidence/clean-source/v1.9.40-8107209.json`。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完成 `104/104`。验收实际改变密度、列顺序与显隐，核对服务端版本化记录，清空 `localStorage`，并在桌面项目中新建第二 Chrome context、重新登录同一账户后恢复相同状态；结束后临时账号、实体和入库夹具均为 `0`。最终报告位于 runtime root 下 `evidence/browser/v1.9.40-server-table-preferences-chrome-final.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批闭合账户级展示连续性和隔离，不等于正式许可数据、参考产品全流程人工评审、专业用户 UAT、人工辅助技术、生产 RUM 或 Commercial Production 已完成；`dense_result_operations` 与 `personal_productivity_and_delivery` 继续保持 `partial`。

## 2026-07-29 药物交易与地域权益及 v1.9.38

- 用户授权参考会话真实打开奈妥木单抗详情并核对“交易&权益”、数据来源和“最终权益归属”表。参考页面在药物上下文中直接给出研发机构、权益类型和权益地区；对照发现本平台 drug dossier 原先只返回通用 `DealRead`，药物页只能显示类型、日期、摘要地域和总额，已治理的交易角色、资产阶段和地域权益必须另行进入交易库才能看到。
- drug dossier 现复用交易检索的 `DealSearchItemRead` 权威合同。药物“交易”分区使用两张专业表：关联交易显示名称/类型/日期、状态/方向、参与方角色/地区/类型、资产交易时与当前阶段、首付款/潜在总额、交易地域、权益数量、更新时间和来源；权益归属显示持有人、类型、地区、独占性、范围、关联交易和来源。参与方、资产、持有人与交易均以稳定 ID 跳转。旧交易缺少角色或阶段时保留已知实体并明确字段未披露，不静默丢失。
- 页面标题明确使用“交易内权益归属”语义，不把单笔交易中的结构化权利称为最终全球权益。缺少生效时间、转授、终止和权利继承链时，不从参考页面、名称或自由文本推断最终所有权。
- 后端 PostgreSQL 测试锁定许可方/被许可方、交易时阶段和独占大中华区商业化权益；组件测试覆盖结构化路径、稳定实体/交易跳转和旧记录回退；真实 Playwright 在药物档案中核对交易类型/状态/方向、双方角色、资产阶段、金额、权益持有人/类型/地区/独占性/范围、完整交易详情、公司档案、历史返回和刷新恢复。
- 最终完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `54` 个文件与 `287/287`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。研究入口文档 SHA-256 为 `c4a1a28c6b467351135c01f29151ad7e77a517b41376f6a1a810aab334caa593`，实现检查点为 `185c91bd42c9e1914268611cd462b38b4bf32d07`。
- Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 与 Edge previous `149.0.4022.98` 均为 `104/104`，四视口各 `26/26`，耗时 `290362/283854/289467 ms`；视觉基线只读复用，临时账号、实体、入库夹具和凭据记录均为零。最终报告位于 runtime root 下 `evidence/browser/v1.9.38-drug-deals-chrome-final.json`、`v1.9.38-drug-deals-edge-current-final.json` 和 `v1.9.38-drug-deals-edge-previous-final.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批关闭的是本地药物交易详情与跨域连续性，不等于最终权利链、正式许可数据覆盖、参考产品全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放或生产 RUM 已完成。

## 2026-07-29 药物适应症、地区进度与权益及 v1.9.37

- 用户授权参考会话真实打开奈妥木单抗详情并核对“基本信息”“交易&权益”“适应症”和“中国研发进度”区段。参考任务把适应症、国家/地区、阶段、阶段日期、全球状态、机构和权益组织在同一药物上下文；对照发现本平台 API 已返回全球/中国阶段及起始日、当前机构集合、权益、标签和历史，但药物页仍复用通用研发管线表，隐藏了大部分已有权威信息。
- 药物“研发管线”现分为两张专业表：适应症与地区进度集中呈现规范适应症、全球/中国阶段与起始日、记录地区、受控状态、靶点/机制和状态日期；研发机构与权益集中呈现当前机构的角色/地区/类型、研发与商业化权益、模态/创新/药品分类、项目标签及合并排序后的阶段历史/里程碑。适应症、靶点和机构均使用稳定实体 ID，来源继续使用 `development_program` 溯源；未治理字段明确标记，不从参考结果补写。
- 组件测试覆盖地区和受控值映射、旧记录兼容、双表字段及适应症/机构跳转；真实 Playwright 使用 PostgreSQL/OpenSearch 夹具核对全球 II 期、中国 I 期、原研/合作研发角色、研发/商业化权益、里程碑、疾病档案跳转、后退与刷新恢复。横向表格均为具名、可键盘聚焦 region，并进入既有档案 axe 和四视口门禁。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `54` 个文件与 `285/285`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。研究入口文档 SHA-256 为 `eb20be864ea03c8a75438e01cb4e8ecebcb35c1fa92acb5601de4a9041429e44`，实现检查点为 `d3148026e723e01014bb251afa187cbc0dae0869`。
- Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 与 Edge previous `149.0.4022.98` 均为 `104/104`，四视口各 `26/26`，耗时 `275113/269513/270545 ms`；视觉基线只读复用，临时账号、实体、入库夹具和凭据记录均为零。报告位于 runtime root 下 `evidence/browser/v1.9.37-drug-development-chrome.json`、`v1.9.37-drug-development-edge-current.json` 和 `v1.9.37-drug-development-edge-previous.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批关闭的是本地药物研发详情与跨域连续性，不等于正式许可数据覆盖、参考产品全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放或生产 RUM 已完成。

## 2026-07-28 药物临床结果与试验详情及 v1.9.36

- 用户授权参考会话真实打开奈妥木单抗详情并核对“临床结果”和“临床试验”区段。参考任务把登记号、适应症、方案、分期、治疗线次、总体评价、核心疗效、规范药物/靶点、申办方和来源组织在药物上下文中；对照发现本平台 API 已有 outcomes、干预、申办方和试验角色，但药物页原先只显示登记号、标题和适应症，用户必须进入每条试验后才能判断证据价值。
- 原“临床试验”标签收束为“临床结果与试验”。结果表只纳入有结果、关键披露或结构化 outcome result 的试验，直接呈现最多两个已治理终点及组别值、总体评价、分期/线次、试验/联用药物和靶点、最近披露；登记表呈现状态、研究/发起类型、干预、申办方、入组及起止日期。所有规范角色使用稳定实体 ID，详情和来源仍为真实 API，缺少结构化终点时明确说明，不从标题或参考页面补写疗效。
- 后端 dossier 合同改用 `ClinicalTrialSearchItemRead`。目标测试暴露并修复了既有根因：`entity_id` 过滤此前只识别通用 `Relationship`，遗漏 `ClinicalTrialEntityRole`；当前在同租户范围内把试验自身实体、`trial_links_entity` 和规范角色作为同一“相关试验”OR 语义，同时保留角色组专用查询的精确约束。OpenAPI 与生成 TypeScript 客户端同步。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `54` 个文件与 `285/285`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。研究入口文档 SHA-256 为 `255265530194f4b4b5a6fccbbd4c8b01351d0b7b9a1dfbd2d5087f9e9ea3e9b6`，实现检查点为 `c1e54ba74c247b9e91b5220cf3a3ceccc3937753`。
- Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 与 Edge previous `149.0.4022.98` 均为 `104/104`，四视口各 `26/26`，耗时 `294166/295416/286864 ms`；视觉基线只读复用，临时账号、实体、入库夹具和凭据记录均为零。报告位于 runtime root 下 `evidence/browser/v1.9.36-drug-clinical-chrome.json`、`v1.9.36-drug-clinical-edge-current.json` 和 `v1.9.36-drug-clinical-edge-previous.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批关闭的是本地药物临床证据详情与关联正确性，不等于正式许可数据覆盖、参考产品全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放或生产 RUM 已完成。

## 2026-07-28 药物获批适应症详情与 v1.9.35

- 用户授权参考会话真实打开奈妥木单抗详情并核对了基础信息、地区阶段、权益、适应症、获批适应症、临床结果等区段。与本平台对照后确认，原药物“监管”分区只展示通用事件，虽然数据库已有规范适应症、机构、获批人群和给药限定，却没有形成面向研究用户的一屏结构化获批视图；这会迫使用户在事件详情间反复打开和人工拼接。
- 现有药物档案收束为“获批与监管”，首先呈现具名、可键盘聚焦的获批适应症表格：规范适应症、日期、地区、审批类型、获批人群、治疗线次、生物标志物、剂型、给药途径、监管机构、申请号和状态；其他申报、标签与安全事件保留在同一分区。适应症按钮使用稳定实体 ID 进入疾病档案，监管事件详情、来源抽屉和浏览器返回均保持连续。未知值保留来源值，缺失值明确显示，不从参考站或标题推断给药方案、撤市原因等未治理事实。
- 后端 dossier 合同改用 `RegulatoryEventSearchItemRead`，在同一租户边界内返回规范 subject、indication 和 organization 关联；OpenAPI 与生成 TypeScript 客户端同步。后端真实 PostgreSQL 测试锁定关联实体，组件测试锁定受控值映射、空值、详情和来源操作，Playwright 使用真实监管正样本验证药物 → 疾病 → 返回 → 监管详情链路。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `54` 个文件与 `284/284`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。研究入口文档 SHA-256 为 `e808e09f7e0e6777fd1d7d832f1e70fe5d468fdb4b88536d52e51557e45359ef`，实现检查点为 `d75284ab08f9910da989a7c3571414e256a141db`。
- Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 与 Edge previous `149.0.4022.98` 均为 `104/104`，四视口各 `26/26`，耗时 `278103/271061/273484 ms`；视觉基线只读复用，临时账号、实体和凭据记录均为零。报告位于 runtime root 下 `evidence/browser/v1.9.35-drug-approvals-chrome.json`、`v1.9.35-drug-approvals-edge-current.json` 和 `v1.9.35-drug-approvals-edge-previous.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批闭合的是本地获批详情与跨域连续性，不等于正式许可数据覆盖、参考产品全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放或生产 RUM 已完成。

## 2026-07-28 外部弹窗/抽屉焦点治理与 v1.9.34

- 源码和真实键盘路径审计确认，外部工作台的保存、编辑、比较及详情抽屉使用多套自定义实现：部分只有 `aria-label` 表单或单独 Escape 监听器，没有统一初始焦点、正反向循环、嵌套层级和关闭后恢复；新闻详情内再打开原始证据时，外层与内层监听器还可能同时响应 Escape。该缺口影响键盘和辅助技术工作流，但不一定被静态 axe 扫描发现。
- 新增共享 `useModalFocus`，只允许栈顶对话层处理 `Tab`、`Shift+Tab` 和 Escape，打开后优先聚焦任务输入或关闭控件，卸载后只向仍连接且可用的触发控件恢复焦点。比较列表、保存检索、已保存检索编辑、Explorer 实体详情、新闻详情、监管详情和原始证据抽屉已统一接入；Explorer 重复保存表单改为共享 `SavedSearchDialog`。保存请求未决时关闭按钮、取消和 Escape 均不可中断操作。
- 新组件测试覆盖保存弹窗的初始焦点、正反向循环、Escape、恢复及 pending 保护，共享 Hook 测试覆盖嵌套栈顶关闭和逐层恢复。真实 E2E 主路径覆盖比较列表异步内容、管线保存、已保存检索编辑、Explorer 详情，以及“新闻详情 → 原始证据”嵌套抽屉，没有用 window 事件或静态 DOM 断言替代用户键盘路径。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `54` 个文件与 `283/283`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。研究入口文档 SHA-256 为 `d314cfa6ddc6870862aecbe21511a66d47809b7d0e17b44d917824107ead601f`，实现检查点为 `124eaa21197a8f985fec5e797ae1ae94d08f5d25`。
- Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 与 Edge previous `149.0.4022.98` 分别 `104/104`，四视口各 `26/26`，耗时 `281808/275715/281118 ms`；视觉基线只读复用，临时账号、实体和凭据记录均为零。报告位于 runtime root 下 `evidence/browser/v1.9.34-modal-focus-chrome-r3.json`、`v1.9.34-modal-focus-edge-current.json` 和 `v1.9.34-modal-focus-edge-previous.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批关闭的是本地自定义对话层焦点合同，不等于人工屏幕阅读器/辅助技术、操作系统缩放、正式许可数据、完整参考差异评审、专业用户 UAT 或生产 RUM 已完成；`state_accessibility_and_responsive_quality` 继续保持 `partial`。

## 2026-07-28 外部横向表格键盘可达性与 v1.9.33

- 四视口基线逐图复核后，源码审计确认多个外部视图仍直接使用 `div.table-frame`：浏览器可以横向滚动，但区域没有业务语义名称，也不能通过键盘获得焦点；部分既有实现还复用笼统的“数据表滚动区域”。该缺口不一定被 axe 报告，但会阻断只用键盘的用户访问窄屏密集表格。
- 新增共享 `ScrollableTableRegion`，以具名 `section` 提供隐式 region 语义和 `tabindex=0`，并保留固定 `.table-frame` 尺寸与既有业务样式。概览、列表、知识、监控、药物/靶点/公司/疾病/通用实体档案、临床结构化结果和交易权益等 11 个外部视图已使用具体业务名称；外部视图不再残留直接 `div.table-frame`。内部运营工作台没有混入本批外部入口范围。
- `ScrollableTableRegion` 组件回归锁定共享/业务样式、非空可访问名称和键盘焦点。Playwright 在 14 个外部工作域以及 5 个实体入口、临床 4 个、专利 3 个、交易 5 个共 17 条档案路径逐页遍历实际 `.table-frame`，要求 section 或显式 region、非空 `aria-label` 和 `tabindex=0`；没有通过跳过页面或放宽 axe 规则获得通过。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、覆盖率 `84.94%`、Mypy `295` 个源文件、前端 `52` 个文件与 `280/280`，以及 Ruff、Biome、TypeScript、OpenAPI 漂移、生产构建、Compose/Kubernetes 和运维合同。实现检查点为 `a7d2a5955587f95451fade271391e0dcf887f6ee`。
- Google Chrome、Edge current 与 Edge previous 分别 `104/104`，四视口各 `26/26`，耗时 `271223/264101/271195 ms`；`snapshots_updated=false`，临时账号、实体、入库夹具和凭据记录均为零。报告位于 runtime root 下 `evidence/browser/v1.9.33-scroll-regions-chrome-final-r3.json`、`v1.9.33-scroll-regions-edge-current-final.json` 和 `v1.9.33-scroll-regions-edge-previous-final.json`。
- 固定分母下已验证代码交付仍保守维持约 `94%`。本批关闭的是自动化键盘滚动合同，不等于人工屏幕阅读器/辅助技术、操作系统缩放、正式许可数据、完整参考差异评审、专业用户 UAT 或生产 RUM 已完成；`state_accessibility_and_responsive_quality` 因这些证据缺口继续保持 `partial`。

## 2026-07-28 八域最多五级服务端排序与 v1.9.32

- 本批将排序从各域分散的单字段参数统一为有序重复 `sort=field:direction`，最多五项，覆盖全局实体、药物与管线、临床试验、专利、交易、监管、流行病学和新闻。共享解析层拒绝未知字段、重复字段、格式错误、超过上限和新旧合同冲突；交易金额在任一优先级参与排序时必须提供币种。PostgreSQL 统一空值末置并追加稳定标识兜底，OpenSearch 使用多字段 sort DSL，语义混合检索只允许相关性作为第一优先级。
- `VirtualDataTable` 新增优先级编号、最多五项增删、上下移动、升降序和显式应用，固定尺寸避免工具栏跳动。排序顺序进入稳定 URL、类型化保存/订阅、受控导出、收费 Agent API、MCP、OpenAPI 和生成客户端；旧 `sort_by/sort_direction` 只保留第一项兼容，不能覆盖或重排新合同。
- 真实 Chrome 首轮验收捕获 Explorer 的实际缺陷：URL 已恢复 `sort=name:asc`，但过滤相关性字段后表格使用错误回退，未暴露匹配的 `aria-sort`。修复为以实际首个可见排序项驱动表头状态，并新增组件回归；没有放宽定位器、隐藏状态或退回客户端排序。E2E 主路径实际设置两级管线排序，核对请求、结构化响应、稳定 URL、刷新恢复、优先级摘要和编辑器状态。
- 完整 `make check` 通过后端 `1111 passed / 34 deselected`、`85%` 覆盖率、Ruff、Mypy `295` 个源文件、前端 `279/279`、OpenAPI 漂移、TypeScript、生产构建、Compose/Kubernetes 和运维合同。Google Chrome、Edge current 与 Edge previous 均 `104/104`，四视口各 `26/26`，`snapshots_updated=false`，临时账号、实体和入库夹具清零。
- 实现提交 `14adf19704e41978c3e24c5072cf1d0202c0b231` 从 `git archive` 隔离完成锁定 Python/前端安装、同一全量门禁、PostgreSQL 升降级、生产镜像构建和非 root、只读、无网络烟测；报告绑定 `1073` 个提交源码文件和内容树 SHA-256 `efccc81169c908b78fe53091a36852a4e8ddec41f22d799fcd29e7395637cc70`。最终文档提交继续由 v1.9.32 clean-source 报告和 Git bundle 独立封存。
- 当前 v1.9.32 提交的 Gitleaks、Semgrep `619` 个目标、Python/Node 依赖审计、源码与三镜像 SBOM、完整漏洞清单及可处置 High/Critical 门禁通过；可处置项为 `0`。API、PostgreSQL、OCR 完整清单仍分别登记 `27/77/45` 个 `not-fixed`、`wont-fix` 或无发行版修复的 High/Critical 条目，未获风险接受，因此没有运行或冒充 release-mode 安全批准。
- 固定分母下，“已验证代码交付”由约 `93%` 保守调整到约 `94%`。正式许可数据、参考全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放、生产 RUM、受控远端/tag 和 Commercial Production 批准仍未闭合，因此 `dense_result_operations` 等相关矩阵状态继续为 `partial`。

## 2026-07-28 专业档案确定性视觉与 v1.9.31

- 视觉审计发现仓库基线只锁定空结果全页和密集结果表格 shell，临床结构化终点、专利法律时间线和交易地域权益等高信息密度档案分区没有像素回归证据。本批在既有真实认证主路径中为三个分区增加 element screenshot，四个强制视口合计新增 12 张仓库自有 PNG；视觉清单升级为 `pharma.workbench-visual-baselines.v3`，浏览器报告升级为 `pharma.browser-acceptance.v9`，每个视口记录五种状态、捕获边界和 SHA-256。
- 人工逐图检查在移动端交易权益表发现横向滚动容器没有业务名称且不能由键盘聚焦。表格现放入 `aria-label="交易权益明细"`、`tabindex=0` 的 region，组件回归锁定语义；没有隐藏表格、删除列或把移动端改成不完整卡片。
- 首次 Edge previous 只读比较在四个视口均稳定复现交易权益截图差异，差异比例约 `0.0024-0.0063`，高于既有 `0.001` 门禁。根因是长文本驱动的自动表格列宽在 Chromium 主版本间取整不同；修复为显式 `colgroup`、固定百分比列宽和 `table-layout: fixed`。没有放宽全局或局部像素阈值，也没有为 Edge 维护独立基线。
- 修复后 Chrome 显式更新运行 `104/104`，随后 Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99` 和 Edge previous `149.0.4022.98` 均以只读模式 `104/104`，四视口各 `26/26`，临时账号、实体和入库夹具清零。报告位于 runtime root 下 `evidence/browser/v1.9.31-dossier-visual-fixed-chrome.json`、`v1.9.31-dossier-visual-fixed-edge-current.json` 和 `v1.9.31-dossier-visual-edge-previous.json`。
- 用户授权参考会话补做真实交互审计：直接输入但不选择候选的 `EGFR` 被参考页明确标记为近似靶点条件并返回宽泛结果；候选层则区分规范靶点、靶点组合、同义词及突变/变体。结果页可在列表和同查询多维可视化间切换，列配置支持显隐与拖拽，排序配置公开限制为最多五个优先级字段。当前平台已具备规范实体/组合、多维格局、列显隐/重排及单字段全命中集服务端排序；最多五级服务端排序仍是明确的本地代码差距，不计为已完成。
- 完整 `make check` 通过后端 `1103 passed / 34 deselected`、Ruff、Mypy 293 个源文件、前端全量测试、OpenAPI 漂移、TypeScript、生产构建、Compose/Kubernetes 和运维合同。固定分母下，“已验证代码交付”由约 `92%` 保守调整到约 `93%`；多级排序、正式许可数据、参考全流程人工评审、专业用户 UAT、人工辅助技术、操作系统缩放和生产 RUM 仍未闭合，体验门禁继续为 `partial`。

## 2026-07-28 专业档案无障碍闭环与 v1.9.30

- 复核发现 `[accessibility-dossier]` 只覆盖靶点、药物、公司、疾病和通用实体 5 个入口，临床试验、专利族和交易的页面级分区没有进入 axe WCAG 2.2 A/AA 门禁，专利档案也未进入代表性 `320 CSS px` 键盘重排路径。本批把审计扩展到 5 个实体入口及临床 4 个、专利 3 个、交易 5 个分区，共 17 条真实档案路径；重排场景改为临床结果、专利时间线和交易权益等密集分区。
- 首次 Google Chrome 扩展运行总计 `100/104`。四个视口均出现项目缺陷：临床页脚对比度 `4.30:1`，交易参与方/资产辅助文字在悬停背景上为 `4.22:1`，交易权益表头为 `4.25:1`；移动端临床结构化结果表产生横向滚动但容器不可由键盘聚焦。没有跳过页面、放宽 axe 规则或隐藏内容。
- 辅助文字改用满足普通文本要求的中性色；临床结果表容器改为带结果指标名称的语义 region，并允许键盘聚焦和滚动。组件测试锁定可访问名称与 `tabindex=0`，避免后续把键盘合同退回普通 `div`。
- 完整前端回归 `272/272`；完整 `make check` 通过后端 `1103 passed / 34 deselected`、Mypy 293 个源文件、OpenAPI 漂移、生产构建、Compose 和 Kubernetes 合同。最终 Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99`、Edge previous `149.0.4022.98` 均 `104/104`，四视口各 `26/26`，快照只读且临时数据清零。
- 固定分母下，“已验证代码交付”由约 `91%` 保守调整为约 `92%`。状态/无障碍/响应式体验门禁仍为 `partial`：人工屏幕阅读器与辅助技术、操作系统缩放、正式数据、生产 RUM 和专业用户 UAT 尚未闭合，自动 axe 全绿不能替代这些外部门禁。

## 2026-07-28 临床关联药物项目组合查询与 v1.9.29

- 授权参考临床结果页把 Modality、创新类型、药品类别、药品标签、全球最高阶段和研发机构国家/地区作为关联药物属性。平台将临床合同升级到 `pharma.clinical_trial.search.v9`，六类条件进入稳定 URL、完整命中集分面、保存/订阅、受控导出、人员 HTTP、收费 Agent API 和 MCP，不在浏览器本地筛选。
- 查询使用一个关联 `DevelopmentProgram` 存在性条件绑定所有已选属性，且只允许试验药物或联用药物角色连接该项目；机构国家/地区通过当前 `organization_set_version` 的机构行判定，历史集合不能扩大结果。受控语料中同一试验同时关联小分子 `first_in_class` 项目和抗体 `best_in_class` 项目，抗体 + `best_in_class` + III 期 + US 返回唯一正样本，抗体 + `first_in_class` 返回 0。
- 首次真实 PostgreSQL 浏览器运行暴露 facet 子查询对含 `json` 项目标签的整行执行 `DISTINCT`，PostgreSQL 因 `json` 无等值运算符使全部临床查询返回 500。删除无必要的行级去重后，各 facet 继续按 `count(distinct trial_id)` 计数，组织分面继续独立去重；未吞异常、未禁用分面、未改用客户端结果。
- 后端聚焦回归 `46/46`、前端合同回归 `40/40`、完整前端 `272/272`、OpenAPI `346` 个生成文件漂移为 0，生产 Web 构建通过。Google Chrome、Edge current 和 Edge previous 分别 `104/104`，每套四视口各 `26/26`；正负结果、URL 刷新、表单恢复、WCAG、320px 键盘重排和临时数据清理均通过。
- 固定分母下，代码已实现、跨层已集成和自动化已验证均提高一个受控临床查询切片，“已验证代码交付”由约 `90%` 保守调整到约 `91%`。正式授权数据、参考侧逐流程人工差异评审、专业用户 UAT、生产 RUM 和 Commercial Production 批准不变，能力矩阵中的 `partial` 状态不因单域代码闭环上调。

## 2026-07-28 可迁移源码基线与 v1.9.28

- 继承的 599 文件集成状态已形成 Git 检查点，工作树从 591 项状态收束为干净提交；交接文档不再包含个人 WSL 绝对路径。
- 首次 `git archive HEAD` 隔离复现发现 `run-smb-source-acceptance.sh` 在 Git 索引中缺少可执行位，真实结果为后端 `1101 passed / 1 failed / 34 deselected`。根因是 `core.filemode=false` 隐藏了工作树与索引模式差异；随后审计并修复全部 14 个直接执行的 shell 入口，针对性回归 `20/20` 通过。
- 最终隔离复现绑定提交 `c97846e846a26dcec183dbfe41aafbab7b8b5f1d`、1,056 个源码文件和内容树 SHA-256 `35adfdda404bd57d493da3ad354892d760ab47b8630d2c8d8a12dc5e7f1a6749`，完成锁定安装、完整 `make check`、PostgreSQL 迁移升降级、生产镜像构建及非 root、只读、无网络烟测；所有阶段退出码为 0。
- 该批关闭本地可审查、可迁移和可独立复现的源码交付阻断，固定分母下已验证代码交付由 `89%` 保守提高到 `90%`。它不替代受控 remote/tag/签名、授权参考人工差异评审、正式数据、专业 UAT、生产 RUM 或 Commercial Production 批准；能力矩阵中的 `partial` 状态不变。

## 2026-07-28 原始证据研究连续性与 v1.9.27

- 审计发现原始证据查询、证据域和请求只保存在 `EvidenceView` 组件状态；刷新、分享和历史返回均丢失。更严重的是五个硬编码展示域被直接当作 dataset key，但真实投影使用租户数据集 key，用户选择后可能得到 422 而不是筛选结果。
- 新增 `/api/v1/evidence/datasets`，只返回当前主体在当前交付渠道获 scope 且许可证有效的数据集逻辑 key、展示名和归属说明；MCP-only 数据集不会出现在人员入口，RAGFlow 私有 ID、对象 URI 和内部策略不进入响应。前端选项来自该目录，不再硬编码。
- `view=evidence` 现稳定序列化查询、重复 dataset、文档 ID 和引用序号；直接链接自动执行真实检索，刷新、分享及前进/后退恢复同一引用。定位按真实 `locator_kind/locator_value/start_char/end_char` 及兼容页码字段呈现；引用不再命中时显示可恢复的失效状态，不伪造原文阅读器。
- 新增 `[evidence-research-continuity]` 真实场景，不使用 `page.route`：登录后读取当前租户许可目录，以真实 `DeepEGFR` 投影查询，按结果所属 dataset 重提筛选，核对 API 请求体、文档/引用 URL、刷新选中态和历史恢复。Chrome、Edge current、Edge previous 均 `104/104`，四视口各 `26/26`，临时账号、实体和入库夹具为 0。
- 首轮 Chrome 的四个失败均来自新增说明文字仅 `3.35:1` 的颜色对比度；改为独立 `evidence-field-help` 样式后 WCAG A/AA 全绿。另一次运行被 WSL 服务 `E_UNEXPECTED` 中断且没有报告，确认清理为 0 后完整重跑，不将中断计作通过。
- 完整 `make check` 通过后端 `1102 passed / 34 deselected`、覆盖率 `84.87%`、前端 `272/272`、Mypy 293 文件和全部 OpenAPI/构建/部署合同。固定分母下已验证代码交付由 `88%` 保守提高到 `89%`；正式数据、人工参考评审、专业 UAT 和 Commercial Production 仍未完成。

## 2026-07-28 知识专题研究连续性与 v1.9.26

- 审计发现知识专题已有真实列表、当前正文、覆盖摘要、版本历史和不可变差异 API，但检索词、专题选择、正文/治理面板和版本选择全部停留在 `KnowledgeView` 组件状态；刷新、分享和历史返回会丢失上下文，首页专题表格也不能直达具体专题。
- `view=knowledge` 现稳定序列化 `q`、`page=<UUID>`、`panel=governance` 和正整数 `version`；非法 page UUID、无专题时的治理面板和越界版本失败关闭。`KnowledgeView` 在生产入口由 URL 控制，同时保留独立组件复用模式；列表、正文、覆盖、历史与差异继续调用既有服务端 API。首页已发布专题标题按稳定 page ID 打开。
- 组件回归覆盖搜索、专题、面板、版本事件和非法深链；路由回归覆盖规范化、大小写 UUID、危险路径和版本边界。前端完整测试为 `268/268`。
- 新增 `[knowledge-research-continuity]` 真实浏览器场景，不使用 `page.route`：每个视口以验收账户登录，从当前租户真实 `/api/v1/knowledge/pages` 响应选择已发布专题，依次验证专题 URL、刷新、治理面板、不可变版本、再次刷新和两级历史恢复。Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均 `100/100`，四视口各 `25/25`，快照只读且临时夹具清零。
- 完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `268/268` 及全部格式、类型、OpenAPI、生产构建和部署合同。一次非登录 WSL 命令因 PATH 缺少 `uv` 在测试前退出；标准 `bash -lc` 重跑全绿。一次仅用于提取计数的无效 Vitest reporter 同样在测试前退出，默认 reporter 重跑确认计数。
- 本批提高个人研究连续性，但正式授权数据、参考人工差异评审和专业 UAT 仍未完成，因此 `personal_productivity_and_delivery` 与 `personal_team_productivity` 保持 `partial`。固定分母下已验证代码交付由 `87%` 保守提高到 `88%`，Commercial Production 状态不变。

## 2026-07-28 Explorer 快速详情连续性与 v1.9.25

- 全局检索详情此前只保存在 `ExplorerView` 组件状态，打开后 URL 不变，刷新、分享和浏览器历史无法恢复。现有 `entity=<UUID>` 路由合同扩展到 `view=explorer`；人员入口复用权威实体 API 恢复详情，关闭时清除参数，非法 UUID 失败关闭并从规范 URL 丢弃。
- 抽屉现在覆盖受控加载、服务错误、无权/不存在和已加载状态；组件仍保留不受控模式供独立复用。打开专业档案后返回 Explorer 会恢复查询、密度、列和详情历史，用户关闭恢复的详情后可继续排序或其他结果操作。
- 干净 Docker `pnpm build` 首次捕获 UI `Entity` 与 API `EntityRead` 的可选字段边界不一致；改为在 Explorer 受控边界复用既有 UI `Entity` 合同后，TypeScript 与生产构建通过，没有使用类型断言掩盖问题。
- 首轮 Chrome 为 `92/96`：四视口均正确恢复抽屉，但测试在未关闭遮罩时继续点击表头。验收改为明确断言恢复、真实点击“关闭实体详情”、确认 URL 清参，再继续排序；没有强制点击、隐藏遮罩或放宽超时。最终 Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均 `96/96`，四视口各 `24/24`，临时账号、实体和入库夹具均为 `0`。
- 完整 `make check` 首次出现一个 SMB 快照连接器单例失败，单独 `-vv --tb=long` 复现为通过；完整重跑最终通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `264/264` 及全部格式、类型、OpenAPI、生产构建和部署合同。该事件保留为非稳定测试观察，不作为跳过项。
- 本批提高全局检索与密集结果的代码级研究连续性，但正式授权数据、参考人工差异评审和专业 UAT 仍缺，因此矩阵的 `global_search`、`dense_result_operations` 继续保持 `partial`。固定分母下已验证代码交付由 `86%` 保守提高到 `87%`，Commercial Production 状态不变。

## 2026-07-28 新闻/会议结果正确性与 v1.9.24

- 服务层审计确认关键词、事件类型、发布机构、语言、会议/场景、关联规范实体、研究内容范围和发布时间均直接约束同一 `NewsEvent`；没有发现跨事件拼接实现缺陷，但既有浏览器只验证正事件标题和回放，未核对权威总数、稳定 ID 或高判别负样本。
- 单元和真实浏览器夹具新增与正事件共享检索词、`conference_abstract` 类型、发布机构、语言、关联靶点及日期，仅会议为 `AACR 2026` 的负事件。`news-result-correctness` 监听真实 `/api/v1/news-events`，核对 ASCO 查询参数并严格断言 `total=1`、唯一正事件 ID 和负事件排除；时间线、保存、订阅及监控回放继续执行。
- 首轮 Chrome 为 `92/96`：负事件最初复用正事件完整标题，导致既有靶点档案中按可访问名称打开详情的按钮出现两个同名匹配。负标题改为仍包含同一检索词但可区分后，既保留会议为唯一筛选差异，也恢复详情操作唯一性；没有隐藏负事件或放宽 locator。
- 最终 Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。
- 七个既定领域结果正确性切片至此均具备真实正负样本证据；这只证明受控语料内的查询语义，不代表正式授权数据覆盖、参考产品人工差异评审或业务 UAT。固定分母下已验证代码交付由 `85%` 保守提高到 `86%`，Commercial Production 状态不变。
- 最终内容树安全门固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260728-v1.9.24-news-result-correctness-sealed`；该证据仍需绑定干净 commit/tag 才能成为可发布候选证据。

## 2026-07-28 专利族结果正确性与 v1.9.23

- 服务层审计确认关键词、申请人、当前法律状态、关联规范实体、优先权日期和到期日期均直接约束同一 `PatentFamily`；现有合同没有发现跨专利族拼接实现缺陷，但既有测试只证明正族可见，未核对权威总数、稳定 ID 或高判别负样本。
- 单元回归新增与正族标题、申请人及关联实体一致、仅 `legal_status=PENDING` 的专利族，ACTIVE 查询只返回正族。真实浏览器夹具同样新增相邻优先权/到期日期、同申请人、同权利要求但状态为 PENDING 的负族。
- `patent-result-correctness` 监听真实 `/api/v1/patent-families`，核对关键词、申请人和 ACTIVE 状态参数，严格断言 `total=1`、唯一 ID 为正族并排除 PENDING 负族；原专利结果、保存、订阅及监控中心完整回放路径保持不变。该场景进入浏览器报告和发布证据必需集合。
- Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。
- 该批完成专利域首个版本化正负样本结果正确性切片；新闻/会议仍未覆盖，固定分母下已验证代码交付由 `84%` 保守提高到 `85%`，Commercial Production 状态不变。
- 最终内容树安全门固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260728-v1.9.23-patent-result-correctness-sealed`；该证据仍需绑定干净 commit/tag 才能成为可发布候选证据。

## 2026-07-28 流行病学趋势可比性与 v1.9.22

- 审计发现既有提示声称趋势只合并同指标、单位和队列且不跨来源/方法学，但服务端未约束发布机构和方法学，可能把不可比较估计连接成一条趋势。趋势合同现接受稳定 `anchor_observation_id`，验证锚点属于同租户和请求疾病，并从锚点派生患者人群、指标、地区、单位、来源人群口径、年龄、性别、发布机构和方法学九维精确比较键；锚点字段为空时同样使用 `IS NULL` 精确匹配。
- API 的锚点参数为向后兼容可选项，人员工作台的趋势操作始终发送当前观测 ID。OpenAPI、345 个生成客户端文件、前端查询键和响应模型已同步，锚点变化会形成独立查询缓存，不沿用无锚点结果。
- 单元回归和真实浏览器夹具均包含 2024/2025 同来源同方法学正样本，以及 2023 不同发布机构和方法学的诱饵负样本。`epidemiology-trend-correctness` 监听真实 `/api/v1/epidemiology-trends/{disease_id}`，断言请求锚点、响应 `anchor_observation_id`、`total=2`、稳定 ID 集合仅含两条正样本并排除诱饵。
- 首轮 Chrome 因验收按未显示的观测 ID 寻找趋势按钮导致四视口失败，并出现一次无关 comparison-sets socket hang up；改为使用表格内唯一可访问趋势按钮后，Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。
- 完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。该批完成流行病学域首个版本化正负样本结果正确性切片；专利和新闻/会议仍未覆盖，固定分母下已验证代码交付由 `83%` 保守提高到 `84%`，Commercial Production 状态不变。
- 最终内容树安全门固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260728-v1.9.22-epidemiology-trend-correctness-sealed-v2`；该证据仍需绑定干净 commit/tag 才能成为可发布候选证据。

## 2026-07-28 监管事件结果正确性与 v1.9.21

- 服务层审计确认机构、辖区、事件/状态、认定资格、标签变更、黑框警告、安全信号、严重程度、信号状态及两个日期范围均直接约束同一 `RegulatoryEvent`，规范实体/靶点映射只限定主体，没有发现跨事件拼接实现缺陷。既有证据缺少只差一个专业字段的负样本和权威响应集合断言。
- 单元回归新增一条除 `safety_status=monitoring` 外与正事件全部查询条件一致的监管事件，confirmed 查询只返回正事件。浏览器负事件使用独立药物主体以免改变既有管线统计，但关键词和所有专业条件仍与正事件一致，仅信号状态不同。
- `regulatory-result-correctness` 在提交筛选时监听生成客户端权威 `/api/v1/regulatory-event-timeline`，断言 `total=1`、唯一 ID 为 confirmed 正事件并排除 monitoring 负事件；原结果、保存订阅、刷新恢复、最多四项对比、详情抽屉和来源字段路径保持完整。
- Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。
- 该批完成监管域首个版本化正负样本结果正确性切片；流行病学、专利和新闻/会议仍未覆盖，固定分母下已验证代码交付由 `82%` 保守提高到 `83%`，Commercial Production 状态不变。
- 最终内容树安全门通过 Gitleaks、Semgrep 243 条规则/615 个目标零 findings、Python/Node 依赖审计、源码与三类镜像 SBOM、Grype 全量及 actionable High/Critical 门禁；固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260728-v1.9.21-regulatory-result-correctness-sealed`。

## 2026-07-28 交易资产组合结果正确性与 v1.9.20

- 审计确认参与方实体/角色/国家/机构类型和权益类型/地域已分别绑定同一关系行，资产模态与项目标签也绑定同一研发项目；但显式资产、靶点/适应症、研发属性、交易时阶段和当前阶段此前分别判断，交易可由资产 A 满足选中条件、资产 B 满足属性和阶段而跨资产误命中。
- 服务端现构造统一规范资产约束并注入目标/适应症、研发项目、交易时阶段和当前阶段存在性查询。单独资产、靶点或适应症仍保留历史关系兼容；一旦与其他资产维度组合，就要求同一个 `DealAssetAssociation.asset_entity_id`，没有规范证据时失败关闭。
- PostgreSQL 回归构造包含两个资产的交易：选中资产只有 small molecule/follow_on/preclinical，诱饵资产才有 antibody/first_in_class/phase 2/当前 phase 3；组合选中资产与诱饵属性必须返回零。浏览器真实交易使用同样结构，负查询断言 API `total=0` 且排除交易 ID，合法多选组合断言 `total=1` 且只返回唯一稳定 ID。
- 首轮 Chrome 为 `92/96`，原因是新验收监听了不存在的 `/api/v1/deals`，产品实际按生成客户端调用 `/api/v1/deal-transactions`。修正监听路径后 Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。
- 完整 `make check` 通过后端 `1101 passed / 34 deselected`、覆盖率 `84.88%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。该批完成交易域首个版本化正负样本结果正确性切片；监管、流行病学、专利和新闻/会议仍未覆盖，固定分母下已验证代码交付由 `81%` 保守提高到 `82%`，Commercial Production 状态不变。
- 最终内容树安全门通过 Gitleaks、Semgrep 243 条规则/615 个目标零 findings、Python/Node 依赖审计、源码与三类镜像 SBOM、Grype 全量及 actionable High/Critical 门禁；固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260728-v1.9.20-deal-asset-correctness-sealed`。

## 2026-07-27 临床四角色组结果正确性与 v1.9.19

- 临床服务层审计确认规范试验药物、联用药物、试验靶点和联用靶点分别使用独立关系存在性查询，语义为组内 OR、组间 AND。既有单元测试覆盖缺失角色，但真实浏览器只验证正样本文字可见，没有核对权威总数、稳定 ID 或高判别负样本。
- 单元回归新增一条拥有全部请求实体但把试验/联用药物和靶点角色互换的试验，并明确断言不进入结果。浏览器真实 PostgreSQL 夹具新增独立角色互换试验；查询仍包含四个规范角色组和试验药物双候选，HTTP 响应必须 `total=1`、唯一 ID 等于正样本且不含负样本。
- 负样本仍是与管线药物真实关联的临床试验，因此管线跨域信号正确增加到 2 项。首轮 Chrome 因旧总量期望为 `92/96`，更新总量后第二轮又由按钮的旧“1 项临床试验”可访问名称以 `92/96` 失败；两处均按真实事实改为 2，没有隐藏负样本、放宽超时或删除导航断言。
- 最终 Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。
- 最终内容树安全门通过 Gitleaks、Semgrep 243 条规则/615 个目标零 findings、Python/Node 依赖审计、源码与三类镜像 SBOM、Grype 全量及 actionable High/Critical 门禁；固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.19-clinical-role-correctness-sealed`。
- 该批完成临床域首个版本化正负样本结果正确性切片；交易、监管、流行病学、专利和新闻/会议仍未覆盖。固定分母下已验证代码交付由 `80%` 保守提高到 `81%`，Commercial Production 状态不变。

## 2026-07-27 管线组织关系结果正确性与 v1.9.18

- 审计发现药物与管线组合查询分别判断“项目含指定机构”和“项目含某个指定角色/类型/国家机构”，因此当原研方为 A、合作方为 B 时，`A + collaborator` 会被 B 的角色跨关系行错误补足。该问题会产生看似合理但业务语义错误的阳性结果，属于数据正确性缺陷，不是前端展示差异。
- 服务端现把机构稳定 ID、角色、类型和国家/地区绑定到同一个当前 `DevelopmentProgramOrganization` 关系存在性查询。单独机构 ID 仍保留历史 `DevelopmentProgram.organization_entity_id` 兼容；一旦附带关系属性，就只接受当前受治理关系行，不用另一机构或历史集合补齐条件。
- 判别性 PostgreSQL 回归使用同一项目中的原研方和合作方：`合作方 + collaborator + CRO + US` 精确命中一项，`原研方 + collaborator` 与 `合作方 + originator` 均为零，并核对四项 `applied_filters`。真实浏览器场景发送相同四参数，断言 API `total=1`、结果只含预期稳定项目 ID，其他真实管线记录作为负样本。
- Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均为 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`、前端 `262/262` 及全部格式、类型、OpenAPI、生产构建和部署合同。
- 最终内容树安全门通过 Gitleaks、Semgrep 243 条规则/615 个目标零 findings、Python/Node 依赖审计、源码与三类镜像 SBOM、Grype 全量及 actionable High/Critical 门禁；固定证据目录为 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.18-pipeline-relationship-correctness-sealed-v2`。
- 该批建立了组合查询结果正确性的首个版本化正负样本切片，但没有把临床、交易、监管、流行病学、专利和新闻/会议六域标成已评测。`professional_composite_query_depth` 保持代码级 `implemented`，整体体验成熟度仍受正式数据与 UAT 约束；固定分母下已验证代码交付由 `79%` 保守提高到 `80%`，Commercial Production 状态不变。

## 2026-07-27 跨页规范实体比较与 v1.9.17

- 审计发现全局实体结果能跨页保留实体 ID，但管线、临床、专利和交易只保存行 ID，加入列表时再从当前页反查规范实体，前页选择会静默遗漏；同一规范实体的多条领域记录还会重复占用 20 项限额。共享 `usePagedEntitySelection` 现持久保存行到规范实体映射，在页面和服务端排序变化期间保留全部选择，并以最近可见行替换同实体重复项。
- 全局检索也切换到同一选择合同。真实 Chrome 首轮在四视口均为 `92/96`：跳到末页后选择被清空。根因不是浏览器或 API，而是未指定类型时路由每次产生新空数组，effect 以引用变化误判查询条件变化；改为规范类型值键后，offset/排序不清理，关键词、类型或治理状态真实变化仍按原合同清理。
- 真实 205 条 PostgreSQL→outbox→OpenSearch→HTTP→Web 结果用于判别性验收：名称排序后在第一页和末页各选一项，UI 保持 `2/20`，批量写入请求严格包含两个稳定实体 ID，成功后选择清零。场景加入 `pharma.browser-acceptance.v8` 与发布证据必需集合，不使用 mock、浏览器缓存事实或当前页拼接。
- 最终 Google Chrome、Edge `150.0.4078.99`、Edge `149.0.4022.98` 均 `96/96`，四视口各 `24/24`，快照只读且临时账号、实体和入库夹具均为 `0`。完整 `make check` 通过后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`、前端 `262/262` 以及全部格式、类型、OpenAPI、生产构建和部署合同。
- 最终内容树安全证据固定在 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.17-cross-page-comparison-sealed-v2`。该批提高密集结果操作的实现深度，但正式授权数据和专业用户 UAT 未完成，因此 `dense_result_operations` 保持 `partial`；固定分母下已验证代码交付由 `78%` 保守提高到 `79%`，Commercial Production 状态不变。

## 2026-07-27 Edge 双版本兼容与 v1.9.16

- Microsoft Edge 当前版 `150.0.4078.99` 与前一主版本 `149.0.4022.98` 由 `bootstrap-wsl-edge.sh` 通过 Microsoft 签名仓库、密钥指纹和包摘要校验后缓存安装；验收脚本记录真实四段版本，不接受无法归属的浏览器产品或 channel。
- 两个 Edge 版本分别复用 Chrome 仓库基线执行只读完整套件，均为 `96/96`；`1440x900`、`1920x1080`、`1024x768`、`390x844` 各 `24/24`，`snapshots_updated=false`。覆盖公开/内部登录、双工作台隔离、十二域导航、专业查询/详情、保存订阅、受控导出、权限与恢复、RDKit、WCAG 2.2 A/AA、320px 键盘重排、LCP/INP/CLS 和空态/密集态像素比较。
- Edge 150 用时约 `228337 ms`，Edge 149 用时 `226092 ms`；两轮结束后临时账号、实体和入库夹具均为 `0`，报告不记录凭据。没有发现需要浏览器专属 CSS、条件分支、阈值放宽或快照更新的差异。
- 完整 `make check` 重新通过后，最终内容树安全门通过 Gitleaks、Semgrep 243 条规则/614 个目标零 findings、Python/Node 依赖审计、源码与 API/PostgreSQL/OCR SBOM、Grype 全量及 actionable High/Critical 门禁；不可覆盖证据目录为 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.16-edge-compatibility-sealed`。
- 证据边界：该批关闭受支持 Edge 当前/前一主要版本的本地自动兼容缺口，但不替代 Windows 企业策略、操作系统缩放、人工辅助技术、生产 RUM P75、批准参考流程人工差异评审和专业用户 UAT。两个相关体验门禁因此仍保持 `partial`，固定分母下已验证代码交付由 `77%` 保守提高到 `78%`，Commercial Production 状态不变。

## 2026-07-27 密集结果双状态视觉回归与 v1.9.15

- 既有密集结果性能检查点只验证 LCP/INP/CLS，像素基线因运行键进入可见文本和虚拟表格 full-page 高度变化而撤下。本批从根因改造真实夹具：205 条实体使用固定规范名、外部标识和时间，随机运行键仅保留在用于并发隔离的别名中；表格 shell 截图只遮罩服务端命中解释，不遮罩业务列，不放宽 `maxDiffPixelRatio=0.001`。
- 视觉清单升级为 `pharma.workbench-visual-baselines.v2`：四视口各维护空结果 full-page 与真实密集结果 table-shell 两种状态，共八张仓库自有 PNG，每个文件固定 viewport、state、capture 和 SHA-256。浏览器报告升级为 `pharma.browser-acceptance.v8`；发布证据和外部参考配对工具严格解析 v2，旧 v1 或字段/状态组合漂移均失败关闭。
- 人工检查首次新基线发现 `1920x1080` 下表格数据行只占约 1100px、平板工具栏命令文字被挤压换行。`VirtualDataTable` 现以列最小宽度加权 `fr` 伸展、表格 `width:100%` 与像素 `min-width` 保留窄屏横向滚动；1100px 以下工具栏允许自然换行，命令控件禁止压缩文字。组件测试锁定宽度与 grid track 合同。
- 最新应用镜像运行健康。显式基线更新轮真实 Google Chrome `96/96`，随后默认只读轮再次 `96/96`、四视口各 `24/24`、`snapshots_updated=false`；临时账号、实体和入库夹具均为零，未记录凭据。四张密集基线逐张人工复核：宽屏数据行铺满、平板工具栏无重叠、桌面和移动未出现新遮挡。
- 完整 `make check` 通过：后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`，前端 `260/260`，Ruff、Mypy、Biome、TypeScript、OpenAPI、生产构建与部署合同全绿。完整安全门通过 Gitleaks、Semgrep 243 规则/614 目标零 findings、Python/Node 依赖审计、源码和 API/PostgreSQL/OCR SBOM、Grype 全量及 actionable High/Critical 门禁；最终仓库外证据目录为 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.15-dense-visual-v2-final`。
- 证据边界：该批关闭本地 Chrome 的密集结果确定性像素回归和响应式缺陷，不等于 Edge 当前/前一主版本、生产 RUM P75、操作系统缩放、人工辅助技术、授权参考差异评审或业务 UAT 已通过。因此性能/视觉与状态/可访问性体验门禁仍保持 `partial`，固定分母下已验证代码交付从 `76%` 保守提高到 `77%`，Commercial Production 状态不变。

## 2026-07-27 专业实体候选消歧与 v1.9.14

- 已授权参考证据沿用 2026-07-26 真实临床结果查询：输入 `帕博利珠单抗` 后，参考候选明确区分原研、生物类似药、改良剂型和复方/联用方案，并展示英文名、别名、创新类型与独立详情；提交两个规范药物后以 OR 执行。本批只映射公开可观察交互，不保存参考明细、凭据或私有接口载荷。
- 平台根因是后端已经返回权威 `match`，但候选层只有规范名和一个外部 ID，且 API 未返回实体别名。`EntitySearchItemRead` 现在以向后兼容加法返回最多 20 个按规范化别名稳定排序、大小写去重的别名；命中原因继续来自服务端 canonical/alias/external ID/description/semantic 解释，不由浏览器猜测。
- 新的共享 `EntitySearchOption` 同时服务严格单选和最多 20 项的多选控件，显示规范名、命中原因、别名、外部标识，并只读取英文名、创新类型、Modality、药品类别、机构类型、国家/地区六个白名单属性；任意字典字段不会自动进入人员界面。长文本允许换行，移动视口改为纵向候选标题，避免省略号隐藏关键消歧信息。
- API 回归覆盖别名精确命中、跨实体类型命中和 25 个别名输入时稳定截断为前 20 个；组件回归同时覆盖单选/多选命中解释、别名和专业属性。完整 `make check` 为后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`、前端 `260/260`，OpenAPI `345` 个生成文件无漂移，生产构建与部署合同通过。
- 新镜像运行栈状态全绿。真实 PostgreSQL → outbox → OpenSearch → HTTP → Web 夹具通过别名召回规范抗体候选，验证显示规范名、别名精确命中、英文名、创新类型、Modality 后选择稳定 ID，并继续完成临床四角色组组内 OR/组间 AND、查询与刷新恢复。真实 Google Chrome 四视口最终 `96/96`，每个视口 `24/24`；临时账号、实体和入库夹具清零，未记录凭据。
- 完整安全门随后闭合：首次 Grype 数据库 HTTP/2 分段在单段反复复位后，下载器固定 HTTPS/TLS 1.2 + HTTP/1.1，并继续强制 Range 长度、固定数据库摘要、有限重试和导入验证；回归测试锁定该协议。最终 Gitleaks 无泄漏，Semgrep 243 条规则扫描 614 个目标且 0 findings，Python/Node 依赖审计、源码和三类镜像 SBOM、API/PostgreSQL/OCR 全量 Grype 及 actionable High/Critical 门禁全部通过；包含本批最终代码、测试和文档的仓库外证据目录固定为 `pharma-intelligence-runtime/evidence/security/20260727-v1.9.14-entity-disambiguation`。
- 证据边界不变：正式授权数据覆盖、参考产品完整业务 UAT、干净 Git checkpoint 和目标生产环境仍未闭合；安全证据绑定当前内容树摘要但还没有可审查 commit/tag，因此固定分母下把已验证代码交付从 `74%` 保守提高到 `76%`，不提高商业生产就绪状态。

## 2026-07-27 研发机构角色全链路与 v1.9.13 P0 收束

- 机构关系不再压扁为研发项目的单个自由文本名称。`DevelopmentProgramOrganization` 以 `organization_set_version` 保存只追加历史集合，角色限定为 originator/collaborator/licensee 等受控值，并保留规范机构 ID、机构类型和国家/地区；PostgreSQL 强制 RLS，更新和删除触发器失败关闭。治理发布以 originator 维护遗留主机构投影，只提供 `organizations` 的载荷也能稳定生成项目身份，重复回放不重复项目或关系。
- `pharma.pipeline.search.v13` 只读取当前机构集合，并把机构名称全文命中、规范实体关联、角色/类型/国家地区筛选、分面和竞争格局统一到领域服务。相同语义已经进入人员 HTTP、稳定 URL、保存检索回放、受控 CSV/JSON/XLSX 导出、收费 Agent API、MCP、OpenAPI 生成客户端和前端结果表；表格展示全部当前合作关系及角色/地区，不从页面文本猜测。
- 当前批次的判别性测试覆盖历史集合不污染当前结果、originator 唯一性、重复关系拒绝、治理幂等、q/实体/角色/类型/地区查询、格局统计、非法参数拒绝、商业预留身份、MCP/导出透传和 URL 刷新恢复。完整 `make check` 通过：后端 `1100 passed / 34 deselected`、覆盖率 `84.87%`，前端 `260/260`，Mypy `293` 个源文件、OpenAPI `345` 个生成文件、生产构建与部署合同均通过；隔离 PostgreSQL 升级/降级/再升级到 `e2b7c4a1f639` 通过。
- 统一运行栈已升级到 `e2b7c4a1f639`，状态和 RLS 验证通过。真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四视口通过 `96/96`，每个视口 `24/24`；机构筛选进入 URL 和真实 API，刷新后保持，测试后临时账号、实体和入库夹具清零且未记录凭据。
- 证据边界：完整 `make security-check` 在 OCR 镜像从官方源下载锁定 NumPy wheel 时阻塞，尚未进入 Secret/SAST/SBOM/漏洞扫描，因此不能记为安全通过。正式授权机构数据覆盖、专业用户 UAT、干净 Git checkpoint 和目标生产环境仍是独立门禁，本批只把固定分母下的已验证代码交付从 `72%` 上调到 `74%`。

## 2026-07-27 研发状态受控治理（program_status）

- 首轮审计确认的 M-L 级缺口：项目状态此前只有自由文本 `status_detail`，没有受控口径、不可筛选、无分面，仅能排序和导出；结果表却用标签映射把任意文本按已知状态渲染，未映射值直接显示原始 token，形成"看起来是治理值、实际是自由文本"的错觉。
- 新增受控列 `program_status`（`active`/`inactive`/`unknown`，`CheckConstraint` + 索引，迁移 `d1a6b3f9e528`）。迁移回填**只**提升三个精确受控 token，其余一律留 NULL——不按关键词猜测归桶。治理发布层优先采用模型直出的受控字段，否则只在自由文本恰为受控 token 时提升，其他保持 NULL；AI 抽取合同 `ProgramFact` 同步增加该受控可选字段。
- 全链路贯通：领域层筛选（单值枚举）、分面、`applied_filters` 回显、`PipelineSavedSearchQuery`（受控 Literal，非法值失败关闭）、人员 HTTP、导出模型/调用/字段目录/白名单、稳定 URL（非受控值不写入）、保存/回放。合同版本沿用 `pharma.pipeline.search.v10`（本批为同版本内的可选字段增量，无破坏性变更）。
- 结果列改为权威语义：徽章只呈现受控词表；无治理值时显示"状态未治理"并把原始来源文本作为副标题保留，二者不再混淆。判别性测试覆盖三面——受控筛选精确命中、自由文本项在无筛选时可见但不进任何分面桶且 `program_status` 为 NULL、保存合同拒绝词表外取值；组件测试断言未治理项不渲染任何受控徽章文案。
- 后端管线测试 9/9、前端 `259/259`。真实浏览器四视口验收随后执行；值覆盖仍取决于正式授权数据源的治理入库。

## 2026-07-27 资讯规范实体条件贯通（news_search@1 补齐）

- 首轮审计确认的部分缺口：新闻域领域层早已支持 `entity_id` 规范实体过滤（发布方或关联实体命中），实体档案的资讯分区也依赖它，但人员 HTTP、保存合同与受控导出均未开放。本批贯通：`/api/v1/news-events` 暴露 `entity_id`（36 位校验），`NewsSavedSearchQuery` 增字段并计入"至少一个筛选"，监控匹配器在变更实体关系之外叠加保存条件实体的第二个关联子句（AND 语义，回放保持精确保存语义），导出模型/调用/Web 白名单三处同步，稳定 URL `entity_id` 参数与已应用条件条（"关联实体"标签，可见可清除）、保存/回放逐字段恢复。
- 范围边界如实登记：新闻关联实体横跨药物/靶点/疾病/机构四类，现有 `EntityFilterSelect` 为严格单类型组件；本批以"跨域回钻进入 + 条件条治理 + 保存/订阅/回放"交付该条件（与实体档案资讯分区的既有研究动线一致），页内多类型规范选择器登记为后续组件项，不以单类型选择器冒充完整消歧。
- 后端资讯/监控/对比 27 项、前端 `258/258` 通过；完整 `make check` 退出码 0。

## 2026-07-27 密集结果性能预算检查点（webvitals 扩展）

- 首轮审计未验证尾部证实：LCP/INP/CLS 预算此前只在总览与空态检索一处执行，密集表格路径零性能门禁。`[browser-quality]` 场景在 205 条真实夹具的分页流程后新增密集检查点：全新导航进入密集实体表（init script 按导航重置 vitals）、真实表头排序交互产生 INP，随后执行与首检查点相同的 LCP≤2500ms/INP≤200ms/CLS≤0.1 断言，指标以独立 `dense-results-quality-metrics` 注解入报告。四视口两轮（基线更新轮与裸跑轮）预算断言全部通过。
- 同点位曾尝试为密集视图建立第二组像素基线，经三轮迭代确认其先天非确定：夹具键逐轮随机使行内文本变化（遮罩可治），而虚拟化表格异步行测量使 fullPage 高度在窄视口逐轮不同（1046 vs 1632px，遮罩不可治）。按"非确定性必须显式处理、不得放宽 maxDiffPixelRatio 吸收"的纪律，撤下该截图仅保留性能预算；确定性的空态基线继续作为视觉锚点，密集视图像素回归登记为需要种子化定高夹具设计的后续项，不静默销项。
- 最终真实 Chrome 四视口 `96/96`，裸跑无失败、无快照更新。

## 2026-07-27 实体检索排序纳入保存合同（entity_search@1 补齐）

- 首轮审计未验证尾部证实的缺口：`entity_search@1` 是八域中唯一不保存服务端排序的合同——保存后回放固定回到相关性降序，用户显式选择的名称/类型/更新时间排序丢失。`EntitySearchQuery` 增 `sort_by`/`sort_direction`（默认 relevance/desc，旧保存 JSON 兼容），保存链携带当前已应用排序，监控回放恢复完整排序状态；监控匹配为存在性查询不受排序影响。
- 同批核销一条过时候选：`declared-sort-fields-unreachable` 复核为大半过时——流病实际 5/9、监管 5/8 排序字段可从共享表直达（首轮登记时低估了 `id:` 形态的可排序列），剩余为次要字段且 URL/保存排序在服务端仍完整执行；不再为其添加低信息密度列。
- 前端 `258/258`；行级对比批次同轮完成第五轮真实 Chrome 四视口 `96/96` 裸跑零快照更新。

## 2026-07-27 行级选择与加入对比扩展到六个结构化工作域

- 首轮审计未验证尾部确认的真实缺口：共享结果表的受控行选择与"加入对比"此前只接了全局检索与监管（后者为专属四事件对比）。本批把管线、临床、专利、交易四域接入同一对比列表链路：行选择上限 20、全选当前页、清空、加入时携带列表期望版本、版本冲突在对话框内可恢复。
- 复用收敛：新增共享 `AddToComparisonControl` 封装选单查询、原子批量写入、缓存更新与反馈，四域各以行→规范实体映射接入（管线行→去重药物实体、临床行→试验实体、专利行→专利实体、交易行→交易实体）。全局检索后续可迁移到同一控件，不新增第二套写入语义。
- 范围边界如实登记：流行病学与新闻的行是观察记录/资讯事件而非可对比的规范实体，不接入实体对比；监管域保留其专属的最多四项事件对比机制。该边界与对比列表"稳定实体 ID、最多 20 条"的权威合同一致。
- 交易域一处既有测试按列索引取排序表头，复选列引入后索引位移——改为按可访问列名定位，无断言放宽。前端 `258/258`。

## 2026-07-27 药物分类维度权威建模（创新类型/适应症领域/药品类别，pharma.pipeline.search.v10）

- GOAL §5.1.1.2「分类与标签」族要求创新类型、适应症领域、药品类别等多维可组合条件；此前三个概念全仓零建模。本批按 `modality` 的既有范式补齐权威层：`DevelopmentProgram` 新增三个可空索引列（Alembic `c9f5a2e8d417`），治理 `ProgramFact` 增加三个受长度约束的抽取字段并在发布路径写入权威列——不发明临床受控词表，取值由治理入库产生，与 modality 一致（GOAL §21：本体错误合并比漏合并风险更高）。
- 查询合同升级 `pharma.pipeline.search.v10`：三维各支持最多 20 值多选，组内 OR、组间 AND；facet、`applied_filters`（`in`）、保存合同（旧单值 JSON 规范化、空列表拒绝）、监控回放、稳定 URL 重复参数、受控导出（模型/调用/白名单/重复集合）、人员 HTTP、收费 Agent API 与 MCP（`_canonical_repeated_filter` 合并复数参数）全链路贯通；`CompetitiveProgramRead` 公开三字段。
- Web：管线工作台新增三个与模态同构的 `FacetMultiSelect` 分面复选，选项完全由服务端 facet 供给——真实数据到位前 facet 自然为空，不出现前端虚构选项或虚假可用维度。
- 判别性测试：组内 OR（两创新类型命中 2）、组间 AND（biosimilar∩oncology 命中 1）、无值维度零命中、facet 计数与 `applied_filters` 回显。后端 `1095/1095`、前端 `258/258`、Alembic 单头回环通过。
- 边界如实登记：列与链路已就绪，但三个维度的取值覆盖依赖正式授权数据源的治理入库；空数据状态下筛选维度可见但无可选项，这是与 modality 相同的既有产品行为，不构成"能力已交付"的商业声明。
- 统一运行镜像重建（含迁移 `c9f5a2e8d417`）后，真实 Google Chrome 四视口 `96/96`（3.9 分钟）：管线三个新分面控件经 `--update-snapshots` 进入像素基线，裸跑复验无失败、无快照更新。

## 2026-07-27 专利域条件深度：规范实体与优先权/到期日期窗口

- 对标审计第 5 节长期记录专利域"只支持关键词/申请人/法律状态三个条件"，而领域层 `entity_id` 规范实体过滤早已存在（收费 Agent API/MCP 在用），人员 HTTP 却未暴露；优先权与到期日期窗口则在全链路缺失。GOAL §5.1.1.2「专利与权益」族要求化合物/序列专利到期时间窗可组合查询。
- 领域层 `_patent_filters` 增加 `priority_from/to`、`expiration_from/to` 闭区间条件；`search_patent_families` 暴露五个新参数并回显进 `applied_filters`（gte/lte）。`PatentSavedSearchQuery` 增 `entity_id` 与四个日期字段：全部计入"至少一个筛选"，反向区间失败关闭；监控匹配经共享 `_saved_date_start/_saved_date_end` 转为当日闭区间语义。
- 人员 HTTP `/api/v1/patent-families` 暴露 `entity_id` 与四个日期参数（`_validated_utc_datetime_range` 校验）；导出模型、导出调用与 Web 导出白名单同步扩展（沿用交易域"导出集=列表集"的教训），`_BoundedExportQuery` 区间校验对补齐两组日期。
- 专利前端从 6 位置参数形态重构为与监管/流病/新闻一致的打包 `PatentSavedSearchInput` 架构：查询键、请求构造、保存、排序、分页、格局回钻、清除全部走同一输入对象；URL 增加 `entity_id`（UUID 校验）与四个日期参数，保存回放逐字段恢复。筛选栏新增规范实体选择器与优先权/到期两组日期控件。
- 判别性测试：日期窗口内 1 命中、窗口外拒绝、`applied_filters` 回显、空窗口下 landscape 总量同步为零；契约与导出测试同步更新。前端 `258/258`、后端专利/契约/对比 21 项全绿；完整 `make check` 退出码 0。
- 统一运行镜像重建后，真实 Google Chrome 四视口 `96/96`（3.9 分钟）：专利筛选栏新增的规范实体选择器与两组日期控件经 `--update-snapshots` 进入像素基线，裸跑复验无失败、无快照更新。正式授权数据与专业用户 UAT 仍是独立门禁；本批不改变能力矩阵状态。

## 2026-07-27 监管、流行病学与资讯同查询统计分析闭环（八域 landscape 齐平）

- 继专利批次后，本批把监管、流行病学、新闻三域接入同查询统计分析，至此八个结构化工作域全部具备"列表、统计、回钻共享同一服务端查询"的 GOAL 门禁能力，`dense_result_operations` 的四域代码缺口全部关闭。
- 服务端：`RegulatoryLandscapeRead`（事件类型/监管机构/决定年份）、`EpidemiologyLandscapeRead`（统计口径/地区/人群口径）、`NewsLandscapeRead`（事件类型/会议期刊/发布年份），全部由数据库对完整授权命中集聚合，缺失值为显式 `__missing__` 桶；标量分布收敛到共享 `_landscape_scalar_buckets` 助手，年份用跨引擎 `func.extract`。每域各有"全集≠当前页"判别性测试（单条页长下总量与桶不塌缩、随筛选变化）。
- 前端：统计组件泛化为配置驱动的 `DomainLandscape`（专利批次的组件改为薄壳配置），监管/流病按打包 filters 模式并入 `displayMode`/`analysisView`，新闻把既有 `list|timeline` 展示轴扩展为三值 `list|timeline|landscape` 并保留"时间线必须 research 口径"的既有约束。回钻映射：监管 事件类型→event_type、机构→agency；流病 口径→measure、地区→geography、人群→population_scope；新闻 事件类型→eventType、会议→venue；年份桶只读。
- 保存/订阅：三域 saved 合同补 `display_mode`/`analysis_view`（默认值兼容旧 JSON，运行时验证新闻 timeline 约束不受影响），守卫排除展示字段，监控回放恢复完整展示状态；稳定 URL 使用 `display=landscape`/`analysis_view=table`。
- 后端全量与前端 `258/258` 通过，OpenAPI 344 文件重生成无漂移；完整 `make check` 退出码 0。
- 统一运行镜像重建后，真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 通过 `96/96`（4.0 分钟）：四域新增的列表/统计切换控件经 Chrome 专属 `--update-snapshots` 进入像素基线，随后裸跑复验无失败、无跳过、无快照更新。正式授权数据与专业用户 UAT 仍是独立门禁；本批不改变能力矩阵状态。

## 2026-07-27 专利同查询统计分析（landscape）闭环

- GOAL 第 5.1.1.1 节"同查询统计分析"门禁要求列表、统计、回钻和受控导出共享同一服务端查询。管线、临床、交易已具备该能力，专利域此前只有列表与 facet——`dense_result_operations` 的四域代码缺口（专利/监管/流病/新闻）由本批关闭第一个。
- `PatentFamilySearchResult` 新增 `landscape`：数据库对完整授权命中集聚合法律状态分布（含显式 `__missing__` 桶）、前 8 申请人和优先权年份（`func.extract` 跨引擎），占比按全集计算；缺失值标注"未披露"而非静默丢弃。判别性后端测试验证"全集≠当前页"（3 条夹具、单条页长下 landscape 仍报 3）与"随筛选变化"。
- 展示状态照临床批次范式：`display=landscape`/`analysis_view=table` 进稳定 URL，`PatentSavedSearchQuery` 增 `display_mode`/`analysis_view`（默认 list/chart 兼容旧 JSON），`hasPatentSearchFilter` 排除展示字段防守卫恒真；监控回放恢复完整展示状态。
- 新 `PatentLandscape` 组件复用交易域三段式与既有 `pipeline-landscape-distribution` 样式：法律状态回钻 `legal_status` 筛选、主要申请人回钻 `applicant`、优先权年份只读；图示/语义表格由 URL 所有状态受控切换，`__missing__` 桶禁止回钻。
- 后端专利与契约测试 8/8、前端 258/258、Ruff/Mypy/Biome/tsc 干净，完整 `make check` 退出码 0。真实浏览器四视口验收与正式授权数据仍是独立门禁，本批不改变能力矩阵状态。

## 2026-07-27 档案路由 WCAG 审计接入与真实 Chrome 四视口全绿

- 新增 `[accessibility-dossier]` 场景把 `target`/`drug`/`company`/`disease`/`entity` 五条实体专业档案路由纳入 axe WCAG 2.2 A/AA 审计；此前 axe 只覆盖 14 个列表型工作域，五条档案路由约 3400 行独有 UI 从未被扫描。场景注册进验收脚本场景表并由浏览器运行时契约测试锁定。
- 首跑即在全部四视口抓出真实违规，全部为 `color-contrast (serious)`：三个弱化文本色在档案页 560+ 节点系统性低于 AA（`#71838c` 3.63–3.94:1、`#6d7f88` 3.84:1、`#60737d` 4.23:1，字号 9–11px 普通字重）。首轮只修四条档案专用规则不收敛后，改为弱化色板全局 AA 化：`#71838c`/`#6d7f88` → `#5a6b74`（最深底 `#f4f6f7` 上 5.12:1），`#60737d` → `#53646d`（`#e8eef1` 上 5.24:1），共 29 处、组件无内联残留。更深的替代色在任何更浅底色上只会更合规，14 个列表域审计继续通过。
- 修复后 mobile-390 仍暴露第二类违规 `scrollable-region-focusable (serious)`：档案表格容器在 390px 横向滚动时无键盘访问（桌面视口不溢出故不触发）。按仓库既有钦定模式（`VirtualDataTable` 的滚动视口）把五个档案视图的 14 处 `table-frame` 改为 `section aria-label + tabIndex={0}`，闭合标签同步，Biome a11y 规则以同一 biome-ignore 说明豁免。
- R5b/v9 引起的控件形态变化同步进验收驱动：专业查询编排器的项目标签/里程碑类型改 `fill`，管线工作台的药物模态/项目标签断言改为与交易域一致的展开-复选模式；无断言放宽、无超时延长。
- 过程中确认并记录一个运维事实：`run-browser-acceptance.sh` 不重建应用镜像——spec 从宿主树执行、被测应用来自容器镜像，改动前端产品代码后必须先 `make up-observed` 再验收，否则测的是旧 bundle。色板修复后未重建的一轮"失败"即此类假结果，重建后失败根因立即更替，证明修复实际生效。
- 视觉基线因有意的合规色改按 Chrome 专属 `--update-snapshots` 机制重生成。最终裸跑真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `96/96`（3.9 分钟），无失败、无跳过、无快照更新；`[accessibility-dossier]` 四视口全绿。
- 本批把 `state_accessibility_and_responsive_quality` 的代码级覆盖缺口（档案路由从未被审计）关闭并取得本地四视口证据；该门禁仍保持 `partial`，因为人工辅助技术测试、操作系统级缩放、生产 RUM P75 与专业用户 UAT 未闭合。

## 2026-07-27 管线模态与项目标签多选专业查询（pharma.pipeline.search.v9）

- GOAL 第 5.1.1.2 节「分类与标签」族要求 Modality 与药品标签等维度支持多选组合；交易域已在 `pharma.deal.search.v6` 落地同一语义，管线域此前仍是单选。本批把管线 `modality` 与 `program_tag` 升级为最多 20 个去重值的多选条件：组内 OR、组间 AND，查询合同版本升级为 `pharma.pipeline.search.v9`。
- 服务端语义完全对齐交易先例：`DevelopmentProgram.modality` 用集合成员匹配，`program_tags` 按任一选中标签存在匹配；`applied_filters` 回显从 `eq` 变为 `in`。人员 HTTP 与收费 Agent API 使用重复查询参数（上限 20、去重、逐值长度约束），MCP `get_competitive_pipeline` 保留既有单值参数并新增 `modalities`/`program_tags` 复数参数，由既有 `_canonical_repeated_filter` 合并；商业预留请求身份按集合语义绑定。
- 保存/订阅兼容：`PipelineSavedSearchQuery` 与导出模型的 before-validator 把旧单值字符串规范化为单元素列表，旧 URL、旧保存 JSON 与旧 MCP 单值参数语义不变；监控消费者经同一过滤构造器复用 v9 语义，无需重放迁移。
- 修复一个连带发现的既有 P0 契约缺陷：交易与管线的多选 before-validator 此前把空列表原样返回，`[] is not None` 会通过"至少一个筛选"校验，形成不施加任何条件的全库订阅（GOAL 明令失败关闭）。两处 validator 现将空集合规范化为 None，并有直接断言 `{"asset_modality": []}` / `{"modality": []}` 被拒绝的回归测试。
- Web 侧：管线工作台的模态与项目标签控件从单选下拉换成与交易一致的 `FacetMultiSelect` 分面复选；格局回钻在多选语义下写入单元素集合；稳定 URL 使用重复参数，旧单值深链解析为单元素集合。全局专业查询编排器维持单选输入，但在边界统一映射为集合。
- 判别性后端测试：三条程序夹具验证组内 OR（两模态命中 2 条、两标签命中 2 条）与组间 AND（antibody∩first_in_class 为 0）；旧单值规范化与空列表拒绝各有独立断言。后端 `1088/1088`、前端 `258/258` 通过。
- 同类客户端守卫一并修复：`hasPipelineSearchFilter` 原实现对空数组返回真（`[] !== ""`），会让"无筛选禁止保存/订阅"前端守卫在多选字段引入后恒失效；现按数组长度判定并有直接回归断言。交易侧经复核不受影响（其守卫基于空数组已折叠为 `undefined` 的保存查询）。
- 本批不改变能力矩阵状态；真实浏览器四视口验收、正式授权数据与专业用户 UAT 仍是独立门禁。

## 2026-07-27 临床格局图示/表格视图纳入 URL 与保存合同

- GOAL 密集结果门禁要求统计"视图…可刷新、分享、前进后退"。临床格局的图示/表格切换此前是组件内 `useState`，两张矩阵各自独立、刷新即回图示；且 `clinical_trial_search@1` 合同连 `display_mode` 都未保存，监控回放永远回到列表模式——管线与交易域的同类状态早已进入 URL 与保存合同。
- `ClinicalTrialLandscape` 受控化：`analysis_view` 进入稳定 URL（默认图示不写冗余参数）、两张矩阵共享同一状态；`ClinicalTrialSavedSearchQuery` 追加 `display_mode`/`analysis_view` 展示状态字段（默认 list/chart，旧保存 JSON 兼容已运行验证，非法值失败关闭）。展示状态不改变事实查询，监控消费者过滤语义不受影响。
- 保存链路带上两个字段，`hasTrialSearchFilter` 显式排除展示字段以免其默认值使"无筛选禁止保存"守卫恒真；监控中心回放恢复 `display=landscape&analysis_view=table` 完整状态。组件测试改为受控语义（点击→回调→重渲染断言），路由往返新增 `analysis_view` 断言。前端 `258/258` 通过。
- 本批不改变能力矩阵状态；真实浏览器四视口验收仍待运行。

## 2026-07-27 清除专业查询编排器的前端自造枚举

- 对标审计第 2 节规则要求"枚举由版本化领域契约定义，禁止前端自造选项"。全局专业查询编排器此前为管线"项目标签"硬编码 4 个选项、为"里程碑类型"硬编码 5 个选项，而两个字段在权威模型与查询契约中都是受长度约束的自由文本，没有任何服务端词表：这些下拉是前端虚构的枚举，会把用户可查询的值错误地限制在虚构清单内。
- 两个控件改为与后端语义一致的自由文本输入（240/120 字符上限）。受治理取值的选项呈现继续由管线工作台内的服务端 facet 提供（该路径本就存在），编排器不再自造清单。既有组件测试经 label 驱动不受影响，`258/258` 通过。
- 建立真正的受控词表属于"分类与标签"族的领域建模批次（创新类型/适应症领域/药品类别同批），需要权威模型、迁移与治理词表，不在本微批范围。

## 2026-07-27 权威计数、导出查询一致性与实体检索查询契约修正

本批不新增业务功能，只关闭三个已确认的正确性与契约缺口，并补齐一条从未被覆盖的可访问性审计路径。三项缺口均由仓库内代码证据确认，不依赖参考产品新证据。

### 1. 靶点全景概览停止在浏览器端补造事实

- `TargetDossierResponse` 曾是唯一没有服务端 `summary` 的实体档案响应（公司、疾病、药物均已有），靶点概览因此在浏览器端自行汇总。原实现在 `TargetView.tsx` 用 `programs.length` / `trials.length` / `patents.length` / `regulatory.length` 统计截断后的展示数组，与同屏 `coverage[].total` 自相矛盾；阶段分布同样由截断数组 `reduce` 得出。
- 其中两处是独立于截断的判定错误：`legal_status?.toLowerCase().includes("active")` 会把 `Inactive` 计为有效专利（`"inactive".includes("active")` 为真）；`overall_status?.toLowerCase().includes("recruit")` 会把 `Active, not recruiting` 与 `Not yet recruiting` 计为招募中。两个来源字段在权威模型中都是自由文本列，无枚举约束。
- 服务端新增 `_target_dossier_summary`，全部计数由数据库对完整授权结果集聚合。受治理字段直接权威聚合：项目阶段是数据库 Enum，监管 `event_type` 有 CheckConstraint（批准口径固定为 `approval` 与 `conditional_approval`）。自由文本状态由版本化词表 `target-dossier-status@1` 按归一 token **精确匹配**，不使用子串包含；词表外的取值计入新增的 `unclassified_trial_status_count` 与 `unclassified_patent_status_count`，在界面显式提示"来源状态未受治理，未计入统计"，不静默错分。
- 测试经过判别性验证而非仅跑绿：把精确匹配改回子串匹配后 `active_patent_count` 由 2 变 3 并失败；把 summary 改为从截断记录取值后 `clinical_trial_count` 由 6 变 1 并失败。

### 2. 受控导出与结果列表恢复同一查询集

- 交易域的 `asset_entity_id`、`target_entity_id`、`disease_entity_id`、`asset_modality`、`asset_program_tag` 五个条件存在于稳定 URL，服务端 `_DealExportQuery` 与 `search_deals` 调用也早已支持，但 Web 导出目录白名单缺这五项，`currentDomainExportQuery()` 按白名单取参时被静默剥离，导出集因此大于屏幕结果集。
- 流行病学域的 `disease_entity_id` 缺口更深：Web 白名单、`_EpidemiologyExportQuery` 与调用处三处均缺失，尽管领域查询本身支持该参数。本批同时补齐三处。
- 监管域经复核**不是**缺口，其白名单与导出模型字段一一对应，未作改动。
- 后端新增两条判别性用例，直接断言引擎收到的条件；前端新增两条 URL→导出查询的契约用例。

### 3. 全局实体检索接入统一查询契约元数据

- `SearchResult` 与 `AgentEntitySearchResult` 曾是仅有的两个不继承 `QueryResultMetadata` 的检索响应，七个专业域均已继承。两者现均返回 `query_schema_version="pharma.entity.search.v1"`（复用导出侧既有版本常量，非新造）与服务端规范化的 `applied_filters`。
- ExplorerView 的"当前条件"区此前由随每次按键变化的草稿 state 驱动，而 URL 与实际查询只在提交时更新，因此未提交的输入会被显示成已应用状态。现改用共享 `AppliedFiltersBar` 渲染服务端 `applied_filters`，与其余六个视图一致。新增回归用例断言输入未提交时该区域不变。
- 本批未给实体检索编造 `coverage` 或 `warnings` 文案：导出侧已将 entities 的 warnings 定义为真实空列表，`as_of` 因实体检索经异步投影存在新鲜度语义分歧，留待独立批次连同投影水位一并处理，不在本批用 `now()` 冒充数据时点。

### 4. 实体专业档案纳入 WCAG 自动审计

- axe 审计此前只覆盖 14 个列表型工作域，`target`/`drug`/`company`/`disease`/`entity` 五条实体档案路由从未被扫描，而这五条由独立组件渲染，含列表视图不存在的标签组、覆盖网格与溯源抽屉。design-qa 历史记录中该门禁的 partial 理由只写过外部阻塞项，从未记录这条代码级覆盖缺口。
- 新增 `[accessibility-dossier]` 场景覆盖五条路由，并注册进验收脚本场景表与浏览器运行时契约测试。所用夹具 ID 均为验收脚本既有导出值，无新增外部依赖。

### 边界

- 本批只提升代码与本地验收证据，不改变任何能力矩阵状态。`dense_result_operations`、`personal_productivity_and_delivery`、`state_accessibility_and_responsive_quality` 与 `performance_and_visual_regression` 继续保持 `partial`：正式授权数据覆盖、专业客户 UAT、生产 RUM 和人工参考差异评审均未闭合。
- 新增的 axe 场景需在真实 Chrome 四视口运行后才能作为门禁证据；本批仅完成代码与契约测试，浏览器验收结果不在本记录中预先声明。

## 2026-07-27 临床试验四角色组规范实体查询闭环

- 授权 NextPharma 临床结果查询将试验药品、联用药品、试验靶点和联用靶点分成四个规范实体选择器。本平台据此升级为 `pharma.clinical_trial.search.v8`：每组最多 20 个去重稳定实体 ID，组内 OR、组间 AND；旧 `role_entity_id/role_entity_ids + role_entity_role` 仅保留历史深链兼容，新工作流不再使用单角色选择器或名称模糊搜索冒充实体消歧。
- 四组条件已经贯通 PostgreSQL 领域查询、HTTP、收费 Agent API、MCP、服务端 `applied_filters`、稳定重复 URL 参数、类型化保存/订阅、监控重放、受控导出、生成式 OpenAPI client 和外部临床工作台。单个重复参数仍保持数组类型，避免保存或导出时把单元素角色组降成字符串。
- 完整 `make check` 退出码为 `0`，通过 Ruff、严格 Mypy `292` 个源文件、后端全量测试、OpenAPI 漂移检查、Biome、TypeScript、前端 `254/254`、生产构建、运维契约、Compose 和 Kubernetes 渲染。统一运行镜像为 `sha256:22207da95041faf7e90276ce4a4ac8dc3a5f99e65fa31df93f08133595ee04f0`，API、MCP、parser、worker、monitoring worker、search projector 和 search maintenance 使用同一镜像并达到健康状态。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `92/92`，每个 project `23/23`，耗时 `302,163 ms`。`[clinical-normalized-drug-or][clinical-role-groups]` 场景以真实 PostgreSQL 夹具验证四组 URL 恢复、通过 UI 增加第二个试验药物、真实 `/api/v1/trials` 重复参数、组内 OR、组间 AND、结果命中和刷新恢复；没有测试重试或快照更新。
- 四视口 CLS 均为 `0`，最慢 LCP `200 ms`、最慢 INP `48 ms`；临时账号、临时实体和临时入库夹具清理后均为 `0`，结构化报告未记录凭据。该性能仅为本地受控导航，不替代生产 RUM、长稳或目标基础设施容量批准。
- 本批将外部工作台代码交付完成度提高到约 `72%`。正式授权数据覆盖、专业客户 UAT、目标服务器部署、生产安全/容量/灾备和商业审批仍未完成，因此状态仍是 Development，不得宣称已达到商业生产交付。

## 2026-07-26 已认证临床结果查询与完整命中集格局闭环

- 在用户已授权登录的 NextPharma“临床结果”中真实输入 `帕博利珠单抗`。候选层明确区分原研药、企业生物类似药、改良剂型和复方/联用方案，并展示英文名、别名、创新类型与详情；实际提交条件包含两个规范药品并以 OR 连接，参考页在审计时点返回 `2,202` 条。结果区真实提供列表/可视化、按试验聚合、自定义列、自定义排序、订阅和导出；统计的列表口径分别为“披露年份 × 试验阶段”和“试验阶段 × 总体评价”。审计不保存第三方明细或凭据，参考条数不进入平台测试夹具。
- 本平台临床查询升级为 `pharma.clinical_trial.search.v6`。`GET /api/v1/trials` 在同一租户过滤和已应用查询中返回分页 `items` 与完整命中集 `landscape`；数据库侧聚合最近结果披露年份 × 分期、分期 × 结果评价两张矩阵，空年份、空分期和空评价保留未披露桶，不从当前页近似全量。多阶段试验按受治理阶段分别计数，最近披露时间缺失时才使用 `results_first_posted`。
- 外部临床工作台新增列表/可视化切换。两张矩阵分别支持图示/语义表格，分期或评价图例可继续写回原查询；`display=landscape` 进入稳定 URL，刷新、前进后退和返回列表恢复同一查询。受控导出、保存/订阅和收费 MCP 继续复用事实查询合同，展示模式不改变监控或计费语义。
- 完整 `make check` 通过 Ruff、严格 Mypy `292` 个源文件、后端 `1071/1071`、覆盖率 `84.56%`、OpenAPI 客户端 `335` 个文件无漂移、Biome `162` 个文件、TypeScript、前端 `248/248`、生产构建、Compose、Kubernetes 和运维契约。研究/内部生产文档 SHA-256 分别为 `1b4bd9e4e397ad95c9be5abc504f22443d45e522eaac2e9adb6f9d65d8a74f65` 和 `8cabaa7a998760a6dfe11ac76006fbef48fcc0ba88473139e0e97943984de394`。
- 统一运行镜像为 `sha256:06278d336100e629fca4db09bac7b2145a67f0b52f589612ce7d6fc693fb0443`；API、MCP、parser、worker、search projector、search maintenance 和 monitoring worker 使用同一镜像且全部健康，`/health/ready` 返回 `ready` 且 OpenSearch 可用。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `198,839 ms`，`clinical_full_result_landscape=true`。真实 PostgreSQL 夹具验证查询、完整命中集矩阵、图示/列表、URL/刷新恢复和返回结果列表；四视口 CLS 均为 `0`，最慢 LCP `80 ms`、最慢 INP `32 ms`，没有重试或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批闭合临床结果的同查询统计分析，但 IIT/IST、疗法线次、试验简称和结果级最优剂量字段仍需受治理模型与合法来源；正式授权数据覆盖、专业客户 UAT、生产 RUM 和目标服务器部署也未完成。因此整体完成率保持 `70%`，预计代码收束仍需 `2-4` 周，商业发布周期继续取决于数据授权、UAT 和目标环境。

## 2026-07-26 已认证 PD1 组合查询与管线密集结果闭环

- 登录恢复后在授权 NextPharma 会话中真实执行基础查询：输入 `PD1` 后，联想区区分“按靶点/按靶点组合”，候选项展示规范名称、同义词、详情与复选选择；选中规范 `PD1` 并同时限定“有临床结果”和“有交易”，参考页返回 `51` 条。结果区保留可读的 AND 条件表达式，并实际提供列表/可视化、自定义列、自定义排序、订阅和导出。本记录只作为交互对标，不保存第三方结果数据或把参考条数写入平台测试。
- 代码对照确认本平台已有规范实体、跨域信号、列设置、列顺序、密度、服务端排序和同查询格局，因此没有重复造控件。`pharma.pipeline.search.v8` 将已有权威作用机制、总体阶段、项目状态、记录地区、全球阶段起始和中国阶段起始补入密集结果表，并把六项加入 HTTP、保存查询、导出和全结果集服务端排序白名单；浏览器不按当前页重排或推断字段。
- 管线列表现在提供 20 个可配置专业列。总体/全球/中国阶段继续按受控阶段语义展示，状态使用明确中文标签，缺失值保持“未披露”；列显示与顺序仅作为个人本地偏好，不改变事实查询，排序字段、方向、筛选、分析和分页继续由稳定 URL 持有。
- 完整 `make check` 在路由修复前后各执行一次，最终通过 Ruff、严格 Mypy `292` 个源文件、后端 `1071/1071`、覆盖率 `84.55%`、OpenAPI 客户端 `333` 个文件无漂移、Biome `160` 个文件、TypeScript、前端 `247/247`、生产构建、Compose、Kubernetes 和运维契约。最终研究/内部生产文档 SHA-256 分别为 `a07b63a5825ad15522e627d85f863b874b1b947fe0c926de9cf22bf4169eea50` 和 `2bbf115c66c30feb5689c3a1f7e2b8bcef529e3ac6ba892ee8b17bbe0b5ec46d`。
- 首轮 Chrome 为 `84/88`：四视口 API 均已按 `mechanism_of_action` 正确排序，但工作台路由仍保留旧排序白名单，URL 只保存 `sort_direction=asc` 而丢失排序字段。修复扩展路由白名单并把作用机制加入 URL 往返回归，没有绕过断言、重试或延长超时；随后重新运行完整工程门和完整浏览器套件。
- 统一运行镜像为 `sha256:cb1a2f97b9d02b1eece013f125ff18e257209037559b2eb691da442db246e2e0`；API、MCP、parser、worker、search projector、search maintenance 和 monitoring worker 使用同一镜像，13 个服务均正常，`/health/ready` 返回 `ready` 且 OpenSearch 可用。构建期间临时代理已停止，不保留 WSL `7890` 监听。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `217,575 ms`，40 个严格场景中 `pipeline_dense_results=true`。四视口 CLS 均为 `0`，最慢 LCP `220 ms`、最慢 INP `176 ms`；真实链路验证六个字段、作用机制全结果集排序、URL/刷新恢复、列隐藏持久化和恢复，临时账号、实体与入库夹具清理后均为 `0`，报告未记录凭据。
- 本批把已认证参考工作流转化为可审计的平台代码闭环，但正式授权数据覆盖、参考其他领域的真实执行证据、专业客户 UAT、生产 RUM 和目标服务器部署仍未完成。因此整体完成率保持 `70%`，预计代码收束仍需 `2-4` 周，商业发布周期继续取决于数据授权、UAT 和目标环境。

## 2026-07-26 交易全结果集格局分析闭环

- 参考交易页可见“数据统计”以及图表/列表切换，并在查询区提供交易阶段、参与方、地域权益、金额、资产模态等专业条件；当前参考会话仍被手机号/验证码登录弹窗阻塞，因此只登记为 `observed`，没有绕过验证或宣称执行了受保护查询。
- 本平台交易查询升级为 `pharma.deal.search.v7`。服务端对完整授权命中集计算交易类型、状态、方向、地域权益、币种、资产模态、交易阶段、当前阶段、参与方国家和权益区域十个结构化分布，不以当前分页样本近似全量；单值维度显式统计缺失值，多资产和多参与方维度允许占比重叠并在界面解释口径。
- 外部工作台在同一交易入口提供列表/数据统计切换、图表/语义表格切换、Top 5/8/20/50 和维度下钻。分析状态写入稳定 URL，可刷新、前进后退、保存、订阅和逐字段回放；下钻回到受治理的交易筛选，不增加第三入口或内部运营痕迹。
- 完整 `make check` 通过 Ruff、严格 Mypy `292` 个源文件、后端 `1071/1071`、覆盖率 `84.55%`、OpenAPI 客户端 `333` 个文件无漂移、Biome `160` 个文件、TypeScript、前端 `247/247`、生产构建、Compose、Kubernetes 和运维契约。研究/内部生产文档 SHA-256 分别为 `704690e72951369a8c28f757b495b5ab6f8236043d1ac48eee80ce58acf41354` 和 `0ab43066967b2c565587a6a71bc09549ac28d8cb2afe4939d8a8ae17edd205df`。
- 统一运行镜像为 `sha256:e1f92acd6c1008f335ecc5eff1ff1d224c569a3c58919a5aaad89e47b20b213c`；API、MCP、parser、worker、search projector、search maintenance 和 monitoring worker 均达到 `healthy`，`/health/ready` 返回 `ready` 且 OpenSearch 可用。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `195,240 ms`，39 个严格场景中 `deal_full_result_landscape=true`。四视口 CLS 均为 `0`，最慢 LCP `84 ms`、最慢 INP `32 ms`；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批闭合交易查询后的全结果集分析和持续研究状态，但正式授权数据覆盖、参考真实查询补证、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合。因此整体完成率保持 `70%`，预计代码收束仍需 `2-4` 周，商业发布周期取决于数据授权、UAT 与目标环境。

## 2026-07-26 交易资产属性多选专业查询闭环

- 交易查询升级为 `pharma.deal.search.v6`。资产模态和项目标签均支持最多 20 个去重值，同一维度使用 OR、两个维度之间使用 AND，并且两个维度必须命中同一条同租户 `DevelopmentProgram`，不能把同一药物的不同研发项目拼成错误命中。服务端数据库测试以两条故意交叉的项目记录验证了该边界。
- 外部工作台用有界复选分面替代两个单选框；已选值进入 `applied_filters` 的结构化 `in` 操作符。稳定 URL 和 HTTP 使用重复参数，保存查询、订阅回放、监控、受控导出、商业请求指纹及收费 MCP 使用同一集合语义；旧单值 URL、保存 JSON 和 MCP 参数规范化为单元素集合，既有位置参数顺序不变。
- 组件、路由、生成式客户端、真实数据库、外部/内部 API、MCP、监控和发布证据均增加回归覆盖。完整 `make check` 通过 Ruff、严格 Mypy `292` 个源文件、后端 `1070/1070`、覆盖率 `84.52%`、OpenAPI 客户端 `331` 个文件无漂移、Biome、TypeScript、前端 `246/246`、生产构建、Compose、Kubernetes 和运维契约。
- 首轮 Chrome 的四个交易多选场景已正确恢复重复 URL 参数和摘要，但验收脚本在“更多交易条件”关闭时直接点击其不可见子控件并达到既有 30 秒用例超时。修正只增加真实用户展开步骤，不使用强制点击、重试或延长超时；随后完整复验通过。
- 统一运行镜像为 `sha256:0b0c8412aacdf33616765c26ff7ff3f8cacb5f15f57c87e6680d9e8ffb1e0f5f`；API、MCP、parser、worker、search projector、search maintenance 和 monitoring worker 均达到 `healthy`，`/health/ready` 返回 `ready` 且 OpenSearch 可用。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `206,473 ms`，38 个严格场景中 `deal_asset_multiselect_query=true`。四视口 CLS 均为 `0`，最慢 LCP `88 ms`、最慢 INP `24 ms`；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 参考交易页当前仍受手机号/验证码登录遮罩限制，本批参考证据保持 `observed`，没有绕过验证或读取未授权数据。正式授权数据覆盖、参考真实查询补证、专业客户 UAT、生产 RUM 和目标服务器部署尚未闭合，因此整体完成率保持 `70%`，不把本地受控验收等同于医药魔方同级商业发布。

## 2026-07-26 交易资产模态与项目标签专业筛选闭环

- 参考交易页面公开可见的查询结构包含 Modality、药品标签、交易阶段、参与方、地域权益和金额等专业维度；当前 Codex 浏览器会话被手机号/验证码登录弹窗阻塞，因此本批参考证据严格登记为 `observed`，没有绕过验证、读取受保护载荷或宣称参考查询已经执行。Goal 升级为 `v1.9.9`，后续主要研发线持续锁定外部用户入口；恢复授权会话后必须补齐真实选择、提交、结果和跨域操作证据。
- 本平台交易查询升级为 `pharma.deal.search.v5`，新增资产模态与项目标签。服务端从交易资产的结构化关联解析同租户权威 `DevelopmentProgram`，两个条件同时提交时必须由同一项目记录共同满足；不会按资产名称、文件文本或模型猜测生成关联，也不会把不同项目的条件拼成伪命中。
- 两项条件进入完整授权结果集分面、`applied_filters`、稳定 URL、已保存查询、订阅回放、监控匹配、受控导出、商业请求指纹、HTTP API 和收费 MCP `get_deals`。MCP 新参数追加在既有位置参数之后，保留兼容性；Web 将低频条件放入高级筛选区，不增加内部术语或新的用户入口。
- 完整 `make check` 通过：Ruff、严格 Mypy `292` 个源文件、后端 `1069/1069`、覆盖率 `84.54%`、OpenAPI 客户端 `331` 个文件无漂移、Biome `158` 个文件、TypeScript、前端 `246/246`、生产构建、Compose、Kubernetes 和运维契约全部通过。构建仅保留既有 RDKit/Ketcher 大块告警，没有新增本地模型依赖或失败门禁。
- Goal 发布矩阵同步到 `v1.9.9` 后，重复全量门在后端覆盖率结束后暴露 Vitest 默认 16 worker 与 WSL 内存/swap 竞争：管线、临床和交易的重交互用例偶发超过既有 5 秒门，但单独与完整前端复现均通过。测试运行器现固定最多 8 个 jsdom worker，保留原 5 秒超时、断言和用例范围；没有用延长超时或重试掩盖不稳定性。发布证据与能力矩阵专项 `303/303` 通过。
- 统一运行镜像重建为 `sha256:bfe25c2268cc15549cacd4e031f07e576ca2736689c16bfc4e03162a69057952`；API、MCP、parser、worker、search projector、search maintenance 和 monitoring worker 均使用该镜像并达到 `healthy`。测试 worker 配置不进入运行代码，重建前后研究与内部入口的生产文档 SHA-256 均分别保持 `68249e2e02320d0fb347d48c31165c76dc2463dd648f74a98eb5b142a68d0854` 与 `e247069fd5d7d5695aac34c4e12047ce3f30670ddadd6633fa901eb47960bd47`；未配置外部 ERP 的可选 billing provider 未启动。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `222,430 ms`，37 个严格场景中 `deal_asset_attribute_query=true`。真实 PostgreSQL 夹具验证筛选、结果、URL、保存、订阅和逐字段回放；四视口 CLS 均为 `0`，最慢 LCP `140 ms`、最慢 INP `40 ms`。临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批达到 `platform-verified`，但参考侧仍只有 `observed`；正式授权数据覆盖、参考真实查询补证、专业客户 UAT、生产 RUM 和目标服务器部署尚未完成。因此整体完成率保持 `70%`，不把本地受控数据或代码通过冒充医药魔方同级商业交付。

## 2026-07-26 管线临床/交易信号与直接跨域研究贯通

- 管线查询升级为 `pharma.pipeline.search.v7`，在既有项目、规范靶点、适应症、机构、区域阶段、权益和里程碑条件上增加临床结果存在性、结果评价、交易存在性、币种及潜在总额范围。服务端通过规范试验角色与交易资产关联执行存在性查询和授权命中集分面，不复制临床或交易事实，也不按名称猜测关联。
- 外部工作台将低频条件收在独立“临床结果与交易信号”折叠区，提交前阻断互斥条件、缺失币种和反向金额区间。结果表直接给出试验数、结果评价、交易数和币种；已应用条件、稳定 URL、刷新、保存订阅、监控、受控导出和生成式 OpenAPI 客户端共享同一查询语义。
- 试验数和交易数不再是只读摘要。非零信号可直接按药物稳定 ID 进入临床试验或交易工作域；临床查询的 `role_entity_id` 单独使用时覆盖试验药物与联用药物全部角色，只有同时提交 `role_entity_role` 才收窄到指定角色。角色缺少实体 ID 在 HTTP、保存查询和导出边界统一失败关闭，查询版本升级为 `pharma.clinical_trial.search.v6`。
- 浏览器历史保存进入跨域页面前的完整管线组合查询；从临床或交易返回后，机构、靶点、适应症、阶段、权益、里程碑、临床结果、交易金额和排序状态全部恢复。跨域页面同时回显规范药物已应用条件和真实关联结果，不按显示名重新检索。
- 收费 MCP 的新增参数追加在旧位置参数之后，保留既有 agent 调用兼容性；布尔 `false` 与金额 `0` 不会被真值判断丢弃。商业预授权请求指纹包含全部新增条件，HTTP 查询不能使用不同条件消费已预留额度。
- 监控匹配除药物、靶点、适应症和机构外，还会沿“试验实体 → 角色化药物 → 研发项目”和“交易实体 → 资产药物 → 研发项目”重新执行固定查询版本。临床结果或交易本身发生变化时能够命中对应管线订阅，未另建关键词近似路径。
- 完整 `make check` 通过后端 `1069/1069`、前端 `246/246`、覆盖率 `84.52%`、OpenAPI `331` 个生成文件无漂移，以及 Ruff、严格 Mypy、Biome、TypeScript、生产构建、Compose 与 Kubernetes 契约。统一镜像为 `sha256:b389d6e34f54bc177f002910cba3b7a6a9091cb3dd195813d25d1d840c46af32`，默认运行拓扑全部健康；未配置外部 ERP 的可选 `billing-provider` profile 保持关闭。
- 首轮 Chrome 为 `84/88`：四个主场景已正确进入带稳定药物 ID 的交易页面并显示真实结果，但测试错误地要求缓存命中也必须产生新网络请求，最终等待到用例总超时。验收改为检查稳定深链、已应用规范实体、真实结果和返回后的完整管线 URL；HTTP/API 回归继续独立验证请求参数，没有删除产品行为断言或放宽超时。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `194,590 ms`，`pipeline_cross_domain_signals=true`、`pipeline_cross_domain_navigation=true`。真实 PostgreSQL 夹具验证复合筛选、直接跨域、规范实体条件、关联结果、浏览器返回和刷新恢复；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批闭合管线与临床/交易的代码级查询链，但正式授权数据覆盖、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合，因此整体完成率保持 `70%`，不把本地受控验收等同于商业发布完成。

## 2026-07-26 交易规范实体查询与远程模型边界

- 授权参考交易页可观察到药品、靶点和适应症分别作为专业查询条件；参考会话存在登录遮罩，因此本批没有绕过登录或宣称执行了受保护结果查询，只采用可见查询模型完善本平台既有交易域。
- 交易查询升级为 `pharma.deal.search.v4`。人员工作台使用规范实体选择器提交药品、靶点和适应症稳定 ID；服务端通过结构化交易资产及权威研发项目解析靶点/疾病关联，返回三个完整授权命中集分面。相同 ID 进入稳定 URL、保存订阅版本、HTTP、收费 MCP、商业计量请求身份、受控导出和监控匹配，不按显示名或自由文本猜测。
- 回归测试发现疾病实体变化未沿“疾病 → 研发项目 → 药品 → 交易”传播到交易订阅。`_deal_filters` 现同时解析直接交易、参与方、药品、靶点和疾病关联；药品、靶点、疾病或交易本身发生变化时都复用同一查询语义触发有界监控判断。
- 生成式模型边界保持第三方 HTTPS API-only。运行中的 API、MCP 和治理 worker 使用 `https://token-plan-cn.xiaomimimo.com/v1` 的 `mimo-v2.5`，密钥只由私有环境注入；统一应用镜像不包含 `vllm`、`ollama`、`transformers`、`torch` 或 `sentence-transformers`。依赖清单和锁文件新增 CI 禁止项，防止后续重新引入本地推理运行时。无业务数据的最小 provider 探针真实返回 HTTP `200`、响应模型 `mimo-v2.5`、`265` usage tokens 和 provider request ID；探针不记录正文或密钥。语义 embedding 未配置，因此当前也没有本地 embedding 或静默回退。
- 完整 `make check` 通过后端 `1069/1069`、前端 `245/245`、覆盖率 `84.52%`、OpenAPI 331 个生成文件无漂移，以及 Ruff、严格 Mypy、Biome、TypeScript、生产构建、Compose 与 Kubernetes 契约。新统一镜像为 `sha256:c11128353ec2c68b17a0340b9cf9d96d67e25f3d2f9fe21129087c1d9843fd7e`，相关应用服务均健康。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `203,498 ms`，`deal_entity_query=true`。真实链路验证三项规范实体查询、结果、URL、保存订阅、逐字段重放和刷新；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批闭合交易规范实体查询和本地模型不可回归边界，但正式授权数据、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合，因此整体完成率保持 `70%`，不以代码级验收冒充商业发布完成。

## 2026-07-26 检索结果直接加入对比列表闭环

- 全局实体检索结果现在复用共享表格的受控行选择，用户可在当前真实结果集中选择最多 20 个实体并直接执行“加入列表”，无需离开查询上下文后再次搜索。选择在查询条件、实体类型或审核上下文变化时清空，不把陈旧结果带入下一次操作。
- 新的列表选择对话框只加载当前用户可编辑且未满 20 项的既有列表，明确显示当前容量和加入后的数量。提交使用 `POST /api/v1/comparison-sets/{id}/members/batch`，服务端在同一事务中校验租户、所有权、重复成员、容量和预期版本，按选择顺序写入全部成员，只生成一个新版本和一条审计事件；任一成员冲突会整体回滚。并发冲突或服务失败时，对话框与行选择保持，重新读取列表版本后允许用户原位恢复。
- 数据库/API 回归验证双成员原子加入只增加一个版本、混合重复批次不会部分写入、重复请求体在边界返回 `422`；组件和生成客户端合同验证成功清空、冲突保留、真实路径和载荷。完整 `make check` 通过后端 `1068/1068`、前端 `245/245`、覆盖率 `84.49%`、OpenAPI 331 个生成文件无漂移，以及格式、类型、生产构建和部署契约。
- 首轮 Chrome 因新增选择列使旧表头定位失效为 `84/88`，修正为忽略结构性空表头后功能用例达到 `88/88`，但退出清理暴露列表成员/所有者外键顺序错误，因此该轮不计为通过。验收清理改为先删除列表导出事件、审计、成员和不可变版本，再删除列表、实体和账号，并能按受控 `e2e-*` 标记恢复异常中断数据。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `182,399 ms`，`result_to_comparison=true`。真实链路创建列表、从真实搜索结果选中两个实体、一次原子加入、进入“对比与列表”核对两个成员；临时账号、实体、列表、成员、入库夹具和临时策略清理后均为 `0`，报告未记录凭据。
- 本批闭合检索结果到持久化列表的代码级工作流，但正式授权数据、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合，因此 `dense_result_operations`、`personal_productivity_and_delivery` 与整体完成率保持原状态。

## 2026-07-26 已保存专业查询维护闭环

- 授权参考页再次确认专业工作台把复合筛选作为可持续复用的研究上下文，而不是一次性关键词。参考会话当前出现登录遮罩，未读取或绕过受保护数据；本批只复用已审计的公开“查询 → 保存/订阅 → 复用”交互语义，并完善本平台现有链路。
- 监控工作台现在只向检索所有者提供“编辑名称与业务说明”，继续调用既有 `PATCH /api/v1/monitoring/saved-searches/{id}`。元数据编辑不提交 `query` 或 `query_type`，因此不会增加查询版本、改变固定主题或丢失领域筛选；企业共享给当前用户的检索仍只有运行入口和明确只读提示。
- 编辑弹窗具备名称/说明长度边界、保存中禁用、服务端冲突错误和原位恢复。组件测试覆盖成功、失败与只读权限，生成客户端合同测试验证真实 `PATCH` 路径和载荷；全量 `make check` 通过后端 `1067/1067`、前端 `242/242`、覆盖率 `84.50%`、OpenAPI 330 个生成文件无漂移，以及格式、类型、生产构建和部署契约。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `180,713 ms`，并独立记录 `saved_search_maintenance=true`。真实链路创建带完整格局参数的管线检索，修改名称与业务说明，确认版本保持 `v1`，再重放全部筛选；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批完善个人效率的代码级生命周期，但正式授权数据、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合，因此 `personal_productivity_and_delivery` 与整体完成率保持原状态，不用局部自动化冒充商业完成。

## 2026-07-26 外部导出与内部策略管理边界

- 外部“对比与列表”原先会在管理员身份下直接显示租户导出策略表单，这与两个工作台独立、外部入口不暴露内部运营痕迹的产品边界冲突。外部页面现在只读取策略来控制真实导出格式、字段、单次上限和授权标注，不再接受策略写入或显示管理控件。
- 租户策略配置迁入内部“商业运营”的独立“导出策略”标签。新面板继续复用既有 `GET /api/v1/workspace/export-policy` 和受 `workspace:export:manage` 保护的 `POST /api/v1/admin/workspace-export-policy`，没有新增策略副本、客户端权威状态或第三入口；未配置、加载失败、保存失败和成功反馈均明确处理。
- 组件回归验证外部管理员也看不到策略管理、内部面板能读取并保存版本化策略；完整 `make check` 通过后端 `1067/1067`、前端 `239/239`、覆盖率 `84.50%`、OpenAPI 330 个生成文件无漂移，以及类型、格式、生产构建和部署契约。
- Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `183,187 ms`；真实管理员会话分别验证外部控件不存在和内部策略可见，全部视口无失败、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批加强双工作台隔离和个人效率交付证据，但正式授权数据、专业客户 UAT、生产 RUM 和目标服务器部署仍未闭合，因此整体完成率与相关 `partial` 门禁保持不变。

## 2026-07-26 疾病负担与研发事件持续监控闭环

- 保存检索注册表新增版本化 `epidemiology_search@1` 与 `news_search@1`。流行病学合同保留疾病稳定 ID、统计指标、地区、单位、规范患者人群、人群/年龄/性别口径、观察期和排序；新闻合同保留事件类型、发布方、语言、会议、发布日期、研究内容范围、列表/时间线和排序。排序或展示默认值不构成全库订阅条件，空筛选、反向日期和不兼容的研究范围/事件类型在 API 边界失败关闭。
- 两域监控消费者直接复用现有 `_epidemiology_filters` 与 `_news_event_filters`。疾病、发布方、规范患者人群关联的疾病/靶点，以及新闻发布方/关联实体变化均通过同一权威数据库语义执行有界存在性查询，没有新增关键词近似规则或旁路索引。
- 流行病学和新闻结果工具栏保存的是已提交、由 URL 持有的完整查询，可同时创建监控主题；监控中心分别显示“流行病学”和“新闻与会议”，逐字段恢复规范 URL 后重新执行真实领域 API。新闻保存对话框和反馈统一使用“新闻与会议”域名，消除了旧“资讯”名称造成的无障碍语义不一致。
- 后端聚焦回归 `315/315`，前端组件与合同聚焦回归 `35/35`；完整 `make check` 通过后端 `1067/1067`、前端 `238/238`、覆盖率 `84.50%`、OpenAPI 330 个生成文件无漂移，以及类型、格式、生产构建和部署契约。
- 首轮真实 Chrome 为 `84/88`，四个新增场景因验收使用旧对话框名称超时；统一产品域名后第二轮仍为 `84/88`，原因是测试要求规范 URL 冗余写入默认 `sort_direction=desc`。最终断言改为验证非默认 `sort_by=value`、省略默认方向和表头 `aria-sort=descending`，未删除功能检查或放宽失败。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `88/88`，每个 project `22/22`，耗时 `182,769 ms`，无失败、跳过或快照更新；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。七个结构化专业域现均具备类型化保存、订阅和完整回放，但正式授权数据、专业用户 UAT 和生产 RUM 未闭合，因此 `personal_productivity_and_delivery` 继续保持 `partial`，整体完成率不因本批单项上调。

## 2026-07-26 监管复合查询保存与订阅闭环

- 授权参考页的实际筛选流程确认，专业订阅必须保存完整组合条件并继续驱动结果和监控，不能只保存关键词或页面标题。本平台新增版本化 `regulatory_search@1`，覆盖机构、辖区、事件/状态、认定资格、标签变更、黑框警告、安全信号、严重程度、处置状态、决定/来源更新时间和排序；无筛选全库订阅、无效枚举和反向日期区间在 API 边界失败关闭。
- 监控消费者直接复用监管查询的 `_regulatory_filters`，以变化的药物、适应症、机构或靶点关联资产作为实体约束执行有界存在性查询，不另写近似关键词规则。`has_boxed_warning=false` 被保留为有效条件，保存版本和监控主题继续受租户、所有权、共享撤回、固定查询版本与审计约束。
- 监管结果工具栏可保存已提交且由 URL 持有的查询，并可同时创建监控主题；监控中心显示“监管与安全”，逐字段恢复稳定 URL 后重跑真实 Domain API。组件覆盖无筛选禁用、完整载荷和成功反馈；API/数据库测试覆盖空合同、日期校验、版本 JSON、关联实体命中、非关联实体拒绝和真实 outbox 到提醒链路。
- 首轮 Google Chrome 为 `83/84`：桌面、宽屏和平板和新增订阅回放均通过，但移动端结果摘要把操作按钮放入普通摘要 flex，详情打开后产生页面级横向溢出。修正为项目既有 `pipeline-result-toolbar` 响应式合同后，没有删除断言或放宽视口。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `84/84`，每个 project `21/21`，耗时 `178,823 ms`，无重试、跳过或快照更新；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。完整 `make check` 同时通过后端 `1064/1064`、前端 `232/232`、覆盖率 `84.45%`、OpenAPI 328 个生成文件无漂移及生产构建/部署契约。
- 药物与管线、临床试验、专利、交易、监管现已具备类型化保存、订阅和完整回放。流行病学与新闻仍未接入同级订阅，正式授权数据覆盖、专业用户 UAT 和生产 RUM 也未闭合，因此 `personal_productivity_and_delivery` 保持 `partial`，整体完成率仍不因单域闭环上调。

## 2026-07-26 专业结果分页闭环

- 授权参考页的真实 `EGFR` 查询返回 `1,150` 条、`58` 页，结果区同时提供邻近页码、末页和“跳至页”。本平台原有八个结构化工作域仅分散实现上一页/下一页，本批将其收束为共享 `ResultPagination`，不增加新入口或第二套查询合同。
- 共享分页器显示当前页、总页数和总记录数，提供首页、上一页、邻近页码、下一页、末页及键盘可提交的跳页输入。越界或非整数页码在浏览器边界明确报错且不发请求；有效页码只换算为现有有界 `offset`，继续由各领域 `onSearchChange` 写入稳定 URL 并调用原 Domain API。服务端返回权威总数后，过大、负数或非页边界的陈旧 URL offset 会自动归一化到最后一个有效页并同步回 URL。
- 八域继续固定每页 `100` 条，刷新后由 URL 恢复当前页；页码按钮使用 `aria-current=page`，图标按钮有唯一可访问名称。桌面和平板保持单行紧凑操作，移动端将跳页表单折到独立一行，四种视口均无页面级横向溢出。
- 初次真实 Chrome 为 `80/84`：直接写入 PostgreSQL 的受控记录没有经过权威搜索投影，因此全局检索没有三页结果。修正验收夹具为 PostgreSQL 写入后产生正式 `canonical.entity.upserted` outbox、由 `pharma-search` 投影至 OpenSearch 并显式刷新；清理继续同时删除数据库实体、outbox/delivery 和派生索引文档。第二轮 `80/84` 已通过真实查询、`offset=200`、5 条末页结果和 URL 断言，只因 Playwright 数字输入断言错误地传入 number 而非 string 失败；仅修正测试类型后全量复验。
- 最终 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `84/84`，每个 project `21/21`，耗时 `200,767 ms`，无重试、跳过或快照更新；临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。分页与数据工厂相关定向回归 `63/63`，完整前端回归 `228/228`，TypeScript、Biome、生产构建与完整 `make check` 通过。
- 该批次提高了 `dense_result_operations` 的实现与真实投影证据，但正式授权数据覆盖、专业用户 UAT 和生产 RUM 仍未闭合，因此体验门禁保持 `partial`，整体完成率不因单项前端优化上调。

## 2026-07-26 专业结果自定义排序闭环

- 经授权参考查询确认，密集结果区需要不依赖横向列头位置的显式自定义排序入口。本平台保留表头快捷排序，同时在所有采用服务端全命中集排序的共享专业结果表增加“排序”菜单；菜单只列出该领域表格真实声明为可排序的字段，不生成新查询字段或旁路 API。
- 字段和升/降序先在菜单内形成本地草稿，只有点击“应用排序”才一次性调用现有领域查询。首轮 Chrome 暴露原实现选择字段即发起查询、加载状态卸载表格并关闭菜单的问题；修正后不再要求用户反复展开菜单，也避免为一次排序意图发送两次请求。
- 应用后继续由既有领域合同规范化 `sort_by`/`sort_direction`，写入稳定 URL，并由服务端对完整授权命中集排序；刷新后菜单、表头 `aria-sort`、结果摘要和 URL 恢复同一状态。选择“默认顺序”复用各领域现有默认排序，不在浏览器自造相关性或业务顺序。
- 移动端菜单展开为工具栏内的全宽静态面板，桌面和平板保持紧凑浮层；方向使用可访问的二元模式按钮，字段使用原生选择器，应用按钮在草稿未变化时禁用。组件回归覆盖草稿不会提前执行和一次性提交，完整前端回归 `224/224`、类型/格式/生产构建通过。
- 第一轮真实 Chrome 因即时查询使菜单关闭，四个主场景超时，其余 `80/84` 通过；未放宽超时或删除断言。按根因修改为原子应用并重建运行镜像后，Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `84/84`，每个 project `21/21`，无重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 该批次提高了 `dense_result_operations` 的实现证据强度，但正式授权数据、专业用户 UAT 和生产 RUM 仍未闭合，因此体验门禁保持 `partial`，整体完成率不因单项前端优化上调。

## 2026-07-26 GOAL v1.9.6 外部用户入口主线

- 后续代码批次以可命名的外部用户研究任务为单位，必须闭合参考查询、领域合同、真实 API、结果/统计、详情/证据、跨域返回、适用的个人效率动作和完整状态；内部工作台、数据工厂、MCP 与商业控制面进入保持和回归模式，除非它们直接阻断该路径。
- 在用户授权的 NextPharma 会话中复核并实际操作规范靶点 `EGFR` 查询：结果总量为 `1,150`，从可视化切换到列表后，查询上下文、订阅与导出保持不变；列表公开显示自定义列、自定义排序、17 个专业字段、分页和稳定实体跳转，可视化公开显示研发阶段、靶点、适应症、靶点组合、研发机构和 Modality 等同查询聚合。
- 上述数量只证明参考工作流在审计时点真实执行，不进入本平台固定断言或测试夹具。Codex 内置浏览器只用于授权参考发现；本平台的布局、响应式、可访问性和交互完成度继续只用真实 Google Chrome/项目 Playwright 验收。
- Goal 中的正式统计口径保持 12 个业务域和 8 个矩阵体验门禁；正文将同查询统计与专业查询订阅单列核验，因此共有 10 个不可省略核验面。二者是展开关系，不允许通过改变分母降低目标。

## 2026-07-26 专利与交易专业查询订阅闭环

- 保存检索注册表新增 `patent_search@1` 与 `deal_search@1`。专利合同固定关键词、申请人、法律状态和排序；交易合同固定现有全部交易类型、状态、方向、参与方角色、阶段、权益、日期、金额、币种和排序条件，并校验互斥参与方、日期/金额范围及金额排序币种约束。
- 监控消费者直接复用 `pharma.patent.search.v1` 的 `_patent_filters` 和当前 `pharma.deal.search.v4` 的 `_deal_filters`，以发生变化的专利、交易或关联规范实体作为约束执行有界存在性查询；没有另写关键词近似逻辑，也没有新增旁路搜索 API 或数据库迁移。
- 专利与交易结果级工具栏复用受控 `SavedSearchDialog`。页面保存已提交且由 URL 持有的查询，不保存未执行草稿；有效查询即使当前零命中也可订阅未来变化，无任何筛选的全库订阅仍失败关闭。监控中心分别显示“专利情报”和“交易与公司”，并逐字段恢复稳定 URL 后重跑真实 Domain API。
- 首轮 Chrome 新场景真实保存、订阅和回放均成功，但验收定位把“申请人”筛选与列设置控件同时命中；第二轮将定位收紧后发现嵌套标签的可访问名称包含选项文本。产品为专利申请人/法律状态和交易方向/参与角色/币种增加显式 `aria-label`，使键盘、辅助技术和自动化获得稳定简洁名称；未删除断言或绕过 UI 状态验证。
- 后端监控、专利与交易聚焦回归 `17/17`，前端组件与合同回归 `45/45`；最终 Google Chrome `150.0.7871.128` 四视口 `84/84`，每个 project `21/21`，无重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 药物与管线、临床试验、专利、交易现已具备直接保存、订阅和完整回放。监管、流行病学和新闻仍需逐域接入同级类型合同，正式业务 UAT 也未完成，因此 `personal_productivity_and_delivery` 继续保持 `partial`，整体完成率不因本批次两个域闭环上调。

## 2026-07-26 临床试验空结果查询保存与订阅闭环

- 保存检索注册表新增版本化 `clinical_trial_search@1` 类型合同，覆盖关键词、注册平台、状态、分期、研究类型、结果存在性与评价、结果和披露日期范围、角色化试验/联用药物与靶点、关键结果、发表编号、会议及排序。类型解析改为显式可扩展注册表，不再为每个新专业域累加嵌套条件；现有版本化 JSON 结构可承载该合同，因此无需数据库迁移。
- 监控消费者不把临床组合查询降级为关键词。它直接复用 `pharma.clinical_trial.search.v6` 的 `_clinical_trial_filters`，包括试验简称、IIT/IST、治疗线次和规范实体任意/指定试验角色语义，并以发生变化的规范实体作为关联实体约束执行有界存在性查询；保存版本、租户、所有权、共享撤回和提醒不可变语义保持不变。
- 临床试验页面保存的是已经提交并由 URL 持有的查询，不是尚未执行的表单草稿。监控中心将其标识为“临床试验”，并恢复所有筛选和排序参数后重新调用真实 API；药物与管线、临床试验共用同一个受控 `SavedSearchDialog`，但领域合同和匹配逻辑相互独立。
- 首轮真实 Chrome 验收发现保存入口只存在于非空结果表格工具栏，导致条件有效但当前零命中的查询无法订阅未来变化。入口已移到结果级工具栏：有效筛选即使当前为空也可保存和订阅，无任何筛选的全库订阅仍由前后端共同失败关闭；没有通过伪造结果或放宽后端校验绕过问题。
- 后端监控、临床查询和 API 聚焦回归 `27/27`，前端组件与合同回归 `41/41`；最终 Google Chrome `150.0.7871.128` 四视口 `80/80`，每个 project `20/20`，无重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批次当时闭合药物与管线、临床试验；专利和交易随后也已闭合。监管、流行病学和新闻仍需逐域接入同级类型合同，正式业务 UAT 也未完成，因此 `personal_productivity_and_delivery` 继续保持 `partial`，整体完成率不因本批次单域闭环上调。

## 2026-07-26 专业管线查询保存与订阅闭环

- 经授权的参考产品会话可观察到在当前组合查询上直接订阅的工作流。本平台只复用该公开交互语义，不读取参考产品 Cookie/存储、受保护源码或数据，也不复制其品牌资产。
- 保存检索注册表新增版本化 `pipeline_search@1` 类型合同，完整保存药物与管线的筛选、排序、列表/格局展示、分析维度、Top 范围、阶段口径和靶点聚合口径。无任何有效筛选的全库查询失败关闭，避免人员误订阅整个管线数据集；现有可扩展 JSON 版本结构可承载该合同，因此无需数据库迁移。
- 监控消费者不把专业查询降级为关键词匹配。它复用 `pharma.pipeline.search.v7` 的同一服务端过滤构造器，并以关系存在性查询判断受治理实体变更是否命中固定查询版本；所有权、企业共享撤回、租户隔离、提醒不可变和 outbox 重放语义保持不变。
- 药物与管线结果工具栏提供“保存/订阅”入口；保存成功后，监控中心将其识别为“药物与管线”，并恢复完整筛选、排序、展示与分析 URL。即使后续用户修改当前页面，订阅仍绑定创建时的不可变版本。
- 后端监控、管线和 API 聚焦回归 `27/27`，前端组件与合同回归 `34/34`；最终 Google Chrome 四视口 `76/76`，每个 project `19/19`，无重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。
- 本批次当时只闭合药物与管线域；临床试验、专利和交易随后也已闭合。监管、流行病学和新闻仍需逐域接入同级类型合同，且正式业务 UAT 未完成，因此 `personal_productivity_and_delivery` 继续保持 `partial`，不据此提升整体完成率。

## 2026-07-26 同查询多维格局分析与三浏览器闭环

- 在经授权的参考产品真实会话中执行 EGFR 基础查询并观察实际结果和统计切换：参考结果为 `1,150` 条，列表/可视化共用查询，统计覆盖研发阶段、靶点、适应症、靶点组合、研发机构和药物类型，并可切换全球/中国/美国/欧盟/日本等阶段口径。审计只记录公开可观察的工作流和交互语义，不读取 Cookie/存储、不下载第三方资产，也不复制页面实现或数据。
- 本平台不新增第二套看板 API。`pharma.pipeline.search.v7` 在同一已应用查询中返回总体/全球/中国阶段、规范靶点、规范适应症、稳定靶点组合、模态、地区和机构八类权威聚合；列表、格局、筛选、档案回钻与受控导出共享同一查询契约。
- URL 所有的 `analysis_dimension`、`analysis_view`、`analysis_top`、`analysis_stage` 和 `target_aggregation` 分别控制维度、图表/表格、Top 5/8/20/50/100/200、总体/全球/中国阶段口径和全部/主靶点聚合。每次变更都触发服务端重查；响应回传采用的 `limit`、`stage_scope` 和 `target_aggregation`，分桶携带真实 `phase_counts`。未建模的美国、欧洲、日本阶段不展示为可用选项。
- ECharts 使用真实阶段构成绘制堆叠条形图，超过 15 个桶时提供有界纵向缩放；语义表格显示阶段构成、数量、占比、筛选和档案回钻。组件/API/路由回归覆盖非法参数、主靶点过滤、阶段构成和 URL 往返；Google Chrome 四视口完整 `76/76`，无重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`。
- 首轮 Chrome 主流程新增交互已通过，但移动端因冗余重载/重置操作挤占既有 180 秒总预算；去掉重复动作后第二轮只剩一个入库重放 `409`。根因是浏览器夹具创建 `ACTIVE` 数据源时没有 `last_scanned_at`，后台调度器可能在人工重放前抢先启动同一 Temporal workflow；夹具改为“刚扫描过”后不再被验收窗口内调度，产品端真实并发冲突规则保持不变。
- 最终 Google Chrome、Microsoft Edge 当前版和 Edge 前一主版本分别 `76/76`，总计 `228/228`；每轮四个 project 各 `19/19`，没有跳过、重试或快照更新，临时账号、实体和入库夹具清理后均为 `0`，报告未记录凭据。生产 RUM P75、授权数据覆盖、成对参考人工评审和专业用户 UAT 仍未完成，因此能力矩阵相关体验项保持 `partial`。

## 2026-07-26 外部参考视觉证据归档契约

- 新增 `pharma.reference-visual-pair.v1`。登记工具只读取经授权的外部参考 PNG，仓库中不复制第三方截图；外部证据只以 SHA-256、字节数、截图尺寸、无查询参数的 HTTPS 页面地址、观察版本、授权工单和外部制品 ID 进入内容寻址配对清单。
- 配对清单只能独占写入仓库外已存在的证据目录，权限固定为 `0600`。参考图片必须在仓库外且不能是符号链接；本平台图片必须是 `apps/web/e2e/visual-baselines/manifest.json` 中登记、摘要一致、无生产数据和无第三方品牌资产的自有基线。
- “同视口”按浏览器 CSS viewport 验证，不误把 Playwright `fullPage` 图片高度当成视口高度。双方截图宽度必须等于声明视口宽度并至少覆盖一个视口；实际全页截图高度分别记录，平台基线仍需匹配权威清单中的 `viewport`。
- URL 中的凭据、查询参数、fragment、非 HTTPS 或非标准端口均失败关闭；清单固定声明不记录凭据、Cookie、查询参数、生产数据和第三方二进制。`pair_id` 绑定工作流、视口和两侧制品元数据，任何字段或外部图片篡改都会被复验拒绝。
- 工具不会根据截图自动宣称功能等价：`review_status=pending`、`parity_claim=false` 和 `automated_equivalence_claim=false` 为强制值。受控真实 CLI 登记与 `make reference-visual-pair-verify` 已通过，6 个行为测试覆盖 schema、路径泄露、私有权限、仓库内第三方图片、视口/URL、身份/二进制篡改和仓库内输出拒绝。
- 这关闭了“可复现、可审计且不复制第三方资产的成对归档机制”代码缺口；真实批准参考流程的外部证据、人工差异结论、产品签字、生产 RUM P75 和专业用户 UAT 仍是商业门禁，因此能力矩阵保持 `partial`。

## 2026-07-26 320 CSS 像素重排与键盘主路径门禁

- 正式 Playwright 套件新增 `[reflow-keyboard]` 场景；每个既有浏览器 project 都在独立页面上下文中将布局收窄到 `320x720` CSS 像素，不增加只跑单一浏览器的旁路 project，也不改变四个强制视口的像素基线。
- 登录流程只用键盘完成邮箱输入、Tab 到密码、Tab 到提交和 Enter 登录；进入工作台后用焦点与 Enter 打开移动导航、展开专业数据库并进入药物与管线。随后读取真实 API 的全局检索、靶点档案、临床试验档案、交易档案和结构检索，逐页等待字体及双帧稳定后拒绝任何文档级横向溢出。
- 首轮 Chrome 中四个新增场景均因测试使用页面标题“药物与研发管线”定位实际导航短标签“药物与管线”而超时；并行等待使两个既有内部运行详情场景也超过上限。定位改为真实可访问名称后，没有增加超时或重试，Chrome、Edge 当前版和 Edge 前一主版本分别 `76/76` 通过，新增场景三浏览器四 project 共 `12/12`，完整执行共 `228/228`。
- `reflow_keyboard` 已进入浏览器报告与发布证据的严格场景集合；缺少任一 project、出现跳过/重试/失败或未知场景都会拒绝报告。三轮均未更新快照，临时账号、实体和入库夹具清理后为 `0`。
- 该门禁证明代码在 320 CSS 像素下的关键重排和键盘激活路径，不等同于操作系统级 200%/400% 缩放、人工焦点顺序审查、NVDA/JAWS/VoiceOver 屏幕阅读器或客户辅助技术 UAT。

## 2026-07-26 Edge 当前与前一主版本兼容门禁

- 新增 `bootstrap-wsl-edge.sh`，从 Microsoft 官方 Edge 仓库读取签名 `InRelease` 和 `Packages`，固定 Microsoft release key 指纹，校验仓库摘要、包大小与包 SHA-256 后才解包到用户级缓存；不写系统 APT 配置、不使用 `sudo`，并分别保存当前与前一主版本指针。
- 浏览器验收新增 `chrome|edge-current|edge-previous` 受控目标。三个目标复用同一 Playwright 配置、真实登录、PostgreSQL 夹具、API、四视口、axe、Web Vitals、像素阈值和清理流程；Edge 只能读取 Chrome 权威视觉基线，不能用 `--update-snapshots` 改写它。
- 发布证据仍使用 `pharma.browser-acceptance.v7`，但浏览器身份只允许严格配对的 `chrome/Google Chrome` 或 `msedge/Microsoft Edge`，产品与 channel 交叉伪装会失败关闭。版本报告只保留经签名包元数据核对的四段版本号。
- 真实 Microsoft Edge `150.0.4078.99`（当前）和 `149.0.4022.98`（前一主版本）分别在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完成 `72/72`，合计 `144/144`。两轮均覆盖双工作台、专业查询、密集结果、档案连续性、自动入库管理、权限、恢复、导出、RDKit、WCAG、性能和像素比较；没有重试、跳过或快照更新，临时账号、实体和入库夹具清理后均为 `0`。
- 带输出的 Edge 当前版再次执行 `72/72`，生成的真实 JSON 由发布证据解析器重新读取并通过。首次解析暴露发布允许列表漏掉已运行的入库重放、隔离治理、主数据回滚、发布治理和质量运营五个场景；权威集合与测试夹具补齐后，完整报告通过严格集合校验，未删除新增场景或放宽未知字段拒绝。
- 该证据关闭代码里程碑中的 Edge 当前及前一主版本自动兼容缺口，但不替代 Windows 原生企业策略验证、人工辅助技术测试、生产 RUM P75 或专业客户 UAT。

## 2026-07-26 交易专业档案闭环

- 交易详情从列表附属弹层升级为页面级专业档案，稳定地址为 `/workspace/research?view=deals&deal=<UUID>`；`section=parties|assets|rights|terms` 分别表示参与方、资产与阶段、地域权益、条款与来源，概览省略 `section`，未知分区失败关闭到概览。
- 档案继续读取既有稳定交易详情端点，不增加第二套搜索后端。概览展示交易方向、状态、地域和金额；其余分区按权威关系展示参与方角色与属性、交易资产及当时/当前阶段、独占或非独占地域权益、金额条款和来源。来源谱系入口在所有分区持续可用。
- 直接打开档案时停止加载完整交易列表；从组合筛选结果或跨域实体档案进入后，URL 分区、刷新、浏览器历史和返回列表均保持同一研究上下文。前端模块继续独立懒加载，交易模块约 `29.41 kB`（gzip `8.12 kB`）。
- 首轮真实 Chrome 验收为 `67/72`：四个视口都发现交易角色 9px 辅助文本对比度低于 WCAG AA，移动端另有一次既有内部入库运行详情等待超时。辅助文本颜色在共享样式中修正，应用镜像重建后未复现该超时。
- 最终真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 为 `72/72`。真实 PostgreSQL 夹具包含许可方、被许可方、规范药物资产、交易时阶段、当前阶段及大中华区独占商业化权益；场景验证五个分区、刷新恢复、返回保留关键词、实体档案跨域进入与历史返回、WCAG 及无页面级横向溢出。临时账号、实体和入库夹具均清零且未记录凭据。
- 药物、公司、疾病、临床试验、专利族、交易和靶点全景的页面级专业档案与跨域返回代码闭环已完成，体验项 `entity_dossiers_and_cross_domain_links` 更新为 `implemented`。正式授权数据覆盖、目标服务器容量、人工无障碍验收和专业客户 UAT 仍由独立商业门禁控制，不能由本地受控夹具替代。

## 2026-07-26 专利族专业档案闭环

- 专利族详情从列表附属弹层升级为页面级专业档案，稳定地址为 `/workspace/research?view=patents&patent=<UUID>`；`section=timeline|relationships` 分别表示法律与权利要求、关联资产，概览省略 `section`，未知分区失败关闭到概览。
- 档案继续读取既有稳定专利族详情端点，不增加第二套搜索后端。概览展示族口径、优先权、申请人、发明人、公开文本、法律状态和预计到期；法律分区展示受治理法律事件与独立权利要求；关联资产按稳定规范实体 ID 回钻。来源与证据入口在所有分区持续可用。
- 直接打开档案时停止加载完整专利列表；从筛选结果或靶点档案进入后，URL 分区、刷新、浏览器历史和返回列表均保持同一研究上下文。前端模块仍独立懒加载，专利模块约 `12.40 kB`（gzip `4.24 kB`）。
- 最终真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 为 `72/72`。真实 PostgreSQL 夹具包含公开文本、授权事件、独立权利要求和规范靶点关联；场景验证三个分区、刷新恢复、返回保留关键词、靶点到专利再历史返回以及无页面级横向溢出。临时账号、实体和入库夹具均清零且未记录凭据。
- 首轮复验的新增专利场景已通过，但既有跨域场景仍按旧 `dialog` 语义定位详情；将断言升级为页面级标题和档案标识后，完整 72 项再次复验通过，未删除跨域历史路径。
- 能力矩阵 `patent_intelligence` 的 P0/P1 代码与本地真实运行证据现已闭环，状态由 `partial` 更新为 `implemented`。交易独立专业档案、正式授权数据覆盖、目标服务器容量和专业客户 UAT 仍未完成；商业交付门禁不会随代码域状态自动放行。

## 2026-07-26 临床试验专业档案闭环

- 临床试验详情从依赖当前列表的弹层升级为可分享、可刷新、可历史恢复的页面级专业档案。稳定地址为 `/workspace/research?view=trials&trial=<UUID>`；`section=design|outcomes|timeline` 分别表示设计与入组、终点与结果、时间线与中心，概览省略 `section`，未知分区失败关闭到概览。
- 档案直接读取既有 `GET /api/v1/trials/{trial_id}` 权威详情，不新建第二套搜索或详情后端。概览、研究设计/队列/入排标准、终点统计结果、注册状态历史和研究中心均来自同一租户隔离记录；列表筛选在进入、刷新和返回档案后保持不变，直接打开档案时不额外请求完整试验列表。
- 前端路由、组件和浏览器合同覆盖试验 ID 与分区的解析/序列化、无效分区回退、URL 驱动标签状态、加载/错误/空状态、返回列表以及来源谱系。结果页继续保留高密度服务端筛选、全命中集排序和许可感知引用，不用模型或当前行文本补造事实。
- 新镜像构建通过，研究入口仍维持 `19` 个懒加载视图，临床试验模块约 `30.10 kB`（gzip `8.66 kB`）。API 与 MCP 使用同一新镜像并通过健康检查。
- 最终真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 为 `72/72`。真实 PostgreSQL 试验包含药物干预、申办方、设计、队列、入排标准、主要终点、统计分析、中心和状态历史；场景从三类以上专业条件查询进入档案，验证四个分区、刷新恢复、返回保留条件及无页面级横向溢出。临时账号、实体和入库夹具均清零且未记录凭据。
- 前两轮分别发现验收夹具基础键与视口实体键不一致、以及标题按钮实际无障碍名称包含注册号；两处均按真实数据和真实可访问名称修正验收流程，未放宽产品断言。最终全量复验通过。
- 临床试验独立查询和专业档案的本地代码与真实运行证据已闭环。专利族专业档案随后也已闭环；交易独立专业档案、正式授权数据覆盖、目标服务器容量和专业客户 UAT 尚未完成，因此体验门禁 `entity_dossiers_and_cross_domain_links` 仍保持 `partial`。

## 2026-07-26 疾病专业档案闭环

- 疾病实体不再永久落入通用实体档案。全局查询、流行病学结果和旧 `view=entity` 疾病深链接统一规范到 `/workspace/research?view=disease&entity=<UUID>`；受控分区覆盖疾病概览、流行病学、研发格局、靶点证据、临床试验、专利、交易、监管、疾病动态和关联网络。旧 `programs` 等可映射分区会通过 `replaceState` 迁移，未知分区回退概览，非疾病实体失败关闭。
- `GET /api/v1/diseases/{disease_id}/dossier` 在服务端复用权威多领域档案与租户隔离流行病学查询，聚合项目、药物、规范靶点、研发机构、模态、阶段分布、试验、专利、标准患者人群、统计指标、地区和最近活动；端点同时要求 `dossiers:read`、`pipelines:read` 与 `epidemiology:read`，不能借基础实体权限绕过疾病负担数据授权。
- 疾病概览展示研发阶段、关联靶点、最新疾病负担、逐域覆盖、数据时点和缺口；流行病学数据库新增稳定 `disease_entity_id` 条件和规范实体选择，不再依赖自由文本维持疾病上下文。十个专业分区继续复用按稳定记录 ID 的跨域详情和许可感知谱系入口。
- 完整仓库门禁通过：Ruff 格式检查 `291` 个文件、Mypy `290` 个源文件、后端 `1039/1039` 且覆盖率 `84.33%`、前端 `213/213`、生成式 OpenAPI `323` 个文件无漂移；Biome、TypeScript、生产构建、工作台代码分割、能力矩阵、运维合同、Compose 与 Kubernetes 渲染均通过。疾病页作为独立懒加载模块输出约 `14.4 kB`，未并入研究入口首屏。
- 新 API 与 MCP 运行在同一镜像 `sha256:210305ba848f04fa1b5c318a09e02832aafabd12cd68ac6942f07c08d1b2ee64`，两者健康。真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 最终 `72/72` 通过，真实 PostgreSQL 夹具验证疾病摘要、疾病负担观测、专业分区 URL、完整流行病学跳转、稳定疾病条件、旧链接迁移及无页面级横向溢出；临时账号、实体和入库夹具均清零且未记录凭据。
- 首轮 Chrome 为 `68/72`，四个视口都已走通功能，但一个宽泛文本断言同时命中疾病筛选控件和结果表名称，被 Playwright 严格模式拒绝；断言收紧到语义明确的“疾病规范实体筛选”后全量复验通过，没有放宽功能、可访问性或布局门禁。
- `disease_dossier_and_epidemiology_continuity` 已闭环。临床试验、专利族和交易等其余独立专业档案、正式授权数据覆盖、目标服务器容量和专业客户 UAT 尚未完成，因此体验门禁 `entity_dossiers_and_cross_domain_links` 仍保持 `partial`，整体稳定分母不因单个档案闭环自动上调。

## 2026-07-26 公司专业档案闭环

- 组织实体不再永久落入通用实体档案。管线结果、公司时间线、全局实体结果和旧 `view=entity` 组织深链接统一规范到 `/workspace/research?view=company&entity=<UUID>`；受控 `section` 覆盖公司概览、研发管线、公司时间线、交易合作、关联网络、临床试验、专利、监管和公司动态。旧 `programs`、`company_intelligence` 等可映射分区会规范到新分区，未知分区回退概览，非组织实体失败关闭。
- `GET /api/v1/companies/{company_id}/dossier` 复用权威多领域档案和公司时间线读取，在服务端按当前项目版本聚合研发项目、药物、规范靶点、适应症、交易、模态、研发阶段分布、最高阶段、带日期事件和最近活动。端点同时要求档案、管线和交易读取权限；Web 使用生成式 OpenAPI 客户端和 TanStack Query，不从当前表格或自由文本推算公司摘要。
- 公司概览提供阶段分布、资产组合、最近事件、领域覆盖、数据时点和缺口警告；九个专业分区继续复用按稳定记录 ID 的领域查询、来源谱系和跨实体跳转。无项目和无时间线的真实空公司分别显示明确空状态，未观察到记录不被解释为全球不存在。
- 后端公司聚合/API 聚焦测试 `2/2` 通过；前端 Biome、TypeScript、生产构建边界和 `45` 个测试文件 `210/210` 通过。新 API 与 MCP 运行在同一镜像 `sha256:fe445a2644387bbf9a3781104398e18acefec0190eeb527c36b03781e70e8758`，两者健康，未认证调用公司档案端点返回 `401`。
- 最终仓库门禁为 Ruff `290` 个文件、Mypy `289` 个源文件、后端 `1037/1037` 且覆盖率 `84.30%`、前端 `210/210`、生成式 OpenAPI `320` 个文件无漂移；生产构建、能力矩阵、发布证据、运维合同、Compose 和 Kubernetes 渲染全部通过。Goal 及三份发布矩阵同步锁定 `1.9.1`，没有放宽生产签名或完整性规则。
- 最终真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 为 `72/72`。同一真实主场景从三类以上条件组合的管线结果进入公司档案，验证服务端摘要、资产回钻、时间线、分区 URL、刷新、浏览器返回、旧链接迁移、空状态、WCAG 和无页面级横向溢出；本地性能为 `CLS=0`、最大 `INP=24ms`、最大 `LCP=356ms`。报告确认临时账号、实体和入库夹具均为 `0`，不记录凭据，且明确 `production_claim=false`。
- 公司专业档案的代码与本地真实运行证据已闭环；疾病、临床试验、专利族和交易等其余专属档案、正式授权数据覆盖、目标服务器容量和专业客户 UAT 尚未闭合，因此体验门禁 `entity_dossiers_and_cross_domain_links` 仍保持 `partial`。

## 2026-07-26 药物专业档案闭环

- 药物不再永久落入通用实体档案。管线结果、全局实体结果和旧 `view=entity` 药物深链接统一规范到 `/workspace/research?view=drug&entity=<UUID>`；受控 `section` 覆盖概览、管线、靶点与适应症、活性、试验、专利、交易、监管、动态和结构。旧通用档案的业务分区会映射到对应药物分区并替换历史，不丢失分享链接的研究上下文。
- `GET /api/v1/drugs/{drug_id}/dossier` 复用权威多领域档案读取模型，在服务端聚合项目、规范靶点集合、适应症、机构、模态、最高总体/全球/中国阶段和最新状态日期；非药物实体失败关闭。Web 使用生成式 OpenAPI 客户端和 TanStack Query，不从列表行、浏览器文本或模型输出拼接摘要。
- 药物概览展示受治理摘要、可回钻靶点/适应症/机构、标准化二维结构、带日期里程碑、数据时点、逐域覆盖和缺口警告；专业分区继续复用按稳定记录 ID 的交易、监管、专利、新闻详情和许可感知谱系入口。缺少可选旧版 `targets` 或 `milestones` 数组时保留主靶点兼容读取并显示明确空状态。
- 定向后端 Ruff、Mypy 与 API/聚合测试 `20/20` 通过；前端 Biome、TypeScript、生产构建边界和 `44` 个测试文件 `207/207` 通过。新 API 与 MCP 运行在同一镜像 `sha256:9ef0e59fe724f3a0acd73111a5df688f140ee1f7ec8cef9c006f3683fc1957b7`，两者健康，未认证调用新端点返回 `401` 而不是 `404`。
- 最终真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 为 `72/72`。场景使用 PostgreSQL/RDKit 真实结构记录，从已筛选管线进入药物档案，验证区域阶段摘要、结构绘制、跨实体跳转、分区 URL、刷新和浏览器返回。前两轮分别暴露精确无障碍名称定位和移动端懒加载区域未滚入视口的验收脚本问题；修正为真实用户路径后全量复验通过。报告确认临时账号、实体和入库夹具均为 `0`，不记录凭据。
- `drug_dossier_and_cross_domain_links` 的代码与本地真实运行证据已闭环；公司、疾病等其余专属档案、正式授权数据覆盖、目标服务器容量和专业客户 UAT 尚未闭合，因此体验门禁 `entity_dossiers_and_cross_domain_links` 仍保持 `partial`。

## 2026-07-26 权威多靶点与靶点组合闭环

- 参考产品的真实组合查询和竞争格局工作流表明，“靶点组合”必须是可查询、可回钻并与列表共享条件的领域事实，不能由浏览器按药物名称或页面文本临时拼接。本平台只采用公开可观察的交互语义，未复制第三方源码、品牌资产、凭据或数据。
- `development_program_targets` 以项目、租户和靶点集合版本保存主靶点与联合靶点，历史版本只追加不覆盖；`development_programs` 保存当前集合版本和按规范实体 ID 排序的稳定组合键。迁移回填旧主靶点，并在 PostgreSQL 强制租户 RLS 和不可变更新/删除触发器。
- AI 治理 schema `2.13.0` 接受旧单靶点输入或最多 20 个规范靶点，强制唯一主靶点、角色与实体去重；物化层只有在集合变化时递增版本，并保留来源文档关系。读取层以当前版本为准，同时保留旧数据的单靶点兼容回退。
- `pharma.pipeline.search.v5` 在人员 HTTP、受控导出和收费 MCP 间共享同一查询语义。关键词和稳定靶点 ID 可命中主靶点或联合靶点；响应返回完整 `targets`、稳定 `target_combination_key` 和全命中集组合分布。外部工作台列表显示全部可回钻靶点，竞争格局可按组合筛选，筛选状态进入 URL 并可刷新恢复。
- 隔离 PostgreSQL 迁移完成升级、回退到 `7f3b9d2a6c81`、再升级到唯一 head `ad7e3c1f9b42`，状态 `passed`。真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768` 和 `390x844` 共 `72/72` 通过；四视口均验证组合图表、真实 API 过滤、URL 恢复和无页面级横向溢出。最终受控夹具、临时账号和入库数据均清零，报告不记录凭据。
- 首次 Chrome 运行为 `68/72`，暴露 PostgreSQL 枚举值与 SQLAlchemy 枚举成员名不一致的真实集成缺陷；根因修复为显式按枚举值持久化后重建并全量复验通过，没有关闭校验或添加环境特例。
- 正式 MCP 互操作门禁使用固定官方 Inspector `0.22.0` 与 Python MCP SDK `1.28.1`，对同一双靶点项目完成发现、分页、篡改游标拒绝、靶点档案、竞品管线、证据和用量结算，共 10 次真实计费调用并通过。两条客户端都校验完整靶点集合、主/联合角色和稳定组合键；报告 `production_claim=false`、`credentials_recorded=false`，夹具清理后项目、实体及项目-靶点行均为 `0`。
- 首次 MCP 运行暴露 `Z` 与 `+00:00` 两种等价时间表达产生不同商业预约指纹。MCP 网关现对全部受控时间范围统一转换为 UTC ISO 字符串，再同时用于预约和领域请求；无效或缺少时区的值仍由领域 API 失败关闭。修复后使用真实服务重新执行完整门禁通过。
- 正式授权数据覆盖、目标服务器容量和专业客户 UAT 仍未完成，因此 `dense_result_operations` 保持 `partial`；本地代码与受控夹具通过不构成商业生产同级声明。

## 2026-07-25 同查询管线格局深度增量（历史基线）

- 参考产品真实 `EGFR` 查询确认，专业结果不是独立静态看板：同一已应用查询可以在密集列表和可视化之间切换，并按研发阶段、靶点、适应症、靶点组合、机构和 Modality 分析，同时保留订阅/导出上下文。本平台只复用公开可观察的工作流语义，没有保存第三方数据、源码、凭据或品牌资产。
- `/api/v1/pipelines` 的完整授权命中集现在除全球/中国阶段、模态、地区和机构外，还按规范靶点 ID 与规范疾病 ID 返回项目数量和占比。聚合在 PostgreSQL 查询层完成，缺失实体单独标为“未披露”，不从名称或描述猜测；图表可继续应用稳定实体筛选或进入对应档案。
- 列表/格局切换继续由稳定 URL 的 `display` 状态控制。受控导出从列表内部工具栏提升为两种展示方式共享的结果操作，仍由服务端重新执行白名单查询、许可字段和数量上限，不导出当前页浏览器缓存。
- 后端/API 定向 `18/18`、前端组件/契约定向 `25/25` 通过；完整门禁为 Ruff 格式 `290` 个文件、Mypy `289` 个源文件、后端 `1034/1034` 且覆盖率 `84.24%`、前端 `204/204`、OpenAPI 客户端 `314` 个文件无漂移、生产构建、Compose 与 Kubernetes 渲染通过。
- 更新运行镜像后，真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过。主路径实际读取管线聚合 API，验证靶点/适应症图表、格局视图导出入口和无页面级横向溢出；临时账号、实体和入库夹具均为 `0`，报告未记录凭据。
- 本节记录当时的单靶点历史基线；该代码缺口已由上方 2026-07-26 权威多靶点增量关闭。正式授权数据与专业用户 UAT 仍未完成，`dense_result_operations` 继续保持 `partial`。

## 2026-07-25 恶意文件隔离治理闭环

- 源版本新增 `NOT_APPLICABLE / PENDING_REVIEW / HELD / RESCAN_REQUESTED / REJECTED / CLEARED` 隔离状态和单调递增版本。系统扫描命中、人员留置/拒绝/复扫、复扫清洁/再次命中和启动失败补偿都写入独立 append-only 决策表；表受强制 PostgreSQL RLS 和拒绝 `UPDATE/DELETE` 的触发器保护。
- 管理 API 提供有界案件列表、按需完整历史和处置端点。人员动作要求 `ingestion:manage`、租户隔离、幂等操作键、期望案件版本和原因；通用源版本重放不能处理活动隔离，永久拒绝不能由无人值守扫描释放，Temporal 启动失败会记录补偿转换并恢复原隔离状态。
- 内部数据工厂新增独立隔离队列和处置弹窗，展示威胁、状态、决策版本与不可变历史；复扫文案明确其仍强制经过 ClamAV。外部研究工作台不暴露运营入口。队列列表不加载全部历史，只有案件详情按需读取，避免案件量增长时产生无界响应。
- `make quarantine-workflow-acceptance` 用真实 EICAR 完成 ClamAV 命中、HTTP 留置、幂等重试、Temporal 复扫、再次命中、永久拒绝、通用重放阻断、append-only 触发器和三张操作表强制 RLS 验证；报告 `pharma.quarantine-workflow-acceptance.v1` 全部通过，数据库、源文件和对象制品均为 `0` 残留且不记录凭据。
- 首轮四视口 Chrome 为 `68/72`，原因是弹窗标题栏和页脚按钮共享“关闭”名称且刷新期间禁用；修复为唯一“关闭隔离案件”名称并显式等待操作完成。重建后真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 为 `72/72`，每个视口都真实调用隔离处置 API，页面无意外横向溢出，临时账号、实体和入库夹具均清零。
- 当前完整门禁为后端 `1016 passed / 29 skipped`、前端 `198/198`、Ruff 格式 `273` 个文件、Mypy `272` 个源文件、OpenAPI 客户端 `286` 个文件无漂移、生产构建通过；SQLite 全迁移链和隔离 PostgreSQL 升级/回退/再升级到唯一 head `e9a2c5d7f604` 均通过。跳过项仍是未配置的独立 PostgreSQL、MCP、OpenSearch、S3、SFTP 或 SMB 外部集成环境。
- `operator_asset_preview_quarantine_replay` 已从 `partial` 提升为 `implemented`。文件与解析治理域仍保持 `partial`，因为目标环境批准恶意文档 corpus、规模吞吐和安全运营 UAT 尚未完成，代码证据不能替代生产签字。

## 2026-07-25 自动入库运行图与精确取消增量

- 内部数据工厂的每条运行现在显示发现、快照、恶意文件扫描、解析、检索投影和 AI 治理六阶段真实聚合状态、版本完成数和有界进度；读取模型一次批量加载源版本，不按运行产生 N+1 查询。数据库原始扫描状态与跨阶段有效状态分开，避免扫描完成后把仍在解析或治理的工作误报为终态。
- Temporal activity 把服务端 workflow ID 与具体 run ID 写入运行记录。管理员取消时必须提交原因、幂等键和期望 `running` 状态；API 只向该精确 execution 发送取消，持久化操作和审计，重复同一请求返回同一结果，状态漂移、未绑定执行和异参复用均失败关闭。worker 在发现、快照、物化、安全扫描、解析、治理和投影边界检查取消标记，保留已经完成的不可变快照并阻止后续阶段继续发布。
- `make ingestion-cancellation-acceptance` 已在真实 Compose 运行线用 1200 个受控 Markdown 文件通过 HTTP、PostgreSQL、Temporal、worker 和文件对象存储链路：Temporal 精确 run 到达 `Canceled`，操作表和审计各一条，取消后解析/投影/治理成功数为 `0`，重复请求幂等，数据库、账号、源文件和对象制品清零，证据不记录凭据。
- 组件测试覆盖逐阶段运行图、进度、取消入口和必填原因；真实 Chrome 四视口验收将运行详情纳入内部工作台主路径。指定阶段恢复由下一增量闭环后，`operator_run_graph_and_recovery` 已提升为 `implemented`；目标环境吞吐演练和数据运营 UAT 仍单独保留。

## 2026-07-25 指定入库阶段恢复增量

- 源版本读取契约新增服务端计算的合法恢复点。安全扫描失败只能重新扫描；解析失败可选择完整安全重放或直接复用已成功扫描；AI 治理和检索投影只有在解析文档及所需文本产物存在时才开放。无版本错误码的投影失败以失败阶段和当前版本状态进行乐观并发校验。
- `from_stage` 已贯通 OpenAPI、人员 API、持久化操作、Temporal payload、worker 和数据工厂。worker 只重置所选阶段及其下游状态；治理重放可从同策略的成功不可变 ExtractionRun 恢复版本状态，不重复调用模型；异参幂等键、状态漂移、缺少快照或缺少前序产物均失败关闭。
- 内部工作台按服务端可用选项展示恢复起点，默认选择最窄恢复范围，要求原因，并保留安全扫描的完整重放选项。组件测试验证选择和请求契约；真实 Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四视口打开源对象、选择恢复点并验证无页面级横向溢出。
- `make source-stage-replay-acceptance` 使用真实 Markdown 完成解析、第三方 LLM API、PostgreSQL、Temporal、worker、事务 outbox、OpenSearch 和不可变对象存储首次入库，再分别注入解析、治理和投影失败并从 HTTP API 恢复。三阶段、幂等和审计均通过，数据库、账号、源文件、对象和检索文档清零；真实 Chrome 全套为 `72/72`。
- 该阶段当时仍缺人工隔离处置；该缺口现已由本文顶部“恶意文件隔离治理闭环”关闭，目标环境 corpus、吞吐和运营 UAT 仍独立保留。

## 2026-07-25 AI 治理运行追踪增量

- 现有内部 `AI 审核` 页面新增“运行追踪”标签，不新增第三套工作台或导航域。运行按租户、`governance:read`、状态、30 条页面和 100000 条最大偏移限制读取。
- `GET /api/v1/governance/runs` 返回来源版本与文件、模型 provider/name、schema、policy/prompt/input/source SHA-256、当前策略匹配、token、成本、状态、时间及最多 20 条结构化校验错误；不返回模型 structured output、原始 prompt、对象 URI、凭据或完整输入。
- 组件回归覆盖状态筛选、历史策略、指纹和校验错误；真实 Google Chrome 主验收在四个视口使用真实人员会话和 API 打开运行追踪并检查无页面横向溢出。正式 provider 账单对账、业务阈值和数据责任人 UAT 仍是目标环境门禁。
- 最终候选在真实运行时通过 Google Chrome `150.0.7871.128` 四视口 `72/72`；首次窄屏验收发现治理分页误用桌面宽表 `620px` 最小宽度，修复为独立可收缩分页后 `390x844` 与其余视口全部通过。后端全量为 `1004 passed / 29 skipped`，前端为 `196/196`，Ruff 检查 264 个文件、Mypy 检查 263 个源文件，OpenAPI 生成客户端 278 个文件无漂移，生产构建及隔离 PostgreSQL 迁移往返到唯一 head `b6d9f2a4c371` 通过。浏览器临时账号、实体和入库夹具均清零，报告不记录凭据。

## 2026-07-25 源版本安全阶段重放增量

- 失败或恶意文件命中的不可变源版本可由管理员填写原因后，从安全扫描阶段启动独立 Temporal 工作流；工作流重新执行恶意文件扫描、解析和后续治理，不修改原始快照，也不提供绕过扫描的“强制发布”。
- `POST /api/v1/admin/source-versions/{version_id}/replay` 要求 `ingestion:manage`、租户隔离、幂等操作键、期望版本状态、期望失败代码和明确起始阶段。操作持久化到独立表；同键同参数返回同一接受结果，同键异参、状态漂移、不可恢复错误和并发工作流均失败关闭，成功动作写入审计。
- 组件只为服务端允许的失败代码显示重放入口，提交成功后展示真实工作流 ID。该阶段当时仅开放 `malware_scan` 起点；解析、治理、投影阶段恢复和人工隔离处置现已分别由本文顶部两个增量闭环。
- `make source-version-replay-acceptance` 已在真实 Compose 运行线通过：受控 scanner 端口故障产生 `malware_scan_unavailable`，人员 HTTP API 接受重放，Temporal/worker 使用健康 ClamAV 重新扫描不可变快照并到达 `asset_only`，同一操作键返回相同结果，操作表与审计各一条，数据库、源文件和对象制品清零。该门禁不使用 mock；Temporal 历史按审计目的保留。

## 2026-07-25 源对象版本与解析预览增量

- 内部数据工厂新增只读“源对象与版本”台账，展示逻辑来源路径、文件类型、处理方式和最近发现时间；详情按不可变版本展示 SHA-256、大小、快照/恶意文件/解析/投影/治理阶段、解析器和失败原因。
- `GET /api/v1/admin/source-assets`、`/source-assets/{asset_id}` 和 `/source-versions/{version_id}/preview` 均要求 `ingestion:read` 并执行租户隔离。响应不下发对象存储 URI、原始对象地址或提取文本地址；解析文本按字符和 8 MB 读取上限返回，恶意文件命中版本服务端直接拒绝预览。
- API 回归覆盖资产清单、版本倒序、解析元数据、安全预览截断、恶意文件拒绝、404 和敏感地址不泄露；组件回归覆盖版本抽屉、恶意结果和只对已解析版本提供预览。该阶段当时未完成的隔离处置和指定阶段回放现已由本文顶部增量闭环。
- 该阶段候选的后端全量测试为 `1001 passed / 29 skipped`；其后 AI 治理运行追踪候选的最新完整结果见本文顶部。跳过项均需未配置的外部 PostgreSQL、MCP、OpenSearch 或 S3/SFTP/SMB 集成环境，不能据此声明目标生产环境已经验收。

## 2026-07-25 入库终态重放增量

- 内部数据工厂为 `failed`、`partial` 和 `canceled` 运行提供受控整次重放；操作员必须填写 3-500 字原因，成功提交后原运行与发现项保持不变，新运行使用独立关联标识。
- `POST /api/v1/admin/ingestion-runs/{run_id}/replay` 要求 `ingestion:manage`、租户隔离、客户端幂等操作键及原运行期望状态。服务端持久化操作状态；同键同参数成功重试返回同一接受结果，同键异参、状态漂移和并发占用返回 `409`，成功动作写入包含原因、期望状态和新运行标识的审计事件。
- 重放复用既有来源治理就绪校验、Temporal 工作流和单来源并发保护，没有新增旁路执行器。该增量关闭“终态失败只能查看、不能由 UI 恢复”的缺口；逐阶段运行图、取消和指定阶段回放仍保持未完成，能力矩阵继续为 `partial`。

## 2026-07-25 内部十域矩阵与检索投影可见性增量

- 新增受 JSON Schema 和测试约束的内部工作台能力矩阵，固定来源与许可、自动入库、文件解析、AI 治理、主数据、发布投影、数据质量、企业、商业和平台运营十域。测试拒绝缺域、重复能力、已实现项空证据、不存在的证据路径以及缺少真实来源/人员 UAT/无命令行完成规则。
- 矩阵没有新增公开入口；十域继续归入独立 `/workspace/internal`。当前明确记录 `split_rollback_and_impact_analysis`、`batch_withdraw_projection_rebuild`、`quality_trends_alert_ownership` 和 `workflow_slo_backup_migration_release_controls` 尚未开始，防止四个导航页面被误报为十域完成。
- 数据工厂通过生成式 OpenAPI 客户端并行读取真实 `/api/v1/admin/search/status`，展示 OpenSearch 可用性、集群、版本、alias 数量和投递状态；服务端继续执行 `ingestion:read` 授权。组件/工作台定向回归 `20/20`、矩阵测试 `3/3`、Biome 和 TypeScript 通过。

## 2026-07-25 专利与新闻稳定详情增量

- 专利族和新闻事件新增按稳定记录 ID 读取的人员 Domain API：`/api/v1/patent-families/{family_id}` 与 `/api/v1/news-events/{event_id}`。两者复用列表的权威聚合读取模型和租户条件，返回关联规范实体、来源字段及领域事实；不存在或跨租户记录返回 `404`，浏览器不从列表缓存拼接详情。
- `patent` 与 `news_event` 进入受控 `WorkspaceLocation`、分享 URL 和生成式 OpenAPI 客户端。专利/新闻列表、靶点全景和通用实体档案均进入同一专业详情抽屉，关闭详情后浏览器返回恢复原实体、原 `section`；来源页面和谱系抽屉保持独立操作。
- 后端详情、租户隔离和 API 回归 `5/5`，浏览器合同组合回归 `9/9`，前端详情/路由/档案定向回归 `46/46` 通过。重新构建部署后，真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，临时账号和实体均为 `0`，报告未记录凭据。
- 代码层的专利/新闻详情和跨域回跳缺口已关闭。正式授权数据覆盖与专业用户 UAT 仍是该体验门禁的完成规则，因此 `entity_dossiers_and_cross_domain_links` 暂保持 `partial`，不能用本地夹具替代业务签字。

## 2026-07-25 实体档案跨域详情连续性增量

- 通用实体档案和靶点全景中的交易、监管记录现在直接进入既有专业详情合同：交易使用稳定 `deal` 标识，监管使用稳定 `regulatory_event` 标识；入口由 `ResearchApp` 统一生成领域 URL，不在档案组件中复制详情状态或事实查询。
- 从专业详情关闭弹窗并使用浏览器返回后，会恢复原实体、原 `section` 和原档案上下文。来源与谱系入口仍是独立操作，避免把“查看专业详情”和“查看证据来源”混成同一动作。
- 首轮真实 Google Chrome 四视口回归为 `68/72`：监管链路已通过，交易链路因真实夹具的 `parties=[]` 生成空按钮名称而失败。根因修复为统一的 `dealPartiesLabel` 空值/非法值回退，并把组件回归改成真实空参与方形状；没有伪造交易方或放宽浏览器断言。
- 修复后前端 Biome、TypeScript、生产构建和 `189/189` 单元/组件测试通过；重新部署后 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，临时账号和实体均为 `0`，报告未记录凭据。
- 该批次当时只把已有稳定专业详情合同接入档案；专利与新闻稳定详情合同已由本文顶部增量补齐。正式数据覆盖和专业用户 UAT 仍未完成，因此 `entity_dossiers_and_cross_domain_links` 继续保持 `partial`。

## 2026-07-25 密集结果受控行选择增量

- 使用用户已登录参考页只读核对公开可见结果交互：基础查询结果采用专业密集表格并提供逐行复选框。审计没有读取网络私有载荷、源码、凭据或复制第三方数据与视觉资产；本平台继续使用独立组件、领域合同和设计系统。
- 共享 `VirtualDataTable` 新增受控行选择契约：稳定行 ID、逐行选择、全选/取消当前页、部分选择状态、选择计数、清空、可选上限和可访问名称均由显式 props 驱动。选择列兼容虚拟滚动、列显隐/重排、密度、全结果服务端排序和横向滚动；启用选择后同时冻结选择列及首个身份列。
- 监管工作域移除页面内重复的对比复选框列，改由共享选择契约直接驱动既有 `regulatoryCompareIds`。选择最多四项，状态继续进入 URL；每项仍通过真实详情 API 加载语义对比，清空后移除 URL 参数和对比表，不新增空壳批量按钮或第二套事实查询。
- 组件与监管集成定向测试 `13/13`，前端全量 `187/187`、Biome 和容器内 TypeScript/生产构建通过。重新部署后，Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，覆盖选择、URL、对比加载、刷新、清空、WCAG、视觉基线和页面级无横向溢出；临时账号与实体均为 `0`，报告未记录凭据。
- 该增量补齐了通用表格行操作和一个真实领域批量上下文，不把尚未接入既有持久化工作流的领域强行加上装饰性动作。专业用户 UAT 仍未完成，因此 `dense_result_operations` 继续保持 `partial`。

## 2026-07-25 四视口身份隔离与研究连续性验收增量

- 正式浏览器门禁不再让 `desktop-1440`、`desktop-1920`、`tablet-1024`、`mobile-390` 共用一个人员账号。脚本为同一次运行生成受正则约束的邮箱前缀，再创建四个独立临时人员；测试根据受控 project 名确定邮箱，密码仍为单次随机值且不写入报告。
- 四个账号共享租户级权威领域事实和固定测试夹具，但人员审计、最近访问、会话、监控与操作归属彼此隔离。外部总览的真实浏览器断言要求当前 project 能看到自己的访问，同时明确拒绝另外三个 project 的实体后缀，防止并行测试污染掩盖跨用户历史泄露。
- 导出策略仍只安装一次并在结束或失败时恢复原快照；清理按本次受控邮箱前缀删除四个账号及其不可变导出事件。首轮真实执行暴露 `psql -c` 不替换变量和项目化显示名破坏像素基线两个问题，均修复根因；一次 `71/72` 失败路径和最终 `72/72` 成功路径都验证临时账号残留为 `0`。
- 凭据派生是无 Node 依赖的纯函数，未知 project、危险前缀和缺失环境均失败关闭；新增 `2/2` 单元测试及 Bash/静态浏览器合同。前端全量测试现为 `185/185`，Biome、TypeScript 和生产构建通过；正式 Google Chrome 四视口最终 `72/72`，旧确定性像素基线、WCAG、性能阈值和全部业务流程继续通过，报告 `credentials_recorded=false`。
- 结合既有两级导航、八域总览启动区、URL 所有权、档案受控标签、浏览器前进/后退及服务端个人最近访问，`information_architecture_and_research_continuity` 从 `partial` 提升为 `implemented`。真实客户数据和专业用户 UAT 仍由产品完成规则独立要求。

## 2026-07-25 总览专业数据库发现增量

- 外部情报总览新增紧凑“专业数据库”启动区，直接覆盖现有药物与管线、临床试验、专利情报、交易与公司、监管与安全、流行病学、新闻与会议、结构检索八个工作域。它只调用既有 `ViewKey` 和稳定 URL，不新增数据接口、业务域、工作台或第三入口，也不暴露数据工厂、AI 审核、商业运营和企业管理等内部能力。
- 桌面和平板使用稳定四列，`390x844` 移动端使用两列；按钮保持固定最小高度、图标、完整名称和明确可访问名称。移动用户无需先打开侧栏即可发现全部专业域；左侧导航仍作为持续导航权威，并继续按核心查询、专业数据库和我的工作分组。
- 组件测试先在旧实现得到缺少 `专业数据库` region 的失败，再覆盖八域存在和专利路由；前端全量 Biome、`183/183` 单测、TypeScript 与生产构建通过。部署后真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 验证八域全部可见、总览直达专利、返回连续性、WCAG 自动审计和无页面级横向溢出，最终正式套件 `72/72`，临时账号与实体均为 `0`。
- 四张总览候选快照经人工检查确认桌面四列、平板四列和移动两列布局无重叠；同时发现并行四视口共享临时账号会使最近访问和总量随任务时序变化。候选动态 PNG 已全部删除，未进入正式像素基线；原有固定无结果查询基线继续由默认只读门禁验证，避免用不确定快照制造假绿色。
- 基于完整模块覆盖、两级导航、稳定路由、组件与四视口真实浏览器证据，`module_coverage_and_discoverability` 从 `partial` 提升为 `implemented`。正式数据覆盖和专业用户 UAT 仍由独立门禁约束，不随本状态迁移放宽。

## 2026-07-25 最近访问完整性与动态图表测试稳定性增量

- 修复个人最近访问读取模型的窗口遗漏：旧实现先截断最新审计事件、再过滤已删除实体；当大量失效历史占满窗口时，较早但仍有效的实体会被错误遗漏。新实现由数据库按规范实体 ID 聚合当前人员的最新成功访问，与当前租户权威实体表连接过滤，再按访问时间和稳定 ID 排序并执行返回上限，不依赖任意扫描条数。
- API 回归在两条有效访问前插入 126 条不存在实体的更新事件；旧实现先得到空列表，数据库聚合实现后稳定返回两条有效实体，同时继续覆盖跨用户隔离、重复访问、权限和参数上限。
- 管线竞争格局使用真实动态 `import()` 保持 ECharts 独立分块。针对全量并发单测中一次超过 Testing Library 默认 1 秒查询窗口的竞态，只把该动态图表断言的局部等待上限调整为 5 秒，没有增加全局超时、移除代码分割或使用模拟图表。组件测试连续 10 轮均为 `4/4`。
- Ruff、Mypy、后端/API/OpenAPI/能力矩阵与发布证据回归 `326/326`；Biome、两轮前端全量并发测试各 `182/182`，TypeScript 与生产构建通过。重新构建部署后，真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，临时账号和临时实体均为 `0`。
- 本增量提高已实现个人研究连续性和竞争格局的可靠性，不替代正式数据覆盖、生产 RUM、专业用户 UAT 或客户体验验收，因此能力矩阵状态不变。

## 2026-07-25 个人最近访问与研究连续性增量

- 外部工作台概览新增个人“最近访问”，数据来自服务端不可变审计事件，不使用 `localStorage`、演示记录或新建旁路历史表；实体详情、通用档案和靶点全景成功读取后记录规范实体 ID。
- `GET /api/v1/workspace/recent-entities` 只读取当前租户、当前人员的成功访问，按最新时间去重，并重新通过权威实体仓储校验当前可见实体；已删除、越权或不存在的历史对象不会显示，也不会占用返回上限。接口要求 `entities:read` 且拒绝非人员主体。
- 概览使用生成式 OpenAPI 客户端加载最多 8 项真实记录，空历史显示明确空状态；点击药物、机构等进入通用规范实体档案，点击靶点进入靶点全景，全部使用稳定实体 ID 和既有 URL 路由。
- API/OpenAPI/能力矩阵回归 `326/326`，前端 Biome、`182/182` 单测和生产构建通过。全量单测首轮出现既有管线动态图表加载竞态 `181/182`，未修改功能即重跑通过；真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，包含个人最近访问、稳定深链、WCAG 自动审计和临时数据清理。
- 该增量完成能力矩阵中的 `personal_recent_research_continuity`。个人与团队效率领域仍需正式数据、专业用户 UAT 和生产体验证据，因此领域和 `personal_productivity_and_delivery` 体验门禁继续保持 `partial`。

## 2026-07-25 专业查询时间预设增量

- 七领域专业查询的所有日期范围统一提供“全部、近 1 个月、近半年、近 1 年、自定义”菜单；相对范围按日历月计算并处理月末截断，提交前转换为明确起止日期，不把“近半年”等相对语义发送给后端。
- 预设和自定义范围继续映射到现有 `WorkspaceLocation`、稳定 URL 与权威领域 API；日期变化仍重置分页。临床真实链路验证 URL 保存 `YYYY-MM-DD`，生成式 API 客户端按后端契约提交当天 `00:00:00.000Z` 至 `23:59:59.999Z` 的完整边界。
- 纯契约测试覆盖全部预设、月末截断和手工范围识别；组件测试覆盖菜单选择、查询位置和无效自定义范围。前端全量测试 `180/180`、Biome、TypeScript 和生产构建通过。
- 真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `72/72` 通过，包含 URL、实际 `/api/v1/trials` 请求、刷新连续性、WCAG 自动审计和页面级无意外横向溢出；临时账号与临时实体均为 `0`。

## 2026-07-25 WCAG 与结构编辑器响应式增量

- 正式浏览器门禁升级为 `pharma.browser-acceptance.v7`：使用真实 Google Chrome `150.0.7871.128` 和 axe `4.12.1`，在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四个视口分别审计公开登录页及全部 14 个外部工作域，覆盖 WCAG 2.0/2.1/2.2 A/AA 自动规则。
- 根据真实失败结果修复共享弱对比文本、监控页错误的 tab 语义、Ketcher 动态图标按钮缺少可访问名称、触控目标尺寸及窄屏工具栏遮挡。结构编辑仍在桌面保留完整 Ketcher 工具，移动端保留可见绘制能力与高级 SMILES/SMARTS 输入，只隐藏窄屏无法完整显示的 Aromatize 快捷按钮。
- 前端全量测试 `175/175`、Biome、TypeScript 和生产构建通过；真实 Chrome 正式套件 `72/72` 通过，每个视口 `18/18`，无失败、重试、跳过或 flaky，临时账号与临时实体均为 `0`。
- 本地受控性能为 LCP `56-120 ms`、INP `16-24 ms`、CLS `0`。自动 axe 与本地指标不替代人工键盘/屏幕阅读器/缩放重排测试、生产 RUM P75、正式数据覆盖和专业用户 UAT，因此 `state_accessibility_and_responsive_quality` 仍保持 `partial`。

## 2026-07-25 专业管线查询分层增量

- 全局专业查询把管线高频条件保留在首层，将全球/中国阶段及起始时间、研发/商业化权益地区、项目标签和里程碑收纳到原生、可键盘操作的“更多管线条件”折叠区；折叠摘要显示当前高级条件数量。
- 所有高级条件都进入受控草稿、日期范围校验、稳定 URL 和既有 `pharma.pipeline.search.v5` 查询，不新增聚合事实 API，也不在浏览器内拼接或推断领域事实。
- 前端全量测试 `174/174`、Biome、TypeScript 和生产构建通过；真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `68/68` 通过，实际断言 `/api/v1/pipelines` 请求参数、URL 恢复和跨领域返回链路。
- 四视口视觉基线经人工检查后有意更新，默认只读像素比较再次通过；本地受控性能为 LCP `100-112 ms`、INP `16-40 ms`、CLS `0`，临时账号与临时实体均为 `0`。这些数据不是生产真实用户 P75，也不替代正式数据覆盖和专业用户 UAT。
- 参考产品仅用于分析高频条件常驻、长尾条件展开的交互组织。本平台使用独立组件、字段合同、视觉系统和数据，不复制第三方品牌、源码或专有数据。

## 2026-07-24 共享结果列顺序增量

- 八个结构化工作域共用的结果表新增列顺序管理；每列提供可键盘操作的上移/下移按钮，列顺序与显隐、密度一起按工作域持久化，详情往返和刷新后恢复，一键恢复默认视图同时清理三个展示偏好。
- 偏好读取会去重列 ID、剔除已删除或未知列，并把新列稳定追加到已有顺序末尾；旧版只包含显隐和密度的 `v1` 偏好可直接迁移，不需要清空用户本地状态。
- 组件测试先验证旧实现失败，再覆盖列顺序、未知字段清理、持久化、默认恢复和服务器排序导航竞态；前端全量测试 `163/163`、Biome `131` 文件、TypeScript 和生产构建通过。
- 首轮真实 Chrome 验收发现内层原生 `fieldset` 被外层菜单宽泛 CSS 选择器错误绝对定位，移动按钮被图标遮挡；收紧为直接子级选择器后，`1440x900`、`1920x1080`、`1024x768`、`390x844` 完整 `64/64` 通过，视觉快照未更新，临时账号和实体均清零。
- 参考产品本轮只观察公开可见的结果工作流：统计图/列表切换、更新时间、来源和导出记录保持在同一研究上下文。本平台采用独立设计和共享表格实现，没有复制品牌资产、源码或第三方数据。权限感知领域导出已实现并通过真实 Chrome 文件验收；专业用户 UAT 仍未完成，因此 `dense_result_operations` 保持 `partial`。

## 2026-07-24 全局实体检索全结果排序与分页增量

- 全局实体检索已从固定前 100 条和浏览器当前页排序升级为受控全命中集排序及 100 条有界分页；名称、实体类型和更新时间表头由服务端排序，默认相关性继续使用 OpenSearch 混合检索。
- 字段排序会切换到完整词法命中集后再排序，避免只对向量候选集排序；数据库回退提供相同字段、方向和稳定并列键，OpenSearch 命中顺序在 PostgreSQL 实体回填时保持不变。
- 排序字段、方向和 offset 进入人员 API 响应、稳定 URL、生成式 OpenAPI 客户端、商业 Agent 查询身份和收费 MCP；MCP 仍只公开签名游标与页深，不公开任意 offset 或 total。
- 真实 PostgreSQL 与 OpenSearch 验证了排序先于分页；后端非集成测试 `989/989`、前端 `162/162`、Google Chrome 150 四视口 `64/64` 通过。浏览器验收同时发现并修复服务器排序导航导致表格默认偏好重置丢失的竞态，临时账号和实体均清零。
- 八个结构化工作域现均使用全结果服务端排序并提供权限感知领域导出；列重排已由本文顶部增量完成。专业用户 UAT 仍未完成，因此 `dense_result_operations` 保持 `partial`。

## 2026-07-24 交易、监管与流行病学全结果排序增量

- 交易、监管和流行病学列表已从当前页排序升级为受控全命中集服务端排序；排序进入版本化 Domain API、稳定 URL、商业 Agent API、MCP 计费查询身份和生成式 OpenAPI 客户端，刷新后恢复。
- 交易状态使用显式生命周期序，披露金额排序必须限定单一币种；监管主题、流行病学疾病和发布方均按同租户规范实体名称排序，空值置后并使用领域标识及稳定 ID 消除并列不确定性。
- 真实 Google Chrome 150 使用隔离 PostgreSQL 三域记录，在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完成新增场景 `4/4`；完整套件 `64/64` 通过，验证真实 API 参数/响应元数据、URL、刷新恢复、表头状态和页面级无横向溢出，临时账号及实体均清零。
- 该批次完成后曾有七个结构化工作域完成全结果排序；全局实体检索和列重排已由本文顶部增量继续升级。当时尚未完成的权限感知领域导出仍阻止 `dense_result_operations` 升级。

## 2026-07-24 临床、专利与资讯全结果排序增量

- 临床试验、专利族和资讯列表已从当前页排序升级为受控全命中集服务端排序；只开放具有明确数据库语义的字段，JSON 聚合和未定义业务顺序的列不显示可排序控件。
- 三域排序字段与方向进入版本化 Domain API、稳定 URL、商业 Agent API、MCP 计费查询身份和生成式 OpenAPI 客户端；空值置后并使用领域标识和稳定 ID 消除并列不确定性，资讯发布方按同租户规范机构名称排序。
- 真实 Google Chrome 150 使用隔离 PostgreSQL 临床、专利和资讯记录，在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 完成新增场景 `4/4`；完整套件 `60/60` 通过，验证真实 API 参数/响应元数据、URL、刷新恢复、表头状态和页面级无横向溢出，临时账号及实体均清零。
- 该批次完成后曾有四个结构化工作域具备全结果排序；交易、监管、流行病学、全局实体检索和列重排已由本文顶部增量继续升级。当时尚未完成的权限感知领域导出仍阻止 `dense_result_operations` 升级。

## 2026-07-24 管线全结果排序增量

- 管线列表的药物、靶点、适应症、机构、模态、全球/中国阶段和状态日期表头改为受控全命中集服务端排序；阶段使用业务阶段序，空值置后并以稳定项目 ID 消除并列不确定性。
- 排序字段与方向进入版本化 `pharma.pipeline.search.v5` 合同、稳定 URL、人员 API、商业 Agent API、MCP 计费查询身份和生成式 OpenAPI 客户端；刷新后恢复，不由浏览器重排当前页冒充全量排序。
- Google Chrome 150 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 执行完整 `56/56` 验收；四种视口均真实点击药物表头并验证 API 参数、响应排序元数据、URL 和刷新状态，没有更新视觉快照，临时账号及实体均清零。
- 临床、专利、资讯、交易、监管、流行病学、全局实体检索、列重排和权限感知领域导出已在后续增量升级；专业用户 UAT 尚未完成，因此 `dense_result_operations` 保持 `partial`。

## 2026-07-24 研究发布时间线增量

- 现有“新闻、公告与会议动态”增加列表/研究发布时间线分段控制，没有新增导航或工作台。
- `content_scope=research` 由服务端限制为 `publication`、`conference_abstract`、`poster`、`presentation`；`display=timeline` 写入 URL 并在刷新后恢复，前端不能把普通新闻伪装成研究发布。
- 时间线显示日期、治理事件类型、标题、会议/期刊、摘要、发布方、关联实体、原始发布页和记录级溯源；结果继续使用 100 条有界分页。
- 后端领域测试、前端组件/合同/路由测试、OpenAPI 生成链路和部署后真实 HTTP 请求均通过。当前正式租户的研究发布记录为 0，协议验证不等同于生产数据覆盖率。
- Google Chrome 150 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四视口完成列表切换、服务端 scope 请求、URL 恢复、时间线内容和页面级无横向溢出，新增流程 `4/4` 通过。

## 2026-07-24 知识专题覆盖与版本增量

- 现有“知识专题”入口内增加“专题正文/覆盖与版本”切换，没有新增工作台或暴露内部治理操作。
- 当前版本显示治理事实、独立来源、关联实体、缺少有效引用数量和 predicate 覆盖；版本时间线可选择历史版本并查看新增/移除事实、来源标题和原文定位。
- API 对历史限制为 50 版，服务端上限为 100 版；详细差异每类最多返回 100 项并显式标记截断。专题、版本和差异读取均执行 `knowledge:read` 与租户 RLS。
- SQLite API 测试、生成 OpenAPI 合同、前端组件/合同测试以及一次性 PostgreSQL 迁移往返、RLS 和 append-only 篡改测试已通过。
- 部署后的真实 HTTP API 已读取现有专题的覆盖、版本和差异；Google Chrome 150 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四视口完成新增流程 `4/4`，同页切换、版本选择、来源定位和页面级无横向溢出均通过。完整性能门禁仍待当前外部高 CPU 专利提取任务释放资源后复验。

## 2026-07-24 监控共享撤销增量

- 已保存检索所有者可在监控工作台切换“仅自己/企业共享”；其他同租户人员看到明确只读提示，没有修改入口。
- 撤回共享在服务事务内暂停其他所有者的继承主题，重新启用和后台消费者均再次验证当前可见性；旧固定查询版本不能继续产生提醒。
- SQLite 服务/API 回归、一次性 PostgreSQL 迁移/RLS/真实消费者验收和前端组件测试通过。真实 Google Chrome 在四视口以单工作线程完成新增监控流程 `4/4`。
- 完整 44 项 Chrome 性能门禁本轮两次受同时运行的外部高 CPU 计算任务影响，出现 INP 超限和 30 秒流程超时；门禁没有放宽，当前不能把本轮功能 Chrome 结果替代完整性能证据。

## 2026-07-24 共享结果操作增量

- 八个外部结构化工作域使用同一虚拟化结果表，并分别使用稳定偏好键；列可见性和标准/紧凑密度在跨页面与刷新后恢复，一键恢复默认视图。
- 该增量最初将全部领域排序明确限定为“当前页”；当前八个结构化工作域已由后续增量全部升级为全命中集服务端排序。表内横向滚动保持首个身份列可见。
- 真实 Google Chrome 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 重跑 44 条场景并全部通过；新增验收覆盖偏好持久化、排序边界、冻结列和页面级无意外横向溢出，视觉基线未更新。
- 组件测试覆盖有效偏好恢复、非法字段剔除、当前页/全结果两种排序提示、受控排序回调、列隐藏、密度切换和默认恢复；服务器导航前同步持久化默认偏好。列重排和权限感知领域导出已完成；专业用户 UAT 尚未完成，`dense_result_operations` 保持 `partial`。

## 2026-07-24 四视口视觉与性能增量

- 真实 Google Chrome `150.0.7871.128` 在 `1440x900`、`1920x1080`、`1024x768`、`390x844` 执行同一套 11 条场景，共 `44/44` 通过；没有失败、重试、跳过或 flaky。
- 工作台基线来自真实登录与真实 API 的固定无结果查询，四张仓库内 PNG 均通过默认只读像素比较，允许差异比例上限 `0.001`；摘要与来源记录在 `apps/web/e2e/visual-baselines/manifest.json`。
- 已认证工作台完整导航的本地受控指标：LCP `80-120 ms`、INP `16-32 ms`、CLS `0`，临时账号和临时实体运行后均为 `0`；探针在登录后重新导航并重置，避免把登录页 LCP 误算为工作台首屏。
- Chrome 验收发现并修复了两个真实窄屏问题：联想层遮挡/移动提交按钮，以及列选择浮层遮挡结果行。
- 本增量把 `performance_and_visual_regression` 从 `not_started` 提升为 `partial`。后续已经完成 Edge 当前及前一主版本自动兼容门禁，以及不复制第三方二进制的外部内容寻址成对归档机制；生产真实用户 P75、真实批准参考流程的人工差异结论和专业用户 UAT 仍未完成，因此不能据此宣称整体商业同级。

## 状态

**PASS（本次基础查询升级范围）**

检查日期：2026-07-22

## 对照对象

- 参考：用户已登录的 NextPharma 基础查询页及用户标注截图。
- 本地：`/workspace/research?view=explorer`，使用 Codex 内置浏览器的真实本地运行时与真实会话。
- 产品边界：借鉴专业医药数据库的信息密度、分域查询和筛选组织，不复制第三方品牌、源码、专有字段或数据。

## 可见结构检查

| 检查项 | 结果 | 说明 |
|---|---|---|
| 顶部全局搜索 | PASS | 始终可见，与当前工作台上下文分离 |
| 左侧专业导航 | PASS | 外部研究能力独立；没有内部入库、治理、计费入口 |
| 基础查询层级 | PASS | 标题、领域切换、查询条件、治理筛选和结果连续排列 |
| 信息密度 | PASS | 8 个真实领域入口、单行主查询、紧凑筛选和结果摘要 |
| 布局稳定性 | PASS | Codex 浏览器桌面截图无重叠、裁切或文本溢出 |
| 响应式 | PASS | Google Chrome 自动验收覆盖桌面与移动端，共 22 项通过 |
| 状态完整性 | PASS | 初始、联想加载/失败、查询加载/错误、空结果、保存和详情状态已实现 |
| 可访问性 | PASS | 语义导航、组合框、分组、对话框、精确标签和 `aria-pressed` 已验证 |

## 交互检查

- 领域标签发送真实 `entity_type`，不是仅改变样式。
- 治理标签发送真实 `review_status`，并写入 URL 和保存检索合同。
- 输入至少 2 个字符后 250 ms 请求规范实体联想，最多 10 条，支持取消。
- 结果名称打开通用实体详情；靶点可继续进入多域全景。
- 空数据库中检索 `EGFR` 返回 0 条及明确空状态，没有填充演示结果。

## 视觉结论

本地页面已达到专业数据库工作台所需的连续、紧凑、可扫描布局。与参考页相比，本地保留自己的深色侧栏、青绿色状态色和中性数据表风格；这属于品牌与设计系统边界，不做像素级复制。查询区采用参考页同类的“领域标签 + 字段行 + 筛选行”结构，但只显示已接通的真实条件。

## 尚未冒充完成的范围

- 药物模态、适应症树、全球/中国研发阶段、里程碑、公司地域、监管资格等筛选尚无对应领域事实合同，因此本次没有绘制不可用控件。
- 当前本地权威库尚未导入正式业务实体，无法用真实生产数据做结果密度和详情字段完整率验收。
- 药物专属详情已由本文顶部增量闭环；机构、疾病、临床、专利和交易仍需各自的专属详情页，当前通用实体档案只是这些领域的可用入口，不是最终形态。

以上缺口不影响本次基础查询架构和交互验收，但仍阻止项目被宣称为与成熟商业医药数据库整体同级。

---

## 药物与研发管线增量验收

检查日期：2026-07-22

验收环境：WSL Compose 真实运行时、PostgreSQL 18 + RDKit、Codex 内置浏览器。测试使用隔离的持久化验收记录，完成后必须删除，不计入正式业务数据。

| 检查项 | 结果 | 说明 |
|---|---|---|
| 真实 API 查询 | PASS | 登录后 `GET /api/v1/pipelines` 返回 200；非法阶段返回 422 |
| 组合筛选 | PASS | 关键词和最高阶段同时作用于服务端查询，结果与精确 facets 一致 |
| 稳定 URL | PASS | `q=EGFR&phase=phase_2` 刷新后恢复输入、选项和结果 |
| 管线表格 | PASS | 药物、靶点、适应症、机构、模态、阶段、地区、日期、来源和档案列全部可见 |
| 实体深链 | PASS | 历史基线可打开通用药物档案；现已升级为带稳定分区、服务端摘要、结构和跨域详情的药物专业档案 |
| 覆盖边界 | PASS | 明确显示授权、时效和治理状态限制，不把未观察到记录表述为不存在 |
| 控制台 | PASS | 本地主链路无应用错误或警告 |
| 宽屏布局 | PASS | 实测表格 `clientWidth=1391`、`scrollWidth=1391`，无不必要横向溢出 |
| 移动断点 | 未验证 | Codex 浏览器视口覆盖未实际改变窗口尺寸；本次不据此声明移动端通过 |

当前正式数据库没有研发管线业务记录，因此本次证据只证明运行协议、真实数据库查询和界面链路成立，不证明商业数据覆盖率或业务 UAT 已完成。

---

## 临床试验与结果增量验收

检查日期：2026-07-22

验收环境：重建后的 WSL Compose 真实运行时、PostgreSQL 18、Codex 内置浏览器。测试使用具备固定 marker 的隔离持久化记录和独立只读验收账户；验收结束后用户、试验、实体与关系计数均恢复为 `0`，不计入正式业务数据。

| 检查项 | 结果 | 说明 |
|---|---|---|
| 真实 PostgreSQL 查询 | PASS | `GET /api/v1/trials` 的关键词、注册平台、状态、分期和研究类型组合筛选返回唯一试验 |
| JSON 分期分面 | PASS | PostgreSQL `json_array_elements_text` 路径返回精确 `PHASE2: 1`，注册平台、状态和研究类型分面同步一致 |
| 参数边界 | PASS | `offset=100001` 在 API 边界返回 `422`，没有进入无界查询 |
| 独立人员工作域 | PASS | 外部导航具有独立“临床试验”入口、标题、筛选区、结果表和稳定 URL；内部工作台没有混入该页面 |
| 组合筛选与清除 | PASS | Codex 浏览器实际操作四个下拉筛选和关键词；查询写入 URL，清除后 URL 与五个控件同时归零 |
| 刷新恢复 | PASS | 在独立标签刷新完整深链接后，关键词、四个筛选值和唯一结果全部恢复 |
| 关联实体深链 | PASS | 试验行返回药物和靶点两个稳定实体；点击靶点进入 `/workspace/research?view=entity&entity=...` 的治理档案 |
| 信息密度与布局 | PASS | 与 NextPharma 参考页同轮并列截图检查；采用连续筛选带和密集数据表，桌面实测 `body clientWidth=1707`、`scrollWidth=1707`，无页面级横向溢出 |
| 表格宽度 | PASS | 桌面实测结果视口 `clientWidth=1391`、`scrollWidth=1391`，字段未被页面级裁切 |
| 控制台 | PASS | 完整查询、筛选、清除、跳转和刷新链路无浏览器 `error`、`warn` 或 `warning` |
| 移动断点 | 未验证 | Codex 浏览器视口覆盖把 `390x844` 错误映射为 `1560x3376` 并生成平铺画面；已重置覆盖，本次不据此声明移动端通过 |

该历史增量在 2026-07-26 已由页面级临床试验专业档案继续闭环：队列、终点、结果和状态历史视图现已实现并通过四视口真实 Chrome 验收。正式数据库仍没有合法授权的生产试验覆盖，因此不能据此宣称达到商业数据覆盖或业务 UAT 要求。

---

## 临床结果密集字段与治理查询增量验收

检查日期：2026-07-26

验收环境：WSL Compose 真实运行时、PostgreSQL 18 + RDKit、OpenSearch 3.7、统一应用镜像 `sha256:73f4b98937e12e951636c842feb9a42e86b32e7cade7e0db9588b6cb223299d9`、项目 Playwright 调用 Google Chrome。隔离验收数据在执行后清零，不计入正式业务数据。

| 检查项 | 结果 | 说明 |
|---|---|---|
| 治理与迁移 | PASS | `b8e4c1d7a206` 增加可空试验简称、受限 `iit/ist` 和非空治疗线次数组；治理物化只接受结构化来源字段，不按申办方或标题推断 |
| 查询合同 | PASS | `pharma.clinical_trial.search.v6` 在 Web、HTTP、导出、保存订阅、商业 Agent API 和 MCP 共享试验简称、发起类型和治疗线次过滤、分面及稳定排序 |
| 结果密度 | PASS | 列表与专业档案显示试验简称、IIT/IST、治疗线次；核心疗效只读取结构化主要终点首项结果，缺失时显示“未报告” |
| 稳定状态 | PASS | 三项筛选进入生成式 OpenAPI 客户端、商业请求身份、稳定 URL、刷新恢复、保存查询和监控重放 |
| 全量工程门禁 | PASS | Ruff、Mypy `292` 个源文件、后端 `1071/1071`、前端 `248/248`、OpenAPI `335` 个生成文件、生产构建和部署合同通过 |
| 真实运行时 | PASS | `/health/live` 与 `/health/ready` 通过，数据库迁移头为 `b8e4c1d7a206`，API、MCP、parser、worker、搜索和监控服务健康 |
| 真实浏览器 | PASS | Chrome/Playwright `88/88`；1440、1920、1024、390 四个项目各 `22`，无快照更新，临时账户、实体和入库夹具结束后均为 `0` |
| 发布证据校验 | PASS | 发布证据验证用例 `300/300`，新增 `clinical_result_dense_fields` 场景被要求在全部四个 Chrome 项目通过 |

该批证明代码、查询语义、运行时和受控验收数据链已经闭合，不证明正式商业数据已覆盖全球试验，也不替代数据许可审查、专业用户 UAT、目标服务器容量测试和生产 SLO 批准。

---

## 2026-07-30 v1.9.50 全局管线临床结果与交易信号验收

- 共享合同：新增 `pipelineSignals.ts`，由全局专业查询和管线专业页共同使用结果评价标签、存在性标签及四条互斥/金额校验；专业页原有行为未复制或降级。
- 人员交互：全局查询从权威 facet 目录选择临床结果存在性、结果评价、交易存在性和币种，并输入潜在总额上下限；选择“无结果”或“无交易”会清空并禁用依赖字段。
- 稳定状态：`has_clinical_results=true`、`clinical_result_evaluation=positive`、`has_deal=true`、`deal_currency=USD`、金额 `100000000` 至 `500000000` 同时进入真实 `/api/v1/pipelines` 请求、稳定 URL 和刷新恢复。
- 工程门禁：定向组件/合同回归 `42/42`；`make frontend-check` 通过 OpenAPI 352 文件漂移、Biome、TypeScript、`308/308` 前端测试和生产构建；相关后端/API/MCP/监控/矩阵回归 `82/82`。候选入口为 `research-main-D1uf4I3A.js`。
- 视觉审阅：Chrome 显式更新后人工检查 `1440x900`、`1920x1080`、`1024x768`、`390x844` 四张工作台基线；新增区保持折叠，桌面/平板栅格稳定，移动端无横向溢出、文字或按钮重叠。
- 失败与恢复证据：首轮误用仍提供旧 `research-main-DFISooxa.js` 的 `8080` 容器，目录缺失并受旧候选键盘行为影响，仅 `100/112`，不计为通过；改用本批 `research-main-D1uf4I3A.js` 的隔离 preview 后功能达到 `108/112`，剩余四项均为新增折叠区造成的预期工作台像素基线变化。显式基线更新轮 `112/112` 仅用于人工审阅，不生成正式证据；之后三轮均在只读基线上通过。
- 正式浏览器证据：Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99`、Edge previous `149.0.4022.98` 均为 `112/112`，四视口各 `28/28`，合计 `336/336`；所有视口 CLS 为 `0`，三浏览器最慢 LCP `164 ms`、最慢 INP `56 ms`。快照只读、临时账户/实体/入库夹具均为 `0`，凭据未写入报告。
- 证据边界：浏览器连接隔离 `vite preview` 与现有真实 API/PostgreSQL/OpenSearch；现有 `8080` 容器仍提供旧候选，未在本批替换。正式授权数据、参考产品真实提交、业务 UAT、目标服务器和生产性能仍未验证。

---

## 2026-07-30 v1.9.51 全局临床试验属性与结果评价验收

- 共享合同：新增 `trialFilters.ts`，由全局专业查询和临床试验专业页共同使用 IIT/IST、治疗线次、结果评价显示值及“未发布结果+结果评价”互斥校验；既有 `pharma.clinical_trial.search.v10` 和专业页查询行为未复制或降级。
- 人员交互：全局查询可填写试验简称并选择发起类型、治疗线次和结果评价；选择“未发布结果”会立即清空并禁用结果评价，直接构造冲突草稿则在提交前失败关闭。
- 稳定状态：`acronym=BRIDGE-*`、`initiation_type=ist`、`therapy_line=first_line`、`result_evaluation=positive` 同时进入真实 `/api/v1/clinical-trials` 请求、稳定 URL 和刷新恢复。
- 工程门禁：定向组件/合同回归 `40/40`；`make frontend-check` 通过 OpenAPI 352 文件漂移、Biome、TypeScript、`309/309` 前端测试和生产构建；相关临床/API/MCP/监控/矩阵后端回归 `68/68`。候选入口为 `research-main-BeXRVvDE.js`。
- 正式浏览器证据：Google Chrome `150.0.7871.128`、Edge current `150.0.4078.99`、Edge previous `149.0.4022.98` 均为 `112/112`，四视口各 `28/28`，合计 `336/336`；三轮均只读复用既有视觉基线，没有快照更新，临时账户、实体和入库夹具均为 `0`。证据位于仓库外 `pharma-intelligence-runtime/evidence/browser/main-professional-trial-profile-20260730-*.json`。
- 证据边界：浏览器连接隔离 `vite preview` 与现有真实 API/PostgreSQL/OpenSearch；临时 `5174` 已停止，现有 `8080` 容器仍提供旧候选且未替换。正式授权数据、参考产品真实提交、业务 UAT、目标服务器和生产性能仍未验证。
