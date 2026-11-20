# 流程图拓扑与交互契约（Flow Topology Spec）

本规范定义了 `flow.svg` 与 `spec.json`（及编译后 `walkthrough.html` 中的 `NODES` / `VARS`）之间的结构化契约，确保流程图具备**完整连线拓扑**、**判断菱形可点选联动**以及**增量改点与当前焦点的精准琥珀橙 `#D97706` 标引**。

---

## 1. 连线规范（拓扑可追溯）

在 `flow.svg` 中，所有表示节点流向的连线 `<polyline>` **必须**携带完整的起止节点拓扑属性：

| 属性名 | 必填性 | 值规范 | 说明 |
| :--- | :--- | :--- | :--- |
| `data-from` | **必填** | 源节点 ID（须存在于 `nodes` 中） | 标识连线起点，如 `F_FORM` 或 `D_AMOUNT_50K`。 |
| `data-to` | **必填** | 目标节点 ID（须存在于 `nodes` 中） | 标识连线终点，如 `F_LEADER` 或 `F_FINANCE`。 |
| `data-branch` | **菱形出边必填** | 分支选项 ID（对应 `vars` 中 `branchVar` 的 `options[].id`） | 当 `data-from` 为判断菱形（`D_*`）时**必填**，用于按当前激活的分支变量值高亮对应通路。 |

### 示例：连线 SVG

```xml
<!-- 普通流向连线 -->
<polyline
  points="180,110 180,160"
  data-from="F_FORM"
  data-to="D_AMOUNT_50K"
  marker-end="url(#arrow)" />

<!-- 判断菱形发出的条件分支连线（必填 data-branch） -->
<polyline
  points="180,220 180,280"
  data-from="D_AMOUNT_50K"
  data-to="F_FINANCE"
  data-branch="gt_50k"
  marker-end="url(#arrow)" />
```

**约束**：
- 任何用于表达业务流转的 `<polyline>` 禁止缺失 `data-from` 或 `data-to`；从 `D_*` 出发的连线禁止缺失 `data-branch`。
- 装饰性辅助线不得使用裸 `<polyline>` 冒充流程连线（应使用 `<line>` 或 `<path class="bg-grid">`）。

---

## 2. 节点与判断菱形规范（对齐 `spec-v2.schema.json`）

### 2.1 SVG DOM 属性契约

所有流程节点统一包裹在 `<g>` 容器内：

| 属性名 | 必填性 | 值规范 | 说明 |
| :--- | :--- | :--- | :--- |
| `data-node` | **必填** | 普通节点 `F_*` / `N_*`；判断菱形强制 `D_*` | 全局唯一节点 ID，与 `spec.json` 的 `nodes` 字典键严格 1:1 对应。 |
| `data-node-type` | **判断菱形必填** | 固定值 `decision`（普通节点可选 `process` / `start` / `end`） | 凡包含菱形 4 顶点 `<polygon>` 的判断节点 `<g>`，**必须**同时携带 `data-node="D_*"` 与 `data-node-type="decision"`。 |
| `role` / `tabindex` | 推荐 | `role="button" tabindex="0"` | 支持键盘焦点与点击选中。 |

```xml
<g class="flow-node flow-decision"
   data-node="D_AMOUNT_50K"
   data-node-type="decision"
   role="button"
   tabindex="0">
  <polygon points="180,160 260,190 180,220 100,190" />
  <text x="180" y="194" text-anchor="middle">金额 &gt; 5万？</text>
</g>
```

### 2.2 `NODES` 与 `VARS` 数据对齐契约（分支规则归属 `VARS`）

`walkthrough.html` 中的 `NODES` 与 `VARS` 由 `spec.json` 的 `nodes` 与 `vars` 1:1 投影生成：
- **`NODES` 中不包含 `rules` 数组**：`nodeDef` 的合法属性严格对齐 `spec-v2.schema.json`，即 `{ page, title, isDecision, branchVar, state, change, anno }`。
- **分支规则统一存放在 `VARS` 中 `kind: "branch"` 的变量定义内**：通过 `diamond` 绑定判断菱形 ID（等于 `NODES[D_*].branchVar` 反向指向的变量），并在 `options: [{ id, label, target }]` 中声明所有分支选项及跳转目标节点 `target`。

```json
{
  "vars": [
    {
      "id": "amount_tier",
      "label": "采购金额区间",
      "kind": "branch",
      "default": "gt_50k",
      "diamond": "D_AMOUNT_50K",
      "nodes": ["D_AMOUNT_50K", "F_LEADER", "F_FINANCE"],
      "options": [
        { "id": "le_50k", "label": "<=5万", "target": "F_LEADER" },
        { "id": "gt_50k", "label": ">5万", "target": "F_FINANCE" }
      ]
    }
  ],
  "nodes": {
    "D_AMOUNT_50K": {
      "page": "p-apply-form",
      "title": "金额 > 5万？",
      "isDecision": true,
      "branchVar": "amount_tier",
      "change": "modified",
      "anno": [
        ["金额路由判断", "采购金额 <= 5万走直属主管单级审批；> 5万在主管同意后加签财务总监复核。"]
      ]
    },
    "F_FINANCE": {
      "page": "p-finance-audit",
      "title": "财务总监复核",
      "change": "new",
      "anno": [
        ["大额加签复核", "本期新增节点：仅当采购金额 > 5万元时触发。"]
      ]
    }
  }
}
```

---

## 3. 配色铁律与 `change` 增量标引规范

流程图画布严格执行 **「95% 纯黑白灰底图 + 5% 唯一琥珀橙 `#D97706` 工程标引色」**：

1. **存量节点与静态底图（100% 纯黑白灰阶）**：
   - 未变更节点（`change` 未设置或 `"unchanged"`）的边框、填充、文字与默认连线一律采用黑白灰阶（`#111111` / `#666666` / `#E5E5E5` / `#FFFFFF`），严禁将通过/驳回/异常节点涂成绿色、红色或品牌蓝色。
2. **本期改动增量高亮（Delta → 琥珀橙 `#D97706`）**：
   - 当节点在 `spec.json` 中声明 `change: "new"` 或 `change: "modified"` 时，画布自动为该节点渲染 **琥珀橙 `#D97706`** 增量描边/角标，让评审人一眼识别本期新增或修改的流程环节。
3. **当前走查焦点与激活分支（Focus → 琥珀橙 `#D97706`）**：
   - 点击任意流程节点或判断菱形 `D_*` 时，当前焦点选框（`#sel-ring`）及当前 `branchVar` 选值对应的 `data-branch` 激活通路使用琥珀橙 `#D97706` 标引高亮，其余非激活分支保持浅灰或虚线弱化。

---

## 4. 判断菱形的三种标准交互行为

1. **点击检视与高亮分支**：点击 `D_*` 菱形时，联动打开抽屉展示 `NODES[id].page` 原型页、`NODES[id].anno` 节点规则，以及 `VARS` 中对应 `branchVar` 的切换控件，同时高亮当前激活的 `data-branch` 出边。
2. **切换分支联动原型**：用户在控制栏切换 `branchVar` 的任一 `option` 时，同步更新全局状态快照 `vars[branchVar]`、重绘激活通路，并可一键推进至对应 `option.target` 节点页面。
3. **关联评审备注**：在全局流程视图（`view: "flow"`）选中 `D_*` 或任意节点记录备注时，自动写入 `view: "flow"`、`node: "<NODE_ID>"`、`page: NODES[id].page` 及当前 `vars` 快照（若还在原型上点选了 `@[组件名]`，则同步写入 `targets` 列表）。
