# 组件落点与内联批注契约（Anchor Schema）

本规范定义了交互走查工作台（`walkthrough.html`）中**原型页面根容器与语义组件落点**的 HTML 属性契约、输入框内联 `@[组件名]` 胶囊点选与退格删除规则、统一的 `review-feedback.md` / `review-feedback.jsonl` 导出格式，以及**加载 + 导出双时机回查校验规则**，确保评审意见能够局部精准回写到 `prd.md` 与 `pages/<page_id>.html`。

---

## 1. 页面根容器与组件 HTML 属性契约

### 1.1 页面根容器统一格式

每个位于 `pages/<page_id>.html` 的原型页面片段，最外层根容器**必须**统一为 `<div>` 并同时声明 `class="page"`、`id`、`data-page` 与 `data-page-id`：

```html
<div class="page" id="p-apply-form" data-page="p-apply-form" data-page-id="p-apply-form">
  <!-- 页面内容：100% 纯黑白灰阶 wt-* 组件 -->
</div>
```

### 1.2 语义组件 `data-*` 属性契约

所有可交互控件或可被评审点选的业务区块，必须遵循以下属性契约：

| 属性名 | 必填性 | 命名与格式规范 | 示例 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `data-comp-id` | 语义组件必填 | **点分小写英文语义路径**：`<module>.<element>.<type>` | `form.submit.btn` | **同页唯一稳定语义 ID**。跨版本迭代只要语义未变，ID 必须保持稳定，严禁使用下划线杂糅前缀、随机哈希或动态下标。 |
| `data-comp-name` | 语义组件必填 | 简洁的人类可读中文名称 | `提交采购申请按钮` | 用于在备注输入框 `@[组件名]` 胶囊、评审列表与导出文件中展示。 |
| `data-comp-role` | 推荐填写 | 枚举：`control` \| `modal` \| `container` \| `text` \| `feedback` \| `nav` | `control` | 标识组件语义角色，辅助 AI 局部增量修订。 |
| `data-anchor` | 兼容旧版（可选） | 旧版锚点字符串 | `anchor-submit` | 仅作向后兼容降级查找；所有新生成原型必须输出标准点分小写 `data-comp-id`。 |

> **色彩边界约束（95% 纯黑白灰 + 5% 琥珀橙 `#D97706`）**：原型页面内的所有业务组件（含主按钮 `.wt-btn-primary`、弹窗 `.wt-modal`、驳回/错误提示 `.wt-alert`）一律保持 **100% 纯黑白灰阶 `wt-*`**，严禁引入品牌蓝、成功绿、危险红等业务语义色。全系统仅在**点选/走查当前焦点框（Focus）**与 **`SPEC_CARDS` 增量改点锚定框（Delta）**上使用唯一工程标引色 **琥珀橙 `#D97706`**。

### 示例 HTML 片段

```html
<div class="page" id="p-apply-form" data-page="p-apply-form" data-page-id="p-apply-form">
  <div class="wt-card" data-comp-id="form.main.card" data-comp-name="采购单填写卡片" data-comp-role="container">
    <div class="wt-field">
      <label class="wt-label">采购金额（元） *</label>
      <input class="wt-input" type="number" value="65000"
             data-comp-id="form.amount.input"
             data-comp-name="采购金额输入框"
             data-comp-role="control" />
    </div>
    <div class="wt-card-ft wt-between">
      <button class="wt-btn" data-comp-id="form.draft.btn" data-comp-name="保存草稿按钮" data-comp-role="control">保存草稿</button>
      <button class="wt-btn wt-btn-primary" data-comp-id="form.submit.btn" data-comp-name="提交采购申请按钮" data-comp-role="control">确认发起审批</button>
    </div>
  </div>
</div>
```

---

## 2. 内联 `@[组件名]` 胶囊点选与退格删除规则

当评审人在 `walkthrough.html` 中点击「+ 记备注」或「+ 新增」打开备注编辑器（`#memo-input`）时，自动进入捕获阶段语义组件点选模式：

