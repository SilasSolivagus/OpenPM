# OpenPM

> **开源、跨公司、可落地的 AI 产品需求生产与交互评审闭环工作区**  
> *From Wiki & Ideas to Living Specs, Wireframes, Flowcharts, and Click-to-Comment Walkthroughs.*

OpenPM 不是一组零散的写 PRD 提示词，而是一套**「契约驱动 + 确定性编译 + 所见即所得点选评审 + 局部精准回写」**的产品经理标准工作区。  
兼容 **Antigravity（反重力）、Claude Code、Cursor、WorkBuddy、deepseek-harness、Codex** 等主流 AI Agent 客户端，同时支持用 **Obsidian** 直接打开管理。

---

## ⚡ 30 秒一键启动（复制粘贴即可用）

### 1. 克隆仓库并在你的 AI 工具中打开
```bash
git clone https://github.com/SilasSolivagus/OpenPM.git && cd OpenPM
```

### 2. 复制下面这句话，直接发给你的 AI Agent
```text
请先阅读本仓库根目录的 AGENTS.md，帮我初始化 OpenPM 工作区并开始一个新需求。
```

> Agent 会通过 `AskUserQuestion` 一次性向你确认 **5 项基础信息**（公司/业务/产品/端形态/参考与 Wiki）及最小 Wiki 凭证（支持 **企业微信智能机器人 API 长连接**、**Confluence PAT** 或 **纯本地 Obsidian**）。即使你直接跳过不回答，也会自动启用纯黑白灰阶 `wt-*` 线框 + 纯本地模式兜底开跑，绝不卡死。

---

## 核心闭环架构

```mermaid
flowchart LR
  W1["01 Pull Wiki<br/>历史拉取与对比"] --> P["02 Draft PRD<br/>结构化需求文档"]
  P --> W2["03 Wireframe<br/>纯灰阶骨架原型"]
  P --> F["04 Flow Canvas<br/>拓扑流程图 SVG"]
  W2 --> C["05 Build Walkthrough<br/>确定性编译单文件 HTML"]
  F --> C
  C --> G{"Preflight Gate<br/>静态门禁校验"}
  G -- 通过 --> R["团队离线评审<br/>输入框内联 @组件 批注"]
  R -- 导出 .md / .jsonl --> P
  P --> V["Version Manager<br/>快照 · Diff · 回滚"]
  V --> W3["06 Push Wiki<br/>图文对照表 + 交互附件交付"]
  R -. 双盲评分 & Taste 沉淀 .-> I["07 Iterate Skills<br/>回归测试 & 自我迭代"]
```

---

## 核心设计原则

- **学骨架不学配色（永远纯黑白灰阶 `wt-*`）**：即便提供了公司参考截图或视觉规范，也**只学习页面布局、导航形态、卡片/弹窗结构与文案习惯**；原型与流程图配色始终锁定纯黑白灰阶，让团队评审聚焦业务逻辑而非颜色争议。
- **极简内联 `@组件` 评审**：点击「+ 记备注」自动激活原型点选；点击组件直接在输入框内插入可用退格键删除的 `@[组件名]` 胶囊，一条备注支持 `@` 多个组件；加载与导出双时机回查落点，失效当场标红阻断。
- **跨公司 Wiki 适配器 & `.env.local` 安全隔离**：
  - **企业微信**：支持智能机器人 API 模式（`Bot ID` + `Secret`，长连接免域名直通文档/微盘/消息）及群机器人 Webhook；
  - **Confluence**：支持 `PAT` 个人访问令牌自动上传截图、`walkthrough.html.zip` 与「左图右文」对照表，并回写 `_manifest.json` 防误覆盖；
  - **纯本地 / Obsidian**：零配置即开即用；所有密钥统一存入 `.env.local`（已被 `.gitignore` 隔离）。
- **双盲 A/B 评分与 Taste 沉淀**：`07-iterate-skills` 通过历史样本双盲对比、独立裁判打分及「上 Wiki 前手动改写率」度量，越用越懂你的业务与品味。

---

## 内置示例（双击即可在浏览器体验）

- **B 端企业管理后台（纯中立 `wt-*` 线框）**：`projects/b-end-approval-flow/walkthrough.html`
- **C 端多状态强交互（App/PC 双端 + 随机题型）**：`templates/walkthrough-sample-v2.html`

---

## 常用命令行工具（通常由 Agent 自动调用）

```bash
# 1. 编译单文件三栏交互 HTML
python3 scripts/build_walkthrough.py \
  --spec projects/b-end-approval-flow/spec.json \
  --svg projects/b-end-approval-flow/flow.svg \
  --pages-dir projects/b-end-approval-flow/pages \
  --out projects/b-end-approval-flow/walkthrough.html

# 2. 交付前静态门禁校验（支持 spec.json 与 walkthrough.html）
python3 scripts/preflight_check.py projects/b-end-approval-flow/spec.json
python3 scripts/preflight_check.py projects/b-end-approval-flow/walkthrough.html

# 3. 版本快照、Diff 对照与回滚
python3 scripts/version_manager.py snapshot projects/b-end-approval-flow --note "评审后局部更新"
python3 scripts/version_manager.py diff projects/b-end-approval-flow v1 v2
python3 scripts/version_manager.py rollback projects/b-end-approval-flow v1
```

---

## 致谢

本项目在流程图拓扑联动与 `flowspec/1`、`walkmap/1` 契约思想上深受 [roxorlt/UEmaster](https://github.com/roxorlt/UEmaster) 启发，并在其基础上补全了 `spec-v2` 真相源、菱形可寻址、内联 `@组件` 点选回写、门禁校验、多端入口引导与跨公司可插拔工作区闭环。
