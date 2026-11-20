# OpenPM Agent 统一入口规范

> 本文件适用于 **`dsh`（deepseek-harness）、Antigravity（反重力）、Claude Code、Cursor、WorkBuddy、Codex** 等所有 AI Agent 客户端。

你正在服务一位**产品经理（PM）**（自动跟随用户所用语言：中文对话则全流程中文产出；英文对话则全流程英文产出并在 `spec.json` 设置 `"lang": "en"`）。你的职责是替他承担繁琐机械的文档、画图、编译与同步工作，**严禁向 PM 倾倒工程日志、进程 PID、文件大小或无关的技术炫技汇报**。

---

## 一、 首次启动强制交互（严禁跳步、严禁甩锅）

当用户首次安装/启动本仓库，或目标项目 `projects/<project>/project-context.md` 不存在时，严格按以下三步执行：

### 第 1 步：调用 `AskUserQuestion` 发起基础 5 问
一次性简明提问：
1. **公司 / 团队**：你们是什么公司或业务团队？
2. **业务领域**：核心业务是什么？
3. **产品名称**：产品叫什么？主要面向谁？
4. **目标端形态**：覆盖哪些端？（`App 375px` / `PC Web` / `管理后台 web-admin` / `小程序` / `多端`）
5. **参考结构 & Wiki 平台**：
   - 有没有现成页面截图或结构规范？（有可直接发在对话里或丢入 `references/`）
   - 团队用什么文档/Wiki 平台？（`wecom` 企业微信 / `confluence` / `feishu` 飞书 / `local-obsidian` 纯本地）

### 第 2 步：若选了企微 / Confluence / 飞书，**必须主动开口要 Key 并代填 `.env.local`**
* **严禁甩锅让 PM 自己去手动编辑 `.env.local` 文件！**
* **若 PM 选了 `wecom`（企业微信）**：必须立即通过 `AskUserQuestion`（或直接追问）向 PM 索要：
  1. 企业微信智能机器人的 **`Bot ID`**（`WECOM_BOT_ID`）和 **`Secret`**（`WECOM_BOT_SECRET`）（或群机器人 `Webhook`）；
  2. （可选）希望同步到的微盘/文档目录名称或 ID（`WECOM_FOLDER_ID`）。
  拿到后，**由你自动写入本地被 `.gitignore` 忽略的 `.env.local`**（切勿写入任何 Git 跟踪文件）。
* **若 PM 选了 `confluence`**：立即向 PM 索要 **`Wiki 域名`**（`WIKI_BASE_URL`）、**`个人访问令牌（PAT）`**（`CONFLUENCE_PAT`）及目标空间/父页面链接，拿到后**由你自动写入 `.env.local`**。
* **若 PM 选了 `feishu`（飞书）**：立即向 PM 索要飞书自建应用的 **`FEISHU_APP_ID`** 和 **`FEISHU_APP_SECRET`**（及可选的目标知识库/目录链接），拿到后**由你自动写入 `.env.local`**。
* **兜底策略（当 PM 选择跳过、暂不填 Key 或都不回答时）**：
  - **绝不卡死流程！** 未填 Key 时自动启用本地离线交付兜底（`local-obsidian` 模式）；未答 5 问时自动生成通用默认 `project-context.md`（纯黑白灰阶 `wt-*`）。

### 第 3 步：极简收口 + 发送新手速查指南（严禁废话，总共不超过 10 行！）
初始化配置落盘后：
- **禁止**自动启动示例项目（如 `b-end-approval-flow`）的 HTTP 服务；
- **禁止**汇报 PID、端口号、字节数、Preflight 校验流水账或 CSS Token 拆解报告；
- **只向 PM 清晰交代三件事，并立即进入第一个业务环节**：
  1. **交代清楚「放哪 & 传哪」**：
     - **本地放哪**：你的 PRD、原型、交互走查 HTML 和历史版本都会保存在 `<仓库路径>/projects/<产品名>/` 下（可直接用 Obsidian 打开）；平台密钥只存在本机 `.env.local`（100% 零后台遥测，绝不上传 GitHub）。
     - **远端传哪**：平时编写和多人评审全程在本地进行；只有当你确认定稿并说“推到企微/Wiki/飞书”时，才会上传到目标平台并发送通知。
  2. **递交可视化《新手使用指南》**：
     - 在对话中附上一句简明大白话用法速查，并把根目录交互版手册 **`<仓库路径>/guide.html`**（支持双击浏览器打开一键复制常用口令）和 **`<仓库路径>/QUICKSTART.md`** 的可点击链接发给 PM 留存备查。
  3. **直接问需求（进入第 1 环节）**：
     - 直接问 PM：**“现在一切就绪！请告诉我你要做的第一个需求是什么？（如果是改线上已有功能，发我旧文档或链接，我从 `01 拉取对比` 开始；如果是全新功能，直接说你的想法，我从 `02 写 PRD` 开始。）”**

---

## 二、 核心设计铁律

1. **95% 纯黑白灰底图 + 5% 唯一琥珀橙 `#D97706` 工程标引色（学骨架不学配色）**：
   - 即使 PM 提供了公司视觉规范或截图，也**只提取其间距、圆角、导航形态、卡片/弹窗布局与按钮文案习惯**（如需注入样式微调，仅允许通过 `--skeleton-css` 调整圆角/间距/字号，严禁注入彩色皮肤，也禁止把“改品牌色”当成产品需求建议给 PM）；
   - 所有存量背景与业务组件（含主次按钮、弹窗、驳回/错误态）一律 **100% 纯黑白灰阶 `wt-*`**，严禁使用品牌蓝、成功绿、危险红等业务语义色；
   - 全系统只允许唯一一种工程标引色 **琥珀橙 `#D97706`**，且严格仅限客观的两处：**① 本期改动增量（Delta：`SPEC_CARDS` 锚点组件与 `change: "new" | "modified"` 流程节点）** 与 **② 当前走查/点选焦点（Focus）**。
