---
name: 01-pull-wiki
description: 调用 scripts/wiki_sync.py 从企业微信、Confluence、飞书或本地 Obsidian 拉取历史 PRD 至 history/prd-remote.md，生成 history/pull-diff.md 与可视化 history/pull-diff-report.html 对比基线。
---

# 01 - Pull Wiki（拉取历史 PRD 与基线对比）

## 目标
从团队知识库（`wecom` 企业微信 / `confluence` / `feishu` 飞书 / `local-obsidian` 本地）拉取目标项目的线上历史 PRD，落盘至标准路径 `<project_dir>/history/prd-remote.md`，并自动生成与本地草稿的结构化差异文件 `<project_dir>/history/pull-diff.md` 及浏览器可视化对比报告 `<project_dir>/history/pull-diff-report.html`，确保改线上已有功能时有据可依。

## 输入
- `project_dir`：目标项目路径（如 `projects/b-end-approval-flow`）
- `<project_dir>/project-context.md`（读取 `wiki_adapter` 与 `wiki_config`）
- 根目录 `.env.local`（存放平台凭证，已被 `.gitignore` 隔离，严禁进 Git）

## 执行步骤
0. **首次启动强制引导（Onboarding Gate）**：
   - 若 `<project_dir>/project-context.md` 不存在，**必须先按根目录 `AGENTS.md` 调用 `AskUserQuestion` 执行基础 5 问**；
   - 若 PM 选了 `wecom`、`confluence` 或 `feishu`，**必须主动向 PM 索要对应凭证（`Bot ID`+`Secret` / `CONFLUENCE_PAT` / `FEISHU_APP_ID`+`FEISHU_APP_SECRET`）并由你自动代写入 `.env.local`**，严禁甩锅让 PM 手改文件；
   - 若 PM 跳过或不答，自动启用纯黑白灰阶 `wt-*` + `local-obsidian` 兜底生成 `project-context.md`，绝不卡死流程。
1. **调用统一同步脚本拉取基线**：
   ```bash
   python3 scripts/wiki_sync.py pull <project_dir>
   ```
   - 脚本根据 `project-context.md` 中的 `wiki_adapter`（遵循 `adapters/` 协议）拉取远端文档，写入 `<project_dir>/history/prd-remote.md`（不会直接覆盖本地未提交的 `<project_dir>/prd.md`）。
2. **生成或核对 `history/pull-diff.md` 与 `history/pull-diff-report.html`**：
   - 若本地已有 `<project_dir>/prd.md`，对比 `history/prd-remote.md` 与 `prd.md`，输出结构化差异 `<project_dir>/history/pull-diff.md`，并生成可视化行内高亮对比报告 `<project_dir>/history/pull-diff-report.html`（可通过 `python3 scripts/wiki_diff_report.py <project_dir> --stage pull` 独立刷新，供 PM 在浏览器直观查看远端基线与本地草稿的逐词差异）；
   - 若本地尚无 `<project_dir>/prd.md`，以 `history/prd-remote.md` 为基线初始化 `<project_dir>/prd.md` 供 `02-draft-prd` 增量改写。
3. **输出标准工作区文件**：
   - `<project_dir>/project-context.md`
   - `<project_dir>/history/prd-remote.md`
   - `<project_dir>/history/pull-diff.md`
   - `<project_dir>/history/pull-diff-report.html`
   - `<project_dir>/prd.md`

## 验收标准
- 远端基线统一保存在 `history/prd-remote.md`，差异对比保存在 `history/pull-diff.md` 与可视化报告 `history/pull-diff-report.html`，全程统一调用 `python3 scripts/wiki_sync.py pull`。
- 凭证未泄露至任何 Git 跟踪文件；若远端无权限或离线，清晰提示引导 PM 将旧文档放入 `history/prd-remote.md` 兜底继续，绝不伪造历史需求。
