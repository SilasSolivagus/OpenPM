# 动态社区内容发布器人机验证 PRD（v2.0）

- **项目标识**：`demo-captcha-publish`
- **版本**：`v2.0`
- **目标端**：动态社区（App 375px + Web 宽屏）
- **关联上下文**：`project-context.md`

---

## 1. 业务目标与非目标

- **业务目标**：在动态社区的原创动态发布器与转发动态发布器提交环节接入云端前置风控与三题型人机验证，对白名单/正常用户保持零打扰放行，对灰名单请求拉起安全验证并在通过后自动续传发布，对高频失败或黑名单账号精准拦截，全链路 100% 保留用户已编辑内容。
- **非目标（Out of Scope）**：
  - 点击社区底部「+ 发动态」、话题页参与按钮或动态卡片「转发」**进入发布器前**的交互保持线上现状，不前置拦截。
  - C 端不提供手动切换验证码题型入口（统一由云端随机下发）。

---

## 2. 核心业务流程与判断规则

### 2.1 提交前置校验与未登录衔接（`F_ENTRY` → `F_EDITOR` → `F_PUBLISH_CLICK` → `D_LOGGED_SUBMIT`）
1. **发布器同页内容校验（`F_EDITOR`）**：用户点击「发布」（Web 宽屏支持 `Ctrl/Cmd+Enter`）时，先执行原有内容非空及字数校验；空内容仅展示同页提示，不触发云端风控请求。
2. **登录状态判断（`D_LOGGED_SUBMIT`）**：
   - **已登录（`in`）**：直接携带当前登录账号（`uid`）请求发布前云端风控判断（`F_RECHECK`）。
   - **未登录（`out`）**：拉起社区登录浮层（`F_LOGIN`），底层发布器内容完整保留。
3. **登录结果分流（`D_LOGIN_OK`）**：
   - **登录成功（`ok`）**：仅由点击发布触发的登录，在成功后自动按当前登录账号（`uid`）衔接请求云端风控判断（`F_RECHECK`）；非发布动作触发的登录不发起发布风控判断。
   - **取消关闭（`cancel`）**：点击关闭或按 `ESC` 退出登录浮层，回到发布器保留已编辑内容，本次不发布且不弹 Toast（`F_CANCEL_LOGIN`）。
   - **尚未完成（`pending`）**：验证码输错或待确认时停留在原登录浮层，不计入人机验证失败次数（`F_LOGIN_PENDING`）。

### 2.2 云端风控分级处置（`F_RECHECK` → `D_SUBMIT`）
同一登录账号（`uid`）在 App 375px 与 Web 宽屏、原创动态与转发动态、三种验证题型间**跨端共用**当日失败计数与黑白名单状态。云端按以下优先级返回结果：
1. **直接放行（`allow`）**：命中白名单或正常低风险用户，静默进入原有发布提交流程（`F_SUBMIT`）。
2. **直接拒绝（`deny`）**：当前处于黑名单内，停留发布器保留全部已编辑内容，Toast 提示「发布失败，请稍后再试」（`F_BLOCK_PUBLISH`），不重复累加失败次数或拉黑天数。
3. **需要验证（`verify`）**：命中风控灰名单，保持发布器内容不丢失，弹出「安全验证」浮层（`F_VERIFY_PUBLISH`）。

### 2.3 三题型安全验证浮层与结果分流（`F_VERIFY_PUBLISH` → `D_VERIFY_PUBLISH`）
- **随机下发三种题型（`captcha_type`）**：云端从 **字符验证码（`chars`）**、**滑块拼图（`slider`）**、**九宫格图片（`grid`）** 中随机下发 1 种展示于验证主区域（`captcha.body`）。
- **换题规则**：点击「换一张」（`captcha.refresh.btn`）刷新同题型新题，不计入失败次数。
- **校验结果判断（`D_VERIFY_PUBLISH`）**：
  - **通过（`pass`）**：清零当日明确失败计数，关闭验证浮层并自动续传原有发布流程（`F_SUBMIT`）。
  - **明确失败（`fail`）**：进入当日失败上限 `N` 判断（`D_RETRY_ALLOWED`）。
  - **边界中断（`abort`）**：进入验证中断原因分流（`D_PUBLISH_ABORT`），所有边界中断均**不计入**当日失败次数。

### 2.4 明确失败重试与累计入黑解黑机制（`D_RETRY_ALLOWED`）
- **未达当日上限 `N`（`under_n` → `F_VERIFY_FAILED_PUBLISH`）**：
  - 保留安全验证浮层（不弹 Toast、无强制读秒冷却），原题目置灰锁定并隐藏「换一张」，展示「验证失败」状态提示与「重新验证」按钮（`captcha.retry.btn`）。
  - 用户点击「重新验证」（`F_RETRY`）时，重新向云端发起完整风控判断（回流 `F_RECHECK`）；若仍需验证则随机下发新题。
