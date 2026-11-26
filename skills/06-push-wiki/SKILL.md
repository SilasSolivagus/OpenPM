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

## 标准执行步骤（支持同页多状态对比子表、严禁主图套娃重复、全变体灰阶截图、诚实状态码！）

> **核心交付门禁（严禁踩坑）**：
> 1. **允许同页多状态对比子表，严禁主图套娃与内容重复**：外层三列 `序号 | 页面 | 需求说明` 为主图文对照容器；当同一页面存在多个状态/异常态（如多账号态 / 单账号态 / 空态 / 校验报错态）时，允许通过 `spec.json` 的 `state_groups` 或 `prd.md` 内的 `| 原型 | 说明 |`（配 `![状态名](page_id)`）在父页面右栏内嵌多状态图文对比子表（公共规则写在外层，各态差异规则写在子表）；**依然严禁把外层左栏同一张主图与外层已写规则原样重复套娃复述一遍**，每条业务规则全篇只准出现一次！
> 2. **完整覆盖多端变体 & 强制 100% 纯灰阶**：`wiki_sync.py` 自动截取基页面及全部 `variant_of`（如 `Web/PC` + `App 375px`）变体并强制 `grayscale(100%)`；**若返回退出码 `3`（`SCREENSHOT_CAPTURE_FAILED`，受限沙箱拦截无头浏览器），必须申请提权脱离沙箱重跑，严禁交付无图文档！**
> 3. **严禁“假成功”（退出码 `2` 诚实汇报）**：企微智能机器人 `WECOM_BOT_ID` 无法调用企业 `wedoc` 接口（`40013 invalid corpid`）。当 `wiki_sync.py push` 返回**退出码 `2`（`REMOTE_PUSH_NOT_UPLOADED`）**时，代表**本地 `wiki-export/<项目名>-产品方案.docx` 和 `wiki-page.html` 已生成完毕，但尚未上传到企微远端**——此时若有企微 MCP 上传工具则只传单篇 `.docx`，若无则必须如实把本地 `.docx` 和 `wiki-page.html`（一键复制）交由 PM 导入，**绝不准谎称“已自动上传企微成功”！**
> 4. **本地工程源文件隔离**：严禁把 `project-context.md`、`spec.json`、裸 `prd.md`、`pages/*.html` 上传到企微微盘或 Wiki。

1. **调用统一同步脚本执行打包与推送**：
   ```bash
   python3 scripts/wiki_sync.py push <project_dir>
   ```
   脚本遵循 `adapters/` 协议自动完成：
   - **打包与截图**：准备关键节点纯灰阶页面截图（`<project_dir>/screenshots/*.png`），并将 `walkthrough.html` 压缩为 `<project_dir>/wiki-export/walkthrough.html.zip`；
   - **组装「左图右文」对照正文**：顶部放置元数据（含 `DOC_VERSION_HASH`）与 `walkthrough.html.zip` 下载入口，正文生成三列表格 **`序号 | 页面截图（左） | 需求说明（右，支持同页多状态 `原型 | 说明` 对比子表自动折叠与嵌套子表）`**（Confluence 模式下确保 Storage XML 闭合零破表）；
   - **防覆盖校验与回写 `_manifest.json`**：推送前先比对 `<project_dir>/_manifest.json` 中的 `remote_version`，确认远端未被他人更新后再上传附件与正文，并在成功后回写最新 `_manifest.json`（含 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`）；
   - **零权限离线兜底**：若未填凭证或处于 `local-obsidian` 模式，完整离线交付包自动保存在 `<project_dir>/wiki-export/`，供 PM 直接粘贴或归档；
   - **生成本地可视化变更核验报告（`push-diff-report.html`）**：自动（或通过 `python3 scripts/wiki_diff_report.py <project_dir> --stage push`）输出 `<project_dir>/wiki-export/push-diff-report.html`（并归档一份至 `history/push-diff-report.html`），直观展示线上基线或 `v1` 初稿与本次定稿的行级/词级高亮差异（**仅限本地审阅，严禁上传远端 Wiki 或微盘**）。

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
- `<project_dir>/wiki-export/push-diff-report.html`（及归档副本 `history/push-diff-report.html`，**仅限本地审阅，严禁上传远端 Wiki**）
- `<project_dir>/_manifest.json`
- `<project_dir>/versions/vN/` 快照与 `versions/changelog.md` 记录

## 验收标准
- 统一通过 `python3 scripts/wiki_sync.py push <project_dir>` 执行交付。
- 交付物同时包含可读的「左图右文」对照表与可交互的 `walkthrough.html.zip`，且 `_manifest.json` 与版本快照均已落盘。
