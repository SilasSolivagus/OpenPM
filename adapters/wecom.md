# 企业微信适配器（WeCom Adapter）

本适配器用于对接**企业微信**进行需求文档拉取（`01-pull-wiki`）、交互原型交付（`06-push-wiki`）与群评审通知。

---

## 一、 PM 需要提供的最小清单（通过 `AskUserQuestion` 收集）

所有敏感凭证统一保存在项目根目录的 **`.env.local`**（已被 `.gitignore` 强隔离，**严禁写入 `project-context.md` 或提交到 Git**）。

| 接入等级 | 适用场景 | PM 只需提供的字段 |
| :--- | :--- | :--- |
| **Level 1（推荐）：智能机器人 API 模式** | PM 在企业微信创建了支持 AI Agent 接入的**智能机器人（API 模式 / 长连接，免域名免 IP）**，可通过开放 CLI/MCP 直通文档、微盘与消息 | `WECOM_BOT_ID` + `WECOM_BOT_SECRET`（可选 `WECOM_FOLDER_ID`） |
| **Level 2：群机器人通知模式** | 公司不开放文档/微盘 API，仅在群里发评审通知 | `WECOM_WEBHOOK`（群里“添加群机器人”获取） |
| **Level 3：零权限本地兜底** | 内网完全隔离，无任何机器人权限 | **无需任何配置**：本地生成完整交付包（Markdown + 截图 + `walkthrough.html.zip`），PM 手动拖入微盘/群聊 |

---

## 二、 拉取与交付流程

### `01-pull-wiki`（拉取）
1. **Level 1**：通过机器人开放的文档/微盘接口读取指定 `doc_id` 或目录下的历史文档，保存至 `projects/<name>/history/prd-vX.md`。
2. **Level 3 兜底**：PM 从企微文档导出 Markdown/Word 或复制正文放入 `history/`，照常生成 `diff.md`。

### `06-push-wiki`（交付）
1. **打包交付物**：将 `walkthrough.html` 压缩为 `walkthrough.html.zip`，并截取关键页面至 `screenshots/`。
2. **Level 1 推送**：通过智能机器人长连接 CLI/MCP 接口，将图文对照文档写入目标文档/微盘目录，上传 `walkthrough.html.zip` 附件，并在本地回写 `_manifest.json`（记录 `doc_id`、版本号与推送时间）。
3. **Level 2 通知**：通过 `WECOM_WEBHOOK` 向研发/设计群发送 Markdown 评审卡片，附带改动摘要与附件下载指引。
