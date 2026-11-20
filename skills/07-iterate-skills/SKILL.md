---
name: 07-iterate-skills
description: 自我迭代 Skill：跑 evals/test-cases/ 回归测试，定期汇报改动并强制使用 AskUserQuestion 让用户决定「改不改、改哪」，严格区分写入 project-decisions.jsonl 与 skill-defects.jsonl，避免通用 Skill 过拟合。
---

# 07 - Iterate Skills（Skill 自我迭代与回归门禁）

## 目标
在持续使用 6 个核心工作流 Skill 的过程中，系统化收集问题、运行回归测试用例，并在**人类确认（Human-in-the-Loop）**的前提下安全演进 Skill 与规范，防止将单一项目的业务特例过拟合进通用 Skill。

## 核心原则：严格区分业务决策与 Skill 缺陷
所有反馈与复盘记录必须先分类，再写入对应数据集（严禁混写）：
1. **具体项目的业务改点** $\rightarrow$ 写入 `evals/datasets/project-decisions.jsonl`
   - 例如：“发布器人机验证在风控高风险时增加短信二次验证”、“B 端审批金额阈值调整为 5 万元”。
   - 这类记录只服务于该项目或同类业务参考，**绝对不能**直接写死到通用 `skills/01..06/SKILL.md` 中。
2. **Skill 通用缺陷** $\rightarrow$ 写入 `evals/datasets/skill-defects.jsonl`
   - 例如：“`04-flow-canvas` 生成菱形节点时遗漏 `data-node-type="decision"`”、“`02-draft-prd` 局部修订时误改了未提及的章节”。
   - 仅此类通用能力/规范缺陷才允许进入 Skill 修订候选清单。

## 执行步骤
1. **收集与分类记录**：
   - 从项目评审记录（`review-feedback.md`）、`preflight_check.py` 报错或人工复盘中提取问题。
   - 按上述原则分别追加到 `evals/datasets/project-decisions.jsonl` 或 `evals/datasets/skill-defects.jsonl`。
2. **运行回归测试集**：
   - 遍历 `evals/test-cases/` 下的标准用例（如 `case-01-c-end-captcha.md`、`case-02-b-end-approval.md` 及对应基线），验证当前 Skill 链路是否满足验收标准及 `preflight_check.py` 门禁。
3. **定期汇报并强制询问用户（必须调用 `AskUserQuestion`）**：
   - 汇总当前发现的 `skill-defects.jsonl` 缺陷清单、影响范围与拟修改方案。
   - **强制使用 `AskUserQuestion` 工具**向用户确认：**「改不改、改哪几项」**。
   - 未经用户明确选择同意，**严禁**擅自修改 `skills/` 下的任何 `SKILL.md` 或 `scripts/`。
4. **实施修改与二次回归**：
   - 仅修改用户批准的 Skill 条目。
   - 修改完成后再次运行 `evals/test-cases/` 回归测试与 `preflight_check.py`，确保旧用例无退化（No Regression）。

## 验收标准
- `project-decisions.jsonl` 与 `skill-defects.jsonl` 边界清晰，无项目业务逻辑污染通用 Skill。
- 每次准备修改 Skill 前均通过 `AskUserQuestion` 获得用户明确授权。
- 修改后所有 `evals/test-cases/` 回归通过。
