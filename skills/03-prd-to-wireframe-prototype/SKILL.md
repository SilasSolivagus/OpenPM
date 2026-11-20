---
name: 03-prd-to-wireframe-prototype
description: 根据 prd.md 与 project-context.md 生成 pages/<page_id>.html 纯黑白灰阶 wt-* 线框页面片段（div.page 根容器 + 点分小写 data-comp-id），支持局部增量重绘。
---

# 03 - PRD to Wireframe Prototype（纯黑白灰阶线框原型生成）

## 目标
将 `<project_dir>/prd.md` 与 `<project_dir>/project-context.md` 转化为保存在 `<project_dir>/pages/<page_id>.html` 的纯黑白灰阶 `wt-*` 线框原型片段，严格打上标准根容器属性与点分小写组件语义锚点，实现内联 `@[组件名]` 点选评审与增量改点标引。

## 输入
- **`evals/taste-profile.md`（开工前必读）**：绘制或修改页面前先读取已固化的组件排版品味与避坑规则
- `<project_dir>/prd.md`
- `<project_dir>/project-context.md`（读取端形态 `phone` / `wide` 及 `ui_kit` 骨架配置）
- 契约参考：`specs/anchor-schema.md`、`specs/spec-v2-schema.md`
- 可选：`<project_dir>/references/`（现成页面截图或 HTML 片段，**仅提取布局骨架与文案习惯**）
- 可选：`<project_dir>/review-feedback.md` / `.jsonl`（用于局部增量重绘）

## 强制契约与色彩铁律
1. **100% 纯黑白灰阶 `wt-*` 业务底图（严禁彩色皮肤与非标私有类）**：
   - 所有业务页面背景、导航栏、卡片、主次按钮（`.wt-btn` / `.wt-btn-primary`）、表单输入（`.wt-input` / `.wt-select` / `.wt-textarea`）、弹窗（`.wt-modal`）以及驳回/报错提示（`.wt-alert` / `.wt-badge`）一律使用标准 **纯黑白灰阶 `wt-*` 类名**。
   - **严禁**引入品牌蓝、成功绿、危险红等任何业务语义色，**严禁**使用非 `wt-*` 的私有组件前缀，也**严禁**注入任何彩色主题文件（全系统唯一工程标引色琥珀橙 `#D97706` 由工作台编译器专用于标记 `SPEC_CARDS` 增量与当前焦点，页面 HTML 内禁止自行涂色）。
   - 若存在 `references/` 参考图，只学习间距密度、圆角、导航/弹窗结构与按钮文案习惯；若需微调骨架尺寸，仅通过 `skeleton.css`（编译期 `--skeleton-css`）调整圆角、间距与字号。
2. **统一页面根容器格式（强制 `<div>` 四属性）**：
   - 每个 `<project_dir>/pages/<page_id>.html` 的最外层根容器**必须**严格写为：
     ```html
     <div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">
       <!-- 页面纯灰阶 wt-* 结构 -->
     </div>
     ```
   - 严禁使用裸 `<section class="proto-page">` 或缺失 `id` / `data-page` / `data-page-id`。
3. **点分小写 `data-comp-id` 组件锚点（强制）**：
   - 页面内所有可交互元素（`button`、`input`、`select`、`textarea`、`[role="button"]`）及关键弹窗/卡片容器，**必须**同时携带：
     - `data-comp-id="<module>.<element>.<type>"`：**点分小写英文语义路径**（如 `form.submit.btn`、`form.amount.input`、`captcha.slider.track`），同页内绝对唯一，跨版本保持稳定；
     - `data-comp-name="<可读中文名称>"`（如 `提交采购申请按钮`、`采购金额输入框`）；
     - 可选 `data-comp-role="control|modal|container|text|feedback|nav"`。
4. **局部精准重绘**：
   - 收到 `review-feedback.md` / `.jsonl` 时，仅修改 `targets[].page` 涉及的 `pages/<page_id>.html` 对应组件片段，严禁重写未提及的页面或随意变更既有 `data-comp-id`。

## 输出
- `<project_dir>/pages/<page_id>.html`（每个基础页面一个 HTML 片段；多端对称变体可在 `spec.json` 中通过 `variant_of` 继承复用）

## 验收标准
- 所有页面均位于 `pages/<page_id>.html`，根元素为 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">`。
- 100% 交互控件带同页唯一的点分小写 `data-comp-id` 与中文 `data-comp-name`。
- 100% 使用纯黑白灰阶 `wt-*` 类名，零彩色内联样式、零非标私有类名残留。
