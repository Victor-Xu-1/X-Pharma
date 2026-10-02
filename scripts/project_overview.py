from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRICES = (
    "external-workbench-capability-matrix.json",
    "internal-workbench-capability-matrix.json",
)
STATUS = {"implemented": "代码已实现", "partial": "部分实现 / 待验收", "planned": "计划中", "not_started": "未实现"}
STYLE = """
:root{color-scheme:light;
--paper:#faf9f5;
--ink:#292824;
--muted:#66655e;
--line:#dedbd2;
--accent:#a65135}

*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;
background:var(--paper);
color:var(--ink);
font:16px/1.75 system-ui,sans-serif}

main{max-width:1120px;
margin:auto;
padding:48px 32px 80px}
header{border-bottom:1px solid var(--line);
padding-bottom:32px}

.brand{display:flex;
align-items:center;
gap:12px;
font-size:19px}
.brand img{width:46px;
height:46px}
h1,h2,h3{font-family:Georgia,'Songti SC',serif;
font-weight:500;
line-height:1.3}

h1{font-size:clamp(32px,5vw,54px);
margin:28px 0 18px}
h2{font-size:29px;
margin:48px 0 18px}
h3{font-size:21px;
margin:0 0 12px}

p{margin:10px 0 16px}
.lead{max-width:860px;
color:var(--muted);
font-size:18px}
nav{display:flex;
gap:18px;
flex-wrap:wrap;
margin-top:24px}

a{color:var(--accent);
text-underline-offset:4px}
a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);
outline-offset:4px}

.grid{display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));
gap:16px}
.card,.node{border:1px solid var(--line);
border-radius:14px;
padding:21px;
background:#fffefa}

.card p:last-child{margin:0}
.flow{display:grid;
gap:14px}
.flow-row{display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));
gap:14px}
.node strong{display:block;
margin-bottom:8px}

.arrow{text-align:center;
color:var(--muted);
font-size:14px}
.note{border-left:3px solid var(--accent);
padding:12px 18px;
background:#f2ede4}

.muted,small{color:var(--muted)}
.pill{display:inline-block;
border:1px solid var(--line);
border-radius:30px;
font-size:12px;
padding:2px 10px;
white-space:nowrap}

details{margin:12px 0;
border:1px solid var(--line);
border-radius:12px;
background:#fffefa}
summary{cursor:pointer;
padding:17px 20px;
font-weight:550}

.domain-body{padding:0 20px 18px}
.table-region{overflow-x:auto}
table{width:100%;
border-collapse:collapse;
min-width:620px;
font-size:14px}
th,td{text-align:left;
padding:12px;
border-top:1px solid var(--line);
vertical-align:top}

th{color:var(--muted)}
table{table-layout:fixed}
th:nth-child(2),td:nth-child(2){width:80px;white-space:nowrap}
th:nth-child(3),td:nth-child(3){width:140px;white-space:nowrap}
code{font:13px ui-monospace,monospace;
overflow-wrap:anywhere}
ul{padding-left:21px}
.evidence{margin-top:6px;
font-size:12px;
overflow-wrap:anywhere}

footer{margin-top:50px;
border-top:1px solid var(--line);
padding-top:22px;
font-size:13px;
color:var(--muted)}
@media(max-width:760px){main{padding:28px 20px 50px}
.grid,.flow-row{grid-template-columns:1fr}
h2{margin-top:34px}
.card,.node{padding:18px}
}

@media print{body{background:white}
main{max-width:none;
padding:0}
details{break-inside:avoid}
nav{display:none}
summary{list-style:none}
.grid{grid-template-columns:repeat(3,1fr)}
}

"""


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_matrix(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("domains"), list):
        raise ValueError(f"Invalid capability matrix: {path.name}")
    return value


def render_domains(matrix: dict[str, Any]) -> str:
    output: list[str] = []
    for domain in matrix["domains"]:
        rows: list[str] = []
        for capability in domain["capabilities"]:
            evidence = " · ".join(f"<code>{escape(item)}</code>" for item in capability["evidence"])
            rows.append(
                f"<tr><td><code>{escape(capability['id'])}</code><div class='evidence'>{evidence}</div></td>"
                f"<td>{escape(capability['priority'])}</td>"
                f"<td>{escape(STATUS.get(capability['status'], capability['status']))}</td></tr>"
            )
        gaps = "".join(f"<li>{escape(item)}</li>" for item in domain.get("remaining_gaps", []))
        output.append(
            f"<details><summary>{escape(domain['title'])} <span class='pill'>"
            f"{escape(STATUS.get(domain['status'], domain['status']))}</span></summary>"
            "<div class='domain-body'><div class='table-region' role='region' "
            f"aria-label='{escape(domain['title'])}能力清单' tabindex='0'>"
            "<table><thead><tr><th scope='col'>能力与源码证据</th><th scope='col'>优先级</th>"
            "<th scope='col'>状态</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
            + (f"<p>仍需完成：</p><ul>{gaps}</ul>" if gaps else "")
            + "</div></details>"
        )
    return "".join(output)


