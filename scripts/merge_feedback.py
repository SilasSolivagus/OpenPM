#!/usr/bin/env python3
"""Multi-reviewer feedback aggregator, anchor validator, and component conflict detector.

Merges multiple colleagues' exported review-feedback-*.jsonl / .md files for a project:
  1. Deduplicates identical entries while preserving each reviewer's `author` attribution;
  2. Re-validates every comment's target page & `data-comp-id` against current `pages/*.html`;
  3. Detects multi-reviewer component/page conflicts (>= 2 distinct comments targeting the same
     `page::comp_id` with different suggestions) so the AI Agent never silently overwrites one
     colleague's feedback with another's;
  4. Outputs `<project_dir>/review-merged.md` and `<project_dir>/review-merged.jsonl` partitioned into
     `AUTO_APPLY`, `CONFLICTS_NEED_PM_DECISION`, and `INVALID_ANCHORS`.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _collect_dom_anchors(project_dir: Path) -> Tuple[Set[str], Dict[str, Set[str]]]:
    pages_dir = project_dir / "pages"
    page_ids: Set[str] = set()
    anchors_by_page: Dict[str, Set[str]] = {}
    if pages_dir.is_dir():
        for html_file in sorted(pages_dir.glob("*.html")):
            pid = html_file.stem
            page_ids.add(pid)
            txt = html_file.read_text(encoding="utf-8", errors="ignore")
            cids = set(re.findall(r'\bdata-(?:comp-id|anchor)\s*=\s*["\']([^"\']+)["\']', txt))
            anchors_by_page[pid] = cids

    spec_file = project_dir / "spec.json"
    if spec_file.is_file():
        try:
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
            pages_obj = spec.get("pages") or {}
            for pid, pdef in pages_obj.items():
                page_ids.add(pid)
                if pid not in anchors_by_page and isinstance(pdef, dict):
                    base = pdef.get("variant_of")
                    if isinstance(base, str) and base in anchors_by_page:
                        anchors_by_page[pid] = set(anchors_by_page[base])
        except Exception:
            pass
    return page_ids, anchors_by_page


def _parse_md_feedback(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    fm_reviewer = ""
    m_rev = re.search(r"^\s*reviewer\s*:\s*(.+?)\s*$", raw, flags=re.MULTILINE)
    if m_rev and m_rev.group(1).strip() != "anonymous":
        fm_reviewer = m_rev.group(1).strip()
    fallback_author = fm_reviewer or re.sub(r"^review-feedback-?", "", path.stem) or "评审人"

    blocks = re.split(r"^##\s+\[", raw, flags=re.MULTILINE)
    items: List[Dict[str, Any]] = []
    for idx, blk in enumerate(blocks[1:], start=1):
        def _field(name: str) -> str:
            m = re.search(rf"^-\s+\*\*{re.escape(name)}\*\*:\s*`([^`]*)`", blk, flags=re.MULTILINE)
            return m.group(1).strip() if m else ""

        targets_str = _field("targets")
        targets: List[Dict[str, Any]] = []
        if targets_str:
            try:
                parsed_t = json.loads(targets_str)
                if isinstance(parsed_t, list):
                    targets = parsed_t
            except Exception:
                pass
        vars_str = _field("vars")
        vars_obj: Dict[str, Any] = {}
        if vars_str:
            try:
                parsed_v = json.loads(vars_str)
                if isinstance(parsed_v, dict):
                    vars_obj = parsed_v
            except Exception:
                pass

        body = ""
        if "**修改意见**：" in blk:
            after = blk.split("**修改意见**：", 1)[1]
            body = re.split(r"^---\s*$", after, flags=re.MULTILINE)[0].strip()

        author = _field("author")
        if not author or author == "anonymous":
            author = fallback_author

        items.append(
            {
                "id": _field("id") or f"{path.stem}_{idx}",
                "author": author,
                "source_file": path.name,
                "version_hash": _field("version_hash"),
                "view": _field("view") or "flow",
                "node": _field("node"),
                "page": _field("page"),
                "vars": vars_obj,
                "comp_id": _field("comp_id"),
                "comp_name": _field("comp_name"),
                "targets": targets,
                "text": body,
            }
        )
    return items


def _parse_jsonl_feedback(path: Path) -> List[Dict[str, Any]]:
    fallback_author = re.sub(r"^review-feedback-?", "", path.stem) or "评审人"
    items: List[Dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        author = str(obj.get("author") or "").strip()
        if not author or author == "anonymous":
            author = fallback_author
        obj["author"] = author
        obj["source_file"] = path.name
        obj.setdefault("id", f"{path.stem}_{idx}")
        items.append(obj)
    return items


def _validate_item(item: Dict[str, Any], page_ids: Set[str], anchors_by_page: Dict[str, Set[str]]) -> bool:
    targets = item.get("targets") or []
    page = str(item.get("page") or "").strip()
    if isinstance(targets, list) and targets:
        for t in targets:
            if not isinstance(t, dict):
                return False
            tp = str(t.get("page") or page).strip()
            cid = str(t.get("comp_id") or "").strip()
            if tp not in page_ids:
                return False
            if cid and cid not in anchors_by_page.get(tp, set()):
                return False
        return True
    return bool(page and page in page_ids)


def merge_project_feedback(project_dir: Path, input_files: List[Path]) -> Tuple[Path, Path, Dict[str, int]]:
    page_ids, anchors_by_page = _collect_dom_anchors(project_dir)

    raw_items: List[Dict[str, Any]] = []
    for f in input_files:
        if f.suffix.lower() == ".jsonl":
            raw_items.extend(_parse_jsonl_feedback(f))
        elif f.suffix.lower() == ".md" and f.name != "review-merged.md":
            raw_items.extend(_parse_md_feedback(f))

    # Deduplicate exact repeats
    deduped: List[Dict[str, Any]] = []
    seen_sigs: Set[str] = set()
    for it in raw_items:
        txt = str(it.get("text") or "").strip()
        if not txt:
            continue
        sig = f"{it.get('author')}|{it.get('page')}|{it.get('comp_id')}|{txt}"
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        it["anchor_valid"] = _validate_item(it, page_ids, anchors_by_page)
        deduped.append(it)

    # Detect component-level / node-level multi-comment conflicts among valid items
    touch_buckets: Dict[str, List[int]] = {}
    for idx, it in enumerate(deduped):
        if not it["anchor_valid"]:
            continue
        targets = it.get("targets") or []
        keys: List[str] = []
        if isinstance(targets, list) and targets:
            for t in targets:
                if isinstance(t, dict) and t.get("comp_id"):
                    keys.append(f"{t.get('page') or it.get('page')}::{t['comp_id']}")
        if not keys:
            keys.append(f"page::{it.get('page') or it.get('node') or 'unknown'}")
        for k in set(keys):
            touch_buckets.setdefault(k, []).append(idx)

    conflict_indices: Set[int] = set()
    conflict_groups: Dict[str, List[Dict[str, Any]]] = {}
    for k, idxs in touch_buckets.items():
        if len(idxs) < 2:
            continue
        distinct_texts = {str(deduped[i].get("text") or "").strip() for i in idxs}
        if len(distinct_texts) >= 2:
            for i in idxs:
                conflict_indices.add(i)
            conflict_groups[k] = [deduped[i] for i in idxs]

    auto_apply = [it for idx, it in enumerate(deduped) if it["anchor_valid"] and idx not in conflict_indices]
    invalid_items = [it for it in deduped if not it["anchor_valid"]]

    out_md = project_dir / "review-merged.md"
    out_jsonl = project_dir / "review-merged.jsonl"

    reviewers = sorted({str(it.get("author") or "评审人") for it in deduped})
    now_iso = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    md_lines = [
        "---",
        f"project: {project_dir.name}",
        f"merged_at: {now_iso}",
        f"reviewers: {json.dumps(reviewers, ensure_ascii=False)}",
        f"total_merged: {len(deduped)}",
        f"auto_apply_count: {len(auto_apply)}",
        f"conflict_group_count: {len(conflict_groups)}",
        f"invalid_anchor_count: {len(invalid_items)}",
        "---",
        "",
        "# 多人评审汇总与冲突裁决单（Merged Review Feedback）",
        "",
        "## 一、 无冲突可直接精准回写项（AUTO_APPLY）",
        "",
    ]
    if not auto_apply:
        md_lines.append("（无）\n")
    else:
        for i, it in enumerate(auto_apply, start=1):
            md_lines.append(
                f"{i}. **[{it.get('author')}]** 页面 `{it.get('page')}` · 组件 `{it.get('comp_id') or '整页'}`（{it.get('comp_name') or '-'}）：{it.get('text')}"
            )
        md_lines.append("")

    md_lines.append("## 二、 多人同组件冲突/重叠待 PM 拍板项（CONFLICTS — Agent 严禁擅自二选一！）\n")
    if not conflict_groups:
        md_lines.append("（无冲突）\n")
    else:
        for g_idx, (target_key, group_items) in enumerate(conflict_groups.items(), start=1):
            md_lines.append(f"### 冲突组 C-{g_idx:02d}：目标 `{target_key}`（共 {len(group_items)} 条不同意见，请调用 AskUserQuestion 让 PM 裁决）")
            for sub in group_items:
                md_lines.append(f"- **{sub.get('author')}**（来源 `{sub.get('source_file')}`）：{sub.get('text')}")
            md_lines.append("")

    md_lines.append("## 三、 落点已失效待人工核对项（INVALID_ANCHORS）\n")
    if not invalid_items:
        md_lines.append("（无失效项）\n")
    else:
        for it in invalid_items:
            md_lines.append(
                f"- **[{it.get('author')}]** 原落点 `{it.get('page')} :: {it.get('comp_id')}` 未命中当前 DOM：{it.get('text')}"
            )
        md_lines.append("")

    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    jsonl_rows: List[str] = []
    for idx, it in enumerate(deduped):
        resolution = (
            "invalid_anchor"
            if not it["anchor_valid"]
            else ("conflict_needs_pm" if idx in conflict_indices else "auto_apply")
        )
        rec = dict(it)
        rec["merge_resolution"] = resolution
        jsonl_rows.append(json.dumps(rec, ensure_ascii=False))
    out_jsonl.write_text("\n".join(jsonl_rows) + ("\n" if jsonl_rows else ""), encoding="utf-8")

    stats = {
        "total": len(deduped),
        "reviewers": len(reviewers),
        "auto_apply": len(auto_apply),
        "conflict_groups": len(conflict_groups),
        "invalid": len(invalid_items),
    }
    return out_md, out_jsonl, stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge multiple reviewers' feedback (.jsonl/.md), validate anchors, and detect component conflicts."
    )
    parser.add_argument("project_dir", type=Path, help="Target project directory (e.g. projects/b-end-approval-flow)")
    parser.add_argument("files", nargs="*", type=Path, help="Feedback .jsonl or .md files (auto-scans project if omitted)")
    args = parser.parse_args()

    proj = args.project_dir.resolve()
    if not proj.is_dir():
        print(f"[merge_feedback] Error: project directory not found: {proj}", file=sys.stderr)
        return 1

    files: List[Path] = [f.resolve() for f in args.files if f.is_file()]
    if not files:
        candidates: List[Path] = []
        reviews_sub = proj / "reviews"
        if reviews_sub.is_dir():
            candidates.extend(sorted(reviews_sub.glob("*.jsonl")) + sorted(reviews_sub.glob("*.md")))
        candidates.extend(sorted(proj.glob("review-feedback*.jsonl")) + sorted(proj.glob("review-feedback*.md")))
        # Prefer .jsonl over same-stem .md when both exist from same reviewer
        by_stem: Dict[str, Path] = {}
        for c in candidates:
            if c.name in ("review-merged.md", "review-merged.jsonl"):
                continue
            if c.stem not in by_stem or c.suffix.lower() == ".jsonl":
                by_stem[c.stem] = c
        files = list(by_stem.values())

    if not files:
        print(f"[merge_feedback] No review feedback files found in {proj}.", file=sys.stderr)
        return 1

    out_md, out_jsonl, stats = merge_project_feedback(proj, files)
    print(
        f"[merge_feedback] Merged {stats['total']} item(s) from {stats['reviewers']} reviewer(s) -> {out_md.name} & {out_jsonl.name} | "
        f"auto_apply={stats['auto_apply']}, conflict_groups={stats['conflict_groups']}, invalid={stats['invalid']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
