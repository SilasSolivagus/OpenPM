---
name: 05-flow-walkthrough
description: 汇总补全 spec.json（pages、state_groups、spec_cards），依次执行 preflight_check.py spec.json、build_walkthrough.py 确定性编译与 preflight_check.py walkthrough.html 门禁。
---

# 05 - Flow Walkthrough（`spec.json` 汇总与交互走查工作台确定性编译）

## 目标
汇总 `02-draft-prd`、`03-prd-to-wireframe-prototype` 与 `04-flow-canvas` 的产物，补全单一真相源 `<project_dir>/spec.json`（`version: "spec-v2"`），通过确定性编译器 `scripts/build_walkthrough.py` 生成单文件离线交互工作台 `<project_dir>/walkthrough.html`，并在后台静默通过编译前后双阶段 `preflight_check.py` 门禁。

## 输入
- `<project_dir>/prd.md`
- `<project_dir>/pages/<page_id>.html`（纯黑白灰阶 `wt-*` 页面片段）
- `<project_dir>/flow.svg`
- `<project_dir>/spec.json`（已含 `04-flow-canvas` 同步的 `nodes` 与 `vars`）
- 可选：`<project_dir>/skeleton.css`（仅允许微调圆角、间距、字号，严禁彩色皮肤）
- 契约参考：`specs/spec-v2.schema.json`、`specs/spec-v2-schema.md`、`specs/preflight-checklist.md`

## 标准执行步骤（严禁跳步）

### 第 1 步：汇总补全 `<project_dir>/spec.json`
确保 `spec.json` 完整包含并对齐以下字段：
1. `version`: `"spec-v2"`；`meta`: `{ project, title, doc_version, platform_default, entry_node, prd_source }`。
2. `vars` 与 `nodes`：核对与 `flow.svg` 节点、`data-branch` 出边及本期 `change: "new" | "modified"` 标记完全一致。
3. `pages`：登记所有 `pages/<page_id>.html` 的 `frame`（`"phone" | "wide"`）、`title`、`components`（点分小写 `comp_id`、`comp_name`、`role`）及可选多端 `variant_of` / `overrides`。
4. `state_groups`（可选）：登记同页局部状态切换组。同页多状态/异常态可通过 `prd.md` 的 `| 原型 | 说明 |`（左列 `![状态名](page_id)`）或 `spec.json` 的 `state_groups`（支持可选 `parent_page`、`fold_into_parent` 及 `states[].bullets` / `spec`）表达，导出时自动折叠合并为父页面右栏图文状态子表。
5. `spec_cards`：提炼本期核心需求改点卡（`{ id, title, page, anchor, body }`），`anchor` 指向对应页面内改点组件的 `data-comp-id`（用于在 `spec` 单页改点视图触发唯一工程标引色 **琥珀橙 `#D97706`** 锚定高亮）。
6. `memos`（可选）：默认为空数组 `[]`（或保留符合 `memoDef` 的有效历史批注）。

### 第 2 步：编译前门禁校验 `spec.json`
```bash
python3 scripts/preflight_check.py <project_dir>/spec.json
```
必须返回退出码 `0` 方可进入编译；若有报错，先静默修复 `spec.json`。

### 第 3 步：确定性编译 `walkthrough.html`
```bash
python3 scripts/build_walkthrough.py \
  --spec <project_dir>/spec.json \
  --svg <project_dir>/flow.svg \
  --pages-dir <project_dir>/pages \
  --out <project_dir>/walkthrough.html
```
- 如项目配置了 `<project_dir>/skeleton.css`，可追加 `--skeleton-css <project_dir>/skeleton.css`（仅限微调圆角、间距、字号；**严禁**注入任何品牌蓝/红/绿彩色皮肤）。
- 编译产物自带：95% 纯黑白灰 `wt-*` 底图 + 5% `#D97706` 琥珀橙增量/焦点标引、`flow | spec` 双视图切换、输入框内联 `@[组件名]` 胶囊（支持 `Backspace` 退格一键删除）及 `DOC_VERSION_HASH` 双时机回查导出（`.md` / `.jsonl`）。

### 第 4 步：编译后门禁校验 `walkthrough.html` 与 `v1` 初稿基线快照
```bash
python3 scripts/preflight_check.py <project_dir>/walkthrough.html
```
- 仅当退出码为 `0` 时，才可将干净的 `<project_dir>/walkthrough.html` 交付给 PM（**严禁向 PM 倾倒门禁校验日志、文件字节数或后台命令流水账**）。
- **自动留存初稿基线**：若 `<project_dir>/versions/v1` 尚不存在，编译通过门禁后立即在后台静默运行 `python3 scripts/version_manager.py snapshot <project_dir> --note "v1 初稿基线"`（供定稿时 `eval_tracker.py score` 自动对比计算真实的初稿→定稿返工修改率）。

## 输出
- `<project_dir>/spec.json`（通过 `spec-v2` 门禁）
- `<project_dir>/walkthrough.html`（通过 DOM 拓扑、菱形分支与锚点门禁）

## 验收标准
- `preflight_check.py <project_dir>/spec.json` 与 `preflight_check.py <project_dir>/walkthrough.html` 退出码均为 `0`。
- 离线 `file://` 双击打开三栏联动、菱形分支切换、内联 `@[组件名]` 退格删除及 `.md` / `.jsonl` 导出全部正常。
