---
name: 06-push-wiki
description: 通过 adapters/ 将更新后的 PRD 文字版、原型图及可交互 HTML 附件写回内网 Wiki（或本地/Obsidian），并调用 scripts/version_manager.py 打版本快照。
---

# 06 - Push Wiki（回写 Wiki 与版本快照）

## 目标
将通过门禁检查并完成评审定稿的 `prd.md`、原型切片/说明以及可交互的 `walkthrough.html` 附件，通过 `adapters/` 安全写回内网 Wiki 或本地 Obsidian/Markdown 仓库，并调用版本管理脚本打上不可变快照，形成完整的版本闭环。

## 输入
- `<project_dir>/project-context.md`（目标 Wiki 页面 ID 或本地导出路径）
- `<project_dir>/prd.md`
- `<project_dir>/walkthrough.html`（必须已通过 `scripts/preflight_check.py`）
- 可选：`--note "<本次发布说明>"`

## 执行步骤
1. **前置门禁复核**：
   - 确认 `<project_dir>/walkthrough.html` 存在且通过 `python3 scripts/preflight_check.py <project_dir>/walkthrough.html`。
2. **打本地版本快照（强制）**：
   - 在写回远端前，先调用版本管理脚本生成新版本快照并追加 `changelog.md`：
     ```bash
     python3 scripts/version_manager.py snapshot <project_dir> --note "<发布说明>"
     ```
3. **调用 Adapter 写回目标文档库**：
   - 通过 `adapters/` 将 `prd.md` 正文更新至目标页面，并将 `walkthrough.html` 及关键原型截图作为附件上传/关联。
   - 若写入目标为本地 Obsidian / Markdown 仓库，则同步更新目标文档及附件引用路径。
4. **记录回写回执**：
   - 将远端版本号、更新时间与访问链接记录到 `<project_dir>/versions/changelog.md` 对应版本条目下（或输出到终端摘要）。

## 验收标准
- 本地已生成新的 `vN` 快照目录且 `versions/changelog.md` 已更新。
- 远端 Wiki 或本地目标仓库已同步最新 PRD 正文与 `walkthrough.html` 附件。
- 若远端写入失败，本地快照仍保持完整，且不虚报推送成功。
