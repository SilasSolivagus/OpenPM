#!/usr/bin/env python3
"""Deterministic single-file walkthrough.html compiler for spec-v2 projects.

Usage:
    python3 scripts/build_walkthrough.py \
        --spec <spec.json> \
        --svg <flow.svg> \
        --pages-dir <pages_dir> \
        --out <walkthrough.html>

Zero external dependencies (Python 3 standard library only).
Zero business-specific hardcoding; emits neutral wt-* wireframe CSS.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SEL_RING_SVG = (
    '<rect id="sel-ring" fill="none" stroke="#111111" stroke-width="2.5" '
    'stroke-dasharray="6 4" rx="8" visibility="hidden" pointer-events="none"/>'
)


def _json_for_script(obj: Any) -> str:
    """Serialize JSON safely for embedding inside HTML <script> tags."""
    raw = json.dumps(obj, ensure_ascii=False)
    return raw.replace("</", "<\\/")


def _load_spec(spec_path: Path) -> Dict[str, Any]:
    """Load and perform basic structural validation on spec.json (spec-v2)."""
    if not spec_path.is_file():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("spec.json root must be a JSON object")
    if data.get("version") != "spec-v2":
        raise ValueError(f"Unsupported spec version: {data.get('version')!r} (expected 'spec-v2')")
    for key in ("meta", "vars", "nodes", "pages"):
        if key not in data:
            raise ValueError(f"spec.json missing required top-level field: '{key}'")
    if not isinstance(data["nodes"], dict) or not data["nodes"]:
        raise ValueError("spec.json 'nodes' must be a non-empty object")
    if not isinstance(data["pages"], dict) or not data["pages"]:
        raise ValueError("spec.json 'pages' must be a non-empty object")
    return data


def _load_svg(svg_path: Path) -> str:
    """Load flow.svg and ensure selection ring element is present."""
    if not svg_path.is_file():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    svg_text = svg_path.read_text(encoding="utf-8").strip()
    if "<svg" not in svg_text or "</svg>" not in svg_text:
        raise ValueError(f"Invalid SVG content in {svg_path}: missing <svg>...</svg>")
    if 'id="sel-ring"' not in svg_text and "id='sel-ring'" not in svg_text:
        idx = svg_text.rfind("</svg>")
        svg_text = svg_text[:idx] + "\n" + SEL_RING_SVG + "\n" + svg_text[idx:]
    return svg_text


def _apply_variant_overrides(fragment_html: str, page_def: Dict[str, Any]) -> str:
    """Apply deterministic variant overrides (copy, layout) to inherited page HTML."""
    overrides = page_def.get("overrides")
    if not isinstance(overrides, dict):
        return fragment_html

    copy_map = overrides.get("copy")
    if isinstance(copy_map, dict):
        for comp_id, new_text in copy_map.items():
            escaped_cid = re.escape(str(comp_id))
            pattern = re.compile(
                rf'(<([a-zA-Z0-9]+)[^>]*\bdata-comp-id=["\']{escaped_cid}["\'][^>]*>)(.*?)(</\2>)',
                re.DOTALL,
            )
            replacement_text = html.escape(str(new_text))
            fragment_html = pattern.sub(
                lambda m: f"{m.group(1)}{replacement_text}{m.group(4)}",
                fragment_html,
            )

    layout = overrides.get("layout")
    if isinstance(layout, str) and layout.strip():
        safe_layout = html.escape(layout.strip(), quote=True)
        fragment_html = f'<div class="wt-layout-{safe_layout}">{fragment_html}</div>'

    return fragment_html


def _resolve_page_fragment(
    page_id: str,
    pages: Dict[str, Any],
    pages_dir: Path,
) -> str:
    """Load <page_id>.html from pages_dir, falling back to variant_of chain if needed."""
    direct_path = pages_dir / f"{page_id}.html"
    if direct_path.is_file():
        return direct_path.read_text(encoding="utf-8").strip()

    visited = {page_id}
    cur_id = page_id
    chain: List[Dict[str, Any]] = []
    while True:
        page_def = pages.get(cur_id, {})
        chain.append(page_def)
        base_id = page_def.get("variant_of")
        if not base_id:
            break
        if base_id in visited:
            raise ValueError(f"Circular variant_of reference detected at '{base_id}'")
        visited.add(base_id)
        base_path = pages_dir / f"{base_id}.html"
        if base_path.is_file():
            content = base_path.read_text(encoding="utf-8").strip()
            for layer in reversed(chain):
                content = _apply_variant_overrides(content, layer)
            return content
        cur_id = base_id

    raise FileNotFoundError(
        f"Page fragment not found for '{page_id}': expected {direct_path}"
    )


def _wrap_page_fragment(page_id: str, fragment_html: str) -> str:
    """Wrap or normalize a page fragment with standard .page, id, data-page, data-page-id."""
    esc_id = html.escape(page_id, quote=True)
    open_match = re.match(
        r'^\s*<div\b([^>]*)>(.*)</div>\s*$',
        fragment_html,
        re.DOTALL | re.IGNORECASE,
    )
    if open_match:
        attrs_str = open_match.group(1)
        id_match = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs_str)
        if id_match and id_match.group(1) == page_id:
            # Normalize class, data-page, data-page-id on existing outer container
            new_attrs = attrs_str
            cls_match = re.search(r'\bclass\s*=\s*["\']([^"\']*)["\']', new_attrs)
            if cls_match:
                classes = cls_match.group(1).split()
                if "page" not in classes:
                    classes.insert(0, "page")
                new_attrs = (
                    new_attrs[:cls_match.start()]
                    + f'class="{" ".join(classes)}"'
                    + new_attrs[cls_match.end():]
                )
            else:
                new_attrs += ' class="page"'
            if "data-page=" not in new_attrs:
                new_attrs += f' data-page="{esc_id}"'
            if "data-page-id=" not in new_attrs:
                new_attrs += f' data-page-id="{esc_id}"'
            return f"<div{new_attrs}>{open_match.group(2)}</div>"

    return (
        f'<div class="page" id="{esc_id}" data-page="{esc_id}" data-page-id="{esc_id}">'
        f"{fragment_html}"
        f"</div>"
    )


def _build_pages_html(
    pages: Dict[str, Any],
    pages_dir: Path,
) -> Tuple[str, str, Dict[str, str]]:
    """Build HTML strings for phone and wide device frames plus PAGE_FRAME map."""
    phone_chunks: List[str] = []
    wide_chunks: List[str] = []
    page_frame: Dict[str, str] = {}

    for page_id, page_def in pages.items():
        frame = page_def.get("frame", "phone")
        if frame not in ("phone", "wide"):
            frame = "phone"
        page_frame[page_id] = frame
        fragment = _resolve_page_fragment(page_id, pages, pages_dir)
        wrapped = _wrap_page_fragment(page_id, fragment)
        if frame == "wide":
            wide_chunks.append(wrapped)
        else:
            phone_chunks.append(wrapped)

    return "\n".join(phone_chunks), "\n".join(wide_chunks), page_frame


WB_CSS = """\
:root {
  --wt-bg: #f7f7f7; --wt-white: #ffffff;
  --wt-border: #c0c0c0; --wt-border-light: #e0e0e0;
  --wt-text: #333333; --wt-dim: #888888; --wt-light: #aaaaaa;
  --wt-fill: #e8e8e8; --wt-fill-dark: #d0d0d0; --wt-accent: #555555;
  --wt-pick: #2563eb; --wt-danger: #dc2626;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  height: 100%; background: var(--wt-bg); color: var(--wt-text);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px; line-height: 1.5; overflow: hidden;
}
button, input, textarea, select { font: inherit; color: inherit; }
button {
  cursor: pointer; border: 1px solid var(--wt-border); background: var(--wt-white);
  color: var(--wt-text); border-radius: 5px; padding: 5px 10px; font-size: 12px;
}
button:hover:not(:disabled) { background: var(--wt-fill); }
button:disabled { opacity: 0.45; cursor: default; }
button.primary, button.primary:hover:not(:disabled) {
  background: var(--wt-accent); color: var(--wt-white); border-color: var(--wt-accent);
}
.hidden { display: none !important; }

/* Workbench Topbar */
.wb-topbar {
  height: 50px; background: var(--wt-white); border-bottom: 1px solid var(--wt-border);
  display: flex; align-items: center; padding: 0 16px; gap: 12px;
  position: relative; z-index: 200; user-select: none;
}
.fp-title { font-size: 15px; font-weight: 700; white-space: nowrap; }
.seg-group {
  display: inline-flex; align-items: center; background: var(--wt-bg);
  border: 1px solid var(--wt-border); border-radius: 6px; padding: 2px; gap: 2px; flex-shrink: 0;
}
.seg-btn {
  border: none; background: transparent; padding: 4px 10px; border-radius: 4px;
  font-size: 12px; color: var(--wt-dim); white-space: nowrap;
}
.seg-btn:hover:not(.active) { background: var(--wt-fill); color: var(--wt-text); }
.seg-btn.active, .seg-btn.active:hover {
  background: var(--wt-accent); color: var(--wt-white); font-weight: 600;
}
.wb-global-vars { display: inline-flex; align-items: center; gap: 10px; flex-shrink: 0; }
.wb-gvar { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--wt-dim); white-space: nowrap; }
.topbar-spacer { flex: 1; min-width: 8px; }
#flow-node-ref {
  font-size: 12px; color: var(--wt-dim); max-width: 240px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fp-bar {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
  color: var(--wt-dim); flex-shrink: 0; white-space: nowrap;
}
.zb {
  padding: 3px 9px; border: 1px solid var(--wt-border); border-radius: 4px;
  cursor: pointer; background: var(--wt-white); user-select: none;
  color: var(--wt-text); white-space: nowrap;
}
.zb:hover { background: var(--wt-fill); }
.zv { min-width: 42px; text-align: center; }
.memo-toggle { white-space: nowrap; flex-shrink: 0; }
.memo-toggle.active, .memo-toggle.active:hover {
  background: var(--wt-accent); color: var(--wt-white); border-color: var(--wt-accent);
}

