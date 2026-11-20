# `spec-v2` 单一真相源契约规范（`spec.json`）

本规范定义了 `spec.json`（`version: "spec-v2"`）作为产品交互流程、原型页面、状态变量与评审卡的**单一真相源（Single Source of Truth, SSoT）**，对应 JSON Schema 为 [`specs/spec-v2.schema.json`](./spec-v2.schema.json)（`$id: "https://openpm.dev/specs/spec-v2.schema.json"`）。所有下游交付物（包括运行时数据结构与 `walkthrough.html` 单文件走查交付物）均由 `spec.json` 确定性编译生成，严禁在 HTML 生成阶段凭空捏造节点、页面或分支规则。

---

## 1. 顶层结构概览

`spec.json` 为标准 UTF-8 JSON 对象，包含以下 8 个顶层字段：

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `version` | `string` | **必填** | 固定值 `"spec-v2"`，标识契约版本。 |
| `meta` | `object` | **必填** | 项目元信息（项目 ID、标题、需求文档版本、默认端、入口节点等）。 |
| `vars` | `array` | **必填** | 全局变量（`global`）、局部组件变量（`local`）与分支判断变量（`branch`）定义列表。 |
| `nodes` | `object` | **必填** | 流程图节点字典（`node_id -> node_def`），包含普通动作节点（`F_*` / `N_*`）与判断菱形（`D_*`）。 |
| `pages` | `object` | **必填** | 原型页面字典（`page_id -> page_def`），支持通过 `variant_of` 声明端变体继承与参数化覆写。 |
| `state_groups` | `object` | 可选 | 同页局部状态组字典（`group_id -> group_def`），用于同一页面内切换校验态/空态/错误态。 |
| `spec_cards` | `array` | 可选 | 本期需求改点卡列表（`01..N`），绑定到具体 `page` 与组件锚点 `anchor`（在单页改点视图触发琥珀橙 `#D97706` 增量标引）。 |
| `memos` | `array` | 可选 | 初始或持久化的结构化评审批注列表（遵循 `memoDef`）。 |

---

## 2. 字段详细契约

### 2.1 `meta`（项目元信息）

```json
{
  "project": "b-end-approval-flow",
  "title": "企业采购审批流（v2.0 多级金额路由与驳回重提）",
  "doc_version": "v2.0",
  "platform_default": "web-admin",
  "entry_node": "F_LIST",
  "prd_source": "prd.md"
}
```

编译器会根据 `meta` 与项目规格确定性注入全局常量 `DOC_VERSION_HASH`，用于比对历史评审备注落点是否跨版本失效。

### 2.2 `vars`（状态与分支变量）

每个变量对象结构如下：

- `id` (`string`, 必填)：唯一变量标识（如 `platform`、`amount_tier`）。
- `label` (`string`, 必填)：展示名称。
- `kind` (`"global" | "local" | "branch"`, 必填)：
  - `global`：全局端/场景切换变量（如 `platform`、`publish_scene`）。
  - `local`：仅在指定 `pages` 生效的局部组件变量（需提供 `pages: string[]`）。
  - `branch`：绑定到判断菱形的流程分支规则变量，必须包含 `diamond`（指向 `nodes` 中的 `isDecision: true` 节点）与 `nodes`（关联节点 ID 数组）。
- `default` (`string`, 必填)：默认选中的选项 `id`。
- `when` (`object`, 可选)：级联显示条件，键为前置变量 `id`，值为期望的选项 `id` 或数组。
- `options` (`array`, 必填，至少 1 项)：
  - `id` (`string`, 必填)：选项值（与判断菱形出边 `<polyline data-branch="...">` 一一对应）。
  - `label` (`string`, 必填)：选项展示文案。
  - `target` (`string`, `branch` 类型必填)：选择该分支时跳转的目标节点 ID，**必须存在于 `nodes` 中**。

### 2.3 `nodes`（流程节点）

键为全局唯一 `node_id`（普通节点建议 `F_*` 或 `N_*`，判断菱形强制 `D_*`）：

