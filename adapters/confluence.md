# Confluence 适配器（`confluence`）

本适配器用于将本地生成的 `prd.md`、`walkthrough.html` 与 Atlassian Confluence（Cloud 或 Data Center）对齐，支持工程团队的标准研发流转。

---

## 1. 适用配置（`project-context.md`）

在 `project-context.md` 中配置如下适配器参数：

```yaml
wiki_adapter: confluence
wiki_config:
  base_url: "https://<your-domain>.atlassian.net/wiki"
  space_key: "PROD"
  parent_page_id: "<父页面 ID>"
  page_id: "<当前 PRD 页面 ID，首次发布留空>"
  jira_epic_key: "<关联 Jira Epic，如 PROD-123，可选>"
```

---

## 2. 字段映射模板

| 本地字段 | Confluence 目标位置 | 转换规则 |
| :--- | :--- | :--- |
| `title` | Page Title | 直接映射（同 Space 下需唯一） |
| `version_hash` / `status` / `owner` / `jira_epic_key` | Page Properties 宏（`ac:structured-macro ac:name="details"`） | 转为页面顶部「页面属性」两列表格，并自动添加标签（Labels），如 `prd`、`in-review` |
| `prd.md` 正文 | Confluence Storage Format (XHTML) | Markdown 标题、表格、Code Macro、Info/Warning Panel（对应 GitHub Alerts `> [!NOTE]` / `> [!WARNING]`）映射为标准宏 |
| `walkthrough.html` | Page Attachment（页面附件） | 作为附件上传至当前 Page，并在顶部 Page Properties 中放置下载/预览链接 |
| `review-feedback.md` | 本地回写文件 / 页面评论附件 | 评审人从 `walkthrough.html` 导出 `review-feedback.md` 后交回 AI；AI 修订后更新 Page 版本并递增 `version_hash` |

---

## 3. 交付与回写工作流

1. **发布同步**：
   - 若环境已配置 Confluence CLI / MCP / REST API，AI 可直接通过 `PUT /rest/api/content/{page_id}` 更新正文并上传 `walkthrough.html` 附件。
   - 若处于离线/受限网络环境，AI 输出符合 Confluence 粘贴规范的富文本/Markdown 片段，由 PM 粘贴并手动上传 `walkthrough.html` 附件。
2. **评审回写**：
   - 保持 `walkthrough.html` 为唯一交互评审入口，导出的 `review-feedback.md` 存入本地 `projects/<project-slug>/review-feedback.md`，确保每次迭代都有精确的 `comp_id` 与 `version_hash` 追溯。
