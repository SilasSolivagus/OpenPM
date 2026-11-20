# 企业微信适配器（`wecom` · 原生企微在线文档交付规范）

本适配器用于对接**企业微信在线文档 / 智能文档（WeDoc）**，核心铁律是：**「本地留工程源文件给 AI 反复复用，远端只交付一篇人类同事点开即读的企业微信在线文档」**。

---

## ⚠️ 严禁违规操作（最高红线！）

当向企业微信知识库 / 微盘推送定稿时：
1. **严禁把本地工程文件当成普通网盘文件一股脑上传到企微目录！**
   - 绝对禁止上传：`confluence-storage.xml`、`project-context.md`、`spec.json`、裸 `prd.md`、`wiki-page.html`、`flow.svg`、`pages/*.html`。这些文件仅保存在本地 `projects/<project>/` 供 AI Agent 后续增量改稿复用！
2. **远端企微知识库里应该只有什么？**
   - **唯一核心交付物**：在目标知识库空间下创建或更新**一篇原生的「企业微信在线文档（文档 `doc_type=3` 或智能文档 `doc_type=11`）」**，标题直接用干净的业务名称（如《创建网页分享·第一期》），正文直接写入排版好的结构化 PRD 与页面对照表；
   - **可选单一交互附件**：仅当需要让同事下载点选走查时，可在文档旁附带**唯一一个**重命名干净的 `《<需求标题>-交互走查原型.html》`（或 `.zip`），绝不准堆放其他杂乱工程文件！

---

## 1. 凭证配置（`.env.local` 隔离）

| 模式 | 用途 | `.env.local` 字段 |
| :--- | :--- | :--- |
| **原生企微文档 API 模式（推荐）** | 调用 `wedoc/create_doc` + `wedoc/document/batch_update` 直接新建/更新企微在线文档或智能文档 | `WECOM_CORP_ID`（或 `WECOM_BOT_ID`）+ `WECOM_CORP_SECRET`（或 `WECOM_BOT_SECRET`），可选 `WECOM_SPACE_ID`、`WECOM_FOLDER_ID`、`WECOM_DOC_TYPE=3`（`3`=文档，`11`=智能文档） |
| **客户端已挂载企微文档 MCP / 插件模式** | 若当前 Agent 客户端（如 Codex / WorkBuddy）已连接企微文档 MCP 工具 | 直接调用企微「新建在线文档 / 写入文档正文」工具创建单篇企微文档，并将返回的 `docid` 与 `url` 写入 `_manifest.json`，**严禁调用微盘文件上传接口把本地目录的 `.xml` / `.md` 原文件传上去！** |
| **群机器人通知（可选叠加）** | 文档创建/更新完成后往研发群发卡片链接 | `WECOM_WEBHOOK` |

---

## 2. 标准执行流程

1. **拉取旧文档（`01-pull-wiki`）**：读取已有企微在线文档正文存入本地 `history/prd-remote.md`，输出 `history/pull-diff.md`。
2. **定稿推送单篇企微在线文档（`06-push-wiki`）**：
   - 运行 `python3 scripts/wiki_sync.py push projects/<project>`（或调用客户端企微在线文档创建/更新工具）；
   - 若 `_manifest.json` 中尚无 `remote_page_id`（0 启动首次定稿），在目标知识库创建**一篇企业微信文档/智能文档**并写入正文，保存 `docid` 与 `share_url` 到本地 `_manifest.json`；
   - 若已有 `remote_page_id`，直接更新同一篇企微文档正文，保持文档链接永久不变。
