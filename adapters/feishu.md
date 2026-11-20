# 飞书文档适配器（`feishu`）

本适配器通过 `python3 scripts/wiki_sync.py` 将本地项目与飞书云文档 / 知识库（Feishu / Lark Docs）双向同步，交付标准「左图右文」对照表、`walkthrough.html.zip` 交互附件并维护 `_manifest.json` 防覆盖保护。

---

## 1. 配置与凭证隔离（`project-context.md` + `.env.local`）

### 1.1 `.env.local`（敏感凭证，由 AI Agent 主动索要并自动代写，严禁进 Git）

```dotenv
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_SPACE_ID=
FEISHU_FOLDER_TOKEN=
```

### 1.2 `project-context.md`（非敏感文档定位信息）

```yaml
wiki_adapter: feishu
wiki_config:
  space_or_parent: "<父目录或知识库节点 Token>"
  doc_id: ""   # 已存在文档 doc_token；首次发布留空，推送后记录至 _manifest.json
```

---

## 2. 「左图右文」交付结构与字段映射

| 本地产物 | 飞书文档目标载体 | 转换规则 |
| :--- | :--- | :--- |
| `title` | 文档标题（Document Title） | 直接映射 |
| 元数据 + `walkthrough.html.zip` | 顶部高亮块（Callout）+ 文件附件块 | 展示项目负责人、`DOC_VERSION_HASH`、更新时间，并插入 `walkthrough.html.zip` 附件块供评审人下载双击打开 |
| `screenshots/*.png` + `prd.md` | **「左图右文」三列表格 Block** | 按核心业务节点输出三列对照表：`序号 \| 页面纯灰阶截图（左，Image Block） \| 需求规则、状态与异常说明（右）` |
| `_manifest.json` | 本地 `projects/<project>/_manifest.json` | 记录 `adapter`、`remote_page_id`（`doc_token`）、`remote_version`（`revision_id`）、`pushed_at`、`walkthrough_hash`，推送前检查远端修订号防止多人冲突覆盖 |
| `review-feedback.md` / `.jsonl` | 本地回写输入 | 评审人在 `walkthrough.html` 内联 `@[组件名]` 批注并导出文件后，放回项目目录触发局部精准修订 |

---

## 3. 标准拉取与推送工作流

1. **拉取历史基线（`01-pull-wiki`）**：
   - 运行 `python3 scripts/wiki_sync.py pull projects/<project>`，拉取飞书文档 Block 内容转为结构化 Markdown 存入 `projects/<project>/history/prd-remote.md`，并生成 `projects/<project>/history/pull-diff.md`。
2. **图文对照交付（`06-push-wiki`）**：
   - 运行 `python3 scripts/wiki_sync.py push projects/<project>`：比对 `_manifest.json` 中的 `remote_version` 无冲突后，上传 `screenshots/*.png` 图片素材与 `walkthrough.html.zip` 文件块，更新「左图右文」文档正文并回写 `_manifest.json`。
   - **离线兜底**：当未配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 时，自动在 `projects/<project>/wiki-export/` 生成飞书粘贴友好的「左图右文」Markdown、`screenshots/` 与 `walkthrough.html.zip`。