/* Workbench Stage & Flow Canvas */
.wb-stage { position: relative; width: 100vw; height: calc(100vh - 50px); display: flex; overflow: hidden; }
.flow-panel { flex: 1; min-width: 0; height: 100%; position: relative; overflow: hidden; display: flex; flex-direction: column; }
.flow-panel.fs .inspector-drawer { display: none !important; }
.flow-svg {
  flex: 1; width: 100%; height: 100%; overflow: hidden; background: var(--wt-bg);
  cursor: grab; touch-action: none; user-select: none; position: relative;
}
.flow-svg:active { cursor: grabbing; }
.flow-canvas-inner { transform-origin: 0 0; will-change: transform; }
.flow-canvas-inner.smooth { transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1); }
.flow-svg svg {
  width: 100%; height: auto; display: block; background: var(--wt-white);
  border: 1px solid var(--wt-border-light); border-radius: 8px;
}
.flow-svg g[data-node] { cursor: pointer; }
.flow-svg g[data-node]:hover rect,
.flow-svg g[data-node]:hover polygon { stroke: #333333; stroke-width: 2.5px; }
.flow-svg polyline.branch-active { stroke: #111111 !important; stroke-width: 2.8px !important; }
.flow-svg polyline.branch-dim { opacity: 0.32; }

/* Inspector Drawer & Device Frames */
.inspector-drawer {
  position: absolute; top: 12px; right: 12px; bottom: 12px; width: 706px;
  max-width: calc(100% - 24px); z-index: 90; background: var(--wt-white);
  border: 1px solid var(--wt-border); border-radius: 10px;
  display: flex; flex-direction: column; overflow: hidden;
}
.inspector-drawer.wide-mode { width: min(1040px, calc(100% - 24px)); }
.insp-head {
  height: 46px; padding: 0 14px; border-bottom: 1px solid var(--wt-border-light);
  background: var(--wt-bg); display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.insp-badge {
  font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: 2px 7px; border: 1px solid var(--wt-border); border-radius: 4px;
  background: var(--wt-white); color: var(--wt-dim);
}
#anno-node-title {
  font-size: 14px; font-weight: 700; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.insp-body {
  flex: 1; min-height: 0; display: flex; gap: 16px; padding: 14px;
  background: var(--wt-bg); overflow: hidden; justify-content: center;
}
.stage { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; min-height: 0; max-height: 100%; }
.frame-phone {
  width: 375px; min-height: 660px; max-height: 100%; overflow-y: auto;
  background: var(--wt-white); border: 1px solid var(--wt-border); border-radius: 14px; position: relative;
}
.frame-phone::-webkit-scrollbar { width: 0; }
.frame-wide {
  width: 690px; max-height: 100%; overflow-y: auto;
  background: var(--wt-white); border: 1px solid var(--wt-border); border-radius: 8px; position: relative;
}
.pick-mode-on { outline: 2px solid var(--wt-pick); outline-offset: 2px; cursor: crosshair !important; }
.pick-mode-on * { cursor: crosshair !important; }
.page { display: none; padding-bottom: 24px; background: var(--wt-white); min-height: 100%; }
.page.active { display: block; }

/* Right Rule & Variable Panel */
.anno-panel { width: 286px; flex-shrink: 0; max-height: 100%; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.anno-card { padding: 11px 12px; border: 1px solid var(--wt-border-light); border-radius: 8px; background: var(--wt-white); }
.anno-card-title {
  font-size: 12px; font-weight: 700; color: var(--wt-text);
  padding-bottom: 6px; margin-bottom: 8px; border-bottom: 1px solid var(--wt-border-light);
}
.anno-item { font-size: 12px; color: var(--wt-text); line-height: 1.65; margin-bottom: 8px; }
.anno-item:last-child { margin-bottom: 0; }
.anno-item b { display: block; color: var(--wt-text); margin-bottom: 2px; }
.var-block { margin-bottom: 10px; }
.var-block:last-child { margin-bottom: 0; }
.var-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; font-size: 12px; }
.var-kind-tag {
  font-size: 10px; padding: 1px 5px; border: 1px solid var(--wt-border-light);
  border-radius: 3px; color: var(--wt-dim); background: var(--wt-bg);
}
.var-opts { display: flex; flex-wrap: wrap; gap: 5px; }
.var-opt {
  padding: 4px 9px; font-size: 11.5px; border-radius: 4px;
  border: 1px solid var(--wt-border); background: var(--wt-white);
}
.var-opt.cur, .var-opt.cur:hover {
  background: var(--wt-accent); color: var(--wt-white); border-color: var(--wt-accent); font-weight: 600;
}
.branch-go-btn { margin-top: 6px; width: 100%; font-size: 11.5px; padding: 4px 8px; }
.st-group { display: flex; flex-direction: column; gap: 6px; }
.st-btn {
  width: 100%; padding: 7px 10px; text-align: left; border: 1px solid var(--wt-border);
  border-radius: 5px; font-size: 12px; background: var(--wt-white); color: var(--wt-text); cursor: pointer;
}
.st-btn:hover { border-color: var(--wt-accent); }
.st-btn.cur, .st-btn.cur:hover {
  background: var(--wt-accent); color: var(--wt-white); border-color: var(--wt-accent);
  cursor: default; font-weight: 600;
}

/* Spec Cards View */
.spec-panel { flex: 1; min-width: 0; height: 100%; overflow-y: auto; padding: 24px 28px 60px; position: relative; }
.spec-ws {
  max-width: 1020px; margin: 0 auto; display: grid;
  grid-template-columns: 375px minmax(380px, 1fr); gap: 44px; align-items: start; position: relative;
}
.spec-ws.wide-spec { max-width: 1240px; grid-template-columns: 690px minmax(340px, 1fr); gap: 32px; }
@media (max-width: 1140px) {
  .spec-ws.wide-spec { grid-template-columns: 1fr; }
  .spec-ws.wide-spec .spec-sticky { position: static; }
}
.spec-sticky { position: sticky; top: 4px; z-index: 20; }
.spec-cards { display: flex; flex-direction: column; gap: 12px; padding-top: 8px; }
.spec-card {
  background: var(--wt-white); border: 1px solid var(--wt-border-light);
  border-radius: 8px; padding: 13px 15px; cursor: pointer;
}
.spec-card.active { border-color: var(--wt-text); border-width: 1.5px; }
.spec-card-hd { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.spec-idx {
  font-size: 11px; font-weight: 700; padding: 1px 7px;
  border: 1px solid var(--wt-border); border-radius: 4px; background: var(--wt-bg);
}
.spec-card-hd b { font-size: 13.5px; flex: 1; }
.spec-card-bd { font-size: 12.5px; line-height: 1.65; color: var(--wt-text); }
.tether-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 45; overflow: visible; }
.anchor-box {
  position: absolute; pointer-events: none; border: 2px dashed var(--wt-text);
  border-radius: 6px; background: rgba(85, 85, 85, 0.06); z-index: 44;
}

/* Memo Drawer (Minimalist Multi-Capsule Picking) */
.memo-drawer {
  width: 320px; flex-shrink: 0; height: 100%; background: var(--wt-white);
  border-left: 1px solid var(--wt-border); display: flex; flex-direction: column; z-index: 120;
}
.memo-hd {
  height: 46px; padding: 0 14px; border-bottom: 1px solid var(--wt-border-light);
  background: var(--wt-bg); display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; gap: 6px;
}
.memo-form { padding: 12px; border-bottom: 1px solid var(--wt-border-light); flex-shrink: 0; background: #fafafa; }
.memo-ctx {
  display: block; font-size: 11px; color: var(--wt-dim); background: var(--wt-white);
  border: 1px solid var(--wt-border-light); border-radius: 4px; padding: 4px 8px;
  margin-bottom: 8px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.memo-editor {
  width: 100%; min-height: 86px; max-height: 220px; overflow-y: auto;
  border: 1px solid var(--wt-border); border-radius: 5px; padding: 7px 9px;
  font-size: 12px; line-height: 1.55; margin-bottom: 6px; background: var(--wt-white);
  color: var(--wt-text); outline: none; white-space: pre-wrap; word-break: break-word;
}
.memo-editor:focus { border-color: var(--wt-accent); }
.memo-editor:empty::before { content: attr(data-placeholder); color: var(--wt-light); pointer-events: none; }
.memo-at-chip {
  display: inline-flex; align-items: center; padding: 1px 6px; margin: 0 2px;
  border-radius: 4px; background: var(--wt-fill); border: 1px solid var(--wt-border);
  color: var(--wt-text); font-size: 11.5px; font-weight: 600; user-select: all;
}
.memo-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.memo-empty { text-align: center; color: var(--wt-light); font-size: 12px; padding: 24px 12px; }
.memo-item { border: 1px solid var(--wt-border-light); border-radius: 6px; padding: 10px; background: var(--wt-bg); }
.memo-item.invalid { border-color: var(--wt-danger); background: #fef2f2; }
.memo-item-hd { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 4px; }
.memo-item-ctx {
  font-size: 11px; font-weight: 600; color: var(--wt-accent); cursor: pointer;
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.memo-item-ctx:hover { text-decoration: underline; }
.memo-invalid-badge {
  font-size: 10px; font-weight: 600; color: var(--wt-white); background: var(--wt-danger);
  padding: 1px 6px; border-radius: 3px; flex-shrink: 0;
}
.memo-item-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 5px; }
.memo-item-tag {
  font-size: 10.5px; color: var(--wt-pick); background: #eff6ff; border: 1px solid #bfdbfe;
  border-radius: 999px; padding: 1px 6px;
}
.memo-item-meta {
  font-size: 10.5px; color: var(--wt-dim); margin-bottom: 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.memo-item-txt { font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
.memo-item-ft {
  margin-top: 7px; display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: var(--wt-light);
}
.memo-del-btn { border: none; background: transparent; color: var(--wt-dim); padding: 1px 5px; font-size: 11px; }
.memo-del-btn:hover { color: var(--wt-danger); background: transparent; }
.memo-export { padding: 10px 12px; border-top: 1px solid var(--wt-border-light); background: var(--wt-bg); display: flex; gap: 6px; }
.memo-export button { flex: 1; padding: 5px 6px; font-size: 11.5px; white-space: nowrap; }

#pick-highlight-overlay {
  position: fixed; z-index: 9999; pointer-events: none;
  border: 2px solid var(--wt-pick); background: rgba(37, 99, 235, 0.10);
  border-radius: 4px; display: none; transition: all 0.06s ease;
}
#pick-label-badge {
  position: fixed; z-index: 10000; pointer-events: none;
  background: #1e293b; color: #ffffff; font-size: 11.5px; font-weight: 600;
  padding: 3px 8px; border-radius: 4px; white-space: nowrap; max-width: 300px;
  overflow: hidden; text-overflow: ellipsis; box-shadow: 0 2px 8px rgba(0,0,0,0.22); display: none;
}

.guard-mask {
  position: fixed; inset: 0; z-index: 10050; background: rgba(0,0,0,0.42);
  display: flex; align-items: center; justify-content: center; padding: 16px;
}
.guard-modal {
  width: 400px; max-width: 100%; background: var(--wt-white); border: 1px solid var(--wt-border);
  border-radius: 10px; padding: 18px; box-shadow: 0 12px 32px rgba(0,0,0,0.18);
}
.guard-modal h3 { font-size: 15px; margin-bottom: 8px; color: var(--wt-danger); }
.guard-modal p { font-size: 12.5px; line-height: 1.6; color: var(--wt-text); margin-bottom: 14px; }
.guard-actions { display: flex; justify-content: flex-end; gap: 8px; }
"""


WT_WIREFRAME_CSS = """\
/* Neutral Wireframe Component Library (wt-*) */
.wt-stack { display: flex; flex-direction: column; gap: 10px; }
.wt-row { display: flex; align-items: center; gap: 8px; }
.wt-col { display: flex; flex-direction: column; gap: 6px; }
.wt-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.wt-divider { height: 1px; background: var(--wt-border-light); margin: 8px 0; }
.wt-muted { color: var(--wt-dim); font-size: 12px; }

/* Navigation */
.wt-navbar {
  height: 44px; padding: 0 12px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--wt-border-light); background: var(--wt-white); font-weight: 600;
}
.wt-tabbar {
  display: flex; border-top: 1px solid var(--wt-border-light); background: var(--wt-bg);
}
.wt-tabbar-item {
  flex: 1; text-align: center; padding: 9px 4px; font-size: 11.5px; color: var(--wt-dim); cursor: pointer;
}
.wt-tabbar-item.active { color: var(--wt-text); font-weight: 700; }
.wt-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--wt-border-light); padding: 0 12px; }
.wt-tab {
  padding: 8px 12px; font-size: 12.5px; color: var(--wt-dim); border: none;
  background: transparent; border-bottom: 2px solid transparent; border-radius: 0;
}
.wt-tab.active { color: var(--wt-text); font-weight: 700; border-bottom-color: var(--wt-text); }
.wt-breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--wt-dim); }

/* Buttons */
.wt-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 5px;
  padding: 6px 12px; border: 1px solid var(--wt-border); border-radius: 6px;
  background: var(--wt-white); color: var(--wt-text); font-size: 12.5px; cursor: pointer;
}
.wt-btn:hover:not(:disabled) { background: var(--wt-fill); }
.wt-btn-primary { background: var(--wt-accent); color: var(--wt-white); border-color: var(--wt-accent); }
.wt-btn-primary:hover:not(:disabled) { background: #3f3f3f; }
.wt-btn-ghost { background: transparent; border-color: transparent; }
.wt-btn-danger { background: var(--wt-white); color: var(--wt-text); border-color: var(--wt-text); font-weight: 600; }
.wt-btn-sm { padding: 3px 8px; font-size: 11.5px; }
.wt-btn-block { width: 100%; }

/* Cards & Lists */
.wt-card {
  border: 1px solid var(--wt-border-light); border-radius: 8px;
  background: var(--wt-white); overflow: hidden;
}
.wt-card-hd {
  padding: 10px 12px; border-bottom: 1px solid var(--wt-border-light);
  background: var(--wt-bg); font-weight: 700; font-size: 12.5px;
}
.wt-card-bd { padding: 12px; }
.wt-card-ft { padding: 8px 12px; border-top: 1px solid var(--wt-border-light); background: var(--wt-bg); }
.wt-list { display: flex; flex-direction: column; }
.wt-list-item {
  padding: 10px 12px; border-bottom: 1px solid var(--wt-border-light);
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.wt-list-item:last-child { border-bottom: none; }
.wt-avatar {
  width: 32px; height: 32px; border-radius: 50%; background: var(--wt-fill);
  border: 1px solid var(--wt-border); display: inline-flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.wt-badge, .wt-tag {
  display: inline-block; padding: 1px 6px; font-size: 11px; border-radius: 4px;
  border: 1px solid var(--wt-border); background: var(--wt-bg); color: var(--wt-dim);
}
.wt-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
  border-radius: 999px; border: 1px solid var(--wt-border); background: var(--wt-bg); font-size: 11.5px;
}

/* Forms */
.wt-form { display: flex; flex-direction: column; gap: 10px; }
.wt-field { display: flex; flex-direction: column; gap: 4px; }
.wt-label { font-size: 12px; font-weight: 600; color: var(--wt-text); }
.wt-input, .wt-textarea, .wt-select {
  width: 100%; padding: 6px 9px; border: 1px solid var(--wt-border);
  border-radius: 5px; background: var(--wt-white); font-size: 12.5px;
}
.wt-textarea { min-height: 72px; resize: vertical; }
.wt-help { font-size: 11px; color: var(--wt-dim); }
.wt-error { font-size: 11px; color: var(--wt-danger); }

/* Tables */
.wt-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.wt-table th, .wt-table td {
  padding: 7px 9px; border: 1px solid var(--wt-border-light); text-align: left;
}
.wt-table th { background: var(--wt-bg); font-weight: 700; }

/* Modals & Drawers */
.wt-mask {
  position: absolute; inset: 0; background: rgba(0, 0, 0, 0.36);
  display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 20;
}
.wt-modal {
  width: 100%; max-width: 320px; background: var(--wt-white);
  border: 1px solid var(--wt-border); border-radius: 10px; overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,0.16);
}
.wt-modal-hd {
  padding: 10px 14px; border-bottom: 1px solid var(--wt-border-light);
  font-weight: 700; display: flex; align-items: center; justify-content: space-between;
}
.wt-modal-bd { padding: 14px; font-size: 12.5px; }
.wt-modal-ft {
  padding: 10px 14px; border-top: 1px solid var(--wt-border-light);
  display: flex; justify-content: flex-end; gap: 8px; background: var(--wt-bg);
}

/* Feedback & States */
.wt-toast {
  margin: 16px auto; max-width: 280px; padding: 9px 14px; border-radius: 6px;
  background: #222222; color: #ffffff; text-align: center; font-size: 12px;
}
.wt-banner, .wt-alert {
  padding: 8px 12px; border-radius: 6px; border: 1px solid var(--wt-border);
  background: var(--wt-bg); font-size: 12px;
}
.wt-alert-danger { border-color: var(--wt-danger); background: #fef2f2; color: var(--wt-danger); }
.wt-empty { padding: 28px 16px; text-align: center; color: var(--wt-dim); font-size: 12px; }
.wt-skeleton {
  height: 14px; border-radius: 4px; background: var(--wt-fill);
}
"""


ENGINE_JS = """\
var currentNode = null;
var currentState = null;
var currentPage = null;
var varValues = {};
var wbView = "flow";
var activeSpecId = null;

(VARS || []).forEach(function (v) {
  if (v && v.id && v.options && v.options.length) {
    varValues[v.id] = v.default || v.options[0].id;
  }
});

function computeDocVersionHash() {
  var parts = [];
  parts.push(Object.keys(NODES || {}).sort().map(function (k) {
    var n = NODES[k] || {};
    return k + ":" + (n.page || "") + ":" + (n.branchVar || "");
  }).join(","));
  parts.push((VARS || []).map(function (v) {
    return v.id + ":" + (v.options || []).map(function (o) {
      return o.id + ">" + (o.target || "");
    }).join("/");
  }).join(","));
  parts.push((SPEC_CARDS || []).map(function (c) {
    return c.id + ":" + (c.page || "") + ":" + (c.anchor || "");
  }).join(","));
  document.querySelectorAll(".page").forEach(function (pg) {
    var comps = Array.prototype.slice.call(pg.querySelectorAll("[data-comp-id]"))
      .map(function (el) { return el.getAttribute("data-comp-id"); });
    parts.push((pg.id || "") + "=" + comps.join(","));
  });
  var raw = parts.join("|");
  var h = 2166136261;
  for (var i = 0; i < raw.length; i++) {
    h ^= raw.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return ("00000000" + h.toString(16)).slice(-8);
}

var DOC_VERSION_HASH = computeDocVersionHash();
var MEMO_STORAGE_KEY = "wt_memos_" + DOC_VERSION_HASH;

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function checkVarWhen(v) {
  if (!v.when) return true;
  for (var k in v.when) {
    var expected = v.when[k];
    var actual = varValues[k];
    if (Array.isArray(expected)) {
      if (expected.indexOf(actual) < 0) return false;
    } else if (actual !== expected) {
      return false;
    }
  }
  return true;
}

function isVarApplicable(v) {
  if (!checkVarWhen(v)) return false;
  var hasNodes = Array.isArray(v.nodes) && v.nodes.length > 0;
  var hasPages = Array.isArray(v.pages) && v.pages.length > 0;
  if (!hasNodes && !hasPages) return true;
  var nMatch = hasNodes ? v.nodes.indexOf(currentNode) >= 0 : false;
  var pMatch = hasPages ? v.pages.indexOf(currentPage) >= 0 : false;
  return nMatch || pMatch;
}

function syncDeclarativePageVars() {
  document.querySelectorAll("[data-when-var]").forEach(function (el) {
    var varId = el.getAttribute("data-when-var");
    var expected = el.getAttribute("data-when-val");
    if (!varId || expected === null) return;
    var vals = expected.split(",").map(function (s) { return s.trim(); });
    el.classList.toggle("hidden", vals.indexOf(String(varValues[varId])) < 0);
  });
}

function renderGlobalVars() {
  var bar = document.getElementById("global-vars-bar");
  if (!bar) return;
  var globals = (VARS || []).filter(function (v) {
    return v.kind === "global" && checkVarWhen(v);
  });
  bar.innerHTML = globals.map(function (v) {
    var btns = (v.options || []).map(function (o) {
      var active = varValues[v.id] === o.id ? " active" : "";
      return '<button type="button" class="seg-btn' + active + '" onclick="setVar(\\'' +
        escapeHtml(v.id) + '\\',\\'' + escapeHtml(o.id) + '\\')">' +
        escapeHtml(o.label) + '</button>';
    }).join("");
    return '<div class="wb-gvar"><span>' + escapeHtml(v.label) + '</span>' +
      '<div class="seg-group">' + btns + '</div></div>';
  }).join("");
}

function renderScopedVars() {
  var card = document.getElementById("vars-card");
  var body = document.getElementById("vars-body");
  if (!card || !body) return;

  var scoped = (VARS || []).filter(function (v) {
    return v.kind !== "global" && isVarApplicable(v);
  });

  var activeBranches = [];
  (VARS || []).forEach(function (v) {
    if (v.kind === "branch" && v.diamond) {
      var cur = (v.options || []).find(function (o) { return o.id === varValues[v.id]; });
      if (cur && cur.target) {
        activeBranches.push({ diamond: v.diamond, target: cur.target, optId: cur.id });
      }
    }
  });
  highlightBranchEdges(activeBranches);

  if (!scoped.length) {
    body.innerHTML = "";
    card.classList.add("hidden");
    return;
  }

  body.innerHTML = scoped.map(function (v) {
    var tag = v.kind === "branch" ? "分支条件" : "局部组件";
    var curOpt = (v.options || []).find(function (o) { return o.id === varValues[v.id]; });
    var optsHtml = (v.options || []).map(function (o) {
      var curCls = varValues[v.id] === o.id ? " cur" : "";
      return '<button type="button" class="var-opt' + curCls + '" onclick="setVar(\\'' +
        escapeHtml(v.id) + '\\',\\'' + escapeHtml(o.id) + '\\')">' +
        escapeHtml(o.label) + '</button>';
    }).join("");
    var goHtml = (v.kind === "branch" && curOpt && curOpt.target && NODES[curOpt.target])
      ? '<button type="button" class="branch-go-btn" onclick="goBranch(\\'' +
        escapeHtml(v.id) + '\\')">跳转至：' +
        escapeHtml(NODES[curOpt.target].title || curOpt.target) + ' →</button>'
      : "";
    return '<div class="var-block"><div class="var-head"><b>' + escapeHtml(v.label) +
      '</b><span class="var-kind-tag">' + tag + '</span></div>' +
      '<div class="var-opts">' + optsHtml + '</div>' + goHtml + '</div>';
  }).join("");
  card.classList.remove("hidden");
}