- **达到第 `N` 次失败（`reach_n` → `F_WAIT_BLACK`）**：
  - 立即将该账号加入风控黑名单，关闭安全验证浮层，停留发布器保留全部草稿内容，Toast 提示「发布失败，请稍后再试」。
  - **自然日解黑规则（参数 `M`）**：同一自然日内多次触发最多记 1 个拉黑自然日；历史累计拉黑自然日不足 `M` 天时，于北京时间次日 `00:00` 自动移出黑名单（不自动重发草稿）；达到第 `M` 个拉黑自然日起不再每日自动解黑。

### 2.5 验证中断与异常边界处理（`D_PUBLISH_ABORT`）
1. **主动取消（`cancel` → `F_CANCEL_PUBLISH`）**：点击「取消」、右上角关闭按钮或 Web 按 `ESC`，静默关闭浮层回到发布器，保留已编辑内容，不弹 Toast，不计失败。
2. **网络超时（`timeout` → `F_PUBLISH_NETWORK`）**：请求云端风控判断或提交校验答案超时，关闭验证浮层，停留发布器保留内容，Toast 提示「网络超时，请稍后重试」，不计失败。
3. **验证已过期（`expired` → `F_EXPIRE_PUBLISH`）**：浮层停留过久导致 `challenge_token` 过期时，保留安全验证浮层（复用失败重试布局，隐藏「换一张」），展示「验证已过期」与「重新验证」按钮（`captcha.retry.btn`），不计失败；点击「重新验证」同样回流 `F_RECHECK` 重新请求完整判断。

### 2.6 原有发布流程确认（`F_SUBMIT` → `D_PUBLISH_OK`）
- 风控放行或人机校验通过后，提交按钮置为「发布中...」防重状态（`p-editor-submitting`）。
- **确认成功（`yes` → `F_SUCCESS`）**：展示「发布成功 / 转发成功」提示并刷新社区动态流（`p-source-success`）。
- **发布未成功（`no` → `F_SUBMIT_FAILED`）**：若原有业务接口报错（如内容审核限制或原帖不可转发），停留发布器保留内容并沿用原有失败提示（`p-editor-publish-failed`），不增加人机验证失败计数。

---

## 3. 页面与核心组件锚点清单

| 基础页面 ID（`phone`） | Web 宽屏变体（`wide`） | 页面说明 | 核心组件锚点（`data-comp-id`） |
| :--- | :--- | :--- | :--- |
| `p-source-base` | `p-pc-source-base` | 动态社区信息流发布入口页 | `source.entry.publish_btn`、`source.repost.btn` |
| `p-editor-base` | `p-pc-editor-base` | 发布器（已填写内容有效态） | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input`、`editor.empty_state.btn` |
| `p-editor-empty` | `p-pc-editor-empty` | 发布器（空内容同页校验提示） | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input`、`common.toast` |
| `p-login-base` | `p-pc-login-base` | 未登录提交衔接登录浮层 | `login.sheet`、`login.phone.input`、`login.code.input`、`login.cancel.btn`、`login.pending.btn`、`login.submit.btn` |
| `p-login-pending` | `p-pc-login-pending` | 登录浮层（待完成确认态） | `login.sheet`、`login.cancel.btn`、`login.continue.btn` |
| `p-editor-verify` | `p-pc-editor-verify` | 安全验证浮层（三题型正常作答态） | `captcha.modal`、`captcha.body`、`captcha.chars.input`、`captcha.slider.thumb`、`captcha.grid.cell1`、`captcha.refresh.btn`、`captcha.cancel.btn`、`captcha.submit.btn` |
| `p-editor-verify-failed` | `p-pc-editor-verify-failed` | 安全验证浮层（未达 `N` 失败重试态） | `captcha.modal`、`captcha.body`、`captcha.cancel.btn`、`captcha.retry.btn` |
| `p-editor-expired` | `p-pc-editor-expired` | 安全验证浮层（题目已过期重试态） | `captcha.modal`、`captcha.body`、`captcha.cancel.btn`、`captcha.retry.btn` |
| `p-editor-blocked` | `p-pc-editor-blocked` | 黑名单拦截 / 第 `N` 次失败入黑页 | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input`、`common.toast` |
| `p-editor-cancelled` | `p-pc-editor-cancelled` | 主动取消登录/验证保留草稿页 | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input` |
| `p-editor-network` | `p-pc-editor-network` | 风控或验证网络超时提示页 | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input`、`common.toast` |
| `p-editor-submitting` | `p-pc-editor-submitting` | 原有发布接口提交中防重态 | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input` |
| `p-editor-publish-failed` | `p-pc-editor-publish-failed` | 原有发布流程失败保留草稿页 | `editor.cancel.btn`、`editor.publish.btn`、`editor.content.input`、`common.toast` |
| `p-source-success` | `p-pc-source-success` | 发布/转发成功返回动态流页 | `common.toast`、`source.new_post.btn` |
