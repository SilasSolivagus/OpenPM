# `spec-v2` 单一真相源契约规范（`spec.json`）

本规范定义了 `spec.json`（`version: "spec-v2"`）作为产品交互流程、原型页面、状态变量与评审卡的**单一真相源（Single Source of Truth, SSoT）**。所有下游交付物（包括 `walkmap/1` 运行时数据结构与 `walkthrough.html` 单文件走查交付物）均由 `spec.json` 确定性编译生成，严禁在 HTML 生成阶段凭空捏造节点、页面或分支规则。

---

## 1. 顶层结构概览

`spec.json` 为标准 UTF-8 JSON 对象，包含以下 8 个顶层字段：

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `version` | `string` | **必填** | 固定值 `"spec-v2"`，标识契约版本。 |
| `meta` | `object` | **必填** | 项目元信息（项目 ID、标题、需求文档版本、默认端等）。 |
| `vars` | `array` | **必填** | 全局变量（`global`）、局部组件变量（`local`）与分支判断变量（`branch`）定义列表。 |
| `nodes` | `object` | **必填** | 流程图节点字典（`node_id -> node_def`），包含普通动作节点（`F_*` / `N_*`）与判断菱形（`D_*`）。 |
| `pages` | `object` | **必填** | 原型页面字典（`page_id -> page_def`），支持通过 `variant_of` 声明端变体继承与参数化覆写。 |
| `state_groups` | `object` | 可选 | 同页局部状态组字典（`group_id -> group_def`），用于同一页面内切换校验态/空态/错误态。 |
| `spec_cards` | `array` | 可选 | 需求改点卡列表（`01..N`），绑定到具体 `page` 与组件锚点 `anchor`。 |
| `memos` | `array` | 可选 | 初始或持久化的结构化评审批注列表。 |

---

## 2. 字段详细契约

### 2.1 `meta`（项目元信息）

```json
{
  "project": "demo-captcha-publish",
  "title": "内容发布器人机验证交互走查",
  "doc_version": "v2.0",
  "platform_default": "app",
  "entry_node": "F_ENTRY",
  "prd_source": "local://projects/demo-captcha-publish/prd.md"
}
```

### 2.2 `vars`（状态与分支变量）

每个变量对象结构如下：

- `id` (`string`, 必填)：唯一变量标识（如 `platform`、`login_state`）。
- `label` (`string`, 必填)：展示名称。
- `kind` (`"global" | "local" | "branch"`, 必填)：
  - `global`：全局端/场景切换变量（如 `platform`、`publish_scene`）。
  - `local`：仅在指定 `pages` 生效的局部组件变量（需提供 `pages: string[]`）。
  - `branch`：绑定到判断菱形的流程分支变量，必须包含 `diamond`（指向 `nodes` 中的 `isDecision: true` 节点）与 `nodes`（关联节点 ID 数组）。
- `default` (`string`, 必填)：默认选中的选项 `id`。
- `when` (`object`, 可选)：级联显示条件，键为前置变量 `id`，值为期望的选项 `id` 或数组。
- `options` (`array`, 必填，至少 1 项)：
  - `id` (`string`, 必填)：选项值。
  - `label` (`string`, 必填)：选项展示文案。
  - `target` (`string`, `branch` 类型必填)：选择该分支时跳转的目标节点 ID，**必须存在于 `nodes` 中**。

### 2.3 `nodes`（流程节点）

键为全局唯一 `node_id`（普通节点建议 `F_*` 或 `N_*`，判断菱形强制 `D_*`）：

- `page` (`string`, 必填)：该节点激活时中间栏展示的页面 ID，**必须存在于 `pages` 中**。
- `title` (`string`, 必填)：节点标题。
- `isDecision` (`boolean`, 判断节点必填 `true`)：标记是否为判断菱形；为 `true` 时必须配置 `branchVar`（对应 `vars` 中某 `branch` 变量的 `id`）。
- `branchVar` (`string`, 判断节点必填)：关联的分支变量 ID。
- `state` (`string`, 可选)：默认激活的同页状态，格式 `<group_id>/<state_id>`，需存在于 `state_groups`。
- `anno` (`array`, 可选)：节点右侧说明条目，每项为 `[标题, 正文]` 二元组。