function buildSvgEdgeMap() {
  var polys = document.querySelectorAll("#flow-svg polyline[data-from]");
  var outMap = {};
  polys.forEach(function (pl) {
    var f = pl.getAttribute("data-from");
    var t = pl.getAttribute("data-to");
    if (f && t) {
      (outMap[f] = outMap[f] || []).push({
        to: t,
        branch: pl.getAttribute("data-branch") || "",
        pl: pl
      });
    }
  });
  return { polys: polys, outMap: outMap };
}

function canReachNode(outMap, startId, goalId) {
  var seen = {};
  var q = [startId];
  seen[startId] = true;
  while (q.length) {
    var cur = q.shift();
    var outs = outMap[cur] || [];
    for (var i = 0; i < outs.length; i++) {
      var nxt = outs[i].to;
      if (nxt === goalId) return true;
      if (!seen[nxt]) {
        seen[nxt] = true;
        q.push(nxt);
      }
    }
  }
  return false;
}

function pickDiamondOutgoingEdge(outMap, diamondChoice, dId) {
  var info = diamondChoice[dId];
  var outs = outMap[dId] || [];
  if (!info || !outs.length) return null;
  var rawTarget = info.target;
  var optId = info.optId;
  return outs.find(function (e) { return e.to === rawTarget; }) ||
    outs.find(function (e) { return optId && e.branch === optId; }) ||
    outs.find(function (e) { return diamondChoice[e.to] && canReachNode(outMap, e.to, rawTarget); }) ||
    outs.find(function (e) { return canReachNode(outMap, e.to, rawTarget); }) ||
    null;
}