- `page` (`string`, 必填)：该节点激活时展示的原型页面 ID，**必须存在于 `pages` 中**。
- `title` (`string`, 必填)：节点标题。
- `isDecision` (`boolean`, 判断节点必填 `true`)：标记是否为判断菱形；为 `true` 时必须配置 `branchVar`（对应 `vars` 中某 `kind: "branch"` 变量的 `id`）。
- `branchVar` (`string`, 判断节点必填)：关联的分支变量 ID（分支规则统一存放在该 `branch` 变量的 `options` 中，`nodes` 内不设 `rules` 数组）。
- `state` (`string`, 可选)：默认激活的同页状态，格式 `<group_id>/<state_id>`，需存在于 `state_groups`。
- `change` (`"unchanged" | "modified" | "new"`, 可选)：标记节点在本期需求中的变更状态。存量节点默认 `"unchanged"`（100% 纯黑白灰阶底图）；设为 `"new"` 或 `"modified"` 时，在流程图画布中启用全系统唯一工程标引色 **琥珀橙 `#D97706`** 高亮本期增量。
- `anno` (`array`, 可选)：节点规则说明条目，每项为 `[标题, 正文]` 二元组。

### 2.4 `pages`、根容器契约与 `variant_of` 端变体参数化机制

每个页面片段文件统一保存在 `pages/<page_id>.html`，其**页面根容器**必须统一为：

```html
<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">
  <!-- 内部全部使用纯黑白灰阶 wt-* 类名，交互元素使用点分小写 data-comp-id（如 form.submit.btn） -->
</div>
```

为避免 PC 端（`wide`）或次要端页面整份复制移动端（`phone`）页面定义，`spec-v2` 支持 **`variant_of` 端变体参数化字段**：

```json
"p-editor-base": {
  "frame": "phone",
  "title": "发布器（已填写内容）",
  "components": [
    { "comp_id": "editor.cancel.btn", "comp_name": "取消按钮", "role": "control" },
    { "comp_id": "editor.publish.btn", "comp_name": "发布按钮", "role": "control" }
  ]
},
"p-pc-editor-base": {
  "variant_of": "p-editor-base",
  "frame": "wide",
  "title": "PC 发布器（已填写内容）",
  "overrides": {
    "layout": "pc-timeline-modal",
    "copy": {
      "editor.publish.btn": "发布（Ctrl/Cmd+Enter）"
    },
    "components_patch": {
      "editor.publish.btn": { "shortcut": "Ctrl/Cmd+Enter" }
    }
  }
}
```

**`variant_of` 约束规则**：
1. `pages[page_id].variant_of` 指向的基页面 ID **必须存在于 `pages` 中**。
2. 禁止自引用（`variant_of !== page_id`）及循环继承。
3. 编译器展开变体页时，自动继承基页面的 `components`、默认 `title` 与基础 HTML 结构，仅将变体页声明的 `frame`、`title` 与 `overrides`（`layout`、`copy`、`components_patch`、`add_components`、`remove_components`）做确定性合并。

### 2.5 `state_groups`（同页状态组）

```json
"editor": {
  "title": "发布器同页校验态",
  "states": [
    { "id": "filled", "label": "已填写内容（有效提交）", "page": "p-editor-base" },
    { "id": "empty", "label": "空内容校验提示", "page": "p-editor-empty" }
  ]
}
```

每个 `states[].page` **必须存在于 `pages` 中**。

### 2.6 `spec_cards`（本期改点卡）

每张改点卡包含：`id`、`title`、`page`（必须存在于 `pages`）、可选 `anchor`（目标组件的 `data-comp-id`，如 `form.submit.btn`）与 `body`。在 `spec`（单页改点）视图下，`SPEC_CARDS` 绑定的锚点组件与连线以唯一工程标引色 **琥珀橙 `#D97706`** 标示本期改动增量（Delta）。

### 2.7 `memos`（评审批注，`memoDef`）

