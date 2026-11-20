# Case 01: C 端多状态强交互 — 内容发布触发人机验证

## 用例类型
- **端类型**：C 端（移动端 `phone` / 桌面端 `wide` 发布器浮层）
- **核心考察点**：高频状态切换、人机验证浮层、风控分支跳转、异常兜底、纯灰阶 `wt-*` 组件与点分小写锚点完整性

## 输入摘要
1. 用户在内容发布器点击「立即发布」。
2. 服务端前置风控检查：
   - 低风险：直接发布成功，跳转结果页。
   - 中/高风险：拦截发布并弹出人机验证浮层（滑块拼图 / 字符 / 九宫格）。
3. 人机验证交互状态：
   - 初始态、拖拽/作答中、校验中（Loading）、校验成功（自动续传发布）、校验失败（保留浮层提示并支持重新验证）、当日失败达上限 N 入黑拦截、网络超时重试。

## 必检断言（Assertions）
1. **PRD 结构化 (`02-draft-prd`)**：
   - `<project_dir>/prd.md` 必须包含唯一功能点 ID（如 `F-01`、`F-02`、`F-03`）。
   - 必须显式定义「校验失败」「失败达上限锁定」「接口超时」3 类异常分支，且不混入彩色皮肤伪需求。
2. **纯灰阶原型与点分锚点 (`03-prd-to-wireframe-prototype`)**：
   - 页面输出至 `<project_dir>/pages/<page_id>.html`，根容器统一为 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">`。
   - 100% 采用标准纯黑白灰阶 `wt-*` 类名（如 `.wt-modal`、`.wt-card`、`.wt-btn`、`.wt-btn-primary`），严禁出现非标私有组件类名或品牌蓝/红/绿业务语义色。
   - 人机验证弹窗、滑块拖动控件、发布按钮、重新验证按钮等所有交互元素必须同时具备同页唯一的**点分小写** `data-comp-id`（如 `captcha.slider.modal`、`captcha.slider.track`、`editor.publish.btn`、`captcha.retry.btn`）与中文 `data-comp-name`。
3. **流程图拓扑与 `spec.json` 分支同步 (`04-flow-canvas`)**：
   - `<project_dir>/flow.svg` 中风控判断节点与人机校验结果判断节点必须为菱形 `<polygon>` 且包裹 `<g data-node="D_*" data-node-type="decision">`。
   - 所有 `<polyline>` 必须具备 `data-from` 和 `data-to`，且从 `D_*` 出发的每条分支连线必须携带匹配 `spec.json` `vars` 选项的 `data-branch`。
   - `spec.json` 的 `nodes` 中本期新增/修改节点标注 `change: "new" | "modified"`（触发琥珀橙 `#D97706` 增量高亮）。
4. **双阶段门禁校验 (`05-flow-walkthrough`)**：
   - `python3 scripts/preflight_check.py <project_dir>/spec.json` 与 `python3 scripts/preflight_check.py <project_dir>/walkthrough.html` 均必须返回退出码 `0`。