function highlightBranchEdges(activeBranches) {
  var g = buildSvgEdgeMap();
  g.polys.forEach(function (pl) {
    pl.classList.remove("branch-active");
    pl.classList.remove("branch-dim");
  });
  if (!activeBranches || !activeBranches.length) return;
  var diamondChoice = {};
  activeBranches.forEach(function (item) {
    if (item.diamond) diamondChoice[item.diamond] = item;
  });
  var visited = {};
  function walkDiamond(dId) {
    if (!dId || visited[dId] || !diamondChoice[dId]) return;
    visited[dId] = true;
    var outs = g.outMap[dId] || [];
    var chosen = pickDiamondOutgoingEdge(g.outMap, diamondChoice, dId);
    if (!chosen) return;
    chosen.pl.classList.remove("branch-dim");
    chosen.pl.classList.add("branch-active");
    outs.forEach(function (e) {
      if (e !== chosen && !e.pl.classList.contains("branch-active")) {
        e.pl.classList.add("branch-dim");
      }
    });
    if (diamondChoice[chosen.to]) walkDiamond(chosen.to);
  }
  (g.outMap[currentNode] || []).forEach(function (e) {
    if (diamondChoice[e.to]) {
      e.pl.classList.add("branch-active");
      walkDiamond(e.to);
    }
  });
  Object.keys(diamondChoice).forEach(function (dId) { walkDiamond(dId); });
}

var isRestoringHash = false;
function syncUrlHash() {
  if (isRestoringHash) return;
  var params = new URLSearchParams();
  if (currentNode) params.set("node", currentNode);
  (VARS || []).forEach(function (v) {
    if (v && v.id && varValues[v.id] !== undefined) {
      params.set(v.id, varValues[v.id]);
    }
  });
  if (wbView && wbView !== "flow") params.set("view", wbView);
  var newHash = "#" + params.toString();
  if (location.hash !== newHash) {
    try { history.replaceState(null, "", newHash); } catch (e) { location.hash = newHash; }
  }
}

function parseUrlHash() {
  var raw = (location.hash || "").replace(/^#/, "");
  var out = { node: null, view: null };
  if (!raw) return out;
  var params = new URLSearchParams(raw);
  (VARS || []).forEach(function (v) {
    if (!v || !v.id || !params.has(v.id)) return;
    var val = params.get(v.id);
    if ((v.options || []).some(function (o) { return o.id === val; })) {
      varValues[v.id] = val;
    }
  });
  var n = params.get("node");
  if (n && NODES[n]) out.node = n;
  var vw = params.get("view");
  if (vw === "flow" || vw === "spec") out.view = vw;
  return out;
}

window.getVar = function (varId) { return varValues[varId]; };
window.setVar = function (varId, optId) {
  var v = (VARS || []).find(function (x) { return x.id === varId; });
  if (!v) return;
  var opt = (v.options || []).find(function (o) { return o.id === optId; });
  if (!opt) return;
  varValues[varId] = optId;
  if (opt.page && PAGE_FRAME[opt.page]) {
    showPage(opt.page);
  }
  syncDeclarativePageVars();
  renderGlobalVars();
  renderScopedVars();
  syncUrlHash();
  if (typeof window.onWalkVarChange === "function") {
    window.onWalkVarChange(varId, optId, Object.assign({}, varValues));
  }
};

window.goBranch = function (varId) {
  var v = (VARS || []).find(function (x) { return x.id === varId; });
  if (!v) return;
  var opt = (v.options || []).find(function (o) { return o.id === varValues[varId]; });
  if (!opt || !opt.target) return;
  if (NODES[opt.target]) setViewByNode(opt.target);
};

function renderStates() {
  var card = document.getElementById("state-card");
  var body = document.getElementById("state-body");
  if (!card || !body) return;
  var st = currentState ? String(currentState).split("/") : null;
  var grp = st && STATE_GROUPS[st[0]];
  if (!grp || !grp.states || grp.states.length < 2) {
    body.innerHTML = "";
    card.classList.add("hidden");
    return;
  }
  body.innerHTML = '<div class="st-group">' + grp.states.map(function (s) {
    if (s.id === st[1]) {
      return '<button type="button" class="st-btn cur" disabled>' + escapeHtml(s.label) + '</button>';
    }
    return '<button type="button" class="st-btn" onclick="goState(\\'' +
      escapeHtml(st[0]) + '\\',\\'' + escapeHtml(s.id) + '\\')">' +
      escapeHtml(s.label) + '</button>';
  }).join("") + '</div>';
  card.classList.remove("hidden");
}

function showPage(pageId) {
  currentPage = pageId;
  var frame = PAGE_FRAME[pageId] || "phone";
  var phoneEl = document.getElementById("frame-phone");
  var wideEl = document.getElementById("frame-wide");
  if (phoneEl) phoneEl.classList.toggle("hidden", frame !== "phone");
  if (wideEl) wideEl.classList.toggle("hidden", frame !== "wide");
  var drawer = document.getElementById("inspector-drawer");
  if (drawer) drawer.classList.toggle("wide-mode", frame === "wide");
  var specWs = document.getElementById("spec-ws");
  if (specWs) specWs.classList.toggle("wide-spec", frame === "wide");
  document.querySelectorAll(".page").forEach(function (p) {
    p.classList.toggle("active", p.id === pageId);
  });
  syncDeclarativePageVars();
  if (typeof wbView !== "undefined" && wbView === "spec" && typeof updateSpecTether === "function") {
    requestAnimationFrame(updateSpecTether);
  }
}

window.goState = function (groupId, stateId) {
  var grp = STATE_GROUPS[groupId];
  if (!grp) return;
  var state = (grp.states || []).find(function (s) { return s.id === stateId; });
  if (!state) return;
  currentState = groupId + "/" + stateId;
  showPage(state.page);
  renderStates();
  renderScopedVars();
};

function setViewByNode(nodeId) {
  var n = NODES[nodeId];
  if (!n) return;
  var panel = document.querySelector(".flow-panel");
  if (panel && panel.classList.contains("fs")) toggleFs(false);
  currentNode = nodeId;
  currentState = n.state || null;
  showPage(n.page);

  var ring = document.getElementById("sel-ring");
  var target = document.querySelector('.flow-svg g[data-node="' + nodeId + '"]');
  if (ring && target) {
    var bb = target.getBBox();
    ring.setAttribute("x", bb.x - 7);
    ring.setAttribute("y", bb.y - 7);
    ring.setAttribute("width", bb.width + 14);
    ring.setAttribute("height", bb.height + 14);
    ring.setAttribute("visibility", "visible");
  }

  var badge = document.getElementById("insp-node-id");
  if (badge) badge.textContent = nodeId;
  var titleEl = document.getElementById("anno-node-title");
  if (titleEl) titleEl.textContent = n.title || nodeId;
  var refEl = document.getElementById("flow-node-ref");
  if (refEl) refEl.textContent = nodeId + (n.title ? " · " + n.title : "");
  var annoEl = document.getElementById("anno-body");
  if (annoEl) {
    annoEl.innerHTML = (n.anno || []).map(function (p) {
      return '<div class="anno-item"><b>' + escapeHtml(p[0]) + '</b>' + escapeHtml(p[1]) + '</div>';
    }).join("") || '<div class="wt-muted">暂无节点规则说明</div>';
  }

  renderStates();
  renderGlobalVars();
  renderScopedVars();
  syncUrlHash();
  if (target) panNodeToSafeLeft(target);
  if (typeof updateMemoFormCtx === "function" && !document.getElementById("memo-form").classList.contains("hidden")) {
    updateMemoFormCtx();
  }
  if (typeof window.onWalkNodeChange === "function") {
    window.onWalkNodeChange(nodeId, currentPage, Object.assign({}, varValues));
  }
}
window.goNode = setViewByNode;

