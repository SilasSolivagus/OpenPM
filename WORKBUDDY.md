# WorkBuddy 入口规范

请完整阅读并严格遵守根目录 [AGENTS.md](./AGENTS.md) 中的全部规范，核心执行铁律摘要如下：

1. **首次启动 5 问 & 必须代写 `.env.local`**：当目标项目缺少 `project-context.md` 时，先执行基础 5 问；若 PM 选择 `wecom`、`confluence` 或 `feishu`，**必须主动向 PM 索要对应密钥（企微 `Bot ID`+`Secret` / Confluence `PAT` / 飞书 `FEISHU_APP_ID`+`FEISHU_APP_SECRET`）并由你自动代写入 `.env.local`**，严禁让 PM 自己手动编辑 `.env.local`（不填则自动回退 `local-obsidian` 兜底）。
2. **10 行极简收口、发《新手使用指南》& 禁启示例服务**：配置完成后，**严禁自动启动示例项目本地服务，严禁输出 PID、端口号、字节数或校验流水账**；控制在 10 行内说明「本地存哪、远端何时传」、**把根目录交互手册 [guide.html](./guide.html)（及 [QUICKSTART.md](./QUICKSTART.md)）链接发给 PM**，并直接询问第一个需求。
3. **95% 纯黑白灰底图 + 5% 唯一琥珀橙 `#D97706` 工程标引色**：所有存量背景与业务组件（含主次按钮、弹窗、驳回/错误态）一律 **100% 纯黑白灰阶 `wt-*`**，严禁品牌蓝/成功绿/危险红等业务语义色（仅允许 `--skeleton-css` 微调圆角/间距/字号）；全系统唯一工程标引色 **琥珀橙 `#D97706`** 仅用于 **① 本期改动增量（Delta：`SPEC_CARDS` 锚点组件与 `change: "new"|"modified"` 流程节点）** 与 **② 当前走查/点选焦点（Focus）**。
4. **标准流水线、远端单篇原生文档铁律、错题自进化与无损升级**：开工前必读 `evals/taste-profile.md`；严格遵循 `skills/01-*` ~ `07-*` 与 `scripts/preflight_check.py` 双阶段门禁（`flow.svg` 强制自上而下纵向排版与 100% 正交折线，高亮节点占比 ≤ 75%）；**定稿推企微（`wecom`）只允许创建/更新 1 篇原生企微在线文档（WeDoc），严禁把 `.xml`/`.md`/`.html`/`.zip` 等本地工程文件上传微盘**；改稿与定稿自动运行 `scripts/eval_tracker.py` 记分与沉淀品味；升级旧工作区统一运行 `python3 scripts/upgrade_openpm.py`。