初始为空数组 `[]`，或包含符合 `specs/anchor-schema.md` 与 `memoDef` 的结构化批注对象（统一通过 `targets` 结构化列表与 `text` 正文表达）：

```json
{
  "id": "m_1732093800000",
  "version_hash": "b-end-approval-flow-v2.0",
  "status": "valid",
  "view": "flow",
  "node": "F_FORM",
  "page": "p-apply-form",
  "spec_id": "SC_AMOUNT_THRESHOLD",
  "vars": { "amount_tier": "gt_50k", "audit_decision": "approve" },
  "targets": [
    {
      "page": "p-apply-form",
      "comp_id": "form.submit.btn",
      "comp_name": "提交采购申请按钮",
      "fallback_selector": "[data-comp-id=\"form.submit.btn\"]"
    }
  ],
  "text": "提交按钮文案统一改为「确认发起审批」。",
  "time": "14:30"
}
```

- `view` 枚举固定为 `"flow" | "spec"`；`spec_id` 为可选字段（仅在 `spec` 视图关联具体改点卡时记录）。
- `targets` 为空数组 `[]` 时表示整页/节点级备注，关联当前 `node` 与 `page`；`targets` 非空时，任一落点回查命中数为 `0` 或 `version_hash !== DOC_VERSION_HASH` 即标记 `status: "invalid"`。

---

## 3. `spec.json` → `walkthrough.html` 确定性投影与编译门禁

`05-flow-walkthrough` 技能调用 `scripts/build_walkthrough.py` 时，以 `spec.json`、`flow.svg`、`pages/*.html` 为确定性输入：

| `spec.json` 源字段 | `walkthrough.html` 运行时目标 | 确定性规则 |
| :--- | :--- | :--- |
| `meta` | `<title>`、`META`、`ENTRY_NODE`、`DOC_VERSION_HASH` | 严格读取 `meta.title`、`meta.entry_node` 并生成版本哈希常量 `DOC_VERSION_HASH`。 |
| `nodes` | `var NODES = {...}` + SVG `<g data-node="...">` | 键集合与 `page`/`title`/`isDecision`/`branchVar`/`state`/`change`/`anno` 1:1 映射；`change` 为 `"new"` 或 `"modified"` 的节点渲染琥珀橙 `#D97706` 增量标记。 |
| `vars` | `var VARS = [...]` + SVG `<polyline data-from data-to data-branch>` | 1:1 投影为 `VARS` 数组；`kind === "branch"` 的每条 `options[]` 对应一条从 `diamond` 到 `option.target` 的带 `data-branch` 连线。 |
| `pages` | `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">` + `var PAGE_FRAME = {...}` | 展开 `variant_of` 继承与 `overrides`，输出 `phone`/`wide` 容器及点分小写 `[data-comp-id]`/`[data-comp-name]` 属性。 |
| `state_groups` | `var STATE_GROUPS = {...}` | 1:1 投影。 |
| `spec_cards` | `var SPEC_CARDS = [...]` | 1:1 投影，在 `spec` 视图下用琥珀橙 `#D97706` 锚定增量改点。 |
| `memos` | `var INITIAL_MEMOS = [...]` | 若非空则预置渲染，按 `DOC_VERSION_HASH` 与 `targets` 执行加载时回查。 |

### 确定性编译三步门禁

1. **编译前校验 Spec**：执行 `python3 scripts/preflight_check.py projects/<project>/spec.json`，退出码为 `0` 方可进入编译。
2. **确定性编译（仅允许灰阶与骨架微调）**：执行 `python3 scripts/build_walkthrough.py --spec projects/<project>/spec.json --svg projects/<project>/flow.svg --pages-dir projects/<project>/pages --out projects/<project>/walkthrough.html`（如需微调圆角/间距/字号，仅允许传入 `--skeleton-css`，严禁注入彩色皮肤）。
3. **编译后校验 HTML**：执行 `python3 scripts/preflight_check.py projects/<project>/walkthrough.html`，确保退出码为 `0`。