// =========================================================================
// SVG Canvas Pan & Zoom (Drag, Wheel, Pinch, zoomAt, fitBootZoom, SafeCenter)
// =========================================================================
var zoomPct = 100;
var panX = 0;
var panY = 0;
var flowSvgEl = document.getElementById("flow-svg");
var flowInnerEl = document.getElementById("flow-canvas-inner");
var movedFlag = false;

function applyPan(smooth) {
  if (!flowInnerEl) return;
  flowInnerEl.classList.toggle("smooth", !!smooth);
  flowInnerEl.style.transform = "translate(" + panX + "px," + panY + "px)";
}

function applyZoomPct(pct) {
  zoomPct = Math.min(300, Math.max(30, Math.round(pct)));
  var svg = document.querySelector("#flow-svg svg");
  if (svg) svg.style.width = zoomPct + "%";
  var zv = document.getElementById("zv");
  if (zv) zv.textContent = zoomPct + "%";
}

function zoomAt(value, clientX, clientY) {
  if (!flowSvgEl) return;
  var oldZoom = zoomPct;
  var newZoom = Math.min(300, Math.max(30, value));
  if (newZoom === oldZoom) return;
  var rect = flowSvgEl.getBoundingClientRect();
  var cx = clientX !== undefined ? clientX : (rect.left + rect.width / 2);
  var cy = clientY !== undefined ? clientY : (rect.top + rect.height / 2);
  var relX = cx - rect.left;
  var relY = cy - rect.top;
  var ratio = newZoom / oldZoom;
  panX = relX - (relX - panX) * ratio;
  panY = relY - (relY - panY) * ratio;
  applyZoomPct(newZoom);
  applyPan(false);
}

function setZoom(dir) {
  if (dir === 0) {
    fitBootZoom();
    return;
  }
  var step = dir > 0 ? 25 : -25;
  var rect = flowSvgEl ? flowSvgEl.getBoundingClientRect() : null;
  var cx = rect ? rect.left + rect.width / 2 : undefined;
  var cy = rect ? rect.top + rect.height / 2 : undefined;
  zoomAt(zoomPct + step, cx, cy);
}

function fitBootZoom() {
  if (!flowSvgEl) return;
  var cw = flowSvgEl.clientWidth || 1200;
  var panel = document.querySelector(".flow-panel");
  var drawer = document.getElementById("inspector-drawer");
  var dw = (panel && !panel.classList.contains("fs") && drawer) ? (drawer.offsetWidth + 32) : 0;
  var availW = Math.max(280, cw - dw - 24);
  var targetPct = Math.max(40, Math.min(100, Math.round((availW / cw) * 100)));
  applyZoomPct(targetPct);
  panX = 12;
  panY = 12;
  applyPan(false);
}

function panNodeToSafeLeft(target) {
  if (!target || !flowSvgEl) return;
  var panel = document.querySelector(".flow-panel");
  var drawer = document.getElementById("inspector-drawer");
  var flowRect = flowSvgEl.getBoundingClientRect();
  if (!flowRect.width || !flowRect.height) return;
  var dw = (panel && !panel.classList.contains("fs") && drawer) ? (drawer.offsetWidth + 16) : 0;
  var safeW = Math.max(160, flowRect.width - dw);
  var pad = 28;
  var safeLeft = flowRect.left + pad;
  var safeRight = flowRect.left + safeW - pad;
  var safeTop = flowRect.top + pad;
  var safeBottom = flowRect.bottom - pad;
  var tr = target.getBoundingClientRect();
  if (!tr.width && !tr.height) return;

  var dx = 0;
  var dy = 0;
  if (tr.left < safeLeft || tr.right > safeRight) {
    dx = (flowRect.left + safeW / 2) - (tr.left + tr.width / 2);
  }
  if (tr.top < safeTop || tr.bottom > safeBottom) {
    dy = (flowRect.top + flowRect.height / 2) - (tr.top + tr.height / 2);
  }
  if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
    panX += dx;
    panY += dy;
    applyPan(true);
    setTimeout(function () { if (flowInnerEl) flowInnerEl.classList.remove("smooth"); }, 280);
  }
}

function toggleFs(force) {
  var p = document.querySelector(".flow-panel");
  if (!p) return;
  var on = force !== undefined ? force : !p.classList.contains("fs");
  p.classList.toggle("fs", on);
  var btn = document.getElementById("fs-btn");
  if (btn) btn.textContent = on ? "显示详情" : "全屏画布";
}

if (flowSvgEl) {
  var dragState = { active: false, startX: 0, startY: 0, startPanX: 0, startPanY: 0 };
  flowSvgEl.addEventListener("pointerdown", function (e) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    dragState.active = true;
    movedFlag = false;
    dragState.startX = e.clientX;
    dragState.startY = e.clientY;
    dragState.startPanX = panX;
    dragState.startPanY = panY;
    if (flowInnerEl) flowInnerEl.classList.remove("smooth");
  });
  window.addEventListener("pointermove", function (e) {
    if (!dragState.active) return;
    var dx = e.clientX - dragState.startX;
    var dy = e.clientY - dragState.startY;
    if (!movedFlag && Math.hypot(dx, dy) > 4) movedFlag = true;
    if (movedFlag) {
      panX = dragState.startPanX + dx;
      panY = dragState.startPanY + dy;
      applyPan(false);
    }
  });
  function endFlowDrag() {
    if (!dragState.active) return;
    dragState.active = false;
    if (movedFlag) setTimeout(function () { movedFlag = false; }, 0);
  }
  window.addEventListener("pointerup", endFlowDrag);
  window.addEventListener("pointercancel", endFlowDrag);

  flowSvgEl.addEventListener("click", function (e) {
    if (movedFlag) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    var nodeEl = e.target.closest("g[data-node]");
    if (nodeEl) {
      setViewByNode(nodeEl.getAttribute("data-node"));
    } else {
      toggleFs(true);
    }
  });

  flowSvgEl.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var nodeEl = e.target.closest("g[data-node]");
    if (nodeEl) {
      e.preventDefault();
      setViewByNode(nodeEl.getAttribute("data-node"));
    }
  });

  flowSvgEl.addEventListener("wheel", function (e) {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      var factor = Math.exp(-e.deltaY * 0.008);
      zoomAt(zoomPct * factor, e.clientX, e.clientY);
    } else {
      panX -= e.deltaX;
      panY -= e.deltaY;
      applyPan(false);
    }
  }, { passive: false });

  var gestureStartZoom = 100;
  flowSvgEl.addEventListener("gesturestart", function (e) {
    e.preventDefault();
    gestureStartZoom = zoomPct;
  }, { passive: false });
  flowSvgEl.addEventListener("gesturechange", function (e) {
    e.preventDefault();
    zoomAt(gestureStartZoom * e.scale, e.clientX, e.clientY);
  }, { passive: false });
  flowSvgEl.addEventListener("gestureend", function (e) {
    e.preventDefault();
  }, { passive: false });
}

document.addEventListener("keydown", function (e) {
  if (e.key !== "Escape") return;
  var guardModal = document.getElementById("export-guard-modal");
  if (guardModal && !guardModal.classList.contains("hidden")) {
    closeExportGuard();
    return;
  }
  var memoForm = document.getElementById("memo-form");
  if (memoForm && !memoForm.classList.contains("hidden")) {
    closeMemoForm();
    return;
  }
  if (wbView === "flow") {
    var panel = document.querySelector(".flow-panel");
    if (panel && !panel.classList.contains("fs")) toggleFs(true);
  }
});

// =========================================================================
// Spec Cards Mode (Single-page Spec Tether)
// =========================================================================
function initSpecMode() {
  var sw = document.getElementById("view-switch");
  var box = document.getElementById("spec-cards");
  if (!sw || !box || !SPEC_CARDS || !SPEC_CARDS.length) return;
  sw.classList.remove("hidden");
  box.innerHTML = SPEC_CARDS.map(function (c) {
    return '<div class="spec-card" data-cid="' + escapeHtml(c.id) +
      '" data-page="' + escapeHtml(c.page || "") +
      '" data-anchor="' + escapeHtml(c.anchor || "") + '">' +
      '<div class="spec-card-hd"><span class="spec-idx">' + escapeHtml(c.id) +
      '</span><b>' + escapeHtml(c.title) + '</b></div>' +
      '<div class="spec-card-bd">' + escapeHtml(c.body) + '</div></div>';
  }).join("");
  box.querySelectorAll(".spec-card").forEach(function (el) {
    el.addEventListener("mouseenter", function () { activateSpecCard(el.getAttribute("data-cid")); });
    el.addEventListener("click", function () { activateSpecCard(el.getAttribute("data-cid")); });
  });
}

window.switchWbView = function (view) {
  wbView = view;
  document.getElementById("flow-panel-root").classList.toggle("hidden", view !== "flow");
  document.getElementById("spec-panel-root").classList.toggle("hidden", view !== "spec");
  var stageEl = document.getElementById("flow-stage");
  var specSlot = document.getElementById("spec-stage-slot");
  var inspBody = document.querySelector(".insp-body");
  document.querySelectorAll("#view-switch .seg-btn").forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-wbview") === view);
  });
  if (view === "spec" && SPEC_CARDS && SPEC_CARDS.length) {
    specSlot.appendChild(stageEl);
    activateSpecCard(activeSpecId || SPEC_CARDS[0].id);
  } else {
    inspBody.insertBefore(stageEl, inspBody.firstChild);
  }
  syncUrlHash();
};

