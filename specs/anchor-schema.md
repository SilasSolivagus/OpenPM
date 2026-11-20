# 组件落点 Schema 规范（Anchor Schema）

本规范定义了三栏交互 HTML（`walkthrough.html`）中**原型组件落点**的 HTML 属性契约、语义组件点选吸附规则、支持单条备注 `@` 多组件的评审备注结构化导出格式（`review-feedback.md` / `review-feedback.jsonl`），以及**双时机回查校验规则**，确保评审意见能够精准回写到 PRD 与原型源码，杜绝错位或静默失效。

---

## 1. 原型 HTML 属性契约

所有在 `walkthrough.html` 中可被评审点选的原型元素、组件与页面容器，必须遵循以下 `data-*` 属性契约：

| 属性名 | 必填性 | 命名与格式规范 | 示例 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `data-comp-id` | 语义组件必填 | 点分小写英文语义路径：`<domain>.<module>.<element>` | `captcha.slider.track` | **全局稳定语义 ID**。跨版本迭代时只要语义未变，ID 必须保持不变，严禁使用随机哈希或动态索引。 |
| `data-comp-name` | 语义组件必填 | 简洁的中文/人类可读名称 | `滑块拖动条` | 用于在评审面板、导出反馈与 PRD 对照中展示给产品、研发与评审人。 |
| `data-comp-role` | 推荐必填 | 枚举值：`control` \| `modal` \| `container` \| `text` \| `feedback` \| `nav` | `control` | 标识组件在交互中的语义角色，辅助 AI 修改策略选择。 |
| `data-page-id` | 页面根容器必填 | 小写短横线或下划线标识 | `page_captcha_verify` | 标识整页根容器，供页面级关联与可达性检查使用。 |
| `data-anchor` | 兼容旧版（可选） | 同旧版锚点字符串 | `slider-track` | **向后兼容**：读取与回查时优先识别 `data-comp-id`，若不存在则降级读取 `data-anchor`；新生成原型必须输出 `data-comp-id`。 |

### `data-comp-role` 枚举说明

- `control`：可交互控件（按钮、输入框、滑块、开关、下拉菜单等）。
- `modal`：弹窗、抽屉、浮层、二次确认框。
- `container`：卡片、表单区块、列表项容器、布局分组。
- `text`：核心文案、规则说明、错误提示文案。
- `feedback`：Toast、Banner、Loading 状态、空状态提示。
- `nav`：Tab 栏、面包屑、步骤条、底部导航。

### 示例 HTML 片段

```html
<div data-page-id="page_captcha_verify" data-comp-id="captcha.page" data-comp-name="安全验证页" data-comp-role="container">
  <div class="captcha-modal" data-comp-id="captcha.slider.modal" data-comp-name="滑块验证弹窗" data-comp-role="modal">
    <p class="captcha-tip" data-comp-id="captcha.slider.hint" data-comp-name="拖动提示文案" data-comp-role="text">
      请拖动滑块完成拼图
    </p>
    <div class="slider-track" data-comp-id="captcha.slider.track" data-comp-name="滑块拖动条" data-comp-role="control">
      <button class="slider-thumb" data-comp-id="captcha.slider.thumb" data-comp-name="滑块按钮" data-comp-role="control">→</button>
    </div>
  </div>
</div>
```

---

## 2. 语义组件点选规则（无粒度概念）

评审者在 `walkthrough.html` 中打开「新增评审备注」进入点选模式后，点选器**不再区分**「此元素 / 所在组件 / 整页」粒度，而是统一吸附语义组件并支持多选：

1. **向上吸附语义组件**：点击或悬停原型区任意位置时，只从目标 DOM 节点向上冒泡查找最近的携带 `data-comp-id`（或兼容 `data-anchor`）且位于当前激活页面（`.page.active`）内的语义组件。
2. **禁止裸节点选中**：若未命中任何带语义 ID 的祖先节点，则不选中裸 `<span>` 或无语义容器，避免生成脆弱的 DOM 路径。
3. **未点选时的默认关联**：若评审人未点选任何语义组件直接提交备注，则 `targets` 为空数组 `[]`，默认关联当前流程图节点（`node`）与当前页面（`page`）。
4. **单条备注 `@` 多组件**：打开备注表单后，每次点击原型组件即去重追加一个 `@[组件名] ×` 胶囊到已选列表（支持点击 `×` 单个移除），高亮框展示最后一次点中的组件。

---

## 3. 评审备注结构化导出格式（`review-feedback.md`）

从 `walkthrough.html` 导出的评审文件必须为标准 Markdown，顶部包含 YAML Frontmatter 摘要，正文按条目结构化输出，每条批注**必须**包含以下全部字段：

### 必填字段定义

