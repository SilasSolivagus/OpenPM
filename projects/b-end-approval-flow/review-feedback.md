---
project: b-end-approval-flow
version_hash: b20a50k1
exported_at: 2026-11-20T15:07:00+08:00
total_comments: 1
valid_count: 1
invalid_count: 0
---

# 评审反馈记录（Review Feedback）

## [FB-001] @[采购金额输入框] @[提交采购申请按钮]（valid）

- **version_hash**: `b20a50k1`
- **status**: `valid`
- **view**: `flow`
- **node**: `F_FORM`
- **page**: `p-apply-form`
- **vars**: `{"leader_decision": "approve", "amount_tier": "gt_50k", "audit_decision": "approve"}`
- **targets**: `[{"page": "p-apply-form", "comp_id": "form.amount.input", "comp_name": "采购金额输入框", "fallback_selector": "[data-comp-id=\"form.amount.input\"]"}, {"page": "p-apply-form", "comp_id": "form.submit.btn", "comp_name": "提交采购申请按钮", "fallback_selector": "[data-comp-id=\"form.submit.btn\"]"}]`

**修改意见**：
采购金额输入框提示文案明确标注「单位：人民币元，支持小数点后两位」，提交按钮文案统一改为「确认发起审批」。