function activateSpecCard(cid) {
  activeSpecId = cid;
  var card = (SPEC_CARDS || []).find(function (c) { return c.id === cid; });
  if (!card) return;
  showPage(card.page);
  var specWs = document.getElementById("spec-ws");
  if (specWs) specWs.classList.toggle("wide-spec", (PAGE_FRAME[card.page] || "phone") === "wide");
  document.querySelectorAll(".spec-card").forEach(function (el) {
    el.classList.toggle("active", el.getAttribute("data-cid") === cid);
  });
  requestAnimationFrame(updateSpecTether);
}

function updateSpecTether() {
  var svg = document.getElementById("tether-svg");
  var abox = document.getElementById("anchor-box");
  var ws = document.getElementById("spec-ws");
  if (!svg || !abox || !ws || wbView !== "spec" || !activeSpecId) return;
  var cardEl = document.querySelector('.spec-card[data-cid="' + activeSpecId + '"]');
  var anchor = cardEl && cardEl.getAttribute("data-anchor");
  var targetEl = anchor
    ? (document.querySelector('.page.active [data-comp-id="' + anchor + '"]') ||
       document.querySelector('.page.active [data-anchor="' + anchor + '"]'))
    : null;
  if (!cardEl || !targetEl) {
    svg.innerHTML = "";
    abox.classList.add("hidden");
    return;
  }
  var wr = ws.getBoundingClientRect();
  var tr = targetEl.getBoundingClientRect();
  var cr = cardEl.getBoundingClientRect();
  abox.style.left = (tr.left - wr.left - 4) + "px";
  abox.style.top = (tr.top - wr.top - 4) + "px";
  abox.style.width = (tr.width + 8) + "px";
  abox.style.height = (tr.height + 8) + "px";
  abox.classList.remove("hidden");
  var x1 = tr.right - wr.left + 4;
  var y1 = tr.top - wr.top + tr.height / 2;
  var x2 = cr.left - wr.left;
  var y2 = cr.top - wr.top + 22;
  svg.innerHTML = '<path d="M ' + x1 + ' ' + y1 + ' L ' + x2 + ' ' + y2 +
    '" fill="none" stroke="#333333" stroke-width="1.8" stroke-dasharray="5 4"></path>';
}

// =========================================================================
// Minimalist Pick-and-Memo (Auto Capture Picking + Inline @ Component Chips)
// =========================================================================
var isMemoPickingActive = false;
var lastPickedPageId = "";

function getStageContainers() {
  return [document.getElementById("frame-phone"), document.getElementById("frame-wide")].filter(Boolean);
}

function setMemoPickingActive(active) {
  isMemoPickingActive = !!active;
  getStageContainers().forEach(function (el) {
    el.classList.toggle("pick-mode-on", isMemoPickingActive);
  });
  if (!isMemoPickingActive) hidePickOverlay();
}

function hidePickOverlay() {
  var ov = document.getElementById("pick-highlight-overlay");
  var bg = document.getElementById("pick-label-badge");
  if (ov) ov.style.display = "none";
  if (bg) bg.style.display = "none";
}

function positionPickOverlay(targetEl, labelText) {
  var ov = document.getElementById("pick-highlight-overlay");
  var bg = document.getElementById("pick-label-badge");
  if (!ov || !bg || !targetEl || !targetEl.isConnected) {
    hidePickOverlay();
    return;
  }
  var rect = targetEl.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) {
    hidePickOverlay();
    return;
  }
  ov.style.display = "block";
  ov.style.left = rect.left + "px";
  ov.style.top = rect.top + "px";
  ov.style.width = rect.width + "px";
  ov.style.height = rect.height + "px";

  bg.style.display = "block";
  bg.textContent = labelText;
  var topPos = rect.top - 26;
  if (topPos < 54) topPos = rect.bottom + 4;
  var leftPos = Math.max(8, Math.min(window.innerWidth - 280, rect.left));
  bg.style.left = leftPos + "px";
  bg.style.top = topPos + "px";
}

function getElementDisplayName(el) {
  if (!el) return "";
  var cname = el.getAttribute("data-comp-name");
  if (cname) return cname;
  var cid = el.getAttribute("data-comp-id");
  if (cid) return cid;
  var anc = el.getAttribute("data-anchor");
  if (anc) return anc;
  var tag = el.tagName ? el.tagName.toLowerCase() : "el";
  var txt = (el.textContent || "").replace(/\\s+/g, " ").trim();
  if (txt && txt.length <= 14) return tag + "「" + txt + "」";
  return tag;
}

function buildFallbackSelector(el, pageEl) {
  if (!el || !pageEl || el === pageEl) return "";
  if (el.id) return "#" + CSS.escape(el.id);
  var cid = el.getAttribute("data-comp-id");
  if (cid) return '[data-comp-id="' + cid + '"]';
  var anc = el.getAttribute("data-anchor");
  if (anc) return '[data-anchor="' + anc + '"]';
  var parts = [];
  var cur = el;
  while (cur && cur !== pageEl && cur.nodeType === 1) {
    var tag = cur.tagName.toLowerCase();
    var c = cur.getAttribute("data-comp-id");
    if (c) {
      parts.unshift('[data-comp-id="' + c + '"]');
      break;
    }
    var parent = cur.parentElement;
    if (parent) {
      var sameTag = Array.prototype.filter.call(parent.children, function (ch) {
        return ch.tagName === cur.tagName;
      });
      if (sameTag.length > 1) {
        tag += ":nth-of-type(" + (sameTag.indexOf(cur) + 1) + ")";
      }
    }
    parts.unshift(tag);
    cur = parent;
  }
  return parts.join(" > ");
}

function insertMentionChipInEditor(targetObj) {
  var inp = document.getElementById("memo-input");
  if (!inp || !targetObj) return;
  var chip = document.createElement("span");
  chip.className = "memo-at-chip";
  chip.setAttribute("contenteditable", "false");
  chip.setAttribute("data-comp-id", targetObj.comp_id || "");
  chip.setAttribute("data-comp-name", targetObj.comp_name || "");
  chip.setAttribute("data-fallback", targetObj.fallback_selector || "");
  if (targetObj.page) chip.setAttribute("data-page", targetObj.page);
  chip.textContent = "@[" + (targetObj.comp_name || targetObj.comp_id || "组件") + "]";
  var spaceNode = document.createTextNode(" ");

  var sel = window.getSelection();
  var range = null;
  if (sel && sel.rangeCount > 0) {
    var candidate = sel.getRangeAt(0);
    if (inp.contains(candidate.commonAncestorContainer)) {
      range = candidate;
    }
  }
  inp.focus();
  if (range) {
    range.deleteContents();
    range.insertNode(spaceNode);
    range.insertNode(chip);
    range.setStartAfter(spaceNode);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
  } else {
    inp.appendChild(chip);
    inp.appendChild(spaceNode);
    if (sel) {
      var endRange = document.createRange();
      endRange.setStartAfter(spaceNode);
      endRange.collapse(true);
      sel.removeAllRanges();
      sel.addRange(endRange);
    }
  }
}

function updateMemoFormCtx() {
  var ctxEl = document.getElementById("memo-ctx");
  if (ctxEl) {
    ctxEl.textContent = "当前上下文：" + (currentNode || "-") + " · " + (currentPage || "-");
  }
}

function handlePickSelect(rawTarget) {
  if (!isMemoPickingActive) return;
  var pageEl = rawTarget.closest(".page.active") || document.querySelector(".page.active");
  if (!pageEl) return;
  var compEl = rawTarget.closest("[data-comp-id], [data-anchor]");
  if (compEl && !pageEl.contains(compEl)) compEl = null;
  var targetEl = compEl || rawTarget;
  var compId = targetEl.getAttribute("data-comp-id") || targetEl.getAttribute("data-anchor") || "";
  var compName = getElementDisplayName(targetEl);
  var fallbackSel = buildFallbackSelector(targetEl, pageEl);
  var pageId = pageEl.id || currentPage || "";

  lastPickedPageId = pageId;
  insertMentionChipInEditor({
    page: pageId,
    comp_id: compId,
    comp_name: compName,
    fallback_selector: fallbackSel
  });
  positionPickOverlay(targetEl, "已插入 @" + compName);
}

function handlePickHover(rawTarget) {
  if (!isMemoPickingActive) return;
  var pageEl = rawTarget.closest(".page.active");
  if (!pageEl) {
    hidePickOverlay();
    return;
  }
  var compEl = rawTarget.closest("[data-comp-id], [data-anchor]");
  if (compEl && !pageEl.contains(compEl)) compEl = null;
  var targetEl = compEl || rawTarget;
  var name = getElementDisplayName(targetEl);
  positionPickOverlay(targetEl, "点击添加 @" + name);
}

getStageContainers().forEach(function (container) {
  container.addEventListener("pointerdown", function (e) {
    if (!isMemoPickingActive) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    if (e.button === 0 || e.pointerType !== "mouse") {
      handlePickSelect(e.target);
    }
  }, { capture: true });

  container.addEventListener("click", function (e) {
    if (!isMemoPickingActive) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
  }, { capture: true });

  container.addEventListener("pointermove", function (e) {
    if (!isMemoPickingActive) return;
    handlePickHover(e.target);
  }, { capture: true });

  container.addEventListener("pointerleave", function () {
    if (!isMemoPickingActive) return;
    hidePickOverlay();
  });
});

// =========================================================================
// Memo Storage, Dual-Timing Revalidation & Export (.md + .jsonl)
// =========================================================================
var memos = [];
try {
  var savedRaw = localStorage.getItem(MEMO_STORAGE_KEY);
  if (savedRaw) memos = JSON.parse(savedRaw) || [];
} catch (e) {
  memos = [];
}

if (!memos.length && Array.isArray(INITIAL_MEMOS) && INITIAL_MEMOS.length) {
  memos = INITIAL_MEMOS.map(function (m) {
    return {
      id: m.id || ("m_" + Date.now()),
      versionHash: m.version_hash || DOC_VERSION_HASH,
      view: m.view || "flow",
      node: m.node || "",
      page: m.page || "",
      vars: m.vars || {},
      granularity: m.granularity || (m.comp_id ? "component" : "page"),
      compId: m.comp_id || "",
      compName: m.comp_name || "",
      targets: Array.isArray(m.targets) ? m.targets : [],
      fallbackSelector: m.fallback_selector || "",
      text: m.body || m.text || "",
      time: m.time || ""
    };
  });
}

function persistMemos() {
  try { localStorage.setItem(MEMO_STORAGE_KEY, JSON.stringify(memos)); } catch (e) {}
}

