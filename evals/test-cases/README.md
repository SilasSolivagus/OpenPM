# Evals & 回归测试集说明

本目录用于验证 `skills/01..07` 与 `scripts/preflight_check.py`、`scripts/version_manager.py` 的端到端质量，确保在迭代通用 Skill 时不会引入退化（No Regression）。

## 目录结构
- `test-cases/`：标准端到端测试用例子集，覆盖不同业务形态：
  - `case-01-c-end-captcha.md`：C 端多状态强交互场景（发布器触发人机验证）
  - `case-02-b-end-approval.md`：B 端多角色长链路审批流场景（采购/费用后台审批）
- `datasets/`：结构化问题与决策数据集（JSONL）：
  - `project-decisions.jsonl`：仅记录**具体项目的业务改点**（不进入通用 Skill）
  - `skill-defects.jsonl`：仅记录**Skill 通用缺陷**（作为 `07-iterate-skills` 的改进依据）

## 回归执行流程
1. 选择目标测试用例，按 `02 -> 03 -> 04 -> 05` 链路生成产物。
2. 运行门禁脚本校验产出的 `walkthrough.html`：
   ```bash
   python3 scripts/preflight_check.py <output_walkthrough.html>
   ```
3. 核对用例中的「必检断言（Assertions）」是否全部满足。
4. 若发现 Skill 通用缺陷，记录到 `datasets/skill-defects.jsonl`，并通过 `07-iterate-skills` 经用户确认后迭代修复。
