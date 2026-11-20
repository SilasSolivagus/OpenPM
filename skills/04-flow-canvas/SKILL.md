---
name: 04-flow-canvas
description: 根据 prd.md 与 pages/*.html 生成 flow.svg（连线带 data-from/data-to、菱形带 D_* 与 data-branch），并同步生成 spec.json 中的 nodes（含 change 增量标记）与 vars。
---

# 04 - Flow Canvas（拓扑流程图 `flow.svg` 与节点/分支契约生成）

## 目标
根据 `<project_dir>/prd.md` 的主流程与异常分支，以及 `<project_dir>/pages/<page_id>.html` 的页面清单，生成拓扑严谨的 `<project_dir>/flow.svg`，并同步生成/更新 `<project_dir>/spec.json` 中的 `nodes`（标注本期变更节点的 `change: "new" | "modified"`）与 `vars`（含 `kind: "branch"` 分支规则）。

## 输入
- `<project_dir>/prd.md`
- `<project_dir>/pages/*.html`（获取真实存在的 `<page_id>` 集合）
- 契约参考：`specs/flow-topology-spec.md`、`specs/spec-v2.schema.json`

## 强制拓扑与色彩规范
1. **`flow.svg` 节点与判断菱形属性**：
   - 每个流程节点包裹在 `<g data-node="<NODE_ID>">` 中。
   - **判断菱形（Decision）**：凡包含菱形 4 顶点 `<polygon>` 的节点 `<g>`，**必须**同时携带：
     - `data-node="D_*"`（强制 `D_` 前缀，如 `D_AMOUNT_50K`）
     - `data-node-type="decision"`
   - **普通动作/状态节点**：使用 `data-node="F_*"` 或 `data-node="N_*"`。
2. **`flow.svg` 连线属性（菱形出边必填 `data-branch`）**：
   - 所有流程连线 `<polyline>` **必须**携带非空的 `data-from="<源节点ID>"` 与 `data-to="<目标节点ID>"`。
   - **从判断菱形 `D_*` 出发的每一条 `<polyline>` 必须携带 `data-branch="<option_id>"`**，且 `<option_id>` 与 `spec.json` 中对应 `branchVar` 的 `options[].id` 严格一致。
   - SVG 底图线条、节点框与文字一律保持**纯黑白灰阶**（`#111111` / `#666666` / `#E5E5E5` / `#FFFFFF`），严禁在 SVG 内硬编码红/绿/蓝业务色。
3. **同步生成/更新 `spec.json` 的 `nodes` 与 `vars`**：
   - `nodes` 严格遵循 `spec-v2.schema.json#/nodeDef`：`{ page, title, isDecision?, branchVar?, state?, change?, anno? }`（**不设 `rules` 数组**，分支规则统一放入 `vars` 的 `kind: "branch"` 条目中）。
   - **标注本期改动增量 `change`**：对比历史基线或本期 PRD 范围，将本期新增节点标记为 `"change": "new"`、本期修改节点标记为 `"change": "modified"`、存量未变节点标记为 `"change": "unchanged"`（工作台编译器将自动对 `new` / `modified` 节点渲染唯一工程标引色 **琥珀橙 `#D97706`**）。
   - `vars` 中每个 `kind: "branch"` 变量必须包含 `diamond: "D_*"`、`nodes: [...]`、`default` 以及 `options: [{ id, label, target }]`。

## 输出
- `<project_dir>/flow.svg`
- `<project_dir>/spec.json` 中的 `nodes` 与 `vars` 字段（与 `flow.svg` 节点/连线 1:1 闭合）

## 验收标准
- 100% `<polyline>` 具备有效 `data-from` 和 `data-to`；100% `D_*` 菱形出边具备匹配 `vars` 的 `data-branch`。
- 100% 判断菱形 `<g>` 具备 `data-node="D_*"` 与 `data-node-type="decision"`，并在 `nodes` 中声明 `isDecision: true` 与有效 `branchVar`。
- 所有 `nodes[*].page` 均对应真实的 `pages/<page_id>.html`（或 `spec.json` 中的 `variant_of` 变体页）。