function validateSingleTarget(pageEl, compId, fallbackSelector) {
  if (compId) {
    if (pageEl.querySelectorAll('[data-comp-id="' + compId + '"]').length > 0) return true;
    if (pageEl.querySelectorAll('[data-anchor="' + compId + '"]').length > 0) return true;
  }
  if (fallbackSelector) {
    try {
      if (pageEl.querySelectorAll(fallbackSelector).length > 0) return true;
    } catch (e) {}
  }
  return false;
}

function validateMemoAnchor(memo) {
  if (!memo || !memo.page) return false;
  if (memo.versionHash && memo.versionHash !== DOC_VERSION_HASH) return false;
  var pageEl = document.getElementById(memo.page);
  if (!pageEl || !pageEl.classList.contains("page")) return false;
  if (Array.isArray(memo.targets) && memo.targets.length > 0) {
    return memo.targets.every(function (t) {
      var tPage = t.page ? document.getElementById(t.page) : pageEl;
      if (!tPage || !tPage.classList.contains("page")) return false;
      return validateSingleTarget(tPage, t.compId, t.fallbackSelector);
    });
  }
  if (memo.granularity === "page" && !memo.compId && !memo.fallbackSelector) return true;
  return validateSingleTarget(pageEl, memo.compId, memo.fallbackSelector);
}

function renderMemos() {
  var toggleBtn = document.getElementById("memo-toggle-btn");
  if (toggleBtn) toggleBtn.textContent = "评审备注 (" + memos.length + ")";
  var listEl = document.getElementById("memo-list");
  if (!listEl) return;
  if (!memos.length) {
    listEl.innerHTML = '<div class="memo-empty">暂无评审备注。<br>点击「+ 新增」后，可直接点选原型组件添加 @ 胶囊。</div>';
    return;
  }
  listEl.innerHTML = memos.map(function (m, i) {
    var isValid = validateMemoAnchor(m);
    var titleLabel = m.compName
      ? ("[" + (m.node || m.page) + "] " + m.compName)
      : ("[" + (m.node || m.page) + "] " + m.page);
    var badgeHtml = isValid ? "" : '<span class="memo-invalid-badge">落点已失效</span>';
    var tagsHtml = "";
    if (Array.isArray(m.targets) && m.targets.length > 0) {
      tagsHtml = '<div class="memo-item-tags">' + m.targets.map(function (t) {
        return '<span class="memo-item-tag">@' + escapeHtml(t.compName || t.compId) + '</span>';
      }).join("") + '</div>';
    }
    var metaText = (m.granularity || "page") +
      (m.compId ? " · " + m.compId : (m.fallbackSelector ? " · " + m.fallbackSelector : ""));
    return '<div class="memo-item' + (isValid ? "" : " invalid") + '">' +
      '<div class="memo-item-hd">' +
        '<div class="memo-item-ctx" onclick="jumpToMemo(' + i + ')" title="点击定位">' + escapeHtml(titleLabel) + '</div>' +
        badgeHtml +
      '</div>' +
      tagsHtml +
      '<div class="memo-item-meta">' + escapeHtml(metaText) + '</div>' +
      '<div class="memo-item-txt">' + escapeHtml(m.text) + '</div>' +
      '<div class="memo-item-ft"><span>' + escapeHtml(m.time || "") + '</span>' +
        '<button type="button" class="memo-del-btn" onclick="deleteMemoItem(' + i + ')">删除</button></div>' +
    '</div>';
  }).join("");
}

window.jumpToMemo = function (idx) {
  var m = memos[idx];
  if (!m) return;
  if (m.vars) {
    Object.keys(m.vars).forEach(function (k) { varValues[k] = m.vars[k]; });
  }
  if (m.view === "spec" && wbView !== "spec") switchWbView("spec");
  else if (m.view === "flow" && wbView !== "flow") switchWbView("flow");
  if (m.node && NODES[m.node]) setViewByNode(m.node);
  if (m.page && PAGE_FRAME[m.page]) showPage(m.page);
  renderGlobalVars();
  renderScopedVars();
};

window.deleteMemoItem = function (idx) {
  memos.splice(idx, 1);
  persistMemos();
  renderMemos();
};

window.toggleMemo = function (force) {
  var d = document.getElementById("memo-drawer");
  if (!d) return;
  var on = force !== undefined ? force : d.classList.contains("hidden");
  d.classList.toggle("hidden", !on);
  var btn = document.getElementById("memo-toggle-btn");
  if (btn) btn.classList.toggle("active", on);
  if (!on) closeMemoForm();
};

window.openMemoForCurrent = function () {
  toggleMemo(true);
  lastPickedPageId = currentPage || "";
  hidePickOverlay();
  document.getElementById("memo-form").classList.remove("hidden");
  setMemoPickingActive(true);
  updateMemoFormCtx();
  var inp = document.getElementById("memo-input");
  if (inp) inp.focus();
};

window.closeMemoForm = function () {
  var form = document.getElementById("memo-form");
  if (form) form.classList.add("hidden");
  var inp = document.getElementById("memo-input");
  if (inp) inp.innerHTML = "";
  lastPickedPageId = "";
  setMemoPickingActive(false);
};

window.saveMemoItem = function () {
  var inp = document.getElementById("memo-input");
  var text = inp ? inp.textContent.trim() : "";
  if (!text) return;

  var targets = [];
  var seen = {};
  inp.querySelectorAll(".memo-at-chip").forEach(function (chip) {
    var cid = chip.getAttribute("data-comp-id") || "";
    var cname = chip.getAttribute("data-comp-name") || "";
    var fb = chip.getAttribute("data-fallback") || "";
    var pg = chip.getAttribute("data-page") || lastPickedPageId || currentPage || "";
    var key = (cid || fb) + "@" + pg;
    if (!(cid || fb) || seen[key]) return;
    seen[key] = true;
    targets.push({
      page: pg,
      compId: cid,
      compName: cname,
      fallbackSelector: fb
    });
  });

  var pageId = (targets[0] && targets[0].page) || lastPickedPageId || currentPage || "";
  var gran = targets.length > 0 ? "component" : "page";
  var compId = targets.map(function (t) { return t.compId; }).filter(Boolean).join(", ");
  var compName = targets.length > 0
    ? targets.map(function (t) { return "@" + t.compName; }).join(" ")
    : pageId;
  var fallbackSel = targets.map(function (t) { return t.fallbackSelector; }).filter(Boolean).join(", ");

  var now = new Date();
  var timeStr = now.toTimeString().slice(0, 5);

  memos.unshift({
    id: "m_" + Date.now(),
    versionHash: DOC_VERSION_HASH,
    view: wbView,
    node: currentNode || "",
    page: pageId,
    vars: Object.assign({}, varValues),
    granularity: gran,
    compId: compId,
    compName: compName,
    targets: targets,
    fallbackSelector: fallbackSel,
    text: text,
    time: timeStr
  });
  inp.innerHTML = "";
  persistMemos();
  closeMemoForm();
  renderMemos();
};

var memoInputEl = document.getElementById("memo-input");
if (memoInputEl) {
  memoInputEl.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      saveMemoItem();
    }
  });
  memoInputEl.addEventListener("input", function () {
    if (memoInputEl.innerHTML === "<br>" || memoInputEl.innerHTML === "<br/>") {
      memoInputEl.innerHTML = "";
    }
  });
}

function buildMemosMarkdown(items) {
  var validCount = items.filter(function (m) { return validateMemoAnchor(m); }).length;
  var invalidCount = items.length - validCount;
  var lines = [
    "---",
    "project: " + (META.project || "walkthrough"),
    "version_hash: " + DOC_VERSION_HASH,
    "exported_at: " + new Date().toISOString(),
    "total_comments: " + items.length,
    "valid_count: " + validCount,
    "invalid_count: " + invalidCount,
    "---",
    "",
    "# 评审反馈记录（Review Feedback）",
    ""
  ];
  items.forEach(function (m, idx) {
    var valid = validateMemoAnchor(m);
    var statusStr = valid ? "valid" : "invalid";
    lines.push("## [FB-" + String(idx + 1).padStart(3, "0") + "] " + (m.compName || m.page || m.node) + "（" + statusStr + "）");
    if (!valid) {
      lines.push("");
      lines.push("> [!WARNING] 落点已失效");
      lines.push("> 该条批注在当前原型中未命中目标组件或版本指纹不匹配，请人工核对。");
    }
    lines.push("");
    lines.push("- **version_hash**: `" + DOC_VERSION_HASH + "`");
    lines.push("- **status**: `" + statusStr + "`");
    lines.push("- **view**: `" + (m.view || "flow") + "`");
    lines.push("- **node**: `" + (m.node || "") + "`");
    lines.push("- **page**: `" + (m.page || "") + "`");
    lines.push("- **vars**: `" + JSON.stringify(m.vars || {}) + "`");
    lines.push("- **granularity**: `" + (m.granularity || "page") + "`");
    lines.push("- **comp_id**: `" + (m.compId || "") + "`");
    lines.push("- **comp_name**: `" + (m.compName || "") + "`");
    if (Array.isArray(m.targets) && m.targets.length > 0) {
      lines.push("- **targets**: `" + JSON.stringify(m.targets) + "`");
    }
    lines.push("- **fallback_selector**: `" + (m.fallbackSelector || "") + "`");
    lines.push("");
    lines.push("**修改意见**：");
    lines.push(m.text);
    lines.push("");
    lines.push("---");
    lines.push("");
  });
  return lines.join("\\n");
}

function buildMemosJsonl(items) {
  return items.map(function (m) {
    var valid = validateMemoAnchor(m);
    return JSON.stringify({
      version_hash: DOC_VERSION_HASH,
      status: valid ? "valid" : "invalid",
      view: m.view || "flow",
      node: m.node || "",
      page: m.page || "",
      vars: m.vars || {},
      granularity: m.granularity || "page",
      comp_id: m.compId || "",
      comp_name: m.compName || "",
      targets: m.targets || [],
      fallback_selector: m.fallbackSelector || "",
      text: m.text || "",
      time: m.time || ""
    });
  }).join("\\n");
}

