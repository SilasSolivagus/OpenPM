# PM 品味与高频避坑清单（Taste Profile）

> 本文件由 `07-iterate-skills` 与 `scripts/eval_tracker.py` 自动沉淀更新（升级 OpenPM 时受保护不会被覆盖）。
> **Agent 开工前铁律**：每次执行 `02-draft-prd`、`03-prd-to-wireframe-prototype`、`04-flow-canvas` 前，**必须先读取本文件**，将以下已固化规则直接落实到首版初稿中，严禁重犯！

---

## 已固化规则（Active Rules）

- **[SD-001 · 04-flow-canvas]** 所有包含 4 顶点菱形 `<polygon>` 的判断节点父容器 `<g>` 必须同时声明 `data-node="D_*"` 与 `data-node-type="decision"`，且其每条出边 `<polyline>` 必填与 `VARS` 对齐的 `data-branch`。
- **[SD-002 · 04-flow-canvas]** 工作台左侧流程栏为窄而高的纵向独立分栏，`flow.svg` 必须采用**自上而下（Top-Down `TD`）纵向主干排版**（`viewBox` 宽高比 `≤ 1.45`），严禁画成从左往右（`LR`）的扁长横图。
- **[SD-003 · 04-flow-canvas]** `flow.svg` 中所有 `<polyline>` 的每一段折线必须 **100% 水平或垂直正交（`x1==x2` 或 `y1==y2`）**，严禁使用斜线连接节点。
- **[SD-004 · 04-flow-canvas]** 严守「95% 纯黑白灰底图 + 5% 琥珀橙 `#D97706` 标重点」：即使是 0 启动的全新项目（`v1.0`），也必须将常规入口、基础列表、常规成功/兜底页保留为 `"change": "unchanged"` 黑白灰基线，仅将核心业务判断与关键改点标为 `"new"`（高亮节点占比硬上限 `≤ 75%`，建议 `30%~50%`），严禁满屏 100% 涂橙。
- **[SD-005 · 01-onboarding]** 首次初始化选定企微/Confluence/飞书后必须主动开口索要密钥并代写入 `.env.local`；初始化收口严禁超过 10 行，附上 `guide.html` 新手手册，严禁倾倒进程 PID、端口号或工程校验流水账。
- **[SD-006 · 06-push-wiki]** 远端交付严禁上传 `project-context.md`、`spec.json`、裸 `prd.md` 等本地工程文件；且当企微 `WECOM_BOT_ID` 不支持 `wedoc` 接口（`40013`）返回退出码 `2` 时，**严禁退回本地模拟同步假装推送成功**，必须使用授权 MCP 只传单篇 `.docx` 或如实引导 PM 导入 `.docx` / 一键复制 `wiki-page.html`。
- **[SD-007 · 06-push-wiki]** **严禁外层套内层循环表格与内容重复**：外层三列 `序号 | 页面 | 需求说明` 已经是唯一的左原型右说明结构，右栏严禁再套嵌 `原型 | 说明` 子表复述 `spec_cards` 或外层规则；每条业务规则全篇只出现唯一一次！
- **[SD-008 · 06-push-wiki]** **多端变体（`variant_of`）必须完整并入 + 强制 100% 纯灰阶 + 截图失败立即中止（退出码 `3`）**：同一页面的 `Web/PC` 与 `App 375px` 变体截图须同栏配对展示并强制 `filter: grayscale(100%)` 消除蓝色控件；沙箱拦截截图时立即报错退出，严禁静默产出缺图残次文档。
