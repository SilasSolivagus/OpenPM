# 本地 / Obsidian 适配器（`local-obsidian`）

`local-obsidian` 是本工作区的**默认零依赖适配器**。它直接基于本地文件系统运行，既可以用 **Obsidian** 作为 Vault 打开获得图形化双向链接与属性视图，也可以用 **VS Code / Cursor / 任意编辑器**直接读写，**不依赖任何 Obsidian 付费服务或第三方插件**。

---

## 1. 目录与文件落盘规范

所有项目产物统一落盘在工作区 `projects/<project-slug>/` 目录下：

```text
projects/<project-slug>/
├── project-context.md       # 项目上下文配置
├── prd.md                   # 主 PRD 文档
├── walkthrough.html         # 三栏交互走查单文件（交付物）
└── review-feedback.md       # 评审导出的结构化反馈
```

---

## 2. 字段映射规范

| 工作流字段 | 本地 / Obsidian 载体 | 说明 |
| :--- | :--- | :--- |
| `project` | `prd.md` YAML Frontmatter `project` | 与 `<project-slug>` 保持一致 |
| `version_hash` | `prd.md` YAML Frontmatter `version_hash` | 与 `walkthrough.html` 内置 `VERSION_HASH` 一致 |
| `status` | `prd.md` YAML Frontmatter `status` | 枚举：`draft` \| `in_review` \| `approved` \| `archived` |
| `owner` | `prd.md` YAML Frontmatter `owner` | 负责人姓名或花名 |
| `walkthrough` | 同目录 `walkthrough.html` + 文内双链/相对链接 | `[[walkthrough.html]]` 或 `[打开交互走查](./walkthrough.html)` |
| `feedback` | 同目录 `review-feedback.md` | 评审人在浏览器导出后直接覆盖/保存至此路径 |

### 推荐 `prd.md` 顶部 Frontmatter 模板

```yaml
---
project: <project-slug>
title: <需求标题>
version_hash: <8位哈希>
status: in_review
platform: [H5, Web]
owner: <PM名称>
updated_at: 2026-11-20
---
```

---

## 3. Obsidian 零插件增强技巧（可选）

- **属性面板（Properties）**：Obsidian 原生支持解析 YAML Frontmatter，可直接在文档顶部可视化查看 `status`、`version_hash` 与 `platform`。
- **双链溯源（Backlinks）**：在 `prd.md` 中写入 `[[project-context]]` 与 `[[review-feedback]]`，即可在右侧边栏「反向链接」中一键跳转上下文与历史评审意见。
- **直接预览 HTML**：在系统文件管理器中双击 `walkthrough.html` 即可用默认浏览器打开；若需团队共享，直接将 `walkthrough.html` 单文件发送至群聊或网盘即可。
