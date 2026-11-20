# Case 02: B 端后台审批流 — 多级费用/采购单审批

## 用例类型
- **端类型**：B 端（PC 管理后台 `wide` 工作台）
- **核心考察点**：多角色权限矩阵、条件分支路由（金额阈值）、驳回保留草稿重提、纯灰阶 `wt-*` 组件与点分小写锚点完整性

## 输入摘要
1. 员工提交采购申请单，状态流转：`草稿 -> 直属主管审批 -> [金额 > 50,000?] -> 财务总监复核 -> 审批通过`。
2. 审批人可执行操作：
   - **同意**：流转至下一节点或终态「已通过」。
   - **驳回**：必填驳回原因，保留原单据草稿，支持申请人点击「重新编辑」修改后重提。
3. 异常分支：并发审批冲突（单据已被他人处理）、无审批权限访问拦截。

## 必检断言（Assertions）
1. **PRD 结构化 (`02-draft-prd`)**：
   - `<project_dir>/prd.md` 必须包含角色权限边界（申请人 / 直属主管 / 财务总监）及并发冲突异常说明。
2. **纯灰阶原型与点分锚点 (`03-prd-to-wireframe-prototype`)**：
   - 页面位于 `<project_dir>/pages/<page_id>.html`，根容器统一为 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">`。
   - 全部业务组件（含同意/驳回按钮、驳回提示框）保持 100% 纯黑白灰阶 `wt-*`，且具备同页唯一的**点分小写** `data-comp-id`（如 `form.amount.input`、`form.submit.btn`、`audit.approve.btn`、`audit.reject.btn`）与 `data-comp-name`。
3. **流程图拓扑与增量标引 (`04-flow-canvas`)**：
   - `<project_dir>/flow.svg` 中金额阈值判断（如 `D_AMOUNT_50K`）与审批结果判断（如 `D_AUDIT_OK`）必须为 `<g data-node="D_*" data-node-type="decision">`，且所有菱形出边携带 `data-branch`。
   - 驳回重提回流连线 `<polyline>` 正确标注 `data-from` 与 `data-to`；`spec.json` 中新增的财务复核节点等标注 `change: "new" | "modified"`。
4. **双阶段门禁校验 (`05-flow-walkthrough`)**：
   - `python3 scripts/preflight_check.py <project_dir>/spec.json` 与 `python3 scripts/preflight_check.py <project_dir>/walkthrough.html` 均必须返回退出码 `0`。
