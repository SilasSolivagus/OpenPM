# PRD · Acme AI Cloud Spend Guardrails & Quota Approval (v2.4)

| Field | Value |
| :--- | :--- |
| **Project ID** | `ai-workspace-guardrails` |
| **Version** | `v2.4` |
| **Platforms** | Web Console (`wide`) + Mobile Companion App (`phone` 375px) |
| **Owner** | Platform Billing & Developer Experience |
| **Status** | Ready for Design & Engineering Review |

---

## 1. Problem Statement & Goals

Engineering teams scaling LLM-powered workloads on **Acme AI Cloud** face two opposing failure modes under the legacy v2.3 flat billing model:
1. **Runaway Spend Shock**: Unbounded production loops or benchmark scripts burn thousands of dollars overnight before daily billing digests arrive.
2. **Approval Bottlenecks**: When a hard monthly cap is reached, every top-up—even a routine `$200` staging buffer—blocks on manual executive sign-off, stalling production deployments.

### v2.4 Core Objectives
- **Deterministic Hard-Cap Enforcement**: Allow Workspace Owners to configure a monthly workspace hard cap (default `$2,000`) with selectable runtime enforcement (`Auto-Pause Keys` at 100% vs `Webhook Alert Only`).
- **Tiered Auto-Approval Guardrail (`$500` Threshold)**: Top-up requests `<= $500` within an active cost center auto-approve and unlock paused keys in `< 2 seconds`; requests `> $500` route to the Workspace Owner Approval Console with live burn-rate context.
- **Dual-Platform Parity (Web + Mobile 375px)**: Enable developers and workspace owners to configure policies, request emergency quota top-ups, and approve/reject requests from both the Web Console and the Mobile Companion App.

---

## 2. End-to-End User Flow & Topology (`flow.svg`)

1. **`F_USAGE_DASH` (`unchanged`) — Usage & Spend Dashboard**: Displays real-time monthly spend (`$1,840 / $2,000`, `92%`), active API keys (`18`), pending quota requests (`2`), and per-key burn breakdown.
2. **`F_GUARDRAIL_POLICY` (`new`) — Guardrail Policy Drawer**: Workspace admin configures Monthly Hard Cap (`$2,000`), Tiered Auto-Approve Limit (`$500`), Hard-Cap Action (`Auto-Pause Keys` vs `Alert Only`), and Slack/Webhook notifications (`80%` & `100%`).
3. **`D_HARD_CAP` (`new`, Decision) — Spend Hits 100% Cap?**:
   - Branch `paused`: Spend hits `$2,000 / $2,000` (`100%`) with `Auto-Pause Keys` enabled → transitions to `F_KEY_PAUSED`.
   - Branch `within_cap`: Spend remains `< 100%` (proactive top-up) → transitions directly to `F_QUOTA_REQ`.
4. **`F_KEY_PAUSED` (`new`) — API Key Auto-Paused**: Displays deterministic `429 quota_hard_cap_exceeded` state banner for `sk-prod-...8f2a` with zero overage charges, offering one-click transition to `F_QUOTA_REQ`.
5. **`F_QUOTA_REQ` (`modified`) — Quota Top-Up Request**: Developer selects target project/key, enters extra budget (`+$300` vs `+$800`), picks cost center (`CC-402 Core AI`), and provides justification. Live UI feedback previews whether the request qualifies for instant auto-approval or requires Owner review.
6. **`D_THRESHOLD` (`new`, Decision) — Top-Up > $500 Limit?**:
   - Branch `le_500`: Requested top-up `<= $500` → instant approval & key unlock (`F_QUOTA_ACTIVE`).
   - Branch `gt_500`: Requested top-up `> $500` → routes to Workspace Owner review (`F_OWNER_REVIEW`).
7. **`F_OWNER_REVIEW` (`unchanged`) — Workspace Owner Approval Console**: Presents request summary (`+$800` → `$2,800` cap), 7-day key burn comparison table, and mandatory audit note field.
8. **`D_OWNER_DECISION` (`modified`, Decision) — Owner Approves?**:
   - Branch `approve`: Unlocks paused keys immediately and updates monthly hard cap (`F_QUOTA_ACTIVE`).
   - Branch `reject`: Preserves existing `$2,000` cap, records reviewer comment, and allows developer to revise & resubmit (`F_CAP_RETAINED` → `F_QUOTA_REQ`).
9. **`F_QUOTA_ACTIVE` (`unchanged`) — Quota Active & Keys Unlocked**: Confirms updated monthly cap (`$2,800`), restored `[ACTIVE]` key status, and immutable FinOps audit log entry.
10. **`F_CAP_RETAINED` (`unchanged`) — Cap Retained · Request Denied**: Retains current cap with reviewer feedback banner and `Revise Top-Up Request` loop back to `F_QUOTA_REQ`.

---

## 3. Core Specification Deltas (`SPEC_CARDS`)

- **`SC-01` (`p-guardrail-modal` :: `policy.threshold.input`) — Tiered Auto-Approve Threshold (`$500`)**: Introduces a configurable per-request auto-approval ceiling (`$0`–`$2,000`, default `$500`). Requests at or below this threshold bypass manual queue when cost center status is verified.
- **`SC-02` (`p-quota-request` :: `req.amount.input`) — Live Routing Preview on Top-Up Amount**: Dynamically evaluates requested top-up amount on input/preset selection, surfacing instant `[AUTO-APPROVE]` (`<= $500`) vs `[OWNER REVIEW]` (`> $500`) routing notice before submission.
- **`SC-03` (`p-key-paused` :: `paused.unlock.btn`) — Zero-Overage Hard-Cap Pause & Emergency Top-Up**: Pauses non-exempt API keys within 5s of reaching 100% hard cap (`HTTP 429 quota_hard_cap_exceeded`) and deep-links straight into pre-filled emergency top-up creation.
- **`SC-04` (`p-owner-approval` :: `approve.confirm.btn`) — Atomic Cap Update & Key Unpause with Audit Trail**: Approving a `> $500` request atomically increments the workspace monthly cap, restores paused API keys across edge gateways, and writes a signed FinOps audit log entry.

---

## 4. Non-Functional & Edge-Case Requirements

- **Gateway Propagation Latency**: Hard-cap auto-pause and post-approval key unpause must propagate to all regional inference gateways within `p99 <= 5,000ms`.
- **Idempotency**: Duplicate clicks on `Submit Request` or `Approve & Unlock` within a 60-second window are deduplicated by `request_id` (`REQ-2049`).
- **Audit Retention**: Every policy edit, auto-pause trigger, auto-approval, and manual owner decision records actor, timestamp, old/new cap, and cost center in `Audit Logs` for 365 days.
