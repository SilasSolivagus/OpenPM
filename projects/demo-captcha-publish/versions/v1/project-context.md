# 项目上下文配置：发布器人机验证（demo-captcha-publish）

## 1. 基本信息
- **项目标识**：`demo-captcha-publish`
- **项目名称**：内容发布器人机验证接入
- **目标端**：C 端（Web 端 + H5 移动端自适应发布浮层）
- **所属模块**：内容安全 / 发布网关

## 2. 数据源与同步适配器
- **adapter**：`local-markdown`（示例项目，可切换为 `confluence` / `feishu` / `obsidian`）
- **wiki_source**：`local://projects/demo-captcha-publish/prd.md`
- **page_id**：`DEMO-CAPTCHA-001`

## 3. 业务背景与约束
- **痛点**：近期社区高频出现自动化脚本批量发帖，需要为内容发布器接入前置风控与人机验证拦截能力。
- **核心原则**：
  - 正常低风险用户 **零打扰**（静默放行）。
  - 命中风控的中高风险请求，在不丢失用户已编辑正文的前提下弹出滑块人机验证。
  - 验证通过后自动续传原发布请求，无需用户再次点击发布。
- **界面约束**：
  - 线框原型采用中立风格，桌面端基准宽度 `1200px`，弹窗宽度 `360px`。
  - 所有交互组件必须遵循 `specs/anchor-schema.md` 标注 `data-comp-id` 与 `data-comp-name`。
