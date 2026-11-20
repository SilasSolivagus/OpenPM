---
name: 05-flow-walkthrough
description: 组装三栏交互 HTML（全局流程 + 单页改点 + 捕获阶段点选器 + 评审备注抽屉），交付前必须运行 scripts/preflight_check.py 门禁。
---

# 05 - Flow Walkthrough（三栏交互式评审演示组装）

## 目标
将 `02-draft-prd` 的需求改点、`03-prd-to-wireframe-prototype` 的线框原型页面与 `04-flow-canvas` 的业务流程图 SVG，组装为单文件可离线打开的三栏交互式 HTML（`walkthrough.html`），支持研发、测试与设计在同一页面内完成全链路走查与组件级评审标注。

## 输入
- `<project_dir>/prd.md`
- `<project_dir>/prototype/`（线框原型页面片段）
- `<project_dir>/flow/flow-canvas.svg` 与 `NODES` 元数据
- 可选：`<project_dir>/theme.css`（设计 Token / CSS 变量覆盖文件，用于 `--theme` 注入）
- 可选：`<project_dir>/references/`（参考截图/HTML，已在 `03-prd-to-wireframe-prototype` 阶段提取）

## 主题注入与兜底编译
使用 `scripts/build_walkthrough.py` 组装单文件 `walkthrough.html` 时：
- **有 `theme.css` 时**：传入 `--theme <project_dir>/theme.css`，脚本会将该 CSS 内容内联注入到 `<style id="custom-theme">` 中，覆盖默认 `--wt-*` 变量（如 `--wt-accent`、`--wt-bg`、圆角、字体等）。
- **无 `theme.css` 时（兜底）**：不传 `--theme` 参数，自动使用内置的中立灰阶高保真线框（`wt-*`）样式作为兜底，保证零外部依赖、离线可用且专注交互逻辑评审。

## 三栏交互架构要求
1. **左栏：全局业务流程图**
   - 嵌入 `flow-canvas.svg`，支持点击节点切换当前激活节点与右侧原型页面。
   - 高亮当前节点及关联的 `data-from` / `data-to` 连线。
2. **中栏：单页原型 + 改点说明**
   - 渲染当前节点对应的原型页面（与 `NODES[id].page` 一一对应）。
   - 展示本节点关联的 PRD 功能点 ID（`F-xx`）及本期改点摘要（新增/修改/异常分支）。
3. **右栏：评审备注抽屉 + 捕获阶段点选器**
   - 实现**捕获阶段点选器（Capture-phase Inspector）**：开启点选模式时，在 DOM 捕获阶段拦截点击，读取最近带 `data-comp-id` 和 `data-comp-name` 的祖先组件，高亮轮廓并自动填充至评审备注表单。
   - 评审备注抽屉支持：添加/编辑/删除针对特定 `data-comp-id` 或 `data-node` 的评审意见，并支持一键导出为结构化 `review-feedback.md`（供 `02-draft-prd` 增量修订）。

## 交付门禁（强制）
在声明交付完成前，**必须**运行静态门禁脚本：
```bash
python3 scripts/preflight_check.py <project_dir>/walkthrough.html
```
- 仅当退出码为 `0` 时才允许交付。
- 若返回非 `0` 退出码，必须根据输出的错误清单逐项修复 SVG 属性、组件锚点或 `NODES` 页面引用后重新检查，严禁跳过门禁。

## 输出
- `<project_dir>/walkthrough.html`
- `preflight_check.py` 零错误通过报告

## 验收标准
- 三栏联动正常：点击流程节点可切换原型页与改点；开启点选器可准确捕获 `data-comp-id` / `data-comp-name` 并记录评审备注。
- `python3 scripts/preflight_check.py <project_dir>/walkthrough.html` 退出码为 `0`。
