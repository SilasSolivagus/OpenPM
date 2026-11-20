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

## 标准执行步骤（严守「本地留工程资产、远端只交单篇可读文档」铁律！）

> **最高红线（尤其针对企业微信 `wecom` 与飞书 `feishu`）**：
> - `project-context.md`、`spec.json`、`confluence-storage.xml`、裸 `prd.md`、`wiki-page.html`、`pages/*.html` 是**仅供本地 AI Agent 反复利用的工程源文件，绝对严禁把它们当成网盘附件上传到企业微信知识库/微盘或飞书目录里**！
> - 推往企业微信时，远端目标必须是**创建或更新唯一一篇原生的「企业微信在线文档（文档 `doc_type=3` 或智能文档 `doc_type=11`）」**，让同事点开即读（详见 `adapters/wecom.md`）。

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

3. **自动计算定稿质量分与定期优化检测（`eval_tracker.py`）**：
   ```bash
   python3 scripts/eval_tracker.py score <project_dir> --stage final --note "push-wiki 定稿交付"
   ```
   - 自动对比 `versions/v1` 初稿与当前定稿，计算客观得分（10 分制）与北极星指标「初稿→定稿返工修改率（%）」，记入 `evals/datasets/run-scores.jsonl`；
   - **若输出包含 `[ITERATION_TRIGGER]`**（即累计满 3 个需求交付、或未消化通用错题 ≥ 3 条、或本轮返工偏高），在交付收尾时向 PM 附带 **1 句简明提醒**：*“顺便提醒：最近已攒够几条高频改稿经验，有空对我说一句『复盘优化』，我花 1 分钟帮你固化进专属品味库。”*

## 输出
- 远端已更新的 Wiki / 企微 / 飞书页面（或本地 `<project_dir>/wiki-export/` 离线交付包）
- `<project_dir>/_manifest.json`
- `<project_dir>/versions/vN/` 快照与 `versions/changelog.md` 记录

## 验收标准
- 统一通过 `python3 scripts/wiki_sync.py push <project_dir>` 执行交付。
- 交付物同时包含可读的「左图右文」对照表与可交互的 `walkthrough.html.zip`，且 `_manifest.json` 与版本快照均已落盘。
