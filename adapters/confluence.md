# Confluence 适配器（`confluence`）

本适配器通过 `python3 scripts/wiki_sync.py` 将本地项目与 Atlassian Confluence（Cloud 或 Data Center / Server 7.x+）双向同步，交付标准「左图右文」对照表、`walkthrough.html.zip` 附件并维护 `_manifest.json` 防覆盖保护。

---

## 1. 配置与凭证隔离（`project-context.md` + `.env.local`）

### 1.1 `.env.local`（敏感凭证，由 AI Agent 主动索要并自动代写，严禁进 Git）

```dotenv
WIKI_BASE_URL=https://wiki.yourcompany.com
CONFLUENCE_PAT=your_personal_access_token
CONFLUENCE_SPACE_KEY=PROD
CONFLUENCE_PARENT_PAGE_ID=12345678
```

### 1.2 `project-context.md`（非敏感页面定位信息）

```yaml
wiki_adapter: confluence
wiki_config:
  space_or_parent: "PROD/12345678"   # Space Key 或父页面 ID
  doc_id: ""                         # 首次发布留空，推送后自动回填并记录至 _manifest.json
  jira_epic_key: "PROD-123"          # 可选：关联 Jira Epic
```

---

## 2. 「左图右文」交付结构与字段映射

| 本地产物 | Confluence 目标载体 | 转换与防破表规则 |
| :--- | :--- | :--- |
| `title` | Page Title | 同 Space 下保持唯一标题 |
| 元数据 + `walkthrough.html.zip` | 顶部 Page Properties 宏 + 页面附件 | 注入负责人、`DOC_VERSION_HASH`、状态，并挂载 `walkthrough.html.zip` 下载链接（规避 Confluence 对裸 `.html` 附件预览的安全拦截） |
| `screenshots/*.png` + `prd.md` | **「左图右文」三列 Storage XML 表格** | 转为 `序号 \| 页面纯灰阶截图（左，ri:attachment） \| 结构化需求说明与状态/异常子表（右）`，严格校验 XHTML 闭合防止 Confluence 7.x 破表 |
| `_manifest.json` | 本地 `projects/<project>/_manifest.json` | 记录 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`，推送前比对 `version.number` 防止误覆盖 |
| `review-feedback.md` / `.jsonl` | 本地回写输入 | 评审人下载解压 `walkthrough.html.zip`，在输入框内联 `@[组件名]` 批注并导出后交回本地局部修订 |

---

## 3. 标准拉取与推送工作流

1. **拉取历史基线（`01-pull-wiki`）**：
   - 运行 `python3 scripts/wiki_sync.py pull projects/<project>`，读取指定 `doc_id` 的 Storage Format 正文转换为 Markdown，写入 `projects/<project>/history/prd-remote.md`，并与本地 `prd.md` 对比生成 `projects/<project>/history/pull-diff.md`。
2. **图文对照交付（`06-push-wiki`）**：
   - 运行 `python3 scripts/wiki_sync.py push projects/<project>`：先校验 `_manifest.json` 中的远端版本无冲突，再上传 `screenshots/*.png` 与 `walkthrough.html.zip` 附件，最后写入「左图右文」Storage XML 正文并更新 `_manifest.json`。
   - **离线兜底**：当未填 `CONFLUENCE_PAT` 或处于隔离网络时，脚本自动在 `projects/<project>/wiki-export/` 输出可直接粘贴导入的 Confluence Storage XML / Markdown、`screenshots/` 与 `walkthrough.html.zip`。
