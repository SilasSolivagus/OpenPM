---
name: 07-iterate-skills
description: 运行 evals/ 回归测试集，通过双盲 A/B 对比实验与独立裁判打分量化 Skill 改进收益，并通过 AskUserQuestion 将改动严格分流至 project-decisions.jsonl 与 skill-defects.jsonl。
---

# 07 - Iterate Skills（双盲评分与自我迭代）

## 目标
让整套 OpenPM 体系在真实公司业务中越用越顺手——持续降低 PM 在推送 Wiki 前手动删改重排的比例，让 PM 专注投入**业务理解、公司判断与个人 Taste**。

---

## 一、 双盲 A/B 对比实验与回归门禁

每当修改 `skills/01-*` ~ `06-*` 的指令或模板时，禁止仅凭主观感觉合入，必须执行：
1. **抽取盲测用例**：从 `evals/test-cases/` 及脱敏历史项目中抽取代表性样本，按统一产物路径（`prd.md` → `pages/<page_id>.html` → `flow.svg` → `spec.json` → `walkthrough.html`）生成全套交付物。
2. **硬门禁先行**：对候选产物依次运行 `python3 scripts/preflight_check.py <project_dir>/spec.json` 与 `python3 scripts/preflight_check.py <project_dir>/walkthrough.html`，任一返回非 `0` 直接判定不通过。
3. **双盲独立裁判打分（10 分制）**：将基线版与候选新版匿名标记为方案 A / 方案 B，由独立裁判按以下维度盲评：
   - 需求逻辑闭环与异常兜底覆盖度；
   - 原型骨架贴合度及**「95% 纯黑白灰 `wt-*` 底图 + 5% 琥珀橙 `#D97706` 增量/焦点标引」**遵守度（出现品牌蓝/红/绿业务色或非 `wt-*` 私有组件类直接扣分）；
   - 契约一致性（`<div class="page">` 四属性、点分小写 `data-comp-id`、菱形 `data-branch`、内联 `@[组件名]` 导出与 Confluence/飞书左图右文零破表）；
   - **北极星指标**：预估「上 Wiki 前 PM 需手动删改重排的比例（%）」。

---

## 二、 人机协同裁决（`AskUserQuestion`）与双层数据集分流

1. **简明汇报与确认**：向 PM 呈现双盲评分摘要与改动点，通过 `AskUserQuestion` 由 PM 拍板改哪几条。
2. **严格分流两层 JSONL 数据集（防止将单项目业务规则污染进通用 Skill）**：
   - **具体项目业务决策**（如「采购单金额阈值定为 5 万元」「滑块失败 3 次冷却 60 秒」，`comp_id` 使用点分小写如 `captcha.slider.modal`）→ 写入 `evals/datasets/project-decisions.jsonl`，仅作用于对应项目；
   - **Skill 通用缺陷 / PM 个人 Taste**（如「菱形出边漏写 `data-branch`」「提交按钮文案统一偏好『确认提交』」）→ 写入 `evals/datasets/skill-defects.jsonl`，用于升级 `skills/` 与回归断言。
