---
name: 02-draft-prd
description: 读取 project-context.md 与 history/ 基线，编写或按 review-feedback.md / .jsonl 局部增量修订结构化 prd.md（含 F-xx 功能点、状态机与异常分支）。
---

# 02 - Draft PRD（结构化文字版 PRD 起草与局部增量修订）

## 目标
结合 `<project_dir>/project-context.md` 与 `<project_dir>/history/` 历史基线（如有），编写或局部修订结构化文字版 `<project_dir>/prd.md`。文档必须具备唯一功能点 ID（`F-xx`）、完整状态流转、异常兜底与验收标准（AC），作为下游 `pages/*.html`、`flow.svg` 与 `spec.json` 的需求事实源。

## 输入
- `<project_dir>/project-context.md`（**前置门禁**：若不存在，必须先按根目录 `AGENTS.md` 执行 `AskUserQuestion` 5 问并代写 `.env.local` 凭证；若跳过则自动生成纯黑白灰阶 `wt-*` + `local-obsidian` 默认 `project-context.md`）
- 可选：`<project_dir>/history/prd-remote.md` 与 `<project_dir>/history/pull-diff.md`（改线上已有功能时的历史基线）
- 可选：`<project_dir>/review-feedback.md` 或 `<project_dir>/review-feedback.jsonl`（评审导出的结构化批注，用于局部精准回写）

## 输出结构规范（`<project_dir>/prd.md`）
1. **文档元信息（YAML Frontmatter）**：`project`、`title`、`version_hash`、`status`、`platform`、`owner`、`updated_at`。
2. **业务背景与范围边界**：核心痛点、目标指标、本期范围（In Scope，标注相对于 `history/prd-remote.md` 的新增/修改项）与明确不做（Out of Scope）。
3. **功能点详述（必须含唯一 `F-xx` ID）**：
   - 每个功能点编号如 `F-01`、`F-02`（子项 `F-01.1`），并显式包含：
     - **触发条件与前置校验**
     - **正常主流程**
     - **页面与组件状态定义**（初始态 / 加载态 / 成功态 / 空态 / 错误或驳回态）
     - **异常分支与兜底策略**（网络超时、并发冲突、次数超限锁定、权限拦截等）
     - **验收标准（AC）**
   - **严禁把彩色皮肤写入需求**：遵循「学骨架不学配色」铁律，只定义文案、布局层级与交互反馈，严禁将“主按钮改成品牌蓝色 / 驳回弹窗改成红色”当作产品需求写入 PRD。
4. **角色权限与数据约束**：多角色操作矩阵、字段校验规则与频控阈值。

## 局部精准回写模式（收到 `review-feedback.md` / `.jsonl` 时）
1. **校验批注状态**：逐条解析批注中的 `status`、`node`、`page`、`vars` 与 `targets: [{ page, comp_id, comp_name, fallback_selector }]`：
   - 仅自动回写 `status: "valid"` 的批注；
   - 若存在 `status: "invalid"`（落点已失效或 `version_hash` 不匹配），必须向 PM 指出并请人工确认，严禁盲目猜测修改。
2. **局部增量修改**：只修改受影响的 `F-xx` 章节，**严禁全篇重写未提及的功能点**，保持既有编号与未变更段落完全稳定，并同步告知下游 `03` / `04` 仅重绘对应页面与节点。

## 验收标准
- `<project_dir>/prd.md` 中所有核心功能均带唯一 `F-xx` ID，且覆盖正常态、过渡态与异常兜底。
- 增量修订时未波及无关章节；无任何品牌色/业务红绿配色伪需求。
