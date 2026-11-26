# 文档与 Wiki 平台适配器（Adapters）

本目录说明如何把本地产出的需求方案（`prd.md`、纯灰阶原型截图、`walkthrough.html.zip`）与不同团队的文档平台做拉取（`01-pull-wiki`）和推送（`06-push-wiki`），统一入口脚本为 `python3 scripts/wiki_sync.py`。

写 PRD、画线框图和编译 `walkthrough.html` 的流程与具体平台无关：在项目的 `project-context.md` 里指定 `wiki_adapter`，把密钥放进根目录 `.env.local` 即可切换目标平台。

---

## 支持的平台

| 适配器 ID | 对应平台 | `.env.local` 配置项（由 Agent 代写） | 适用情况 | 详细说明 |
| :--- | :--- | :--- | :--- | :--- |
| `local-obsidian` | 本地目录 / Obsidian | 无需任何密钥（默认项） | 个人使用、内网离线环境、手动粘贴导入 | [local-obsidian.md](local-obsidian.md) |
| `wecom` | 企业微信（在线文档 / 群机器人通知） | `WECOM_BOT_ID`、`WECOM_BOT_SECRET`（可选 `WECOM_WEBHOOK`、`WECOM_FOLDER_ID`） | 用企业微信办公与审阅文档的团队 | [wecom.md](wecom.md) |
| `confluence` | Atlassian Confluence | `WIKI_BASE_URL`、`CONFLUENCE_PAT`、`CONFLUENCE_SPACE_KEY` | 使用 Jira + Confluence 的研发团队 | [confluence.md](confluence.md) |
| `feishu` | 飞书云文档 | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`（可选 `FEISHU_SPACE_ID`） | 使用飞书文档与知识库的团队 | [feishu.md](feishu.md) |

---

## 通用约定

1. **密钥只放 `.env.local`**：所有 Token、Secret、PAT 在首次配置时由 Agent 询问并写入根目录 `.env.local`（已在 `.gitignore` 中忽略），不要写进 `project-context.md` 或任何入库文件。
2. **拉取与差异报告（`01-pull-wiki`）**：执行 `python3 scripts/wiki_sync.py pull projects/<project>`，把远端文档存到 `history/prd-remote.md`，同时生成 `history/pull-diff.md` 和带行内字符级高亮的 `history/pull-diff-report.html`。
3. **左图右文导出与推送（`06-push-wiki`）**：
   - 执行 `python3 scripts/wiki_sync.py push projects/<project>`；
   - 顶部附带离线交互包 `walkthrough.html.zip` 下载入口与版本标识；
   - 正文生成三列「序号 | 页面截图（纯灰阶，含多端变体） | 需求说明（支持内嵌同页多状态 `原型 | 说明` 子表）」表格，并在本地输出 `wiki-export/push-diff-report.html` 供核对本次改动（该报告仅留本地，不上传远端）。
4. **防误覆盖与离线兜底**：
   - 每次同步后更新项目下的 `_manifest.json`（记录远端页面 ID 与版本号），下次推送前先核对远端版本，避免直接覆盖同事在线上的修改；
   - 未填密钥或接口受限时，所有导出文件（`.docx`、`wiki-page.html`、`confluence-storage.xml`、`walkthrough.html.zip`）都会生成在 `projects/<project>/wiki-export/` 下供直接导入或一键复制。
