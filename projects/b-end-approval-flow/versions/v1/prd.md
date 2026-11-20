# 企业采购审批流 PRD（v2.0）

- **项目标识**：`b-end-approval-flow`
- **版本**：`v2.0`
- **端形态**：`web-admin`（企业管理后台）
- **参考基线**：`history/prd-v1.md`

---

## 1. 迭代目标

在 v1.0「直属主管单级审批」基础上，升级两项核心能力：
1. **主管初审后按大额阈值加签财务总监复核**：所有采购单提交后均先经「直属主管初审」；主管同意后，当采购单金额 **> 5 万元**时自动流转至「财务总监复核」节点；金额 **<= 5 万元**时保持单级办结，主管同意即通过。
2. **驳回后保留草稿并支持驳回重提**：无论是直属主管初审驳回还是财务总监复核驳回，系统均保留原采购单填写的金额、事由等草稿数据，并引导申请人通过「重新编辑」回到填报页修改后再次提交。

---

## 2. 业务流程图与判断节点

1. **采购申请列表（`F_LIST` -> `p-apply-list`）**：查看采购单列表与状态，点击「+ 新建采购单」（`list.new.btn`）或驳回单据「重新编辑」（`list.row2.reedit.btn`）进入填报页。
2. **新建/编辑采购申请单（`F_FORM` -> `p-apply-form`）**：填写采购金额（`form.amount.input`，单位：人民币元，支持小数点后两位）与采购事由（`form.reason.input`），点击「确认发起审批」（`form.submit.btn`）进入直属主管初审。
3. **直属主管初审（`F_LEADER` -> `p-leader-audit`）**：所有采购单必经初审节点，展示采购单摘要，提供同意（`audit.approve.btn`）与驳回（`audit.reject.btn`）操作。
4. **主管初审判断（`D_AUDIT_LEADER`）**：判断直属主管是否同意。
   - `同意`（`approve`）：进入「金额阈值判断（`D_AMOUNT_50K`）」。
   - `驳回`（`reject`）：流转至「驳回保留草稿提示页（`F_REJECTED` -> `p-audit-rejected`）」。
5. **金额阈值判断（`D_AMOUNT_50K`）**：判断采购单金额是否 `> 5 万元`。
   - `<= 5万`（`le_50k`）：单级审批完成，直接进入「审批通过结果页（`F_DONE` -> `p-audit-done`）」。
   - `> 5万`（`gt_50k`）：自动加签流转至「财务总监复核（`F_FINANCE` -> `p-finance-audit`）」。
6. **财务总监复核（`F_FINANCE` -> `p-finance-audit`）**：大额采购单专属复核页，需填写复核意见（`finance.comment.input`），选择通过（`finance.approve.btn`）或驳回（`finance.reject.btn`）。
7. **财务复核判断（`D_AUDIT_OK`）**：根据财务总监复核决策分流：
   - `通过`（`approve`）：流转至「审批通过结果页（`F_DONE` -> `p-audit-done`）」。
   - `驳回`（`reject`）：流转至「驳回保留草稿提示页（`F_REJECTED` -> `p-audit-rejected`）」。
8. **审批通过结果页（`F_DONE` -> `p-audit-done`）**：展示最终审批通过状态及完整审批轨迹。
9. **驳回保留草稿提示页（`F_REJECTED` -> `p-audit-rejected`）**：保留原采购单草稿，点击「重新编辑」（`rejected.reedit.btn`）虚线回流至 `F_FORM`（`p-apply-form`）修改重提。

---

## 3. 页面与交互锚点清单

| 页面 ID | 页面名称 | 核心交互锚点（`data-comp-id`） |
| :--- | :--- | :--- |
| `p-apply-list` | 采购申请列表页 | `list.new.btn`、`list.filter.select`、`list.search.input`、`list.row1.view.btn`、`list.row2.reedit.btn`、`list.row3.view.btn` |
| `p-apply-form` | 新建/编辑采购申请单页 | `form.back.btn`、`form.amount.input`、`form.reason.input`、`form.draft.btn`、`form.submit.btn` |
| `p-leader-audit` | 直属主管审批弹窗页 | `audit.close.btn`、`audit.comment.input`、`audit.reject.btn`、`audit.approve.btn` |
| `p-finance-audit` | 财务总监复核页 | `finance.back.btn`、`finance.comment.input`、`finance.reject.btn`、`finance.approve.btn` |
| `p-audit-done` | 审批通过结果页 | `done.back_list.btn`、`done.new_order.btn` |
| `p-audit-rejected` | 驳回保留草稿提示页 | `rejected.back_list.btn`、`rejected.reedit.btn` |
