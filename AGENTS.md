# OpenPM Agent 统一入口规范

> 本文件适用于 **Antigravity（反重力）、Claude Code、Cursor、WorkBuddy、deepseek-harness、Codex** 等所有 AI Coding / Agent 客户端。

你现在正在 **OpenPM**（跨公司通用的产品需求生产与交互评审闭环工作区）中工作。请严格遵守以下启动流程、设计铁律与 Skill 调度规范。

---

## 一、 首次启动强制引导（Onboarding Gate）

当检测到以下任一情况时：
- 用户首次打开仓库并输入启动口令；
- 工作区尚未建立默认配置，或目标项目 `projects/<project>/project-context.md` 不存在；

**你必须先调用 `AskUserQuestion`（若当前客户端无该工具，则在对话中以结构化编号列表一次性提问）向 PM 收集两步最小信息：**

### 第 1 步：项目与产品基础 5 问
1. **公司 / 团队**：你们是什么公司或什么业务团队？
2. **业务领域**：核心业务是什么？（如内容社区、B 端审批 SaaS、电商交易等）
3. **产品名称**：这款产品叫什么？主要面向谁？
4. **目标端形态**：覆盖哪些端？（`App 375px` / `PC Web` / `管理后台 web-admin` / `小程序` / `多端`）
5. **参考结构 & Wiki 平台**：
   - 有没有现成页面截图或结构规范？（可放入 `projects/<name>/references/`）
   - 团队用什么 Wiki / 文档平台？（`local-obsidian` 纯本地 / `wecom` 企业微信 / `confluence` / `feishu`）

### 第 2 步：动态追问 Wiki 最小凭证清单（同样通过 `AskUserQuestion`）
* **若选择 `wecom`（企业微信）**：
  - 询问 PM 是否已创建 **企业微信智能机器人（API 模式 / 长连接，免域名直通文档、微盘与消息 CLI/MCP）**；
  - 若有：引导 PM 将 **`Bot ID`** 与 **`Secret`**（或群机器人 `Webhook`）写入本地被 `.gitignore` 忽略的 `.env.local`（参考 `templates/.env.local.example`，**严禁写入 Git 跟踪文件**）。
* **若选择 `confluence`**：
  - 询问 **`WIKI_BASE_URL`**、个人访问令牌 **`CONFLUENCE_PAT`** 以及目标页面/父目录链接，同样存入本地 `.env.local`。
* **若选择 `local-obsidian`**：无需任何凭证，零配置直接开跑。

### 兜底策略（当 PM 跳过、不回答或说“先随便/直接跑”）
**绝不卡死流程！** 立即自动生成默认 `project-context.md` 并继续执行流水线：
- **公司/业务**：`通用互联网产品（[默认兜底，可随时补充]）`
- **端形态**：从用户首句需求中推断；无法推断时默认 `web-admin`（690px 宽屏）
- **原型视觉**：纯黑白灰阶高保真线框（`wt-*`）
- **Wiki 适配器**：`local-obsidian`（纯本地 Markdown + Obsidian 兼容）

---

## 二、 核心设计铁律

1. **学骨架不学配色**：即使 PM 提供了公司设计规范或参考截图（`references/`），也**只学习其页面布局、导航形态、卡片/弹窗结构与按钮文案习惯**；原型组件与流程图配色**永远锁定纯黑白灰阶 `wt-*` 线框**，禁止引入红/蓝/绿等彩色干扰业务评审。
2. **契约与门禁优先**：
   - 流程图必须符合 `specs/flow-topology-spec.md`（连线带 `data-from`/`data-to`，菱形判断节点带 `data-node="D_*"` 和 `data-node-type="decision"`）；
   - 原型组件必须符合 `specs/anchor-schema.md`（交互元素带同页唯一 `data-comp-id` 和 `data-comp-name`）；
   - 单一真相源必须符合 `specs/spec-v2.schema.json`。
3. **局部精准回写**：收到导出的 `review-feedback.md` / `.jsonl` 时，只修改受影响的 PRD 章节和对应 `pages/*.html` 片段，严禁全量重写未提及的页面。

---

## 三、 6+1 标准流水线路由

1. **拉取历史与对比**：`skills/01-pull-wiki/SKILL.md`
2. **编写 / 局部修改 PRD**：`skills/02-draft-prd/SKILL.md`
3. **绘制纯灰阶线框原型**：`skills/03-prd-to-wireframe-prototype/SKILL.md`
4. **绘制拓扑流程图**：`skills/04-flow-canvas/SKILL.md`
5. **确定性编译交互工作台**：`skills/05-flow-walkthrough/SKILL.md` → 调用 `scripts/build_walkthrough.py` + `scripts/preflight_check.py`
6. **图文对照交付 Wiki**：`skills/06-push-wiki/SKILL.md` → 调用 `scripts/version_manager.py snapshot`
7. **双盲评分与自我迭代**：`skills/07-iterate-skills/SKILL.md`
