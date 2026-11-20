# `walkthrough.html` 交付前自动门禁清单（Preflight Checklist）

在生成 `walkthrough.html` 并向团队或 Wiki 交付之前，AI 或构建脚本必须依次执行以下 5 类自动门禁检查。**任何一项 P0 检查失败，严禁交付**，必须修复源码后重新生成并复检。

---

## 门禁总览

| 检查维度 | 级别 | 检查目标 | 通过标准 |
| :--- | :--- | :--- | :--- |
| 1. SVG 拓扑完整性 | **P0** | 连线 `data-from` / `data-to` 与拓扑连通 | 100% 流程连线具备有效起止属性，无悬空节点 |
| 2. 菱形可点性与注册 | **P0** | `D_*` 判断菱形 DOM 与 `NODES` 配置 | 100% 菱形可点击、已注册 `branchVar` 与 `rules` |
| 3. 组件语义 ID 覆盖 | **P0** | 原型交互控件 `data-comp-id` 覆盖率 | 所有核心交互控件与弹窗均具备唯一语义 ID |
| 4. 页面/节点引用可达性 | **P0** | `NODES` ↔ SVG ↔ 原型页面交叉引用 | 无死链、无未定义的 `page` 或 `targetNode` |
| 5. 单文件离线完整性 | **P1** | 零外部阻塞依赖与文件自包含 | 断网双击 `file://` 打开无报错，评审导出正常 |

---

## 1. SVG 拓扑检查（P0）

- [ ] **连线属性完备**：所有流程连线 `<polyline>` 均携带非空的 `data-from` 和 `data-to` 属性。
- [ ] **起止节点存在**：每条 `<polyline>` 的 `data-from` 和 `data-to` 值均能在当前 SVG 的 `[data-node]` 元素及 `NODES` 字典中找到对应节点。
- [ ] **分支连线标注**：从 `data-node-type="decision"` 节点出发的所有 `<polyline>` 均携带 `data-branch` 属性，且其值与 `NODES[from].rules[].value` 一一对应。

## 2. 菱形可点性与交互检查（P0）

- [ ] **菱形属性规范**：所有判断菱形 `<g>` 均携带 `data-node="D_*"` 和 `data-node-type="decision"`。
- [ ] **规则与变量注册**：`NODES` 中每个 `type === "decision"` 的条目均包含非空的 `branchVar` 字符串和至少 2 条 `rules`（每条包含 `value`、`label`、`targetNode`）。
- [ ] **事件绑定可达**：菱形 `<g>` 未被透明遮罩层（如 `pointer-events: none` 缺失的覆盖层）阻挡点击事件，点击后可正常触发：
  1. 高亮对应分支连线；
  2. 切换 `vars[branchVar]`；
  3. 作为评审备注的 `node` 落点。

## 3. 组件语义 ID 覆盖检查（P0）

- [ ] **核心控件全覆盖**：原型中所有可交互控件（`button`、`input`、`select`、`[role="button"]`、滑块、弹窗容器）均已标注 `data-comp-id` 与 `data-comp-name`。
- [ ] **全局唯一性**：在同一页面与同一变量视图下，`data-comp-id` 无非预期的重复冲突。
- [ ] **命名规范**：`data-comp-id` 符合小写点分语义路径（如 `captcha.slider.track`），不包含随机生成的 UUID 或临时下标。
- [ ] **旧版兼容**：若存在历史 `data-anchor`，已补充或迁移为 `data-comp-id`（或确认落点查找器兼容双属性）。

## 4. 页面与节点引用可达性检查（P0）

- [ ] **节点 → 页面可达**：`NODES` 中所有配置了 `page` 字段的节点，其 `page` 值均能在原型 DOM 中找到对应的 `[data-page-id="<page>"]` 容器。
- [ ] **规则 → 目标节点可达**：所有判断分支 `rules[].targetNode` 均存在于 `NODES` 中，无悬空跳转。
- [ ] **PRD ↔ 节点/组件锚点可达**：PRD 文档中引用的组件 ID 或节点 ID 均真实存在于 `walkthrough.html` 中。
- [ ] **版本指纹存在**：页面全局已注入非空的 `VERSION_HASH`（写入导出 `review-feedback.md` 的 `version_hash` 字段）。

## 5. 单文件离线完整性检查（P1）

- [ ] **无外部阻塞依赖**：HTML 内不依赖外部 CDN 的 JS/CSS 框架（如必须引用，应已内联或提供离线降级方案），在断网环境下通过 `file://` 协议直接打开可正常渲染三栏布局与 SVG。
- [ ] **零控制台致命错误**：页面加载、切换变量、点击节点、开启点选批注、导出 `review-feedback.md` 全链路执行过程中，Console 无 `Uncaught Error` / `TypeError`。
- [ ] **导出校验闭环**：点击「导出评审反馈」可正常下载或复制标准 Markdown，且包含 `version_hash`、`status`、`vars`、`comp_id` 等全部必填字段；当人为删除某已批注组件的 DOM 后再导出，该条记录必须被标记为 `status: invalid` 并附带「落点已失效」警告。
