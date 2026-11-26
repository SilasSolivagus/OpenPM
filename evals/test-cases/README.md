# 评测与回归用例说明

本目录存放 `skills/01-*` ~ `07-*` 与核心脚本（`preflight_check.py`、`build_walkthrough.py`、`wiki_sync.py`、`version_manager.py`）的端到端测试用例和改稿记录，用来防止修改通用规则时把原有功能改坏。

## 目录内容
- `test-cases/`：端到端测试场景：
  - `case-01-c-end-captcha.md`：C 端多状态交互（发布器触发人机验证）
  - `case-02-b-end-approval.md`：B 端多角色审批流（采购/费用多级审批）
- `datasets/`：改稿与缺陷记录（JSONL）：
  - `project-decisions.jsonl`：只记具体项目的业务调整（绑定点分小写 `comp_id`，不混进通用规则）
  - `skill-defects.jsonl`：记录通用问题和个人排版偏好（供 `07-iterate-skills` 复盘提炼）

## 回归检查步骤
1. 选一个测试用例，按标准顺序产出文件：
   - `02-draft-prd` → `<project_dir>/prd.md`
   - `03-prd-to-wireframe-prototype` → `<project_dir>/pages/<page_id>.html`
   - `04-flow-canvas` → `<project_dir>/flow.svg` + `<project_dir>/spec.json`（`nodes` / `vars`）
   - `05-flow-walkthrough` → 补齐 `<project_dir>/spec.json` 并生成 `<project_dir>/walkthrough.html`
2. 跑静态检查与编译：
   ```bash
   python3 scripts/preflight_check.py <project_dir>/spec.json
   python3 scripts/build_walkthrough.py \
     --spec <project_dir>/spec.json \
     --svg <project_dir>/flow.svg \
     --pages-dir <project_dir>/pages \
     --out <project_dir>/walkthrough.html
   python3 scripts/preflight_check.py <project_dir>/walkthrough.html
   ```
3. 对照用例里的检查项逐条核实（黑白灰底图 `wt-*`、`#D97706` 琥珀橙增量标记、点分小写 `data-comp-id`、菱形分支 `data-branch` 及 `@[组件名]` 批注回查）。
4. 遇到通用问题时记入 `datasets/skill-defects.jsonl`，后续通过 `07-iterate-skills` 确认后更新规则。
