# 飞书文档适配器（`feishu`）

本适配器用于将本地生成的 `prd.md`、`walkthrough.html` 与飞书云文档（Feishu / Lark Docs）对齐，实现文档发布与评审回写。

---

## 1. 适用配置（`project-context.md`）

在 `project-context.md` 中配置如下适配器参数：

```yaml
wiki_adapter: feishu
wiki_config:
  space_id: "<飞书知识库空间 ID，可选>"
  parent_node_token: "<父文档/目录节点 Token>"
  doc_token: "<已存在文档 Token，首次发布留空>"
  walkthrough_host: "attachment" # attachment（作为附件上传） | url（托管后的在线链接）
```

---

## 2. 字段映射模板

| 本地字段 | 飞书文档目标位置 | 转换规则 |
| :--- | :--- | :--- |
| `title` | 文档标题（Document Title） | 直接映射 |
| `version_hash` / `status` / `owner` / `platform` | 文档顶部「高亮块（Callout）」元信息表 | 飞书新版文档无原生 YAML Frontmatter，统一渲染为顶部灰底/蓝底 Callout 表格 |
| `prd.md` 正文 | 飞书文档 Block 树 | 标题（H1-H3）、列表、表格、代码块直接转为对应飞书 Block；Mermaid/SVG 流程图建议附带静态 PNG 截图或代码块 |
| `walkthrough.html` | 文档顶部 Callout 内的**文件附件**或**在线预览链接** | 若团队支持内网静态托管，优先填在线 URL；否则直接将 `walkthrough.html` 作为文件块插入文档顶部，提示评审人「下载后浏览器打开」 |
| `review-feedback.md` | 本地回写文件（或从飞书评论区汇总） | 评审人优先在 `walkthrough.html` 中点选导出 `review-feedback.md`；若在飞书划词评论，由 PM/AI 拉取评论后按 `anchor-schema` 归并 |

---

## 3. 交付与回写工作流

1. **发布同步**：
   - 若环境已配置飞书 MCP / CLI，AI 自动将 `prd.md` 转换并写入 `doc_token`（或新建文档并回填 `doc_token` 到 `project-context.md`）。
   - 若无 API 权限（纯本地离线模式），AI 生成飞书兼容格式的 Markdown 剪贴板版本，由 PM 一键粘贴至飞书文档并拖入 `walkthrough.html` 附件。
2. **评审回写**：
   - 评审人打开 `walkthrough.html` 点选批注，导出 `review-feedback.md` 后发回给 PM 或放入本地项目目录，AI 读取后执行迭代并同步更新飞书文档与 `version_hash`。
