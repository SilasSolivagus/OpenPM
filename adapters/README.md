# Wiki 与知识库适配器（Adapters）

本目录定义了产品交付物（`prd.md`、`pages/*.html` 截图、`walkthrough.html.zip`、`review-feedback.md` / `.jsonl`）在不同团队知识库之间双向同步（`01-pull-wiki` 拉取对比与 `06-push-wiki` 图文对照交付）的**标准化适配协议**，底层执行入口统一为 `python3 scripts/wiki_sync.py`。

核心设计原则：**核心生产闭环（PRD → 纯灰阶原型 → 拓扑流程图 → 确定性编译 → 内联 `@组件` 评审回写）与具体 Wiki 平台完全解耦**。在 `project-context.md` 中切换 `wiki_adapter`，并将敏感凭证隔离在根目录 `.env.local` 中，即可无缝对接不同公司的协作体系。

---

## 支持的适配器枚举

| 适配器 ID | 适用平台 | `.env.local` 凭证字段（由 Agent 代写） | 推荐场景 | 详细文档 |
| :--- | :--- | :--- | :--- | :--- |
| `local-obsidian` | 本地文件夹 / Obsidian Vault | **零外部凭证**（默认兜底） | 个人 PM、本地优先团队、内网隔离环境离线交付 | [local-obsidian.md](local-obsidian.md) |
| `wecom` | 企业微信（智能机器人 / 微盘 / 群通知） | `WECOM_BOT_ID`、`WECOM_BOT_SECRET`（可选 `WECOM_WEBHOOK`、`WECOM_FOLDER_ID`） | 企业微信办公体系，长连接免域名直通文档/微盘与群通知 | [wecom.md](wecom.md) |
| `confluence` | Atlassian Confluence | `WIKI_BASE_URL`、`CONFLUENCE_PAT`、`CONFLUENCE_SPACE_KEY` | 中大型研发团队、Jira + Confluence 标准研发流转 | [confluence.md](confluence.md) |
| `feishu` | 飞书云文档（Feishu / Lark Docs） | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`（可选 `FEISHU_SPACE_ID`） | 飞书文档协同与知识库归档团队 | [feishu.md](feishu.md) |

---

## 标准拉取与交付契约（所有适配器通用）

1. **凭证安全隔离（`.env.local`）**：所有 Token、Secret、PAT 统一由 AI Agent 在首次启动时询问 PM 并自动代写入根目录 `.env.local`（已被 `.gitignore` 隔离），**严禁写入 `project-context.md` 或任何 Git 跟踪文件**。
2. **拉取基线与对比（`01-pull-wiki`）**：统一调用 `python3 scripts/wiki_sync.py pull projects/<project>`，将远端最新文档保存至 `projects/<project>/history/prd-remote.md`，并与本地草稿比对生成 `projects/<project>/history/pull-diff.md`。
3. **「左图右文」对照表 + `.zip` 交互附件（`06-push-wiki`）**：
   - 统一调用 `python3 scripts/wiki_sync.py push projects/<project>`；
   - 页面顶部挂载可下载交互工作台附件 `walkthrough.html.zip` 及元数据摘要（含 `DOC_VERSION_HASH`）；
   - 正文转换为**「序号 | 页面截图（左，`screenshots/*.png`） | 需求说明（右，支持嵌套子表）」**图文对照表，兼顾直接在 Wiki 浏览与下载离线交互走查两种习惯。
4. **防误覆盖清单（`_manifest.json`）与离线兜底**：
   - 每次推送成功后在项目目录更新 `_manifest.json`（记录 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`），下次推送前先校验远端版本防止误覆盖他人修改；
   - 当未配置凭证或内网断连时，自动在 `projects/<project>/wiki-export/` 生成完整离线交付包（图文对照文档 + `screenshots/` + `walkthrough.html.zip`），绝不卡死流程。
