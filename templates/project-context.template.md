---
project: my-feature-name          # 项目英文短标识（kebab-case），建议与目录名一致
title: 需求名称（例如：安全风控滑块验证升级）
owner: 产品经理姓名
status: draft                     # draft | in_review | approved | archived
target_release: 2026-12-01        # 预期发布日期或版本迭代号
wiki_adapter: local-obsidian      # local-obsidian | feishu | confluence
wiki_config:
  # 若使用 local-obsidian，无需填写以下字段
  space_or_parent: ""
  doc_id: ""
---

# 项目上下文（Project Context）

> [!NOTE] 使用说明
> 复制本文件到 `projects/<project-slug>/project-context.md` 并填写以下内容。AI 在生成 PRD、原型与 `walkthrough.html` 时将严格遵循此处的术语、端形态与风格约束。

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

## 3. 端形态与线框风格配置

### 3.1 目标端形态（Platforms）

- **主端形态**：`H5` / `Web` / `iOS` / `Android` / `小程序` / `Admin 后台`（保留适用项）
- **交互状态变量（Vars）**：列出需要在 `walkthrough.html` 中支持切换预览的核心状态变量：
  - `platform`: `["H5", "Web"]`
  - `publish_scene`: `["comment", "login"]`
  - `captcha_type`: `["none", "slider", "sms"]`

### 3.2 线框与视觉风格（Wireframe Style）

- **保真度**：`中保真交互线框`（默认，突出结构、状态与文案，避免过度视觉装饰）｜ `高保真品牌色`
- **主色调**：`#2563EB`（品牌主色）/ `#DC2626`（告警/失效标红）
- **设备视口尺寸**：移动端 `375x812` / 桌面端 `1280x800`
- **组件库偏好**：原生轻量 HTML+CSS（单文件零依赖，确保离线 `walkthrough.html` 100% 可用）

### 3.3 跨公司设计规范载入与兜底策略（`ui_kit`，可选）

不同公司的产品经理可通过以下**三种零代码 / 低门槛方式**载入本公司设计规范（可单独使用或组合使用）：

```yaml
ui_kit:
  preset: ""                 # 可选端型预设：ios-app | android-app | miniapp | web-admin | pc-client
  references_dir: ""         # 可选参考目录：如 references/（放入现成页面截图或 HTML 片段）
  theme_css: ""              # 可选样式文件：如 theme.css（覆盖 --wt-* CSS 变量）
```

- **方式 A（最简单：截图 / 参考 HTML 喂入）**：把本公司现成页面截图或 HTML 片段放到项目 `references/` 目录，由 `03-prd-to-wireframe-prototype` 自动提取配色、圆角、导航与表单风格。
- **方式 B（设计 Token / CSS 注入）**：提供 `theme.css`（覆盖 `--wt-accent`、`--wt-bg`、圆角、字体等 CSS 变量），编译 `walkthrough.html` 时通过 `--theme <theme.css>` 参数内联注入。
- **方式 C（端型预设）**：选择 `ios-app` / `android-app` / `miniapp` / `web-admin` / `pc-client`，自动匹配对应视口尺寸与交互控件惯例。
- **不载入时的兜底策略**：若 PM 什么都不配，默认兜底到「**中立灰阶高保真线框（`wt-*`）**」，专注信息层级、状态流转与交互逻辑，不因视觉配色干扰评审。

---

## 4. 已有参考资料与约束（可选）

- **关联旧版 PRD / 竞品链接**：
- **技术与合规约束**：例如「弱网超时阈值为 5s」、「必须支持无障碍键盘操作」。
