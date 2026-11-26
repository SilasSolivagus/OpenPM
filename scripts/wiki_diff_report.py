#!/usr/bin/env python3
"""OpenPM Wiki Sync Diff Report Generator.

Generates self-contained, single-file HTML diff reports (Confluence / GitHub PR
style) with unified diff hunks, intraline character/substring highlighting,
summary counters, changed-pages index, and non-selectable line numbers.

Pure Python standard library — zero third-party dependencies.
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ADAPTER_BADGES: Dict[str, str] = {
    "confluence": "Confluence",
    "wecom": "WeCom",
    "feishu": "Feishu",
    "local-obsidian": "Local",
}


def _splitlines(text: str) -> List[str]:
    if not text:
        return []
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines()


def _intraline_highlight_pair(old_line: str, new_line: str) -> Tuple[str, str]:
    """Compute intraline character/substring diff spans with strict HTML escaping."""
    sm = difflib.SequenceMatcher(None, old_line, new_line, autojunk=False)
    del_parts: List[str] = []
    ins_parts: List[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            sub = old_line[i1:i2]
            if sub:
                esc = html.escape(sub, quote=True)
                del_parts.append(esc)
                ins_parts.append(esc)
        else:
            old_sub = old_line[i1:i2]
            new_sub = new_line[j1:j2]
            if old_sub:
                del_parts.append(
                    f'<span class="hl-del">{html.escape(old_sub, quote=True)}</span>'
                )
            if new_sub:
                ins_parts.append(
                    f'<span class="hl-ins">{html.escape(new_sub, quote=True)}</span>'
                )
    return "".join(del_parts), "".join(ins_parts)


def build_diff_entry(
    title: str,
    old_text: str,
    new_text: str,
    page_id: str = "",
    old_label: str = "old",
    new_label: str = "new",
    remote_url: str = "",
    remote_badge: str = "Confluence",
    force_status: Optional[str] = None,
    context_lines: int = 3,
) -> Dict[str, Any]:
    """Build a structured diff entry with grouped unified hunks and intraline spans."""
    old_text = old_text or ""
    new_text = new_text or ""

    if force_status:
        status = force_status
    elif not old_text.strip() and new_text.strip():
        status = "added"
    elif old_text.strip() and not new_text.strip():
        status = "removed"
    elif old_text == new_text:
        status = "unchanged"
    else:
        status = "updated"

    old_lines = [] if (status == "added" and not old_text.strip()) else _splitlines(old_text)
    new_lines = [] if (status == "removed" and not new_text.strip()) else _splitlines(new_text)

    if force_status is None and status == "updated" and old_lines == new_lines:
        status = "unchanged"

    hunks: List[Dict[str, Any]] = []
    added_lines = 0
    removed_lines = 0

    if status != "unchanged" and (old_lines or new_lines):
        sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        for group in sm.get_grouped_opcodes(n=context_lines):
            if not group:
                continue
            first, last = group[0], group[-1]
            old_len = last[2] - first[1]
            new_len = last[4] - first[3]
            old_start = (first[1] + 1) if old_len > 0 else first[1]
            new_start = (first[3] + 1) if new_len > 0 else first[3]
            header = f"@@ -{old_start},{old_len} +{new_start},{new_len} @@"

            hunk_rows: List[Dict[str, Any]] = []
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for offset in range(i2 - i1):
                        hunk_rows.append(
                            {
                                "type": "ctx",
                                "old_no": i1 + offset + 1,
                                "new_no": j1 + offset + 1,
                                "prefix": " ",
                                "html": html.escape(old_lines[i1 + offset], quote=True),
                            }
                        )
                elif tag == "delete":
                    for idx in range(i1, i2):
                        removed_lines += 1
                        hunk_rows.append(
                            {
                                "type": "del",
                                "old_no": idx + 1,
                                "new_no": None,
                                "prefix": "-",
                                "html": html.escape(old_lines[idx], quote=True),
                            }
                        )
                elif tag == "insert":
                    for idx in range(j1, j2):
                        added_lines += 1
                        hunk_rows.append(
                            {
                                "type": "ins",
                                "old_no": None,
                                "new_no": idx + 1,
                                "prefix": "+",
                                "html": html.escape(new_lines[idx], quote=True),
                            }
                        )
                elif tag == "replace":
                    del_chunk = old_lines[i1:i2]
                    ins_chunk = new_lines[j1:j2]
                    pair_n = min(len(del_chunk), len(ins_chunk))
                    paired_del_html: List[str] = []
                    paired_ins_html: List[str] = []
                    for k in range(pair_n):
                        d_h, i_h = _intraline_highlight_pair(del_chunk[k], ins_chunk[k])
                        paired_del_html.append(d_h)
                        paired_ins_html.append(i_h)

                    for k, raw_line in enumerate(del_chunk):
                        removed_lines += 1
                        line_html = (
                            paired_del_html[k]
                            if k < pair_n
                            else html.escape(raw_line, quote=True)
                        )
                        hunk_rows.append(
                            {
                                "type": "del",
                                "old_no": i1 + k + 1,
                                "new_no": None,
                                "prefix": "-",
                                "html": line_html,
                            }
                        )
                    for k, raw_line in enumerate(ins_chunk):
                        added_lines += 1
                        line_html = (
                            paired_ins_html[k]
                            if k < pair_n
                            else html.escape(raw_line, quote=True)
                        )
                        hunk_rows.append(
                            {
                                "type": "ins",
                                "old_no": None,
                                "new_no": j1 + k + 1,
                                "prefix": "+",
                                "html": line_html,
                            }
                        )

            hunks.append({"header": header, "lines": hunk_rows})

    return {
        "title": title,
        "page_id": str(page_id or "").strip(),
        "old_label": old_label,
        "new_label": new_label,
        "remote_url": str(remote_url or "").strip(),
        "remote_badge": str(remote_badge or "Confluence").strip(),
        "status": status,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "hunks": hunks,
    }


def _format_entry_transition(entry: Dict[str, Any]) -> str:
    title = html.escape(str(entry.get("title") or "Untitled"), quote=True)
    page_id = str(entry.get("page_id") or "").strip()
    old_label = html.escape(str(entry.get("old_label") or "old"), quote=True)
    new_label = html.escape(str(entry.get("new_label") or "new"), quote=True)
    if page_id:
        pid_esc = html.escape(page_id, quote=True)
        return f"{title} ({pid_esc}) {old_label} → {title} ({pid_esc}) {new_label}"
    return f"{title} {old_label} → {title} {new_label}"


def _safe_external_url(url: str) -> str:
    cleaned = (url or "").strip()
    if cleaned.startswith(("http://", "https://")):
        return html.escape(cleaned, quote=True)
    return ""


_REPORT_CSS = """\
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0;
  background: #ffffff;
  color: #24292e;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 1.5;
}
.container {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 28px 64px;
}
h1 {
  margin: 0 0 12px;
  font-size: 24px;
  font-weight: 600;
  color: #1f2328;
  border-bottom: 1px solid #d0d7de;
  padding-bottom: 10px;
}
h2 {
  margin: 28px 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2328;
}
.meta-lines {
  margin: 0 0 16px;
  color: #57606a;
  font-size: 13px;
  line-height: 1.75;
}
.meta-lines code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background: #f6f8fa;
  border: 1px solid #eaeef2;
  border-radius: 4px;
  padding: 1px 6px;
  color: #24292e;
  font-size: 12px;
}
.summary-table, .changed-table {
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 8px;
}
.summary-table {
  min-width: 240px;
}
.changed-table {
  width: 100%;
}
.summary-table th, .summary-table td,
.changed-table th, .changed-table td {
  border: 1px solid #d0d7de;
  padding: 6px 12px;
  text-align: left;
}
.summary-table th, .changed-table th {
  background: #f6f8fa;
  font-weight: 600;
  color: #24292e;
}
.summary-table td:last-child {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.changed-table td.col-idx {
  width: 48px;
  color: #57606a;
  font-variant-numeric: tabular-nums;
}
.changed-table td.col-type {
  width: 110px;
}
.changed-table td.col-add, .changed-table td.col-del {
  width: 72px;
  text-align: right;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.changed-table td.col-add { color: #1a7f37; }
.changed-table td.col-del { color: #cf222e; }
.changed-table a {
  color: #0969da;
  text-decoration: none;
  font-weight: 500;
}
.changed-table a:hover {
  text-decoration: underline;
}
.empty-row {
  color: #57606a;
  text-align: center !important;
  padding: 14px !important;
  background: #f6f8fa;
}
.type-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-transform: capitalize;
  border: 1px solid transparent;
}
.type-added { background: #dafbe1; color: #1a7f37; border-color: #aceebb; }
.type-updated { background: #ddf4ff; color: #0969da; border-color: #9cd7ff; }
.type-removed { background: #ffebe9; color: #cf222e; border-color: #ffcecb; }
.type-moved { background: #fff8c5; color: #9a6700; border-color: #eac54f; }
.files-changed-box {
  border: 1px solid #d0d7de;
  border-radius: 6px;
  background: #ffffff;
  margin-bottom: 18px;
  overflow: hidden;
}
.files-changed-hd {
  background: #f6f8fa;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #d0d7de;
  color: #24292e;
}
.files-changed-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.files-changed-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 14px;
  border-bottom: 1px solid #eaeef2;
  font-size: 13px;
}
.files-changed-list li:last-child {
  border-bottom: none;
}
.fc-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.fc-icon {
  flex-shrink: 0;
  color: #57606a;
  display: inline-flex;
  align-items: center;
}
.fc-link {
  color: #24292e;
  text-decoration: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "PingFang SC", monospace;
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fc-link:hover {
  color: #0969da;
  text-decoration: underline;
}
.fc-stats {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
}
.stat-add {
  background: #e6ffed;
  color: #1a7f37;
  border: 1px solid #aceebb;
  border-radius: 4px;
  padding: 1px 6px;
}
.stat-del {
  background: #ffeef0;
  color: #cf222e;
  border: 1px solid #ffcecb;
  border-radius: 4px;
  padding: 1px 6px;
}
details.diff-card {
  border: 1px solid #d0d7de;
  border-radius: 6px;
  margin-bottom: 20px;
  background: #ffffff;
  overflow: hidden;
}
summary.diff-card-hd {
  list-style: none;
  cursor: pointer;
  background: #f6f8fa;
  padding: 9px 14px;
  border-bottom: 1px solid #d0d7de;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "PingFang SC", monospace;
  font-size: 12.5px;
  font-weight: 600;
  color: #24292e;
}
summary.diff-card-hd::-webkit-details-marker {
  display: none;
}
details.diff-card:not([open]) summary.diff-card-hd {
  border-bottom: none;
}
.diff-hd-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.chevron {
  display: inline-block;
  font-size: 10px;
  color: #57606a;
  transition: transform 0.12s ease;
  user-select: none;
}
details.diff-card[open] .chevron {
  transform: rotate(90deg);
}
.diff-hd-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
a.ext-badge {
  display: inline-block;
  padding: 2px 8px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 11.5px;
  font-weight: 600;
  color: #0969da;
  background: #ffffff;
  border: 1px solid #d0d7de;
  border-radius: 4px;
  text-decoration: none;
}
a.ext-badge:hover {
  background: #f3f4f6;
  border-color: #0969da;
}
.diff-table-wrap {
  width: 100%;
  overflow-x: auto;
}
table.diff-table {
  width: 100%;
  border-collapse: collapse;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "PingFang SC", monospace;
  font-size: 12.5px;
  line-height: 20px;
}
table.diff-table td {
  padding: 0;
  vertical-align: top;
}
table.diff-table td.ln {
  width: 48px;
  min-width: 48px;
  padding: 0 8px;
  text-align: right;
  color: rgba(27, 31, 35, 0.35);
  border-right: 1px solid #eaeef2;
  user-select: none;
  -webkit-user-select: none;
  font-variant-numeric: tabular-nums;
}
table.diff-table td.sign {
  width: 22px;
  min-width: 22px;
  text-align: center;
  color: #57606a;
  user-select: none;
  -webkit-user-select: none;
}
table.diff-table td.code {
  padding: 0 12px 0 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
tr.hunk-row {
  background: #f1f8ff;
  color: #0366d6;
}
tr.hunk-row td.ln-hunk {
  background: #dbedff;
  color: #586069;
  text-align: center;
}
tr.hunk-row td.hunk-cell {
  padding: 4px 10px;
  color: #0366d6;
  font-weight: 500;
  user-select: none;
  -webkit-user-select: none;
}
tr.line-ctx {
  background: #ffffff;
}
tr.line-del {
  background: #ffeef0;
}
tr.line-del td.ln {
  background: #ffdce0;
  color: rgba(27, 31, 35, 0.5);
}
tr.line-del td.sign {
  color: #cf222e;
}
tr.line-ins {
  background: #e6ffed;
}
tr.line-ins td.ln {
  background: #cdffd8;
  color: rgba(27, 31, 35, 0.5);
}
tr.line-ins td.sign {
  color: #1a7f37;
}
span.hl-del {
  background: #fdb8c0;
  border-radius: 2px;
}
span.hl-ins {
  background: #acf2bd;
  border-radius: 2px;
}
.no-diff-note {
  padding: 16px;
  color: #57606a;
  font-size: 13px;
  text-align: center;
}
"""

_FILE_SVG = (
    '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">'
    '<path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914'
    "c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 "
    "14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 "
    '.25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688'
    'l-.011-.013-2.914-2.914-.013-.011Z"></path></svg>'
)


def render_diff_report_html(
    entries: Sequence[Dict[str, Any]],
    report_title: str = "Wiki Sync Diff Report",
    run_id: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    subtitle_meta: Optional[str] = None,
) -> str:
    """Render a self-contained HTML diff report from structured diff entries."""
    now_utc = datetime.now(timezone.utc)
    run_id_val = run_id or now_utc.strftime("%Y-%m-%dT%H-%M-%SZ")
    iso_val = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_val = started_at or iso_val
    finished_val = finished_at or iso_val

    total = len(entries)
    added_cnt = sum(1 for e in entries if e.get("status") == "added")
    updated_cnt = sum(1 for e in entries if e.get("status") == "updated")
    moved_cnt = sum(1 for e in entries if e.get("status") == "moved")
    removed_cnt = sum(1 for e in entries if e.get("status") == "removed")
    unchanged_cnt = sum(1 for e in entries if e.get("status") == "unchanged")
    failed_cnt = sum(1 for e in entries if e.get("status") == "failed")

    changed_entries = [
        e for e in entries if e.get("status") not in ("unchanged", "failed")
    ]
    changed_cnt = len(changed_entries)

    title_esc = html.escape(report_title, quote=True)
    run_esc = html.escape(run_id_val, quote=True)
    start_esc = html.escape(started_val, quote=True)
    finish_esc = html.escape(finished_val, quote=True)
    subtitle_line = (
        f"<div><strong>Context:</strong> {html.escape(subtitle_meta, quote=True)}</div>"
        if subtitle_meta
        else ""
    )

    changed_rows_html: List[str] = []
    if changed_entries:
        for idx, entry in enumerate(changed_entries, start=1):
            st = str(entry.get("status") or "updated")
            st_esc = html.escape(st, quote=True)
            add_n = int(entry.get("added_lines") or 0)
            del_n = int(entry.get("removed_lines") or 0)
            e_title = html.escape(str(entry.get("title") or "Untitled"), quote=True)
            changed_rows_html.append(
                f"<tr>"
                f'<td class="col-idx">{idx}</td>'
                f'<td class="col-type"><span class="type-badge type-{st_esc}">{st_esc}</span></td>'
                f'<td class="col-add">+{add_n}</td>'
                f'<td class="col-del">-{del_n}</td>'
                f'<td><a href="#diff-{idx}">{e_title}</a></td>'
                f"</tr>"
            )
    else:
        changed_rows_html.append(
            '<tr><td colspan="5" class="empty-row">'
            "0 changed pages (all identical to baseline)"
            "</td></tr>"
        )

    fc_items_html: List[str] = []
    cards_html: List[str] = []

    for idx, entry in enumerate(changed_entries, start=1):
        label_html = _format_entry_transition(entry)
        add_n = int(entry.get("added_lines") or 0)
        del_n = int(entry.get("removed_lines") or 0)
        safe_url = _safe_external_url(str(entry.get("remote_url") or ""))
        badge_esc = html.escape(str(entry.get("remote_badge") or "Confluence"), quote=True)

        fc_items_html.append(
            f"<li>"
            f'<span class="fc-left"><span class="fc-icon">{_FILE_SVG}</span>'
            f'<a class="fc-link" href="#diff-{idx}">{label_html}</a></span>'
            f'<span class="fc-stats">'
            f'<span class="stat-add">+{add_n}</span>'
            f'<span class="stat-del">-{del_n}</span>'
            f"</span>"
            f"</li>"
        )

        ext_html = (
            f'<a class="ext-badge" href="{safe_url}" target="_blank" '
            f'rel="noopener" onclick="event.stopPropagation()">{badge_esc}</a>'
            if safe_url
            else ""
        )

        hunks = entry.get("hunks") or []
        if hunks:
            row_buf: List[str] = []
            for hunk in hunks:
                h_hdr = html.escape(str(hunk.get("header") or ""), quote=True)
                row_buf.append(
                    f'<tr class="hunk-row">'
                    f'<td class="ln ln-hunk">...</td>'
                    f'<td class="ln ln-hunk">...</td>'
                    f'<td class="hunk-cell" colspan="2">{h_hdr}</td>'
                    f"</tr>"
                )
                for ln in hunk.get("lines") or []:
                    ltype = ln.get("type", "ctx")
                    old_no = "" if ln.get("old_no") is None else str(ln["old_no"])
                    new_no = "" if ln.get("new_no") is None else str(ln["new_no"])
                    prefix = html.escape(str(ln.get("prefix") or " "), quote=True)
                    code_html = ln.get("html") or ""
                    row_cls = (
                        "line-del"
                        if ltype == "del"
                        else ("line-ins" if ltype == "ins" else "line-ctx")
                    )
                    row_buf.append(
                        f'<tr class="{row_cls}">'
                        f'<td class="ln">{old_no}</td>'
                        f'<td class="ln">{new_no}</td>'
                        f'<td class="sign">{prefix}</td>'
                        f'<td class="code">{code_html}</td>'
                        f"</tr>"
                    )
            body_html = (
                f'<div class="diff-table-wrap">'
                f'<table class="diff-table"><tbody>{"".join(row_buf)}</tbody></table>'
                f"</div>"
            )
        else:
            body_html = '<div class="no-diff-note">No textual line changes</div>'

        cards_html.append(
            f'<details class="diff-card" id="diff-{idx}" open>'
            f'<summary class="diff-card-hd">'
            f'<span class="diff-hd-left"><span class="chevron">&#9654;</span>'
            f'<span class="diff-card-title">{label_html}</span></span>'
            f'<span class="diff-hd-right">'
            f'<span class="stat-add">+{add_n}</span>'
            f'<span class="stat-del">-{del_n}</span>'
            f"{ext_html}"
            f"</span>"
            f"</summary>"
            f"{body_html}"
            f"</details>"
        )

    if not fc_items_html:
        fc_items_html.append(
            '<li style="color:#57606a;justify-content:center;">No files changed</li>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<style>
{_REPORT_CSS}
</style>
</head>
<body>
<div class="container">
  <h1>{title_esc}</h1>
  <div class="meta-lines">
    <div><strong>Run:</strong> <code>{run_esc}</code></div>
    <div><strong>Time:</strong> {start_esc} → {finish_esc}</div>
    <div>Total: {total} pages | Changed: {changed_cnt} | Unchanged: {unchanged_cnt} | Failed: {failed_cnt}</div>
    {subtitle_line}
  </div>

  <table class="summary-table">
    <thead>
      <tr><th>Type</th><th>Count</th></tr>
    </thead>
    <tbody>
      <tr><td>Added</td><td>{added_cnt}</td></tr>
      <tr><td>Updated</td><td>{updated_cnt}</td></tr>
      <tr><td>Moved</td><td>{moved_cnt}</td></tr>
      <tr><td>Removed</td><td>{removed_cnt}</td></tr>
    </tbody>
  </table>

  <h2>Changed Pages</h2>
  <table class="changed-table">
    <thead>
      <tr><th>#</th><th>Type</th><th>+</th><th>-</th><th>Title</th></tr>
    </thead>
    <tbody>
      {"".join(changed_rows_html)}
    </tbody>
  </table>

  <h2>Diffs</h2>
  <div class="files-changed-box">
    <div class="files-changed-hd">Files changed ({changed_cnt})</div>
    <ul class="files-changed-list">
      {"".join(fc_items_html)}
    </ul>
  </div>

  {"".join(cards_html)}
</div>
</body>
</html>
"""


def _strip_yaml_scalar(raw: str) -> str:
    val = raw.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1].strip()
    # Strip trailing inline comment when unquoted
    val = re.sub(r"\s+#.*$", "", val).strip()
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1].strip()
    return val


def _parse_frontmatter(md_text: str) -> Dict[str, Any]:
    lines = _splitlines(md_text)
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}

    data: Dict[str, Any] = {}
    current_section: Optional[str] = None
    for raw_line in lines[1:end_idx]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent >= 2 and current_section and isinstance(data.get(current_section), dict):
            if ":" in raw_line:
                k, v = raw_line.strip().split(":", 1)
                data[current_section][k.strip()] = _strip_yaml_scalar(v)
            continue
        if ":" in raw_line:
            k, v = raw_line.split(":", 1)
            key = k.strip()
            cleaned_v = _strip_yaml_scalar(v)
            if cleaned_v == "":
                data[key] = {}
                current_section = key
            else:
                data[key] = cleaned_v
                current_section = None
    return data


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _extract_md_h1(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        for line in _splitlines(path.read_text(encoding="utf-8")):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    except Exception:
        pass
    return ""


def _read_env_base_url(project_dir: Path) -> str:
    candidates = [
        project_dir / ".env.local",
        project_dir.parent / ".env.local",
        project_dir.parent.parent / ".env.local",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        try:
            for line in _splitlines(env_path.read_text(encoding="utf-8")):
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() == "WIKI_BASE_URL":
                    return _strip_yaml_scalar(v)
        except Exception:
            continue
    return ""


def _load_project_meta(project_dir: Path) -> Dict[str, Any]:
    ctx_path = project_dir / "project-context.md"
    ctx = (
        _parse_frontmatter(ctx_path.read_text(encoding="utf-8"))
        if ctx_path.is_file()
        else {}
    )
    wiki_cfg = ctx.get("wiki_config") if isinstance(ctx.get("wiki_config"), dict) else {}
    manifest = _read_json_dict(project_dir / "_manifest.json")
    spec = _read_json_dict(project_dir / "spec.json")

    def _str_field(val: Any) -> str:
        if val is None or isinstance(val, (dict, list)):
            return ""
        return str(val).strip()

    title = (
        _str_field(manifest.get("title"))
        or _str_field(manifest.get("page_title"))
        or _str_field(ctx.get("title"))
        or _str_field(spec.get("title"))
        or _str_field(spec.get("project_name"))
        or _extract_md_h1(project_dir / "prd.md")
        or project_dir.name
    )
    adapter = (
        _str_field(manifest.get("adapter"))
        or _str_field(manifest.get("wiki_adapter"))
        or _str_field(ctx.get("wiki_adapter"))
        or _str_field(ctx.get("adapter"))
        or "local-obsidian"
    ).lower()

    page_id = (
        _str_field(manifest.get("remote_page_id"))
        or _str_field(manifest.get("page_id"))
        or _str_field(manifest.get("doc_id"))
        or _str_field(ctx.get("page_id"))
        or _str_field(ctx.get("doc_id"))
        or _str_field(wiki_cfg.get("page_id"))
        or _str_field(wiki_cfg.get("doc_id"))
    )

    base_url = (
        _str_field(manifest.get("base_url"))
        or _str_field(manifest.get("wiki_base_url"))
        or _str_field(ctx.get("base_url"))
        or _str_field(ctx.get("wiki_base_url"))
        or _str_field(wiki_cfg.get("base_url"))
        or _str_field(wiki_cfg.get("wiki_base_url"))
        or _read_env_base_url(project_dir)
    )

    remote_version = (
        manifest.get("remote_version")
        or manifest.get("version")
        or _str_field(ctx.get("remote_version"))
        or _str_field(wiki_cfg.get("remote_version"))
    )

    remote_badge = ADAPTER_BADGES.get(
        adapter, adapter.capitalize() if adapter else "Wiki"
    )
    remote_url = (
        _str_field(manifest.get("remote_url"))
        or _str_field(ctx.get("remote_url"))
        or _str_field(wiki_cfg.get("remote_url"))
    )
    if not remote_url and adapter == "confluence" and base_url and page_id.isdigit():
        remote_url = f"{base_url.rstrip('/')}/pages/viewpage.action?pageId={page_id}"
        remote_badge = "Confluence"

    return {
        "title": title,
        "adapter": adapter,
        "page_id": page_id,
        "base_url": base_url,
        "remote_url": remote_url,
        "remote_badge": remote_badge,
        "remote_version": remote_version,
    }


def _build_project_entries(project_dir: Path, stage: str = "push") -> List[Dict[str, Any]]:
    meta = _load_project_meta(project_dir)
    title = meta["title"]
    page_id = meta["page_id"]
    remote_url = meta["remote_url"]
    remote_badge = meta["remote_badge"]
    remote_version = meta["remote_version"]
    ver = str(remote_version) if remote_version not in (None, "") else "1"

    history_dir = project_dir / "history"
    prd_remote_prev = history_dir / "prd-remote.prev.md"
    prd_remote = history_dir / "prd-remote.md"
    prd_v1 = project_dir / "versions" / "v1" / "prd.md"
    prd_local = project_dir / "prd.md"

    entries: List[Dict[str, Any]] = []

    if stage == "pull":
        if prd_remote_prev.is_file() and prd_remote.is_file():
            prev_text = prd_remote_prev.read_text(encoding="utf-8")
            rem_text = prd_remote.read_text(encoding="utf-8")
            if prev_text != rem_text:
                entries.append(
                    build_diff_entry(
                        title=f"{title} [远端线上变更]",
                        old_text=prev_text,
                        new_text=rem_text,
                        page_id=page_id,
                        old_label="remote-prev",
                        new_label=f"remote-v{ver}",
                        remote_url=remote_url,
                        remote_badge=remote_badge,
                    )
                )

        if prd_remote.is_file() and prd_local.is_file():
            rem_text = prd_remote.read_text(encoding="utf-8")
            loc_text = prd_local.read_text(encoding="utf-8")
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text=rem_text,
                    new_text=loc_text,
                    page_id=page_id,
                    old_label=f"remote-v{ver}",
                    new_label="local-working",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                )
            )
        elif prd_remote.is_file():
            rem_text = prd_remote.read_text(encoding="utf-8")
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text=rem_text,
                    new_text=rem_text,
                    page_id=page_id,
                    old_label=f"remote-v{ver}",
                    new_label=f"remote-v{ver}",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                )
            )
        elif prd_local.is_file():
            loc_text = prd_local.read_text(encoding="utf-8")
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text="",
                    new_text=loc_text,
                    page_id=page_id,
                    old_label="remote-none",
                    new_label="local-working",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                    force_status="added",
                )
            )
    else:
        new_text = prd_local.read_text(encoding="utf-8") if prd_local.is_file() else ""
        if prd_remote.is_file():
            old_text = prd_remote.read_text(encoding="utf-8")
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text=old_text,
                    new_text=new_text,
                    page_id=page_id,
                    old_label="remote baseline",
                    new_label="outbound final",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                )
            )
        elif prd_v1.is_file():
            old_text = prd_v1.read_text(encoding="utf-8")
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text=old_text,
                    new_text=new_text,
                    page_id=page_id,
                    old_label="v1 draft",
                    new_label="outbound final",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                )
            )
        else:
            entries.append(
                build_diff_entry(
                    title=title,
                    old_text="",
                    new_text=new_text,
                    page_id=page_id,
                    old_label="none",
                    new_label="outbound final",
                    remote_url=remote_url,
                    remote_badge=remote_badge,
                    force_status="added",
                )
            )

    return entries


