# Evals & 回归测试集说明

本目录用于验证 `skills/01-*` ~ `07-*` 与 `scripts/preflight_check.py`、`scripts/build_walkthrough.py`、`scripts/wiki_sync.py`、`scripts/version_manager.py` 的端到端质量，确保在迭代通用 Skill 时零退化（No Regression）。

## 目录结构
- `test-cases/`：标准端到端测试用例子集，覆盖不同业务形态：
  - `case-01-c-end-captcha.md`：C 端多状态强交互场景（内容发布器触发人机验证）
  - `case-02-b-end-approval.md`：B 端多角色长链路审批流场景（采购/费用后台多级审批）
- `datasets/`：结构化问题与决策数据集（JSONL）：
  - `project-decisions.jsonl`：仅记录**具体项目的业务改点**（点分小写 `comp_id`，严禁混入通用 Skill）
  - `skill-defects.jsonl`：仅记录**Skill 通用缺陷与个人 Taste 偏好**（作为 `07-iterate-skills` 的改进依据）

## 标准回归执行流程
1. 选择目标测试用例，按统一产物约定依次生成：
   - `02-draft-prd` → `<project_dir>/prd.md`
   - `03-prd-to-wireframe-prototype` → `<project_dir>/pages/<page_id>.html`
   - `04-flow-canvas` → `<project_dir>/flow.svg` + `<project_dir>/spec.json`（`nodes` / `vars`）
   - `05-flow-walkthrough` → 补全 `<project_dir>/spec.json` 并确定性编译 `<project_dir>/walkthrough.html`
2. 运行双阶段静态门禁校验：
   ```bash
   python3 scripts/preflight_check.py <project_dir>/spec.json
   python3 scripts/build_walkthrough.py \
     --spec <project_dir>/spec.json \
     --svg <project_dir>/flow.svg \
     --pages-dir <project_dir>/pages \
     --out <project_dir>/walkthrough.html
   python3 scripts/preflight_check.py <project_dir>/walkthrough.html
   ```
3. 核对用例中的「必检断言（Assertions）」是否全部满足（含 95% 纯黑白灰阶 `wt-*` + 5% `#D97706` 琥珀橙标引铁律、点分小写 `data-comp-id`、菱形 `data-branch` 与内联 `@[组件名]` 导出回查）。
4. 若发现 Skill 通用缺陷，记录到 `datasets/skill-defects.jsonl`，并通过 `07-iterate-skills` 经用户确认后迭代修复。