var pendingExportAction = null;
function runWithExportGuard(actionType) {
  if (!memos.length) {
    alert("当前没有可导出的评审备注。");
    return;
  }
  renderMemos();
  var invalidCount = memos.filter(function (m) { return !validateMemoAnchor(m); }).length;
  var validCount = memos.length - invalidCount;
  if (invalidCount > 0) {
    pendingExportAction = actionType;
    document.getElementById("export-guard-msg").textContent =
      "检测到 " + invalidCount + " 条备注的原型落点已失效（可能因页面或组件结构变更），共 " + validCount + " 条有效备注。建议先删除失效备注，或选择仅导出有效备注。";
    var validBtn = document.getElementById("export-valid-only-btn");
    validBtn.disabled = validCount === 0;
    validBtn.textContent = "仅导出有效备注 (" + validCount + " 条)";
    document.getElementById("export-guard-modal").classList.remove("hidden");
    return;
  }
  executeExport(actionType, memos);
}

window.closeExportGuard = function () {
  pendingExportAction = null;
  document.getElementById("export-guard-modal").classList.add("hidden");
};

window.confirmExportValidOnly = function () {
  var actionType = pendingExportAction;
  closeExportGuard();
  var validItems = memos.filter(function (m) { return validateMemoAnchor(m); });
  if (!validItems.length || !actionType) return;
  executeExport(actionType, validItems);
};

function triggerDownload(content, mimeType, filename) {
  var blob = new Blob([content], { type: mimeType });
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function fallbackCopyText(text) {
  var ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand("copy"); } catch (e) {}
  document.body.removeChild(ta);
}

function executeExport(actionType, items) {
  if (actionType === "download_jsonl") {
    triggerDownload(buildMemosJsonl(items), "application/x-ndjson;charset=utf-8", "review-feedback.jsonl");
    return;
  }
  var md = buildMemosMarkdown(items);
  if (actionType === "copy") {
    var btn = document.getElementById("copy-md-btn");
    var done = function () {
      if (btn) {
        var orig = btn.textContent;
        btn.textContent = "已复制";
        setTimeout(function () { btn.textContent = orig; }, 1500);
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(md).then(done, function () { fallbackCopyText(md); done(); });
    } else {
      fallbackCopyText(md);
      done();
    }
  } else if (actionType === "download") {
    triggerDownload(md, "text/markdown;charset=utf-8", "review-feedback.md");
  }
}

window.copyMemosMd = function () { runWithExportGuard("copy"); };
window.downloadMemosMd = function () { runWithExportGuard("download"); };
window.downloadMemosJsonl = function () { runWithExportGuard("download_jsonl"); };

function applyHashState() {
  isRestoringHash = true;
  try {
    var parsed = parseUrlHash();
    var initNode = parsed.node || ENTRY_NODE;
    setViewByNode(initNode);
    if (parsed.view && parsed.view !== wbView && SPEC_CARDS && SPEC_CARDS.length) {
      switchWbView(parsed.view);
    }
  } finally {
    isRestoringHash = false;
  }
  syncUrlHash();
}

window.addEventListener("hashchange", applyHashState);

initSpecMode();
renderMemos();
fitBootZoom();
applyHashState();
"""


def compile_walkthrough(
    spec_path: Path,
    svg_path: Path,
    pages_dir: Path,
    out_path: Path,
    theme_path: Optional[Path] = None,
) -> None:
    """Compile spec.json, flow.svg, and page HTML fragments into a single walkthrough.html."""
    spec = _load_spec(spec_path)
    svg_html = _load_svg(svg_path)

    custom_theme_block = ""
    if theme_path is not None:
        if not theme_path.is_file():
            raise FileNotFoundError(f"Theme CSS file not found: {theme_path}")
        theme_css = theme_path.read_text(encoding="utf-8").strip()
        if theme_css:
            safe_theme_css = re.sub(r"</style", r"<\/style", theme_css, flags=re.IGNORECASE)
            custom_theme_block = f'\n<style id="custom-theme">\n{safe_theme_css}\n</style>'

    meta = spec.get("meta", {})
    title = str(meta.get("title") or meta.get("project") or "交互走查工作台")
    nodes = spec["nodes"]
    vars_list = spec["vars"]
    pages = spec["pages"]
    state_groups = spec.get("state_groups") or {}
    spec_cards = spec.get("spec_cards") or []
    initial_memos = spec.get("memos") or []

    entry_node = meta.get("entry_node")
    if not entry_node or entry_node not in nodes:
        entry_node = next(iter(nodes.keys()))

    phone_pages_html, wide_pages_html, page_frame = _build_pages_html(pages, pages_dir)

    escaped_title = html.escape(title)
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escaped_title}</title>
<style>
{WB_CSS}
{WT_WIREFRAME_CSS}
</style>{custom_theme_block}
</head>
<body>

<header class="wb-topbar">
  <div class="fp-title">{escaped_title}</div>
  <div class="seg-group hidden" id="view-switch">
    <button type="button" class="seg-btn active" data-wbview="flow" onclick="switchWbView('flow')">全局流程</button>
    <button type="button" class="seg-btn" data-wbview="spec" onclick="switchWbView('spec')">单页改点</button>
  </div>
  <div class="wb-global-vars" id="global-vars-bar"></div>
  <div class="topbar-spacer"></div>
  <span id="flow-node-ref" aria-live="polite"></span>
  <div class="fp-bar" id="zoom-bar">
    <span class="zb" onclick="setZoom(-1)">&#65293;</span>
    <span class="zv" id="zv">100%</span>
    <span class="zb" onclick="setZoom(1)">&#65291;</span>
    <span class="zb" onclick="setZoom(0)">适宽</span>
    <span class="zb" id="fs-btn" onclick="toggleFs()">全屏画布</span>
  </div>
  <button type="button" class="memo-toggle" id="memo-toggle-btn" onclick="toggleMemo()">评审备注 (0)</button>
</header>

<div class="wb-stage">
  <aside class="flow-panel" id="flow-panel-root">
    <div class="flow-svg" id="flow-svg"><div class="flow-canvas-inner" id="flow-canvas-inner">{svg_html}</div></div>
    <div class="inspector-drawer" id="inspector-drawer">
      <div class="insp-head">
        <span class="insp-badge" id="insp-node-id"></span>
        <span id="anno-node-title"></span>
        <button type="button" onclick="openMemoForCurrent()">+ 记备注</button>
        <button type="button" onclick="toggleFs(true)">收起 ✕</button>
      </div>
      <div class="insp-body">
        <div class="stage" id="flow-stage">
          <div class="frame-phone" id="frame-phone">
{phone_pages_html}
          </div>
          <div class="frame-wide hidden" id="frame-wide">
{wide_pages_html}
          </div>
        </div>
        <aside class="anno-panel">
          <div class="anno-card hidden" id="vars-card">
            <div class="anno-card-title">条件与局部控制</div>
            <div id="vars-body"></div>
          </div>
          <div class="anno-card hidden" id="state-card">
            <div class="anno-card-title">页面状态切换</div>
            <div id="state-body"></div>
          </div>
          <div class="anno-card">
            <div class="anno-card-title">当前节点规则</div>
            <div id="anno-body"></div>
          </div>
        </aside>
      </div>
    </div>
  </aside>

  <section class="spec-panel hidden" id="spec-panel-root">
    <div class="spec-ws" id="spec-ws">
      <svg class="tether-svg" id="tether-svg"></svg>
      <div class="anchor-box hidden" id="anchor-box"></div>
      <div class="spec-sticky" id="spec-stage-slot"></div>
      <div class="spec-cards" id="spec-cards"></div>
    </div>
  </section>

  <aside class="memo-drawer hidden" id="memo-drawer">
    <div class="memo-hd">
      <b>评审备注</b>
      <button type="button" onclick="openMemoForCurrent()">+ 新增</button>
    </div>
    <div class="memo-form hidden" id="memo-form">
      <div class="memo-ctx" id="memo-ctx"></div>
      <div id="memo-input" class="memo-editor" contenteditable="true" data-placeholder="记录评审结论或待确认项，可直接点选原型插入 @组件（Cmd/Ctrl+Enter 保存）"></div>
      <div style="display:flex;justify-content:flex-end;gap:6px">
        <button type="button" onclick="closeMemoForm()">取消</button>
        <button type="button" class="primary" onclick="saveMemoItem()">保存</button>
      </div>
    </div>
    <div class="memo-list" id="memo-list"></div>
    <div class="memo-export">
      <button type="button" id="copy-md-btn" onclick="copyMemosMd()">复制 MD</button>
      <button type="button" class="primary" onclick="downloadMemosMd()">导出 .md</button>
      <button type="button" onclick="downloadMemosJsonl()">导出 .jsonl</button>
    </div>
  </aside>
</div>

<div id="pick-highlight-overlay"></div>
<div id="pick-label-badge"></div>

<div class="guard-mask hidden" id="export-guard-modal">
  <div class="guard-modal">
    <h3>存在落点已失效的备注</h3>
    <p id="export-guard-msg"></p>
    <div class="guard-actions">
      <button type="button" onclick="closeExportGuard()">取消（去处理）</button>
      <button type="button" class="primary" id="export-valid-only-btn" onclick="confirmExportValidOnly()">仅导出有效备注</button>
    </div>
  </div>
</div>

<script>
var META = {_json_for_script(meta)};
var ENTRY_NODE = {_json_for_script(entry_node)};
var NODES = {_json_for_script(nodes)};
var PAGE_FRAME = {_json_for_script(page_frame)};
var STATE_GROUPS = {_json_for_script(state_groups)};
var VARS = {_json_for_script(vars_list)};
var SPEC_CARDS = {_json_for_script(spec_cards)};
var INITIAL_MEMOS = {_json_for_script(initial_memos)};
{ENGINE_JS}
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic single-file walkthrough.html compiler for spec-v2 projects."
    )
    parser.add_argument("--spec", required=True, help="Path to spec.json (spec-v2)")
    parser.add_argument("--svg", required=True, help="Path to flow.svg")
    parser.add_argument("--pages-dir", required=True, help="Directory containing <page_id>.html fragments")
    parser.add_argument("--out", required=True, help="Output path for walkthrough.html")
    parser.add_argument(
        "--theme",
        required=False,
        default=None,
        help="Optional path to theme.css to inline into <style id=\"custom-theme\"> and override --wt-* variables",
    )
    args = parser.parse_args()

    try:
        compile_walkthrough(
            spec_path=Path(args.spec),
            svg_path=Path(args.svg),
            pages_dir=Path(args.pages_dir),
            out_path=Path(args.out),
            theme_path=Path(args.theme) if args.theme else None,
        )
    except Exception as exc:
        print(f"[build_walkthrough] Error: {exc}", file=sys.stderr)
        return 1

    print(f"[build_walkthrough] Built {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
