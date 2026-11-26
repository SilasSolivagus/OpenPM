# OpenPM Quickstart / 新手速查指南

> Open **[guide.html](./guide.html)** in your browser for an interactive `EN / 中文` cheat sheet with one-click copy buttons.
> 双击打开 **[guide.html](./guide.html)** 可使用带 `EN / 中文` 切换和一键复制按钮的交互版速查页。

[**English**](#english-quickstart) | [**简体中文**](#中文速查指南)

---

<a id="english-quickstart"></a>

## English Quickstart

### 1. Common Prompts

1. **First-time setup**:
   > `Install and initialize https://github.com/SilasSolivagus/OpenPM`
2. **Draft a new feature**:
   > "Spec a new feature for `[describe your idea]` with a PRD and clickable wireframe."
3. **Update an existing live feature (`#D97706` amber delta)**:
   > "Here is our current Wiki doc/link. Add `[describe change]`; pull the diff first and mark only the changes in the wireframe."
4. **Merge team `@[Component]` comments**:
   > "I put the `.jsonl` review files from frontend, backend, and QA into the project folder. Merge them, check for conflicts, and update the spec."
5. **Export and push to Wiki / WeCom / Feishu**:
   > "This spec is final. Export the side-by-side wireframe and spec table and push it to Confluence / WeCom / Feishu."
6. **Update OpenPM scripts (keeps `.env.local` and `projects/`)**:
   > "Run `python3 scripts/upgrade_openpm.py` to update OpenPM without touching my `.env.local` or `projects/`, then re-verify `walkthrough.html`."

### 2. Async Team Review

1. Share `projects/<feature>/walkthrough.html` with engineers and QA (single offline file, opens in any browser).
2. Reviewers click **`+ Add Note`**, type their name and role (for example `Maya - Frontend`), click any wireframe control to insert `@[Component Name]`, and click **`Export .jsonl`**.
3. Click **`Import & Merge`** inside `walkthrough.html` or hand the `.jsonl` files to your agent. If two people leave conflicting requests on the same control, the agent asks you to decide before editing.

### 3. File Locations & Privacy

- **Specs & history**: `projects/<product>/` (works directly as an Obsidian folder; pull/push diff reports live in `history/pull-diff-report.html` and `wiki-export/push-diff-report.html`).
- **Tokens & keys**: Local `.env.local` only (git-ignored).
- **Network**: Runs on the Python 3 standard library with no analytics or background calls. Network requests only run when you pull from or push to your own Wiki.

---

<a id="中文速查指南"></a>

## 中文速查指南

### 一、 常用口令

1. **首次安装**：
   > `帮我安装并启动 https://github.com/SilasSolivagus/OpenPM`
2. **做全新功能**：
   > “我要做一个【填写新功能想法】需求，先帮我出 PRD 和可点选原型”
3. **改线上老功能（自动用 `#D97706` 琥珀橙标出本期改动）**：
   > “这是旧版文档/链接，这期要加【填写改动点】，先拉取对比再出新版原型”
4. **多人评审后合并改稿**：
   > “我把前端、后端和测试导出的 `.jsonl` 评审文件放进项目目录了，帮我合并检查冲突，确认后改稿”
5. **定稿导出 / 推到公司平台**：
   > “这版定稿了，帮我导出左图右文方案推到企业微信 / Confluence / 飞书”
6. **升级脚本（保留 `.env.local` 与现有 `projects/`）**：
   > “帮我运行 `python3 scripts/upgrade_openpm.py` 升级 OpenPM 并重新校验当前项目”

### 二、 多人评审怎么用

1. 把单文件 `projects/<需求名>/walkthrough.html` 发进群里，同事双击用浏览器就能打开；
2. 同事点右上角 **「+ 记备注」**，填上名字（如 `前端-王工`、`测试-小李`），点界面上的按钮或输入框插入 `@[组件名]` 写修改意见，最后点底部 **「导出 .jsonl」** 发回给你；
3. 你可以在自己的 `walkthrough.html` 里点 **「导入合并」** 汇总查看，也可以直接把 `.jsonl` 文件交给 AI：没冲突的直接改对应位置，同一控件意见打架的会先列出来让你拍板。

### 三、 存放位置与隐私

- **本地文件**：存在 `projects/<产品名>/` 下（可直接用 Obsidian 打开；拉取和推送时的行内高亮对比报告分别在 `history/pull-diff-report.html` 和 `wiki-export/push-diff-report.html`）。
- **平台密钥**：只存在本机 `.env.local`（已被 `.gitignore` 忽略，不会进 Git）。
- **无后台上报**：纯本地运行，没有任何统计请求；只有你主动执行拉取或推送时才会访问你配置的文档平台。
- **致谢**：源于 [@roxorlt](https://github.com/roxorlt) 与 [roxorlt/UEmaster](https://github.com/roxorlt/UEmaster)，由 [@SilasSolivagus](https://github.com/SilasSolivagus) 与 [@roxorlt](https://github.com/roxorlt) 共同维护。项目地址：https://github.com/SilasSolivagus/OpenPM
