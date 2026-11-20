---
name: 07-iterate-skills
description: 调用 scripts/eval_tracker.py 汇总历史评分与未消化错题，通过双盲 A/B 对比实验与独立裁判打分量化 Skill 改进收益，经 PM 确认后固化至 evals/taste-profile.md 与 skills/。
---

# 07 - Iterate Skills（自动记分、错题汇总与双盲自我迭代）

## 目标
让整套 OpenPM 体系在真实公司业务中**自动攒经验、定期自进化**——持续降低北极星指标「上 Wiki 前 PM 需手动删改重排的比例（%）」，保证**同一个坑绝不踩第二次**。

---

## 一、 何时触发本技能（自动提醒 + 定期复盘）

1. **平时无感自动攒数据（无需人工干预）**：
   - `05` 首版编译通过自动打 `versions/v1` 初稿快照；
   - `02` 每次收到评审回写或口头纠偏，自动调用 `scripts/eval_tracker.py log-decision`（单项目业务规则）或 `log-defect`（通用画法缺陷/个人品味）；
   - `06` 每次定稿自动调用 `scripts/eval_tracker.py score <project_dir> --stage final` 计算客观得分与返工率。
2. **三大触发入口**：
   - **攒够阈值自动提醒**：当 `eval_tracker.py` 输出 `[ITERATION_TRIGGER]`（距上次迭代满 3 个定稿需求、或 `open` 错题 ≥ 3 条、或单次得分 `< 7.5`）且 PM 同意“复盘优化”时；
   - **PM 主动召唤**：PM 随时说“复盘优化一下”、“看看最近评分”；
   - **定期自动巡检**：配合客户端定时任务（如每周五下午运行 `python3 scripts/eval_tracker.py digest`）。

---

## 二、 标准执行四步法

### 第 1 步：读取评分与错题体检报告
```bash
python3 scripts/eval_tracker.py digest
```
查看近期定稿平均得分、平均返工修改率（%）以及所有 `status: "open"` 的通用错题（`evals/datasets/skill-defects.jsonl`）。

### 第 2 步：拟定候选改进并执行双盲 A/B 回归门禁
针对高频 `open` 错题拟定 `evals/taste-profile.md` 或 `skills/01-* ~ 06-*` 的改进规则，禁止仅凭主观感觉直接合入：
1. **抽取盲测用例**：从 `evals/test-cases/` 或脱敏历史项目中抽取代表性样本，对比改进前后产物（匿名标记为方案 A / 方案 B）。
2. **硬门禁先行**：候选产物必须 100% 通过 `python3 scripts/preflight_check.py`（`spec.json` + `walkthrough.html` 退出码均为 `0`）。
3. **双盲独立裁判打分（10 分制）**：按以下维度盲评方案 A vs B：
   - 需求逻辑闭环与异常兜底覆盖度；
   - 原型骨架贴合度及**「95% 纯黑白灰 `wt-*` 底图 + 5% 琥珀橙 `#D97706` 增量/焦点标引（节点高亮 ≤ 75%）」**遵守度；
   - 流程图自上而下（Top-Down）正交美观度与左右真分栏零遮挡；
   - **北极星指标**：预估「上 Wiki 前 PM 需手动删改重排的比例（%）」。

### 第 3 步：人机协同拍板（`AskUserQuestion`）
用大白话向 PM 简明呈现（控制在 10 行内）：
- 近期平均返工率变化 + 本次提炼出的 1~3 条改进规则 + A/B 盲评得分对比；
- 调用 `AskUserQuestion` 请 PM 拍板固化哪几条（严格区分：具体项目业务规则只留在 `project-decisions.jsonl`，通用规则才进入 `taste-profile.md` 与 `skills/`）。

### 第 4 步：一键落盘固化并重置周期计数
对 PM 确认采纳的改进项，执行：
```bash
python3 scripts/eval_tracker.py mark-resolved SD-00x SD-00y --add-taste "<经 PM 确认的一句话永久品味/避坑规则>"
```
- 自动将对应错题标为 `resolved`、把永久规则追加进 `evals/taste-profile.md`（后续 `02/03/04` 开工前必读生效），并写入 `optimize-checkpoints.jsonl` 重置下一轮 3 单计数周期！
