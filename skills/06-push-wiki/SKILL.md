---
name: push-wiki
description: 将定稿的图文对照 PRD、原型截图及可交互 walkthrough.html.zip 交付到目标 Wiki（Confluence / 企业微信 / 飞书 / 本地 Obsidian），并维护防覆盖 _manifest.json 与版本快照。
---

# 06 · Push Wiki（交付与归档）

## 输入
- `projects/<project>/prd.md`（结构化文字版 PRD）
- `projects/<project>/walkthrough.html`（已通过 `preflight_check.py` 门禁）
- `projects/<project>/project-context.md`（读取 `wiki_adapter` 与目标位置）
- 本地 `.env.local`（仅存放凭证，如 `WECOM_BOT_ID`/`WECOM_BOT_SECRET`、`CONFLUENCE_PAT` 等，**严禁进 Git**）

## 核心交付标准（图文对照表 + 附件 + 防覆盖）

1. **自动截图与打包**：
   - 对 `walkthrough.html` 中的关键业务节点页面自动截取纯灰阶线框图至 `projects/<project>/screenshots/*.png`；
   - 将 `walkthrough.html` 打包为 `walkthrough.html.zip` 作为可下载交互附件。

2. **组装「左图右文」对照交付文档**：
   - 顶部放置交互原型下载链接：`交互原型：walkthrough.html.zip（点击下载）`；
   - 正文采用结构化三列表格：**`序号 | 页面截图（左） | 需求说明（右，支持单元格内嵌套子表）`**，确保不打开 HTML 附件的研发/测试也能直接在 Wiki 阅读完整逻辑；
   - 若目标为 Confluence 7.x，需校验转换后的 Storage XML 严格合法（避免破表）。

3. **按 Adapter 推送与防误覆盖保护**：
   - **Confluence / 企业微信智能机器人**：先上传 `screenshots/*.png` 与 `walkthrough.html.zip` 附件，再更新/创建正文页面；
   - **回写 `_manifest.json`**：每次推送后在项目目录写入/更新 `_manifest.json`（记录 `adapter`、`remote_page_id`、`remote_version`、`pushed_at`、`walkthrough_hash`）。下次推送前先比对远端版本号，防止多人编辑时误覆盖；
   - **零权限兜底**：若无外连权限，在 `projects/<project>/wiki-export/` 下生成完整的离线交付包（图文对照 HTML/XML + `screenshots/` + `.zip`），供 PM 5 秒粘贴上传。

4. **版本快照**：
   - 调用 `python3 scripts/version_manager.py snapshot projects/<project> --note "push-wiki 交付"` 打快照留痕。
