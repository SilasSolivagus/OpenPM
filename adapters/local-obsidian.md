# 本地 / Obsidian 适配器（`local-obsidian`）

`local-obsidian` 是 OpenPM 的**默认零依赖离线适配器**。它直接基于本地标准目录结构运行，既可以用 **Obsidian** 作为 Vault 直接打开管理，也可以用任意编辑器读写，无需配置任何外部 API 密钥。

---

## 1. 标准项目目录与文件约定

所有项目产物统一落盘在 `projects/<project>/` 目录下：

```text
projects/<project>/
├── project-context.md       # 项目上下文与端型/骨架配置
├── history/                 # 历史基线与拉取对比目录
│   ├── prd-remote.md        # 远端或旧版基线 PRD
│   └── pull-diff.md         # 基线与当前 prd.md 的结构化差异对比
├── prd.md                   # 结构化文字版主 PRD（含 F-xx 功能点 ID）
├── pages/                   # 纯黑白灰阶 wt-* 原型页面片段
│   └── <page_id>.html       # <div class="page" id="..." data-page="..." data-page-id="...">
├── flow.svg                 # 业务拓扑流程图（带 data-from/data-to/data-branch 与 D_* 菱形）
├── spec.json                # spec-v2 单一真相源（meta/vars/nodes/pages/state_groups/spec_cards/memos）
├── walkthrough.html         # 确定性编译出的单文件交互走查工作台
├── review-feedback.md       # 评审导出的 Markdown 批注（或 review-feedback.jsonl）
├── wiki-export/             # 执行 wiki_sync.py push 生成的离线图文对照交付包与 .zip
└── versions/                # version_manager.py 管理的版本快照与 changelog.md
```

---

## 2. 字段映射规范

| 工作流字段 | 本地 / Obsidian 载体 | 说明 |
| :--- | :--- | :--- |
| `project` | `prd.md` Frontmatter `project` | 与目录名 `<project>` 保持一致 |
| `version_hash` | `prd.md` Frontmatter `version_hash` | 与 `walkthrough.html` 内置 `DOC_VERSION_HASH` 对齐 |
| `status` | `prd.md` Frontmatter `status` | `draft` \| `in_review` \| `approved` \| `archived` |
| `owner` | `prd.md` Frontmatter `owner` | 产品经理姓名或花名 |
| `walkthrough` | 同目录 `walkthrough.html` 及 `wiki-export/walkthrough.html.zip` | 双击即可在任意浏览器离线打开 |
| `feedback` | 同目录 `review-feedback.md` / `review-feedback.jsonl` | 浏览器导出后放回项目目录，供 `02` / `03` / `04` 局部精准回写 |

---

## 3. Obsidian 零插件协同技巧

- **属性面板（Properties）**：Obsidian 原生解析 `project-context.md` 与 `prd.md` 顶部的 YAML Frontmatter，直观管理需求状态与版本号。
- **双链溯源（Backlinks）**：在 `prd.md` 中使用 `[[project-context]]`、`[[history/pull-diff]]`、`[[review-feedback]]` 双链串联需求演变脉络。
- **一键离线归档**：定稿后执行 `python3 scripts/wiki_sync.py push projects/<project>` 与 `python3 scripts/version_manager.py snapshot projects/<project>`，自动生成离线图文对照包与不可变历史快照。
