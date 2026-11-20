# Claude Code 入口规范

请完整阅读并严格遵守根目录 [AGENTS.md](./AGENTS.md) 中的全部规范，核心执行铁律摘要如下：

1. **首次启动 5 问 & 严禁让 PM 手改 `.env.local`**：当目标项目缺少 `project-context.md` 时，先调用 `AskUserQuestion` 发起基础 5 问；若 PM 选择 `wecom`、`confluence` 或 `feishu`，**必须主动开口向 PM 索要对应凭证（`Bot ID`+`Secret` / `CONFLUENCE_PAT` / `FEISHU_APP_ID`+`FEISHU_APP_SECRET`）并由你直接代写入本地 `.env.local`**，严禁甩锅让 PM 手动改文件（跳过则启用 `local-obsidian` 兜底）。
2. **10 行极简收口、发《新手使用指南》& 禁启示例服务**：初始化落盘后，**严禁自动启动示例项目的 HTTP 服务，严禁汇报 PID、端口号、文件字节数或工程日志**；控制在 10 行以内交代清楚「本地放哪（`projects/<产品名>/` 与 `.env.local`）、远端何时传」，**将根目录交互手册 [guide.html](./guide.html)（及 [QUICKSTART.md](./QUICKSTART.md)）链接直接发给 PM**，并立即询问第一个需求。
3. **95% 纯黑白灰底图 + 5% 唯一琥珀橙 `#D97706` 工程标引色**：所有存量背景与业务组件（含主次按钮、弹窗、驳回/错误态）一律 **100% 纯黑白灰阶 `wt-*`**，严禁品牌蓝/成功绿/危险红等业务语义色（骨架微调仅限 `--skeleton-css` 圆角/间距/字号）；唯一工程标引色 **琥珀橙 `#D97706`** 仅限客观的 **① 本期改动增量（Delta：`SPEC_CARDS` 锚点组件与 `change: "new"|"modified"` 流程节点）** 与 **② 当前走查/点选焦点（Focus）**。
4. **标准流水线、左原型右说明（零套娃零重复）交付铁律与诚实状态码**：执行 `02/03/04` 前必读 `evals/taste-profile.md`；`flow.svg` 强制自上而下（Top-Down）纵向排版与 100% 正交折线（`change: "new"|"modified"` 节点占比 ≤ 75%），编译前后静默通过 `python3 scripts/preflight_check.py`；多人评审用 `python3 scripts/merge_feedback.py` 合并去重与冲突裁决；**定稿运行 `wiki_sync.py push/export` 自动截取全部 `variant_of` 多端纯灰阶原型图生成三列「序号 | 页面 | 需求说明（严禁套嵌 `原型|说明` 循环子表或内外重复）」的 `<项目名>-产品方案.docx`、`confluence-storage.xml` 与 `wiki-page.html`；若返回退出码 `3`（沙箱拦截截图）必须提权重跑，若返回退出码 `2`（远端未上传）严禁假报成功**；升级旧工作区运行 `python3 scripts/upgrade_openpm.py`。