def generate_project_diff_report(
    project_dir: Path,
    stage: str = "push",
    out_path: Optional[Path] = None,
) -> Path:
    """Generate a single-project pull or push HTML diff report."""
    project_dir = Path(project_dir).resolve()
    if stage not in ("pull", "push"):
        raise ValueError(f"Unsupported stage: {stage!r} (expected 'pull' or 'push')")

    started = datetime.now(timezone.utc)
    meta = _load_project_meta(project_dir)
    entries = _build_project_entries(project_dir, stage=stage)
    finished = datetime.now(timezone.utc)

    adapter = meta["adapter"]
    prefix = "Confluence" if adapter == "confluence" else "Wiki"
    report_title = (
        f"{prefix} Pull Diff Report"
        if stage == "pull"
        else f"{prefix} Push Diff Report"
    )
    ver_note = (
        f" | Remote Version: v{meta['remote_version']}"
        if meta.get("remote_version") not in (None, "")
        else ""
    )
    subtitle_meta = f"Adapter: {adapter} | Project: {project_dir.name}{ver_note}"

    html_doc = render_diff_report_html(
        entries=entries,
        report_title=report_title,
        run_id=started.strftime("%Y-%m-%dT%H-%M-%SZ"),
        started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        finished_at=finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
        subtitle_meta=subtitle_meta,
    )

    if stage == "pull":
        target_out = (
            Path(out_path).resolve()
            if out_path
            else (project_dir / "history" / "pull-diff-report.html")
        )
        target_out.parent.mkdir(parents=True, exist_ok=True)
        target_out.write_text(html_doc, encoding="utf-8")
        return target_out

    default_export_out = project_dir / "wiki-export" / "push-diff-report.html"
    target_out = Path(out_path).resolve() if out_path else default_export_out
    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(html_doc, encoding="utf-8")

    # Mirror archival copy into history/push-diff-report.html on standard project runs
    history_copy = (project_dir / "history" / "push-diff-report.html").resolve()
    if (out_path is None or target_out == default_export_out.resolve()) and (
        target_out != history_copy
    ):
        history_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target_out, history_copy)

    return target_out


