# OpenPM Quickstart Manual / 新手速查指南

> Open **[guide.html](./guide.html)** in any browser for the interactive `EN / 中文` cheat sheet with one-click prompt copy buttons.
> 双击在浏览器打开 **[guide.html](./guide.html)** 即可使用支持右上角 `EN / 中文` 一键切换与口令复制的交互版速查手册。

[**English**](#english-quickstart) | [**简体中文**](#中文速查指南)

---

<a id="english-quickstart"></a>

## English Quickstart

### 1. Install + Daily Plain-Language Prompts

1. **First-time install (30 seconds)**:
   > `Install and initialize https://github.com/SilasSolivagus/OpenPM`
2. **Spec a 0-to-1 feature from scratch**:
   > "Spec a new feature for `[describe your feature idea]` with a structured PRD and clickable wireframe workbench."
3. **Modify an existing live feature (5% `#D97706` Amber engineering delta)**:
   > "Here is our current Wiki link/doc. This sprint we are adding `[describe change]`; pull the diff first and highlight only the delta in the wireframe."
4. **Merge multi-reviewer `@[Component]` feedback with conflict detection**:
   > "I dropped the `.jsonl` review files from frontend, backend, and QA into the project folder. Merge them, flag any conflicts, and apply surgical updates."
5. **Finalize and push side-by-side UI + spec table**:
   > "This spec is final. Package the side-by-side wireframe and spec table and push it to Confluence / WeCom / Feishu."
6. **1-line lossless upgrade (preserves `.env.local` and `projects/`)**:
   > "Run `python3 scripts/upgrade_openpm.py` to upgrade OpenPM without touching my `.env.local` or `projects/`, then re-verify the current `walkthrough.html`."

### 2. Multi-Reviewer Spec Crits

1. Send the single-file `projects/<feature>/walkthrough.html` to engineering and QA (zero dependencies, opens offline in any browser).
2. Each reviewer clicks **`+ Add Note`**, enters their name and role (for example `Maya - Frontend`), clicks any control on the wireframe to insert `@[Component Name]`, and clicks **`Export .jsonl`**.
3. Use **`Import & Merge`** in `walkthrough.html` or pass the `.jsonl` files directly to your agent. Conflicting comments on the same control are flagged for your decision before surgical write-back runs.

### 3. Local Storage & Zero-Telemetry Privacy

- **Local files**: Stored in `projects/<product>/` (open directly in Obsidian to browse PRDs and `versions/vN` snapshots).
- **Credentials**: Stored exclusively in local git-ignored `.env.local`.
- **Zero telemetry**: OpenPM runs on the Python 3 standard library with zero analytics or background network calls. Remote calls happen only when you pull or push a single native document on your configured Wiki platform.

---

<a id="中文速查指南"></a>

## 中文速查指南

### 一、 首次安装与日常最常用的 5 句大白话

1. **30 秒首次安装**：
   > `帮我安装并启动 https://github.com/SilasSolivagus/OpenPM`
2. **做全新功能（0 启动，Wiki 空的也能直接跑）**：
   > “我要做一个【填写你的新功能想法】需求，先帮我出结构化 PRD 和可点选交互原型”
3. **改线上已有老功能（自动标出 5% 琥珀橙 `#D97706` 研发增量）**：
   > “这是旧版文档/链接，本期要增加【填写改动点】，先拉取对比再出新版原型”
4. **多人评审后合并回写（自动检测多人改同一组件的冲突）**：
   > “我把前端、后端和测试导出的评审文件放进项目目录了，帮我合并检查有没有冲突，确认后精准回写”
5. **确认定稿推公司平台（企业微信原生在线文档 / Confluence / 飞书）**：
   > “这版定稿了，帮我打包左图右文对照表推到企业微信 / Confluence / 飞书”
6. **一句话无损升级最新版 OpenPM（保留 `.env.local` 与现有 `projects/`）**：
   > “帮我运行 `python3 scripts/upgrade_openpm.py` 无损升级 OpenPM 并重编当前项目”

### 二、 多人评审怎么配合？

1. 把生成的单文件 `projects/<需求名>/walkthrough.html` 发进项目群（零外部依赖，任何人双击即开）；
2. 每位同事点右上角 **「+ 记备注」** -> 在顶部填上自己的署名（如 `前端-王工`、`测试-小李`）-> 点界面控件插入 `@[组件名]` 写修改建议 -> 点底部 **「导出 .jsonl」** 发回给你；
3. 你可以在自己的 `walkthrough.html` 里点 **「导入合并」** 一键查看所有人的汇总批注（同组件多方意见会自动标橙提醒），也可以把这几份文件直接发给 AI：无冲突项自动精准修改，有冲突项 AI 会先列出来请你拍板。

### 三、 存储位置与隐私安全（100% 零遥测承诺）

- **本地文档放哪**：`projects/<产品名>/`（可直接用 Obsidian 打开管理全部版本与快照）。
- **密钥放哪**：仅保存在本机 `.env.local`（已被 `.gitignore` 严格隔离，绝不上传 GitHub）。
- **100% 零后台遥测**：OpenPM 纯本地离线运行，不包含任何后台统计上报或外部追踪请求；只有当你明确要求拉取或推送公司平台时，才会更新目标平台的单篇可读在线文档。
- **支持开源共建**：源于 [@roxorlt](https://github.com/roxorlt) 与 [roxorlt/UEmaster](https://github.com/roxorlt/UEmaster) 灵感创意，由 [@SilasSolivagus](https://github.com/SilasSolivagus) 与 [@roxorlt](https://github.com/roxorlt) 共建。欢迎前往 GitHub 点亮 Star：https://github.com/SilasSolivagus/OpenPM
