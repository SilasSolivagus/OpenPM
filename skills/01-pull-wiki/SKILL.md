---
name: 01-pull-wiki
description: 通过 adapters/ 从内网 Wiki 或本地 Obsidian/Markdown 拉取历史 PRD，生成 Diff 对比页并输出标准工作区文件。
---

# 01 - Pull Wiki（拉取历史 PRD 与上下文）

## 目标
从内网 Wiki（Confluence / 飞书 / Notion 等）或本地 Obsidian / Markdown 仓库拉取目标项目的历史 PRD、既有交互说明与附件元信息，在本地工作区初始化或更新标准项目目录，并生成与本地当前版本的 Diff 对比页，确保后续改动有据可依。

## 输入
- `project_dir`：目标项目工作区路径（如 `projects/demo-captcha-publish/`）
- `project-context.md` 中的数据源配置（`wiki_source`、`page_id` / `local_path`、`adapter` 类型）
- 可选：`--force` 或指定拉取的历史版本/分支

## 依赖与适配器
- 优先通过 `adapters/` 目录下对应的适配器脚本或配置执行拉取（如 `adapters/wiki_adapter.py` 或 `adapters/obsidian_adapter.py`）。
- 严禁在 Skill 中硬编码内网凭证或私有域名；所有鉴权信息必须从环境变量或本地未提交配置文件读取。

## 执行步骤
1. **校验工作区与配置**：
   - 检查 `<project_dir>/project-context.md` 是否存在且包含数据源标识。
   - 若 `<project_dir>/prd.md` 已存在，先提示或备份当前工作区状态。
2. **调用 Adapter 拉取远端/本地基线**：
   - 通过 `adapters/` 获取最新已发布版本的 PRD 正文、图片/原型附件清单及版本号/更新时间。
   - 将拉取到的原始基线保存至 `<project_dir>/baseline/prd-remote.md`（不直接覆盖用户未提交的 `prd.md`）。
3. **生成 Diff 对比页**：
   - 若本地已存在 `<project_dir>/prd.md`，对比 `baseline/prd-remote.md` 与本地 `prd.md`，生成 `<project_dir>/baseline/pull-diff.md`（或 `.html`），高亮新增、修改与删除的段落与功能点 ID。
   - 若本地尚无 `prd.md`，则将基线复制为初始 `<project_dir>/prd.md`。
4. **输出标准工作区清单**：
   - 确保以下目录与文件就绪：
     - `<project_dir>/project-context.md`
     - `<project_dir>/prd.md`
     - `<project_dir>/baseline/prd-remote.md`
     - `<project_dir>/baseline/pull-diff.md`（存在差异时）
     - `<project_dir>/versions/changelog.md`

## 验收标准
- 成功输出标准工作区文件，不丢失本地未保存修改。
- Diff 对比页能清晰展示远端基线与本地草稿的差异功能点（按 `F-xxx` ID 索引）。
- 若远端不可达或鉴权失败，明确报错并停止，不伪造历史文档。