1. **向上冒泡吸附语义组件**：点击或悬停当前激活页面（`.page.active`）内任意位置时，从事件目标向上查找最近的携带 `data-comp-id`（兼容 `data-anchor`）的元素，并以琥珀橙 `#D97706` 焦点框标示；禁止选中无语义 ID 的裸 DOM 节点。
2. **输入框内联插入 `@[组件名]` 胶囊**：点击组件后，直接在 `contenteditable` 输入框光标处内联插入原子胶囊 `<span class="memo-at-chip" contenteditable="false" data-page="..." data-comp-id="..." data-comp-name="..." data-fallback="...">@[组件名]</span>`，单条备注支持连续点选插入多个不同组件的 `@[组件名]` 胶囊（同页同 `comp_id` 自动去重）。
3. **原生退格一键删除**：由于胶囊设置 `contenteditable="false"` 作为不可拆分的原子内联节点，评审人在输入框内按 **`Backspace`（退格键）或 `Delete` 键**即可将整个 `@[组件名]` 胶囊干净删除，无需额外寻找微小的关闭按钮。
4. **未点选组件时的默认关联**：若输入框中未包含任何 `@[组件名]` 胶囊直接保存，则 `targets` 为空数组 `[]`，备注默认关联当前视图（`view: "flow" | "spec"`）、当前流程节点（`node`）与当前页面（`page`）。

---

## 3. 评审备注统一数据结构与导出格式（`.md` & `.jsonl`）

运行时内存、`spec.json` 中的 `memos`（`memoDef`）以及导出的 `review-feedback.jsonl` / `review-feedback.md` 严格共用同一套字段契约（不设粒度字段，也不使用顶层单组件字段，统一通过 `targets` 数组与 `text` 承载）：

### 3.1 标准字段定义（对齐 `spec-v2.schema.json#/memoDef`）

| 字段 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | **必填** | 批注唯一标识 | `"m_1732093800000"` |
| `version_hash` | `string` | **必填** | 页面全局常量 `DOC_VERSION_HASH` 的值，防止旧版批注错写到新版 | `"b-end-approval-flow-v2.0"` |
| `status` | `"valid" \| "invalid"` | **必填** | 落点实时回查状态：`valid`（有效）\| `invalid`（落点已失效） | `"valid"` |
| `view` | `"flow" \| "spec"` | **必填** | 批注发起时的工作台视图：`flow`（全局流程）\| `spec`（单页改点） | `"flow"` |
| `node` | `string` | **必填** | 当前关联的流程图节点 ID（无则 `""`） | `"F_FORM"` |
| `page` | `string` | **必填** | 当前所处的原型页面 ID（对应 `data-page-id`） | `"p-apply-form"` |
| `spec_id` | `string` | 可选 | 在 `spec` 视图下关联的改点卡 ID（如 `"SC_AMOUNT_THRESHOLD"`） | `"SC_AMOUNT_THRESHOLD"` |
| `vars` | `object` | **必填** | 批注时的全局/局部/分支状态变量快照 | `{"amount_tier":"gt_50k","audit_decision":"approve"}` |
| `targets` | `array` | **必填** | 结构化组件落点列表，每项为 `{ page, comp_id, comp_name, fallback_selector }`；未 `@` 组件时为 `[]` | `[{"page":"p-apply-form","comp_id":"form.submit.btn","comp_name":"提交采购申请按钮","fallback_selector":"[data-comp-id=\"form.submit.btn\"]"}]` |
| `text` | `string` | **必填** | 评审修改意见正文（含内联 `@[组件名]` 文本表达） | `"@[提交采购申请按钮] 文案统一改为「确认发起审批」。"` |
| `time` | `string` | **必填** | 记录时间字符串 | `"14:30"` |

### 3.2 标准 `review-feedback.jsonl` 导出格式（每行一条 JSON）

```jsonl
{"id":"m_1732093800001","version_hash":"b-end-approval-flow-v2.0","status":"valid","view":"flow","node":"F_FORM","page":"p-apply-form","vars":{"amount_tier":"gt_50k","audit_decision":"approve"},"targets":[{"page":"p-apply-form","comp_id":"form.amount.input","comp_name":"采购金额输入框","fallback_selector":"[data-comp-id=\"form.amount.input\"]"},{"page":"p-apply-form","comp_id":"form.submit.btn","comp_name":"提交采购申请按钮","fallback_selector":"[data-comp-id=\"form.submit.btn\"]"}],"text":"@[采购金额输入框] 提示补充小数点后两位说明，@[提交采购申请按钮] 文案改为「确认发起审批」。","time":"14:30"}
```

