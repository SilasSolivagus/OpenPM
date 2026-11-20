---
name: 06-push-wiki
description: 调用 scripts/wiki_sync.py 将「左图右文」对照 PRD、纯灰阶截图及 walkthrough.html.zip 推送至企业微信、Confluence、飞书或本地归档，维护 _manifest.json 并打版本快照。
---

# 06 - Push Wiki（图文对照交付与版本快照）

## 目标
当 PM 确认定稿并要求推送时，调用统一的 `scripts/wiki_sync.py` 将定稿的 `prd.md`、关键页面纯灰阶截图与可交互 `walkthrough.html.zip` 组装为标准「左图右文」对照文档，推送至目标知识库（`wecom` / `confluence` / `feishu` / `local-obsidian`），维护 `_manifest.json` 防覆盖清单并自动留存版本快照。

## 输入
- `<project_dir>/prd.md`
- `<project_dir>/walkthrough.html`（已通过 `preflight_check.py` 门禁）
- `<project_dir>/project-context.md`（读取 `wiki_adapter` 与 `wiki_config`）
- 根目录 `.env.local`（读取 `WECOM_BOT_ID`+`WECOM_BOT_SECRET` / `CONFLUENCE_PAT` / `FEISHU_APP_ID`+`FEISHU_APP_SECRET`，严禁进 Git）

## 标准执行步骤

1. **调用统一同步脚本执行打包与推送**：
   ```bash
   python3 scripts/wiki_sync.py push <project_dir>
   ```
   脚本遵循 `adapters/` 协议自动完成：
   - **打包与截图**：准备关键节点纯灰阶页面截图（`<project_dir>/screenshots/*.png`），并将 `walkthrough.html` 压缩为 `<project_dir>/wiki-export/walkthrough.html.zip`；
   - **组装「左图右文」对照正文**：顶部放置元数据（含 `DOC_VERSION_HASH`）与 `walkthrough.html.zip` 下载入口，正文生成三列表格 **`序号 | 页面截图（左） | 需求说明（右，支持嵌套子表）`**（Confluence 模式下确保 Storage XML 闭合零破表）；
   - **防覆盖校验与回写 `_manifest.json`**：推送前先比对 `<project_dir>/_manifest.json` 中的 `remote_version`，确认远端未被他人更新后再上传附件与正文，并在成功后回写最新 `_manifest.json`（含 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`）；
   - **零权限离线兜底**：若未填凭证或处于 `local-obsidian` 模式，完整离线交付包自动保存在 `<project_dir>/wiki-export/`，供 PM 直接粘贴或归档。

2. **创建不可变版本快照**：
   ```bash
   python3 scripts/version_manager.py snapshot <project_dir> --note "push-wiki 定稿交付"
   ```

## 输出
- 远端已更新的 Wiki / 企微 / 飞书页面（或本地 `<project_dir>/wiki-export/` 离线交付包）
- `<project_dir>/_manifest.json`
- `<project_dir>/versions/vN/` 快照与 `versions/changelog.md` 记录

## 验收标准
- 统一通过 `python3 scripts/wiki_sync.py push <project_dir>` 执行交付。
- 交付物同时包含可读的「左图右文」对照表与可交互的 `walkthrough.html.zip`，且 `_manifest.json` 与版本快照均已落盘。