def build_document(root: Path = ROOT) -> str:
    product_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    matrix_root = root / "deploy/release"
    research, internal = [load_matrix(matrix_root / name) for name in MATRICES]
    logo = base64.b64encode((root / "apps/web/src/assets/brand/X-Pharma-logo-128.png").read_bytes()).decode("ascii")
    fingerprint = hashlib.sha256(b"".join((matrix_root / name).read_bytes() for name in MATRICES)).hexdigest()
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>X-Pharma v{escape(product_version)} · 项目目标与完整架构</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<header>
<div class="brand">
<img src="data:image/png;base64,{logo}" alt="">
<strong>X-Pharma</strong>
<span class="pill">v{escape(product_version)}</span>
<span class="pill">Apache-2.0</span>
</div>
<h1>让研发情报可查询、可追溯、可治理。
</h1>
<p class="lead">一个由原始资料、权威事实、证据与知识版本组成的医药情报平台。

人员研究、内部运营与 Agent 访问使用同一事实和许可边界；
模型辅助提取，不能直接改写已发布主数据。
</p>
<nav aria-label="报告导航">
<a href="#goals">项目目标</a>
<a href="#architecture">完整架构</a>
<a href="#identity">账号与组织</a>
<a href="#interaction">页面与查询逻辑</a>
<a href="#abilities">能力清单</a>
<a href="#delivery">交付与缺口</a>
</nav>
</header>
<section id="goals">
<h2>项目目标</h2>
<div class="grid">
<article class="card">
<h3>研究工作台</h3>
<p>实体、药物管线、靶点、化学活性、临床、专利、交易、监管、流行病学、会议新闻、知识与团队研究连续性。
</p>
</article>
<article class="card">
<h3>内部运营</h3>
<p>来源与许可、自动接入、安全解析、模型治理、主数据审核、原子发布与撤回、数据质量、企业、商业和平台运营。
</p>
</article>
<article class="card">
<h3>受控 Agent 访问</h3>
<p>远程 MCP、标准身份、来源许可、权益和风险检查、额度预留与结算、签名分页、有界导出以及可审计的证据引用。
</p>
</article>
</div>
</section>
<section id="architecture">
<h2>完整架构与唯一权威</h2>
<p class="muted">模块化单体按职责演进，运行时以三个隔离工作负载交付。
下图是实现边界，不代表所有生产门禁已完成。
</p>
<div class="flow" role="img" aria-label="研究与内部工作台、MCP经同一网关进入领域查询和接入治理；
PostgreSQL拥有身份、事实和账本，OpenSearch与Markdown是可重建投影。
">
<div class="flow-row">
<div class="node">
<strong>研究工作台</strong>注册 / 登录 / 退出 · 专业查询 · 稳定 URL · 保存与对比</div>
<div class="node">
<strong>内部工作台</strong>组织权限 · 来源 · 治理 · 商业 · 运维</div>
<div class="node">
<strong>Agent MCP</strong>OAuth / scope · 来源许可 · 权益 / 风险 / 计量</div>
</div>
<div class="arrow">↓ 统一身份、审计、生成的 API 契约与数据可见性 ↓</div>
<div class="flow-row">
<div class="node">
<strong>Gateway / HTTP</strong>
<code>api.py → http/</code>
<br>传输、输入、CSRF、请求体、错误与 no-store</div>
<div class="node">
<strong>领域查询与应用命令</strong>
<code>intelligence/ · accounts/ · ingest/commands/</code>
<br>请求上下文、SQL、事务、幂等、授权与状态机</div>
<div class="node">
<strong>Jobs + Parser</strong>受监督后台角色 · Temporal · outbox<br>解析器单独隔离，不持有业务写入权限</div>
</div>
<div class="arrow">↓ 只读来源 → 不可变快照 → ClamAV → 解析 → 模型暂存 → 审核 / 发布 ↓</div>
<div class="flow-row">
<div class="node">
<strong>PostgreSQL · 权威</strong>全局身份 / 组织成员 · 签名 RLS · 主数据 · 知识版本 · 审计 / 商业账本</div>
<div class="node">
<strong>对象存储 · 原始证据</strong>不可变来源版本、解析产物与内容哈希；
许可和生命周期独立于代码许可证</div>
<div class="node">
<strong>可重建投影</strong>OpenSearch · Markdown<br>Valkey负责短时状态；
Temporal负责持久工作流</div>
</div>
</div>
<p class="note">单一实现：领域规则不在 UI、HTTP 与 MCP 复制。
模型 / DTO / HTTP / 查询 / 发布证据的依赖方向受自动检查约束；
旧大文件实现移除，不保留竞争链路。
</p>
</section>
<section id="identity">
<h2>账号、组织与会话</h2>
<div class="grid">
<article class="card">
<h3>一个全局账号</h3>
<p>User 保存身份和账号版本。
home_tenant_id 只是默认归属，不授予角色。
独立注册创建 viewer 空间；
内部邀请默认 analyst。
</p>
</article>
<article class="card">
<h3>多个受邀成员资格</h3>
<p>OrganizationMembership 唯一拥有组织角色、停用和版本。
加入另一组织必须由其管理员邀请并由本人确认，不移动、不合并、不共享原数据。
</p>
</article>
<article class="card">
<h3>每会话一个组织</h3>
<p>切换时暂停工作台、清理旧查询缓存并让服务器确认。
请求绑定账号 / 组织，跨标签页重确认；
组织停用仅撤销本组织会话，改密撤销全局旧会话。
</p>
</article>
</div>
</section>
<section id="interaction">
<h2>筛选、结果与档案的状态归属</h2>
<p>查询草稿、已执行查询与当前预览各有明确归属；页面不以尚未提交的输入冒充结果条件。
跨领域详情和返回使用已校验的同工作台 URL，不依赖未知浏览器历史。
下面描述当前实现规则，实际质量结论仍以对应源码的验证证据为准。
</p>
<div class="flow">
<div class="flow-row">
<div class="node"><strong>1 · 草稿与选择</strong>
输入和候选选择仅修改草稿；有效选择绑定规范实体 ID。
取消、清空、无效输入与失败状态不能偷偷执行另一条查询。
</div>
<div class="node"><strong>2 · 已执行查询</strong>
URL 保存筛选、排序、分页与展示方式；请求及服务端 applied_filters 对应同一查询。
选中比较、保存和导出使用已执行条件，不混入未提交草稿。
</div>
<div class="node"><strong>3 · 预览与完整档案</strong>
URL 保存预览实体和详情分节；来源保留筛选、排序、分页和原预览。
同一实体的读取与成功缓存共用，不为各页面另造数据副本。
</div>
</div>
<div class="arrow">结果 → 快速预览 → 专业档案 → 明确返回已执行查询与原预览</div>
</div>
<div class="grid">
<article class="card"><h3>加载与错误也能返回</h3>
<p><code>ResearchReturnControl</code> 位于懒加载和数据正文之外。
药物、靶点、临床等领域共用唯一来源返回；无来源的临床详情才显示本页试验列表返回。
</p></article>
<article class="card"><h3>有界恢复，不形成循环</h3>
<p><code>useRouteEntity</code> 只在明确导航后对失败且空闲的读取恢复一次。
成功数据继续共享，普通重渲染和再次失败不自行循环请求。
会话未确认时不显示旧账号或旧组织的保护数据。
</p></article>
<article class="card"><h3>真实可操作的预览</h3>
<p>快速预览通过 Portal 脱离正文层叠与横向滚动，保留共享模态焦点管理。
长名称与动作可换行；手机操作不依靠强制点击穿过背景。
公开结果仍只展示已发布记录。
</p></article>
</div>
</section>
<section id="abilities">
<h2>实现能力与明确缺口</h2>
<p>以下清单由仓库两份能力矩阵生成。
<strong>代码已实现不等于客户数据覆盖、真实供应商联调或生产验收完成。
</strong>展开查看源码证据与剩余门禁。
</p>
<h3>外部研究 · {len(research["domains"])} 个领域</h3>{render_domains(research)}
<h3 style="margin-top:30px">内部运营 · {len(internal["domains"])} 个领域</h3>{render_domains(internal)}</section>
<section id="delivery">
<h2>交付、离线与未完成的外部条件</h2>
<div class="grid">
<article class="card">
<h3>开源工程</h3>
<p>源码、迁移、依赖锁、生成客户端、容器定义、测试和运维随仓库交付。
真实配置、密钥、个人和生产数据不提交 GitHub。
</p>
</article>
<article class="card">
<h3>离线运行边界</h3>
<p>HTML 自包含，可断网打开。
软件离线启动需要预装的容器运行时、全部镜像、持久数据及所需安全签名 / 模型文件；
仅源码 ZIP 或 compose.yaml 不是完整迁移包。
</p>
</article>
<article class="card">
<h3>生产门禁</h3>
<p>正式来源授权、客户覆盖与 UAT、企业 IdP、真实计费、托管 / HA、上线审批和发行签名仍需实际环境证据；
远程数据与付费模型不能断网调用。
</p>
</article>
</div>
<p class="note">本页不包含现场密钥、客户数据或运行测试日志，也不把未打包的 Docker 镜像、
未验证的离线模型和原业务数据库迁移描述为已交付。
最终验证、commit、CI 与镜像身份以本轮交付说明为准。
</p>
</section>
<footer>软件版本：X-Pharma v{escape(product_version)} · 生成依据：deploy/release 两份能力矩阵
<br>GOAL.md 契约版本：{escape(research["goal_version"])}（独立于软件版本）
<br>能力矩阵 SHA-256：<code>{fingerprint}</code>
<br>源码责任与调用方向见 docs/codebase-guide.md；
多组织迁移与回退见 docs/accounts-and-organizations.md。
</footer>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the self-contained X-Pharma architecture overview")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/project-overview.html")
    args = parser.parse_args()
    document = build_document()
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != document:
            parser.error("Project overview differs from its capability-matrix source; regenerate it")
    else:
        args.output.write_text(document, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
