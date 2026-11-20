---
name: 04-flow-canvas
description: 生成业务流程图 SVG，强制要求连线带 data-from/data-to、菱形判断节点带 data-node="D_*" 和 data-node-type="decision"（遵循 specs/flow-topology-spec.md）。
---

# 04 - Flow Canvas（业务流程图 SVG 生成）

## 目标
根据 `prd.md` 的主流程、状态流转与异常分支，生成结构严谨、拓扑可解析的业务流程图 SVG，供三栏交互演示页的全局流程画布加载与联动高亮。

## 输入
- `<project_dir>/prd.md`
- 规范参考：`specs/flow-topology-spec.md`
- `<project_dir>/prototype/` 中的页面 `data-page` 列表（确保节点与原型页绑定一致）

## 强制拓扑与属性规范
1. **节点分组与属性**：
   - 每个流程节点必须包裹在 `<g>` 元素中，且带有 `data-node="<NODE_ID>"`。
   - **菱形判断节点（Decision）**：
     - 凡包含菱形 `<polygon>` 的 `<g>`，**必须**同时满足：
       - `data-node="D_*"`（以 `D_` 开头，如 `D_RISK_CHECK`）
       - `data-node-type="decision"`
   - **普通步骤/页面节点**：使用 `data-node="N_*"` 或 `data-node="P_*"`，并标注关联的原型页 `page` ID。
2. **连线属性（强制）**：
   - 所有流程连线 `<polyline>` **必须**同时具备：
     - `data-from="<源节点ID>"`
     - `data-to="<目标节点ID>"`
   - 分支连线需配合 `<text>` 标签清晰标注条件（如 `命中风控`、`通过`、`取消/超时`）。
3. **布局与可读性**：
   - 采用规整的网格坐标（建议正交折线），避免连线穿越节点文字。
   - 主路径自上而下或自左向右清晰展开，异常分支向侧方引出并明确回流或终止节点。

## 输出
- `<project_dir>/flow/flow-canvas.svg`
- 节点元数据表（`NODES` JSON/JS 结构，包含每个节点的 `id`、`title`、`type`、`page`、`prdRef`、`changes`）。

## 验收标准
- 100% 的 `<polyline>` 带有有效的 `data-from` 和 `data-to`。
- 100% 的菱形 `<polygon>` 所在 `<g>` 带有 `data-node="D_*"` 和 `data-node-type="decision"`。
- `NODES` 中所有引用的 `page` 均能在原型 DOM 中找到对应页面。