def generate_batch_diff_report(
    workspace_or_projects_dir: Path,
    stage: str = "push",
    out_path: Optional[Path] = None,
) -> Path:
    """Scan all sub-projects containing prd.md and aggregate into a global diff report."""
    base_dir = Path(workspace_or_projects_dir).resolve()
    if stage not in ("pull", "push"):
        raise ValueError(f"Unsupported stage: {stage!r} (expected 'pull' or 'push')")

    scan_root = (
        base_dir / "projects"
        if (base_dir / "projects").is_dir() and not (base_dir / "prd.md").is_file()
        else base_dir
    )

    started = datetime.now(timezone.utc)
    project_dirs = sorted(
        p
        for p in scan_root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "prd.md").is_file()
    )

    all_entries: List[Dict[str, Any]] = []
    adapters_seen: List[str] = []
    for proj in project_dirs:
        p_meta = _load_project_meta(proj)
        if p_meta["adapter"] not in adapters_seen:
            adapters_seen.append(p_meta["adapter"])
        all_entries.extend(_build_project_entries(proj, stage=stage))

    finished = datetime.now(timezone.utc)
    is_confluence_only = adapters_seen == ["confluence"]
    report_title = (
        "Confluence Sync Diff Report"
        if is_confluence_only
        else f"Wiki Sync Diff Report ({stage.upper()})"
    )
    subtitle_meta = (
        f"Batch {stage} scan | Workspace: {scan_root.name} | Projects scanned: {len(project_dirs)}"
    )

    html_doc = render_diff_report_html(
        entries=all_entries,
        report_title=report_title,
        run_id=started.strftime("%Y-%m-%dT%H-%M-%SZ"),
        started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        finished_at=finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
        subtitle_meta=subtitle_meta,
    )

    target_out = (
        Path(out_path).resolve() if out_path else (scan_root / "_diff-report.html")
    )
    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(html_doc, encoding="utf-8")
    return target_out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Confluence / GitHub PR style HTML Sync Diff Report."
    )
    parser.add_argument(
        "target_path",
        help="Path to a project directory (or workspace/projects directory with --batch).",
    )
    parser.add_argument(
        "--stage",
        choices=("pull", "push"),
        default="push",
        help="Sync stage: 'pull' (remote vs local) or 'push' (baseline vs outbound final).",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Aggregate all sub-projects containing prd.md into a multi-page report.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Custom output HTML file path.",
    )
    args = parser.parse_args(argv)

    target = Path(args.target_path)
    if not target.exists():
        print(f"[ERROR] Target path does not exist: {target}", file=sys.stderr)
        return 1

    out_arg = Path(args.output) if args.output else None
    if args.batch:
        written = generate_batch_diff_report(target, stage=args.stage, out_path=out_arg)
    else:
        written = generate_project_diff_report(target, stage=args.stage, out_path=out_arg)

    print(f"[OK] Diff report written to {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