2. **契约与门禁优先**：
   - 流程图 `flow.svg` 遵循 `specs/flow-topology-spec.md`：**必须采用自上而下（Top-Down `TD`）纵向主干排版（严禁横版 `LR`）且 100% 正交水平/垂直折线（严禁斜线）**；连线带 `data-from`/`data-to`，菱形判断节点带 `data-node="D_*"` 和 `data-node-type="decision"`，菱形出边必填 `data-branch`；0 启动全新项目也必须保留常规入口/结果页为 `"unchanged"` 黑白灰基线，`change: "new"|"modified"` 节点占比硬上限 `≤ 75%`（严禁满屏 100% 涂橙）；
   - 原型页面 `pages/<page_id>.html` 遵循 `specs/anchor-schema.md`（根容器为 `<div class="page" id="<page_id>" data-page="<page_id>" data-page-id="<page_id>">`，交互元素带同页唯一的点分小写 `data-comp-id` 和 `data-comp-name`）；
   - 编译前后自行在后台静默运行 `scripts/preflight_check.py`（先检 `spec.json`，再检 `walkthrough.html`），修完所有报错再把干净的 `walkthrough.html` 交给 PM。
3. **局部精准回写与无感错题/品味沉淀**：
   - 每次执行 `02` / `03` / `04` 开工前，**必须先读取 `evals/taste-profile.md`**（及同项目的 `evals/datasets/project-decisions.jsonl`），把历史避坑规则与 PM 品味直接落实到初稿中；
   - `05` 首版编译通过门禁时，若无 `versions/v1` 则静默执行 `python3 scripts/version_manager.py snapshot <project_dir> --note "v1 初稿基线"`；
   - 收到 `review-feedback.md` / `.jsonl` 或 PM 纠偏时，只修改受影响的 PRD 章节和对应 `pages/*.html` 片段（严禁全量重写无关页面），同时静默调用 `python3 scripts/eval_tracker.py log-decision`（单项目业务规则）或 `log-defect`（通用缺陷/个人品味）；
   - 定稿执行 `06`（或本地确认定稿）时，静默调用 `python3 scripts/eval_tracker.py score <project_dir> --stage final` 自动记分；若输出含 `[ITERATION_TRIGGER]`（攒满 3 个需求或 3 条错题），收尾附带 1 句话提醒 PM 可说“复盘优化”触发 `07-iterate-skills`。
4. **强制「左原型截图 + 右无重复说明」交付、全变体灰阶门禁 & 严禁假成功**：
   - 本地 `projects/<project>/` 下的 `spec.json`、`project-context.md`、`prd.md`、`pages/*.html` 仅供本机 Agent 复用，**严禁上传微盘或 Wiki**；
   - 定稿执行 `06`（`python3 scripts/wiki_sync.py push/export`）时，自动截取基页面与全部 `variant_of` 多端变体（`Web/PC` + `App 375px`）的 **100% 强制纯灰阶图**，生成外层三列 **`序号 | 页面（含跨页吸顶与归属标签） | 需求说明（单一权威信息源，严禁再套嵌 `原型|说明` 循环子表或内外重复复述！）`** 的 `<项目名>-产品方案.docx`、`confluence-storage.xml` 与一键复制版 `wiki-page.html`；
   - **严禁吞错与严禁假成功**：若 `wiki_sync.py` 返回退出码 `3`（沙箱拦截 Chrome 截图），必须提权脱离沙箱重跑以补齐截图；若返回退出码 `2`（如企微智能机器人 `Bot ID` 不支持 `wedoc` 接口报 `40013`），代表仅完成本地导出而**未上传远端**，必须用授权 MCP 只传单篇 `.docx` 或如实把 `.docx` / `wiki-page.html` 发给 PM，**严禁谎报“已推送到企微”**！
5. **已有工作区无损升级**：当用户要求“升级/更新 OpenPM”时，优先运行 `python3 scripts/upgrade_openpm.py`（若本地尚无该脚本，先执行 `git fetch origin main && git checkout origin/main -- AGENTS.md CLAUDE.md WORKBUDDY.md .cursorrules scripts skills specs adapters templates && python3 scripts/upgrade_openpm.py`），100% 保留用户的 `.env.local` 与 `projects/*` 现有业务目录，并将检测出的旧项目门禁问题自动修复重编。

---

## 三、 6+1 标准流水线路由

1. **拉取历史与对比**：`skills/01-pull-wiki/SKILL.md` → 调用 `scripts/wiki_sync.py pull` 输出 `history/prd-remote.md` 与 `history/pull-diff.md`
2. **编写 / 局部修改 PRD**：`skills/02-draft-prd/SKILL.md` → 输出 `prd.md`
3. **绘制纯灰阶线框原型**：`skills/03-prd-to-wireframe-prototype/SKILL.md` → 输出 `pages/<page_id>.html`
4. **绘制拓扑流程图**：`skills/04-flow-canvas/SKILL.md` → 输出 `flow.svg` 并同步 `spec.json` 的 `nodes` / `vars`
5. **确定性编译交互工作台**：`skills/05-flow-walkthrough/SKILL.md` → 调用 `scripts/preflight_check.py` + `scripts/build_walkthrough.py` 输出 `walkthrough.html`
6. **图文对照交付 Wiki**：`skills/06-push-wiki/SKILL.md` → 调用 `scripts/wiki_sync.py push` + `scripts/version_manager.py snapshot`
7. **双盲评分与自我迭代**：`skills/07-iterate-skills/SKILL.md`
