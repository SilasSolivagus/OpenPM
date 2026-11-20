---
project: my-feature-name          # 项目英文短标识（kebab-case），建议与目录名一致
title: 需求名称（例如：安全风控滑块验证升级）
owner: 产品经理姓名
status: draft                     # draft | in_review | approved | archived
target_release: 2026-12-01        # 预期发布日期或版本迭代号
wiki_adapter: local-obsidian      # local-obsidian | wecom | confluence | feishu
wiki_config:
  # 若使用 local-obsidian，无需填写以下字段；所有敏感密钥一律存入根目录 .env.local
  space_or_parent: ""
  doc_id: ""
---

# 项目上下文（Project Context）

> [!NOTE] 使用说明
> 本文件位于 `projects/<project-slug>/project-context.md`，通常由 AI Agent 在首次启动 5 问后自动生成。AI 在生成 `prd.md`、`pages/*.html`、`flow.svg`、`spec.json` 与 `walkthrough.html` 时将严格遵循此处的术语、端形态与骨架约束。

---

## 1. 业务背景与核心目标

- **解决什么问题**：简述当前业务痛点或用户诉求。
- **核心指标 / 成功标准**：例如「验证通过率提升至 95%」、「人工客诉率下降 30%」。
- **本次范围（In Scope）**：
  - 范围项 1
  - 范围项 2
- **明确不做（Out of Scope）**：
  - 暂不涉及项 1

---

## 2. 业务术语表（Glossary）

> 确保 PRD 文案、流程图节点、原型 `data-comp-name` 使用完全一致的业务名词。

| 术语（标准称呼） | 英文 / 代码标识 | 业务定义 | 禁用别称（避免歧义） |
| :--- | :--- | :--- | :--- |
| 滑块验证码 | `slider_captcha` | 用户拖动拼图滑块完成人机校验 | 滑动条、拼图锁 |
| 发布场景 | `publish_scene` | 触发风控校验的具体业务入口（如评论、发帖、登录） | 业务线、入口 |
| *（按需补充）* | | | |

---

## 3. 端形态与线框色彩铁律

### 3.1 目标端形态（Platforms）

- **主端形态**：`App 375px` / `PC Web` / `管理后台 web-admin` / `小程序` / `多端`（保留适用项）
- **交互状态变量（Vars）**：列出需要在 `walkthrough.html` 中支持切换预览的核心状态变量：
  - `platform`: `["app", "pc"]`
  - `publish_scene`: `["comment", "login"]`
  - `captcha_type`: `["chars", "slider", "grid"]`

### 3.2 色彩与线框规范（95% 纯黑白灰底图 + 5% 唯一琥珀橙 `#D97706` 工程标引色）

- **业务底图 100% 纯黑白灰阶 `wt-*`**：所有存量背景与业务组件（含主次按钮、弹窗、驳回/错误态）一律锁定纯黑白灰阶线框（`#111111` / `#666666` / `#E5E5E5` / `#FFFFFF`），**严禁使用品牌蓝、成功绿、危险红等任何业务语义色**。
- **唯一工程标引色 `#D97706`（琥珀橙）**：全系统仅允许在客观的两处出现琥珀橙 `#D97706`：
  1. **本期改动增量（Delta）**：`SPEC_CARDS` 锚定的改点组件，以及 `spec.json` 中标记为 `change: "new" | "modified"` 的流程节点；
  2. **当前走查/点选焦点（Focus）**：当前选中的流程节点、激活分支通路及点选批注框。
- **设备视口尺寸**：移动端 `phone`（`375x812`）/ 桌面端 `wide`（`1280x800`）
- **组件库约束**：原生轻量 HTML+CSS（`wt-*` 标准类，单文件零外部依赖，离线 `file://` 100% 可用）

### 3.3 跨公司骨架规范载入与兜底策略（`ui_kit`，学骨架不学配色）

不同公司的产品经理可通过以下**三种零代码 / 低门槛方式**对齐本公司交互骨架（可单独或组合使用，**永远只学布局结构与文案习惯，不提取彩色皮肤**）：

```yaml
ui_kit:
  preset: ""                 # 可选端型预设：ios-app | android-app | miniapp | web-admin | pc-client
  references_dir: ""         # 可选参考目录：如 references/（放入现成页面截图或 HTML 片段）
  skeleton_css: ""           # 可选骨架微调文件：如 skeleton.css（仅限微调圆角、间距、字号变量）
```

- **方式 A（截图 / 参考 HTML 骨架学习）**：把现成页面截图或 HTML 片段放入项目 `references/` 目录，由 `03-prd-to-wireframe-prototype` 提取导航形态、卡片/弹窗布局、间距密度与按钮文案习惯，映射为纯黑白灰阶 `wt-*` 结构。
- **方式 B（骨架 Token 微调 `--skeleton-css`）**：如需微调组件圆角、间距或字号，提供 `skeleton.css`，在 `build_walkthrough.py` 编译时通过 `--skeleton-css <skeleton.css>` 注入（严禁覆写彩色背景或彩色边框）。
- **方式 C（端型预设）**：选择 `ios-app` / `android-app` / `miniapp` / `web-admin` / `pc-client`，自动匹配对应视口尺寸与交互控件惯例。
- **默认兜底策略**：若 PM 什么都不配，默认采用标准**纯黑白灰阶 `wt-*` 线框**，专注信息层级、状态流转与交互逻辑评审。

---

## 4. 已有参考资料与约束（可选）

- **关联旧版 PRD / Wiki 页面链接**：
- **技术与合规约束**：例如「弱网超时阈值为 5s」、「必须支持无障碍键盘操作」。