### 2.4 `pages` 与 `variant_of` 端变体参数化机制

为避免 PC 端（`wide`）或次要端页面整份复制移动端（`phone`）页面定义，`spec-v2` 引入 **`variant_of` 端变体参数化字段**：

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
3. 编译器在展开变体页时，自动继承基页面的 `components`、默认 `title` 与基础结构，仅将变体页自身声明的 `frame`、`title` 与 `overrides`（`layout`、`copy`、`components_patch`、`add_components`、`remove_components`）做确定性合并。

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

### 2.6 `spec_cards`（改点卡）

每张改点卡包含：`id`、`title`、`page`（必须存在于 `pages`）、`anchor`（组件锚点或 `data-comp-id`）、`body`。

### 2.7 `memos`（评审批注）

初始为空数组 `[]`，或包含符合 `specs/anchor-schema.md` 的历史批注对象。每条批注通过 `targets: [{ comp_id, comp_name, fallback_selector }]` 关联零个或多个语义组件（`targets` 为空数组 `[]` 时默认关联当前 `node` 与 `page`；`targets` 中任一落点回查命中数为 `0` 时即标记为 `status: "invalid"`）。

---

## 3. `spec.json` → `walkmap/1` 投影规则与确定性编译要求

`05-flow-walkthrough` 技能在生成 `walkthrough.html` 时，必须以 `spec.json` 为唯一输入，执行如下确定性投影（`walkmap/1`）：

| `spec.json` 源字段 | `walkmap/1` / `walkthrough.html` 目标 | 确定性规则 |
| :--- | :--- | :--- |
| `meta` | `<title>`、顶部栏标题、入口节点 | 严格读取 `meta.title` 与 `meta.entry_node`。 |
| `nodes` | `var NODES = {...}` + SVG `<g data-node="...">` | 键集合与 `title`/`page`/`isDecision`/`branchVar`/`anno` 1:1 映射；`isDecision: true` 的节点必须输出 `data-node-type="decision"`。 |
| `vars` | `var VARS = [...]` + SVG `<polyline data-from data-to data-branch>` | 1:1 投影为 `VARS` 数组；`kind === "branch"` 的每条 `options[]` 对应一条从 `diamond` 到 `option.target` 的带 `data-branch` 连线。 |
| `pages` | `<div class="page" id="...">` + `var PAGE_FRAME = {...}` | 先展开所有 `variant_of` 继承与 `overrides`，再输出对应 `frame`（`phone`/`wide`）的 DOM 容器与 `[data-comp-id]`/`[data-comp-name]` 属性。 |
| `state_groups` | `var STATE_GROUPS = {...}` | 1:1 投影。 |
| `spec_cards` | `var SPEC_CARDS = [...]` | 1:1 投影，确保 `page` 与 DOM 中页面一致。 |
| `memos` | 初始评审列表数据 | 若非空则预置渲染，保持与 `DOC_VERSION_HASH` 一致。 |

### `05-flow-walkthrough` 确定性编译门禁

1. **编译前门禁**：必须先执行 `python3 scripts/preflight_check.py <project>/spec.json`，退出码为 `0` 方可进入 HTML 编译。
2. **禁止隐式发明**：编译过程中不得新增 `spec.json` 中不存在的 `page_id`、`node_id`、`D_*` 菱形或 `VARS` 选项。
3. **编译后门禁**：生成 `walkthrough.html` 后，必须执行 `python3 scripts/preflight_check.py <project>/walkthrough.html`，确保 DOM 拓扑、菱形交互、组件锚点与 `NODES` 页面引用全部通过。
