---
name: 03-prd-to-wireframe-prototype
description: 根据 PRD 与 project-context.md 生成中立线框原型片段，强制要求所有可评审组件带 data-comp-id 和 data-comp-name（遵循 specs/anchor-schema.md），支持局部增量重绘。
---

# 03 - PRD to Wireframe Prototype（中立线框原型生成）

## 目标
将结构化 `prd.md` 与 `project-context.md` 转化为风格中立、结构清晰、可直接嵌入交互演示页的 HTML/CSS 线框原型片段（`.html` fragment），并严格打上组件评审锚点，实现“点击原型即可定位需求与提评审意见”。

## 输入
- `<project_dir>/prd.md`
- `<project_dir>/project-context.md`（读取目标端尺寸、桌面端/移动端布局约束及 `ui_kit` 配置）
- 规范参考：`specs/anchor-schema.md`
- 可选：`<project_dir>/references/`（本公司现成页面截图或参考 HTML 片段，用于提取设计风格）
- 可选：`<project_dir>/theme.css`（设计 Token / CSS 变量覆盖文件）
- 可选：`<project_dir>/review-feedback.md` 或 PRD Diff（用于局部增量重绘）

## 强制规范
1. **跨公司设计规范载入与兜底规则**：
   - **方式 A（`references/` 自动提取）**：若存在 `<project_dir>/references/` 下的页面截图或参考 HTML 片段，自动提取其中的配色、圆角、导航结构、按钮与表单风格，并映射为标准 `wt-*` 组件结构与 `--wt-*` CSS 变量。
   - **方式 B（`theme.css` 变量兼容）**：若存在 `<project_dir>/theme.css`，原型 HTML 必须保持使用标准 `wt-*` 类名与 `--wt-*` CSS 变量（如 `--wt-accent`、`--wt-bg`），避免硬编码颜色，确保编译期 `--theme` 注入可直接生效。
   - **方式 C（端型预设匹配）**：若 `project-context.md` 的 `ui_kit.preset` 指定了 `ios-app` / `android-app` / `miniapp` / `web-admin` / `pc-client`，自动匹配对应视口尺寸（移动端 `phone` / 桌面端 `wide`）与交互控件惯例（如导航栏、底栏、表单及弹窗规范）。
   - **兜底规则（默认）**：若上述三项均未配置，默认兜底到**中立灰阶高保真线框（`wt-*`）**（中性灰阶、清晰边框、高对比度文字），不引入与业务无关的炫技动效或品牌重度皮肤，专注信息层级、状态流转与交互逻辑，避免视觉配色干扰评审。
2. **可评审组件锚点（强制）**：
   - 所有可交互或可评审组件（包括但不限于 `.pwx-track`、`.pwx-modal`、`button.primary`、`button`、表单输入区、状态提示条、弹窗容器、列表操作区等）**必须**同时具备：
     - `data-comp-id="<页面缩写>_<组件语义ID>"`（全局唯一，如 `pub_btn_submit`、`cap_slider_track`）
     - `data-comp-name="<可读中文组件名称>"`（如 `发布按钮`、`人机验证滑块轨道`）
   - 命名与层级规则严格遵循 `specs/anchor-schema.md`。
3. **多状态覆盖**：
   - 为 PRD 中定义的每个页面/状态生成对应的页面容器（如 `<section class="proto-page" data-page="P_PUBLISH">`），并保证与流程图节点引用的 `page` ID 一致。
4. **局部增量重绘**：
   - 当仅部分 `F-xx` 或 `data-comp-id` 发生变更时，仅重绘受影响的页面或组件片段，保留其余页面的 DOM 结构与既有 `data-comp-id` 不变，避免评审锚点漂移。

## 输出
- `<project_dir>/prototype/pages/` 下的页面片段或 `<project_dir>/prototype/wireframe.html`
- 组件锚点索引清单（`data-comp-id` ↔ `data-comp-name` ↔ `F-xx` 映射表）

## 验收标准
- 所有交互元素与评审容器均包含非空的 `data-comp-id` 和 `data-comp-name`。
- `data-comp-id` 在整个原型中无重复。
- PRD 中所有核心状态与异常弹窗/提示均有对应的原型 DOM 承载。
