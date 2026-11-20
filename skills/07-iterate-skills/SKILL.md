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

### 第 2 步：拟定候选改进并执行随机双盲 A/B 对比实验与 Confluence XML 验证（`ab_eval_harness.py`）
针对高频 `open` 错题修改 `evals/taste-profile.md` 或 `skills/01-* ~ 06-*` 时，禁止仅凭主观感觉合入，必须执行全链路双盲实验：
1. **剔除训练集并随机盲标（`prepare`）**：
   - **严格剔除提炼本次规则的来源项目**（防止拿训练集考自己过拟合），选择 ≥ 3 个独立测试项目生成旧规范（Baseline）与新规范（Candidate）全套产物（含 `wiki_sync.py export` 产出的三列左图右文稿）；
   - 运行 `python3 scripts/ab_eval_harness.py prepare --pairs-json <pairs.json> --exp-dir <exp_dir> --exclude-train <来源项目>`，由加密随机数将新旧方案随机打乱命名为 `plan_A` / `plan_B`，真身密钥锁入 `.blind_key.json`。
2. **程序化嵌套表格与 Confluence XML 严格解析校验（`verify-table-xml`）**：
   - 运行 `python3 scripts/ab_eval_harness.py verify-table-xml <wiki-page.md...>` 与 `preflight_check.py`：
   - 确保外层三列表格 **`0 破表`**、单元格内单行紧凑 HTML `<table>` 100% 平衡还原、且转 `Confluence 7.4+ Storage XML` 通过 Python `ElementTree` 严格闭合解析（`N/N 通过`）。
3. **独立裁判 Subagent 盲评打分（`evals/judge-rubric.md`）**：
   - 启动一个**全新的独立 Subagent**（严禁读取 `.blind_key.json`），仅输入 `blind_cases_for_judge.json` 与 `evals/judge-rubric.md`；
   - 逐项目对 `plan_A` / `plan_B` 输出 **10 分制综合总分 `score_10`**（精确到小数点后两位）、**北极星指标 `estimated_wiki_rewrite_pct`（预估上 Wiki 前需手动删改重排的比例 %）** 以及额外抓出的微调瑕疵（如轻微过度表格化等）。
4. **自动揭盲生成 `ab_validation_report.md`（`unblind`）**：
   - 运行 `python3 scripts/ab_eval_harness.py unblind --exp-dir <exp_dir> --verdicts <judge_verdicts.json>`，自动揭盲输出胜负票数（如 `3:0 全票胜出`）、均分提升（如 `3.17 → 9.33 / 10`）、手动删改率下降（如 `67.0% → 10.7%`）及 XML 解析通过率证据报告。

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
