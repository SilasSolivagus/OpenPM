# 企业微信适配器（`wecom`）

本适配器通过 `python3 scripts/wiki_sync.py` 对接**企业微信**，完成历史需求文档拉取（`01-pull-wiki`）、「左图右文 + `walkthrough.html.zip`」交付与群通知（`06-push-wiki`），并维护 `_manifest.json` 防覆盖保护。

---

## 1. 配置与凭证隔离（`project-context.md` + `.env.local`）

所有敏感凭证统一由 AI Agent 在首次启动时通过 `AskUserQuestion` 询问 PM 并自动代写入根目录 **`.env.local`**（已被 `.gitignore` 隔离，**严禁写入 `project-context.md` 或提交到 Git**）。

| 接入等级 | 适用场景 | `.env.local` 字段 |
| :--- | :--- | :--- |
| **Level 1（推荐）：智能机器人 API 模式** | PM 创建支持 API / 长连接的企微智能机器人，免域名免公网 IP 直通文档、微盘与群消息 | `WECOM_BOT_ID` + `WECOM_BOT_SECRET`（可选 `WECOM_FOLDER_ID`） |
| **Level 2：群机器人通知模式** | 仅需向研发/设计评审群推送通知卡片，附件走微盘或离线包 | `WECOM_WEBHOOK` |
| **Level 3：零权限离线兜底** | 内网隔离或暂未配置任何机器人凭证 | 无需凭证，自动输出至 `projects/<project>/wiki-export/` |

`project-context.md` 配置示例：

```yaml
wiki_adapter: wecom
wiki_config:
  space_or_parent: "<微盘或企微文档目录标识，可选>"
  doc_id: ""
```

---

## 2. 标准拉取与交付流程

### `01-pull-wiki`（拉取历史与对比）
1. **自动拉取**：运行 `python3 scripts/wiki_sync.py pull projects/<project>`，通过企微文档/微盘接口读取指定 `doc_id` 的历史文档，保存至 `projects/<project>/history/prd-remote.md`，并与本地 `prd.md` 比对输出 `projects/<project>/history/pull-diff.md`。
2. **离线兜底**：若无 API 权限，PM 将导出的历史 Markdown 放入 `history/prd-remote.md`，脚本同样生成结构化 `history/pull-diff.md`。

### `06-push-wiki`（图文对照交付与防覆盖）
1. **打包与组装**：运行 `python3 scripts/wiki_sync.py push projects/<project>`，自动打包 `walkthrough.html.zip`，结合 `screenshots/*.png` 组装「左图右文」三列对照文档（`序号 | 页面纯灰阶截图 | 需求说明与嵌套子表`）。
2. **推送与 `_manifest.json` 回写**：校验远端版本无冲突后上传文档与 `walkthrough.html.zip` 至企微文档/微盘，在项目目录回写 `_manifest.json`（记录 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`），并可选通过 `WECOM_WEBHOOK` 发送群评审通知卡片；无外连权限时自动落盘至 `wiki-export/`。
