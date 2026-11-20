# Project Context · Acme AI Cloud (Spend Guardrails & Quota Approval)

## 1. Organization & Product Overview
- **Company / Team**: Acme AI Cloud · Platform Billing & FinOps Team
- **Domain**: Developer Cloud Infrastructure, LLM API Gateway & Workspace Cost Governance
- **Product Name**: Acme AI Cloud Console (`ai-workspace-guardrails`)
- **Target Personas**:
  - **Workspace Owners & FinOps Admins**: Configure monthly spend hard caps, auto-approval thresholds, and review high-tier quota requests.
  - **AI Engineers & Tech Leads**: Monitor project API key burn rates, receive instant webhook alerts, and request quota top-ups without prolonged downtime.
- **Supported Platforms**:
  - `web`: **Web Console** (`wide` 690px SaaS split shell with left navigation, KPI meters, and audit tables)
  - `app`: **Mobile App 375px** (`phone` 375px companion app for on-the-go push alerts, emergency key unlock, and 1-tap owner approvals)
- **Language**: English (`"lang": "en"`)
- **Delivery Mode**: `local-obsidian` (100% offline self-contained single-file `walkthrough.html`)

## 2. Design & Wireframe Standards
- **95% Pure Monochrome Wireframe + 5% Engineering Amber (`#D97706`)**:
  - All baseline layouts, buttons, tables, drawers, and mobile cards strictly use grayscale `wt-*` primitives (`#222222` / `#333333` / `#555555` / `#888888` / `#e0e0e0` / `#f7f7f7` / `#ffffff`).
  - Zero brand colors, zero semantic traffic-light colors, zero colorful emojis (ASCII/monochrome status badges only: `[ACTIVE]`, `[PAUSED]`, `[AUTO]`, `92%`).
  - Amber `#D97706` is reserved exclusively for v2.4 delta highlights (`change: "new" | "modified"` and `spec_cards` tethers) and active inspection/comment focus rings.