| 字段 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `version_hash` | `string` | 生成该 `walkthrough.html` 时的版本指纹（如 Git short SHA 或内容哈希），用于防止旧版页面批注错写到新版 PRD。 | `a1b2c3d4` |
| `status` | `enum` | 落点有效性状态：`valid`（有效）\| `invalid`（落点已失效）。 | `valid` |
| `view` | `string` | 批注发起时的视图上下文（如 `prototype` / `flow` / `prd`）。 | `prototype` |
| `node` | `string` | 当前关联或选中的流程图节点 ID（若无关联则为 `null` 或 `""`）。 | `D_captcha_check` |
| `page` | `string` | 当前所处的原型页面 ID（`data-page-id`）。 | `page_captcha_verify` |
| `vars` | `object` | 批注时的全局/局部状态变量快照（如 `platform`、`publish_scene`、`captcha_type`）。 | `{ "platform": "H5", "publish_scene": "comment", "captcha_type": "slider" }` |
| `targets` | `array` | 绑定的语义组件落点数组，每项为 `{ comp_id, comp_name, fallback_selector }`；空数组 `[]` 表示未指定具体组件，仅关联当前 `node` 与 `page`。 | `[{"comp_id": "captcha.slider.track", "comp_name": "滑块拖动条", "fallback_selector": "[data-comp-id=\"captcha.slider.track\"]"}]` |
| **修改意见正文** | `markdown` | 评审人填写的具体修改建议、预期行为或验收标准补充。 | 建议在弱网失败时保留滑块轨道并在下方展示重试按钮。 |

### 标准 `review-feedback.md` 导出模板

```markdown
---
project: captcha-upgrade
version_hash: a1b2c3d4
exported_at: 2026-11-20T14:30:00+08:00
total_comments: 2
valid_count: 1
invalid_count: 1
---

# 评审反馈记录（Review Feedback）

## [FB-001] @[滑块拖动条] @[安全验证确认按钮]（valid）

- **version_hash**: `a1b2c3d4`
- **status**: `valid`
- **view**: `prototype`
- **node**: `N_slider_verify`
- **page**: `page_captcha_verify`
- **vars**: `{"platform": "H5", "publish_scene": "comment", "captcha_type": "slider"}`
- **targets**: @[滑块拖动条] (`captcha.slider.track`)、@[安全验证确认按钮] (`captcha.confirm.btn`)

**修改意见**：
滑块拖动到最右侧但网络请求超时时，当前直接关闭弹窗会导致用户困惑。建议保留弹窗，在轨道下方展示「网络开小差了，请重试」文案并重置滑块位置。

---

## [FB-002] @[旧版短信入口]（invalid - 落点已失效）

> [!WARNING] 落点已失效
> 该条批注的 `targets` 中存在未命中任何元素的落点（命中数为 0），严禁作为有效落点自动修改。请人工核对是否因组件重命名或移除导致。

- **version_hash**: `a1b2c3d4`
- **status**: `invalid`
- **view**: `prototype`
- **node**: `D_verify_type`
- **page**: `page_captcha_verify`
- **vars**: `{"platform": "Web", "publish_scene": "login", "captcha_type": "sms"}`
- **targets**: @[旧版短信入口] (`captcha.sms.entry`)

**修改意见**：
希望把短信验证码倒计时从 60s 改成 30s。
```

---

## 4. 双时机回查规则（严禁静默失效）

为防止原型结构变更或变量切换后，历史缓存（如 `localStorage`）中的批注变成「幽灵落点」，`walkthrough.html` 运行时必须在**两个关键时机**执行落点回查（Re-validation）：

1. **时机一：HTML 加载时（On Load / On Render）**
   - 当 `walkthrough.html` 初始化或从本地存储恢复批注列表时，逐条校验其 `page` 容器存在，并遍历 `targets` 数组中的每一项，根据 `comp_id`（即 `[data-comp-id="<comp_id>"]`，兼容 `[data-anchor="<comp_id>"]`）和 `fallback_selector` 在当前 DOM（或对应页面/变量状态快照下）执行查询。
   - **命中判定**：若 `targets` 为空数组 `[]`，只需确认 `page` 存在即标记 `status = "valid"`；若 `targets` 非空，仅当**全部**落点均命中（`matchCount >= 1`）时标记 `status = "valid"`；只要 `targets` 中**任一**落点命中数为 `0`，立即将 `status` 置为 `"invalid"`，并在评审列表 UI 中**标红显示「落点已失效」**徽标。

2. **时机二：导出 `.md` / `.jsonl` 时（On Export）**
   - 在用户点击「导出 `review-feedback.md`」或「导出 `.jsonl`」触发导出逻辑前，必须强制再执行一次全量回查。
   - 若某条批注在导出时 `targets` 中任一落点命中数为 `0`：
     - 必须将该条目的 `status` 强制写入为 `invalid`；
     - 必须在导出的 Markdown 中显式标红/警告（如 `> [!WARNING] 落点已失效`）；
     - **严禁静默将命中为 0 的批注当成 `valid` 导出**，确保下游 AI Skill 读取 `review-feedback.md` / `review-feedback.jsonl` 时能够准确跳过或提示人工确认 `invalid` 条目。
