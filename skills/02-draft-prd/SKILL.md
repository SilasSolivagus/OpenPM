---
name: 02-draft-prd
description: 读取 project-context.md 与 history/ 基线，编写或按 review-feedback.md / .jsonl 局部增量修订结构化 prd.md（含 F-xx 功能点、状态机与异常分支）。
---

# 02 - Draft PRD（结构化文字版 PRD 起草与局部增量修订）

## 目标
结合 `<project_dir>/project-context.md` 与 `<project_dir>/history/` 历史基线（如有），编写或局部修订结构化文字版 `<project_dir>/prd.md`。文档必须具备唯一功能点 ID（`F-xx`）、完整状态流转、异常兜底与验收标准（AC），作为下游 `pages/*.html`、`flow.svg` 与 `spec.json` 的需求事实源。

## 输入
- **`evals/taste-profile.md`（开工前必读门禁）**：起草或改稿前必须先读取已沉淀的 PM 个人品味与高频避坑规则（及同项目的 `evals/datasets/project-decisions.jsonl`），严禁重犯历史错误
- `<project_dir>/project-context.md`（**前置门禁**：若不存在，必须先按根目录 `AGENTS.md` 执行 `AskUserQuestion` 5 问并代写 `.env.local` 凭证；若跳过则自动生成纯黑白灰阶 `wt-*` + `local-obsidian` 默认 `project-context.md`）
- 可选：`<project_dir>/history/prd-remote.md` 与 `<project_dir>/history/pull-diff.md`（改线上已有功能时的历史基线）
- 可选：`<project_dir>/review-feedback.md` 或 `<project_dir>/review-feedback.jsonl`（评审导出的结构化批注，用于局部精准回写）

## 输出结构规范（`<project_dir>/prd.md` · 强制「三段式」结构以完美对齐 Wiki 交付）
1. **文档元信息（YAML Frontmatter）**：`project`、`title`、`version_hash`、`status`、`platform`、`owner`、`updated_at`。
2. **第一段（表前全局导读区 · 不绑定单页）**：
   - `## 1. 背景与目标`：核心痛点、业务价值与目标；
   - `## 2. 范围边界`：本期范围（In Scope）与明确不做（Out of Scope）；
   - `## 3. 术语解释与角色职责`（按需）：核心名词定义、多角色操作矩阵；
   - `## 4. 主流程与状态`：端到端业务流转说明（定稿导出 Wiki 时会自动在此处嵌入纯灰阶全局流程图 `flow.svg`）。
3. **第二段（页面功能与字段细则 · 必须显式绑定页面 ID 以归拢进左原型右说明表）**：
   - 在 `## 5. 功能需求` 下，每个功能子项使用 `### F-01 <功能名>（p-<page_id>）` 标注其所属基页面 ID（导出给人类阅读时会自动剥离括号内的工程 ID `p-xxx`，并将其完整聚合到对应页面原型图的右栏！）：
     - **触发条件与前置校验**
     - **字段与组件状态定义**（初始态 / 加载态 / 成功态 / 空态 / 错误或驳回态）
     - **异常分支与验收标准（AC）**
   - **严禁把彩色皮肤写入需求**：遵循「学骨架不学配色」铁律，严禁将“主按钮改成品牌蓝色 / 驳回弹窗改成红色”当作产品需求写入 PRD（注：Wiki 导出文档中的下载超链接保持标准蓝色 `#0052CC`，仅原型界面本身保持纯灰阶）。
4. **第三段（表后全局工程约定与验收区 · 跨页通用规则）**：
   - `## 6. 全局公共逻辑 / 历史数据兼容`（如跨端默认记忆、存量数据映射）；
   - `## 7. 数据埋点与非功能要求`（性能、幂等、监控）；
   - `## 8. 关键验收用例与待确认事项`。

## 多人评审聚合与局部精准回写模式（收到 1 份或多份 `review-feedback*.md` / `.jsonl` 时）
0. **多人评审自动合并与冲突检测（`merge_feedback.py`）**：
   - 当收到多位同事（如前端、后端、测试）导出的多份评审文件，或项目目录下存在多份 `review-feedback-*.jsonl/.md` 时，**必须先运行**：
     ```bash
     python3 scripts/merge_feedback.py <project_dir> [file1 file2 ...]
     ```
   - 脚本自动生成 `<project_dir>/review-merged.md` 与 `review-merged.jsonl`，将所有意见分为三类：
     1. **`AUTO_APPLY`（无冲突且锚点有效）**：直接进入下方局部精准回写；
     2. **`CONFLICTS`（≥2 位评审人对同一 `page::comp_id` 提出不同修改意见）**：**严禁 AI 擅自二选一覆盖！** 必须先调用 `AskUserQuestion` 将冲突双方的原话并列展示给 PM 裁决，拿到拍板结论后再修改；
     3. **`INVALID_ANCHORS`（落点已失效）**：向 PM 指出并请人工确认。
1. **校验单文件批注状态**：逐条解析批注中的 `author`、`status`、`node`、`page`、`vars` 与 `targets: [{ page, comp_id, comp_name, fallback_selector }]`：
   - 仅自动回写 `status: "valid"` 且无多人冲突的批注；
   - 若存在 `status: "invalid"`（落点已失效或 `version_hash` 不匹配），必须向 PM 指出并请人工确认，严禁盲目猜测修改。
2. **局部增量修改**：只修改受影响的 `F-xx` 章节，**严禁全篇重写未提及的功能点**，保持既有编号与未变更段落完全稳定，并同步告知下游 `03` / `04` 仅重绘对应页面与节点。
3. **静默记录业务决策与通用错题（`eval_tracker.py`）**：
   - 若批注属于**当前项目的业务规则拍板**（如阈值、频控、文案特例），后台静默运行：
     `python3 scripts/eval_tracker.py log-decision --project <project> --prd-ref <F-xx> --comp-id <comp_id> --decision "..."`
   - 若批注或口头纠偏指出的是 **AI 通用画法缺陷或 PM 跨项目个人品味偏好**（如按钮命名习惯、布局固定范式、漏写异常分支），后台静默运行：
     `python3 scripts/eval_tracker.py log-defect --skill 02-draft-prd --symptom "..." --root-cause "..."`（累积满 3 条将自动触发 `07-iterate-skills` 合并提醒）。

## 验收标准
- `<project_dir>/prd.md` 中所有核心功能均带唯一 `F-xx` ID，且覆盖正常态、过渡态与异常兜底。
- 增量修订时未波及无关章节；无任何品牌色/业务红绿配色伪需求。
