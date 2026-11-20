## 评审反馈记录（企业采购审批流 · 统一流程联动工作台）

### 1. @[采购金额输入框] (form.amount.input)、@[提交采购申请按钮] (form.submit.btn)
- **状态**: `valid`
- **版本指纹**: `b-end-approval-flow-v1`
- **上下文**: 视图=`全局流程` | 节点=`F_FORM (新建/编辑采购申请单)` | 页面=`p-apply-form` | 变量=`amount_tier=gt_50k, audit_decision=approve`
- **落点列表**:
  - `form.amount.input` (`采购金额输入框`)
  - `form.submit.btn` (`提交采购申请按钮`)
- **修改意见**: 采购金额输入框提示文案明确标注「单位：人民币元，支持小数点后两位」，提交按钮文案统一改为「确认发起审批」。
