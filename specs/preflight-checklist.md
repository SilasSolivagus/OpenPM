# `spec.json` 与 `walkthrough.html` 交付前自动门禁清单（Preflight Checklist）

在编译与向团队或 Wiki 交付 `walkthrough.html` 之前，Agent 必须在后台静默执行 `scripts/preflight_check.py` 完成两阶段自动门禁检查（先检 `spec.json`，编译后再检 `walkthrough.html`）。**任何一项 P0 检查失败，严禁交付**，必须修复源码后重新编译复检。

---

## 门禁总览

| 检查维度 | 级别 | 检查目标 | 通过标准 |
| :--- | :--- | :--- | :--- |
| 1. `spec-v2` 契约合法性 | **P0** | `spec.json` 顶层结构与引用闭合 | 符合 `specs/spec-v2.schema.json`，`nodes`/`pages`/`vars` 交叉引用零悬空 |
| 2. SVG 拓扑完整性 | **P0** | 连线 `data-from` / `data-to` / `data-branch` | 100% 流程连线具备有效起止节点，菱形出边 100% 携带匹配 `data-branch` |
| 3. 菱形可点性与分支绑定 | **P0** | `D_*` 判断菱形 DOM 与 `branchVar` | 100% 菱形带 `data-node="D_*"` + `data-node-type="decision"` 并绑定有效 `branch` 变量 |
| 4. 页面根容器与组件语义 ID | **P0** | `<div class="page" ...>` 与点分 `data-comp-id` | 根容器四属性齐全，所有交互控件具备同页唯一点分小写 `data-comp-id` 与 `data-comp-name` |
| 5. 单文件离线与灰阶色彩规范 | **P1** | 零外部依赖、`DOC_VERSION_HASH` 与导出闭环 | 断网 `file://` 可直接打开，95% 纯黑白灰 `wt-*` + 5% `#D97706` 标引，双时机回查正常 |

---

## 1. SVG 拓扑检查（P0）

- [ ] **纵向自上而下排版（Top-Down `TD`）**：`flow.svg` 的 `viewBox` 宽高比 `width / height ≤ 1.45`，主干流向自上而下，禁止扁长横版（`LR`）流程图。
- [ ] **100% 正交折线（禁止斜线）**：每条 `<polyline>` 的所有折线段均严格水平或垂直（无斜线）。
- [ ] **连线属性完备**：所有流程连线 `<polyline>` 均携带非空的 `data-from` 和 `data-to` 属性。
- [ ] **起止节点存在**：每条 `<polyline>` 的 `data-from` 和 `data-to` 值均能在当前 SVG 的 `[data-node]` 元素及 `NODES` 字典中找到对应节点。
- [ ] **菱形分支连线标注**：从 `data-node-type="decision"`（`D_*`）节点出发的所有 `<polyline>` 均携带非空 `data-branch` 属性，且其值与 `VARS` 中对应 `branchVar`（`kind: "branch"`）的 `options[].id` 一一对应。

## 2. 判断菱形可点性与 `VARS` 绑定检查（P0）

- [ ] **菱形 DOM 属性规范**：所有包含菱形 `<polygon>` 的判断节点 `<g>` 均携带 `data-node="D_*"` 和 `data-node-type="decision"`。
- [ ] **分支变量注册**：`NODES` 中每个 `isDecision: true` 的节点均包含非空 `branchVar`，且在 `VARS` 中存在 `id === branchVar`、`kind === "branch"`、`diamond === <node_id>` 的变量定义，其 `options` 至少包含 2 个带有效 `target` 的分支选项。
- [ ] **增量标记合法**：若节点声明了 `change` 字段，其值必须属于 `"unchanged" | "modified" | "new"`（`"new"` 与 `"modified"` 用于触发琥珀橙 `#D97706` 增量高亮）。
- [ ] **事件绑定可达**：菱形 `<g>` 未被遮罩层阻挡点击事件，点击后可正常高亮对应分支、联动切换 `VARS` 并作为 `view: "flow"` 的评审备注 `node` 落点。

## 3. 页面根容器与组件语义 ID 覆盖检查（P0）

- [ ] **页面根容器标准格式**：每个原型页面根元素统一为 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">`。
- [ ] **核心控件全覆盖**：页面内所有可交互控件（`button`、`input`、`select`、`textarea`、`[role="button"]`、弹窗容器）均已标注非空 `data-comp-id` 与 `data-comp-name`。
- [ ] **点分小写格式与同页唯一性**：`data-comp-id` 统一采用点分小写英文语义路径（如 `form.submit.btn`、`audit.reject.btn`），同一页面内严禁重复，严禁使用随机 UUID 或临时下标。
- [ ] **纯黑白灰阶 `wt-*` 类名**：业务组件统一使用标准 `wt-*` 灰阶线框类名，无历史私有类名残留，无业务红/绿/品牌蓝硬编码配色。

## 4. 页面与节点引用可达性检查（P0）

- [ ] **节点 → 页面可达**：`NODES` 中所有节点的 `page` 值均能在 `pages` 及原型 DOM 中找到对应的 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">` 容器。
- [ ] **分支选项 → 目标节点可达**：`VARS` 中所有 `kind: "branch"` 的 `options[].target` 均存在于 `NODES` 中，无悬空跳转。
- [ ] **状态组与改点卡可达**：`STATE_GROUPS` 中的 `states[].page` 以及 `SPEC_CARDS` 中的 `page`（及 `anchor` 对应的组件）均真实存在于原型 DOM 中。
- [ ] **版本指纹常量存在**：脚本已注入非空的 `DOC_VERSION_HASH` 常量（写入导出备注的 `version_hash` 字段）。

## 5. 单文件离线完整性与导出回查检查（P1）

- [ ] **零外部阻塞依赖**：HTML 内联全部样式与脚本，断网双击 `file://` 打开可正常切换 `flow | spec` 视图。
- [ ] **内联 `@[组件名]` 胶囊与退格删除**：打开备注表单后点选原型组件可在输入框内插入 `@[组件名]` 胶囊，支持 `Backspace` 退格键删除与多组件 `@` 引用。
- [ ] **导出与双时机回查闭环**：导出 `review-feedback.md` 与 `review-feedback.jsonl` 均输出统一的 `{ id, version_hash, status, view ("flow"|"spec"), node, page, spec_id?, vars, targets: [{ page, comp_id, comp_name, fallback_selector }], text, time }` 结构；落点缺失或 `version_hash !== DOC_VERSION_HASH` 时强制标记 `status: "invalid"` 并触发导出守卫拦截。
