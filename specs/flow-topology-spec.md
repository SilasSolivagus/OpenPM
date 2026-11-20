# 流程图拓扑与交互契约（Flow Topology Spec）

本规范定义了 `walkthrough.html` 中内嵌 SVG 流程图与 JavaScript 状态数据（`NODES`）之间的结构化契约，重点解决**连线拓扑缺失**与**判断菱形不可交互**两大问题，确保流程图不仅可看，更可点选、可联动变量、可高亮分支并作为评审落点。

---

## 1. 连线规范（解决缺口 1：拓扑可追溯）

在 SVG 流程图中，所有表示节点流向的连线（`<polyline>`，以及带有箭头或标签的连线路径）**必须**携带完整的起止节点拓扑属性：

| 属性名 | 必填性 | 值规范 | 说明 |
| :--- | :--- | :--- | :--- |
| `data-from` | **必填** | 源节点 ID（须存在于 `NODES` 中） | 标识该连线的起点节点，如 `N_start` 或 `D_captcha_check`。 |
| `data-to` | **必填** | 目标节点 ID（须存在于 `NODES` 中） | 标识该连线的终点节点，如 `N_slider_verify` 或 `E_blocked`。 |
| `data-branch` | 分支连线必填 | 分支条件值（如 `true` / `false` / `slider` / `timeout`） | 当源节点为判断菱形（`D_*`）时，用于标识该连线对应的分支条件，支持按当前变量高亮对应通路。 |

### 示例：连线 SVG

```xml
<!-- 普通流向连线 -->
<polyline
  points="160,80 160,130"
  data-from="N_submit_click"
  data-to="D_captcha_check"
  marker-end="url(#arrow)" />

<!-- 判断菱形发出的条件分支连线 -->
<polyline
  points="160,190 160,250"
  data-from="D_captcha_check"
  data-to="N_slider_verify"
  data-branch="slider"
  marker-end="url(#arrow)" />
```

**约束**：
- 任何 `<polyline>` 只要用于表达流程连接，禁止缺失 `data-from` 或 `data-to`。
- 装饰性辅助线（如背景网格线）不得使用与流程连线相同的语义选择器，或应使用 `<line>` / `<path class="bg-grid">` 以示区分。

---

## 2. 判断菱形规范（解决缺口 2：菱形可点击与变量联动）

在传统流程图中，判断菱形往往只是静态图形，无法点击、无法切换分支、也无法挂载评审备注。本规范强制要求所有判断菱形具备一等公民交互能力：

### 2.1 SVG DOM 属性契约

所有判断菱形容器 `<g>` **必须**满足以下属性要求：

| 属性名 | 必填性 | 值规范 | 说明 |
| :--- | :--- | :--- | :--- |
| `data-node` | **必填** | `D_*` 前缀的节点 ID（如 `D_captcha_check`） | 全局唯一节点 ID，与 `NODES` 字典中的键严格一致。 |
| `data-node-type` | **必填** | 固定值 `decision` | 明确声明该节点为判断菱形，触发菱形专属高亮、分支切换与点击事件。 |
| `tabindex` / `role` | 推荐 | `role="button" tabindex="0"` | 支持键盘焦点与无障碍访问。 |

**普通流程节点对比**：
- 普通动作节点使用 `data-node="N_*"`、`data-node-type="process"`（或 `start` / `end`）。
- 判断菱形节点必须使用 `data-node="D_*"`、`data-node-type="decision"`。

### 示例：判断菱形 SVG

```xml
<g class="flow-node flow-decision"
   data-node="D_captcha_check"
   data-node-type="decision"
   role="button"
   tabindex="0">
  <polygon points="160,130 230,165 160,200 90,165" />
  <text x="160" y="169" text-anchor="middle">风控校验类型?</text>
</g>
```

### 2.2 `NODES` 数据注册契约

所有在 SVG 中出现的 `data-node`（包括 `N_*` 与 `D_*`）必须在脚本的 `NODES` 配置对象中注册。对于 `data-node-type="decision"` 的判断菱形，**必须**注册其关联的 `branchVar` 与 `rules`（规则说明）：

```javascript
const NODES = {
  "D_captcha_check": {
    id: "D_captcha_check",
    type: "decision",
    title: "风控校验类型判断",
    branchVar: "captcha_type", // 关联的全局状态变量名
    rules: [
      { value: "none",   label: "低风险免校验",   targetNode: "N_publish_success" },
      { value: "slider", label: "中风险滑块拼图", targetNode: "N_slider_verify" },
      { value: "sms",    label: "高风险短信验证", targetNode: "N_sms_verify" }
    ],
    description: "根据实时风控评分决定触发何种验证方式。",
    page: "page_captcha_verify"
  }
};
```

### 2.3 判断菱形必须支持的三种交互行为

1. **点击高亮分支**：
   - 点击 `D_*` 菱形时，右侧/顶部详情面板展示该菱形的 `title`、`description` 与全部 `rules`；
   - 同时在 SVG 中高亮该菱形自身，以及所有 `data-from="D_*"` 的出边连线（当前激活 `branchVar` 值对应的 `data-branch` 连线应以主高亮色实线展示，其余分支以次级高亮或虚线区分）。
2. **切换条件（联动全局变量）**：
   - 用户在详情面板或菱形快捷气泡中点击某条 `rule`（例如将 `captcha_type` 切换为 `sms`）时，系统必须同步更新全局状态变量 `vars[branchVar]`；
   - 同步联动中间栏原型视图刷新为对应变量状态，并更新 SVG 中高亮的激活通路。
3. **作为评审备注落点**：
   - 开启「点选批注」模式时，判断菱形 `<g data-node="D_*" data-node-type="decision">` 必须可被直接点选为批注目标；
   - 导出 `review-feedback.md` 时，其 `view` 记为 `flow`，`node` 记为该菱形的 `D_*` ID，`comp_id` / `comp_name` 可映射为节点 ID 与 `NODES[id].title`。
