# Wiki 与知识库适配器（Adapters）

本目录定义了产品交付物（`prd.md`、`walkthrough.html`、`review-feedback.md`）向不同团队知识库同步的**标准化适配协议**。

核心设计原则：**核心工作流（PRD 生产 → 原型 → 走查 → 点选回写）完全解耦于具体 Wiki 平台**。在 `project-context.md` 中切换 `wiki_adapter` 字段，即可在不改动规范的前提下对接不同团队的知识库。

---

## 支持的适配器

| 适配器 ID | 适用平台 | 依赖要求 | 推荐场景 | 详细文档 |
| :--- | :--- | :--- | :--- | :--- |
| `local-obsidian` | 本地文件夹 / Obsidian Vault | **零外部依赖**（默认） | 个人 PM、本地优先团队、无在线 Wiki 权限或追求极速闭环 | [local-obsidian.md](local-obsidian.md) |
| `feishu` | 飞书文档（Feishu / Lark Docs） | 飞书开放平台 API / MCP 或手动导入 | 国内互联网团队、需要飞书文档评论与权限协同 | [feishu.md](feishu.md) |
| `confluence` | Atlassian Confluence | Confluence REST API / MCP 或手动导入 | 中大型研发团队、Jira + Confluence 联动体系 | [confluence.md](confluence.md) |

---

## 标准交付契约（所有适配器通用）

无论采用哪种适配器，一次完整的「Wiki 交付」必须包含以下 4 个标准字段映射：

1. **文档元数据（Metadata）**：`project`、`version_hash`、`status`、`owner`、`updated_at`、`platform`。
2. **PRD 正文（PRD Body）**：结构化 Markdown（含背景、流程图说明、状态机、异常分支、验收标准）。
3. **交互走查附件（Walkthrough Artifact）**：自包含单文件 `walkthrough.html`（附件直传或内网静态托管链接）。
4. **评审回写入口（Feedback Loop）**：将评审导出的 `review-feedback.md` 放回项目目录或关联至文档评论区，供 AI Skill 读取迭代。