### 3.3 标准 `review-feedback.md` 导出模板

```markdown
---
project: b-end-approval-flow
version_hash: b-end-approval-flow-v2.0
exported_at: 2026-11-20T14:30:00Z
total_comments: 2
valid_count: 1
invalid_count: 1
---

# 评审反馈记录（Review Feedback）

## [FB-001] @[采购金额输入框] @[提交采购申请按钮]（valid）

- **id**: `m_1732093800001`
- **version_hash**: `b-end-approval-flow-v2.0`
- **status**: `valid`
- **view**: `flow`
- **node**: `F_FORM`
- **page**: `p-apply-form`
- **vars**: `{"amount_tier":"gt_50k","audit_decision":"approve"}`
- **targets**:
  - `p-apply-form` :: `form.amount.input`（采购金额输入框，`[data-comp-id="form.amount.input"]`）
  - `p-apply-form` :: `form.submit.btn`（提交采购申请按钮，`[data-comp-id="form.submit.btn"]`）
- **time**: `14:30`

**修改意见**：
@[采购金额输入框] 提示补充小数点后两位说明，@[提交采购申请按钮] 文案改为「确认发起审批」。

---

## [FB-002] @[旧版加急开关]（invalid - 落点已失效）

> [!WARNING] 落点已失效
> 该条批注的 `targets` 在当前原型 DOM 中未命中目标组件或 `version_hash` 与 `DOC_VERSION_HASH` 不匹配，严禁自动回写，请人工核对。

- **id**: `m_1732093800002`
- **version_hash**: `b-end-approval-flow-v1.0`
- **status**: `invalid`
- **view**: `spec`
- **node**: `F_FORM`
- **page**: `p-apply-form`
- **spec_id**: `SC_AMOUNT_THRESHOLD`
- **vars**: `{"amount_tier":"le_50k","audit_decision":"approve"}`
- **targets**:
  - `p-apply-form` :: `form.urgent.switch`（旧版加急开关，`[data-comp-id="form.urgent.switch"]`）
- **time**: `14:12`

**修改意见**：
@[旧版加急开关] 默认置为关闭。
```

---

## 4. 双时机回查规则（严禁静默失效）

为防止原型局部重绘或版本升级后，`localStorage` 或 `INITIAL_MEMOS` 中的历史批注变成「幽灵落点」，`walkthrough.html` 运行时必须在**两个关键时机**强制执行落点回查：

1. **时机一：HTML 加载与渲染时（On Load / On Render）**
   - 校验 `memo.version_hash` 是否与当前页面注入的 `DOC_VERSION_HASH` 一致，且 `document.getElementById(memo.page)` 为有效 `.page` 容器。
   - 遍历 `memo.targets`：对每个 `{ page, comp_id, fallback_selector }`，在目标页容器内查找 `[data-comp-id="<comp_id>"]`（降级兼容 `[data-anchor="<comp_id>"]` 与 `fallback_selector`）。
   - **命中判定**：`targets` 为 `[]` 时只要 `page` 存在且版本一致即为 `"valid"`；`targets` 非空时，必须**全部**目标均命中（`matchCount >= 1`）才标记 `"valid"`，任一落点未命中立即置为 `"invalid"` 并在抽屉条目展示「落点已失效」警示标签。

2. **时机二：复制或导出 `.md` / `.jsonl` 时（On Export）**
   - 点击「复制 MD」「导出 .md」「导出 .jsonl」前必须再次全量执行回查。
   - 若存在 `invalid` 批注，弹出导出守卫提示框提醒评审人「先处理失效备注」或「仅导出有效备注」；若包含失效条目导出，必须强制写入 `status: "invalid"` 并附带 `> [!WARNING] 落点已失效`，**严禁将失效落点静默当作 `valid` 导出**。
