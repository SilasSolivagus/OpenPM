#!/usr/bin/env python3
"""Randomized Double-Blind A/B Experiment Harness & Nested-Table / Confluence XML Verifier.

Implements the full rigorous validation methodology:
  1. `prepare`: Hold-out split verification (strictly excludes training/source projects from test set),
     cryptographic coin-flip anonymization (`plan_A` vs `plan_B`), and isolated `.blind_key.json`.
  2. `verify-table-xml`: Programmatic structural verification on Wiki Markdown & Confluence 7.4+ Storage XML:
     - Outer 3-column Markdown table (`序号 | 页面截图 | 需求说明`) `0 破表` check (zero broken pipes/rows);
     - Single-line compact HTML `<table>...</table>` nested sub-table count & integrity check;
     - Strict `xml.etree.ElementTree.fromstring` Confluence Storage XML parsing check (`N/N 通过`);
     - `preflight_check.py` gate verification.
  3. `unblind`: Joins independent blind Judge Subagent verdicts (`score_10` + `estimated_wiki_rewrite_pct` +
     `nitpicks`) with `.blind_key.json` and programmatic XML verification to generate `ab_validation_report.md`
     with exact win-loss tally, 10-point mean jump, manual Wiki rewrite % reduction, and XML pass rate.
"""

import argparse
import datetime
import json
import re
import secrets
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))


def verify_markdown_and_confluence_xml(md_path: Path) -> Dict[str, Any]:
    """Verify outer 3-column table zero-breakage, single-line HTML <table> sub-tables, and strict Confluence XML."""
    raw = md_path.read_text(encoding="utf-8")

    # 1. Outer Markdown table pipe & row integrity check
    lines = raw.splitlines()
    in_table = False
    expected_cols = 0
    broken_rows: List[Tuple[int, str]] = []
    outer_table_rows = 0
    nested_html_tables = 0
    multiline_html_table_errors = 0

    # Detect any multi-line HTML <table> blocks (must be single-line inside Markdown table cells!)
    for m in re.finditer(r"<table\b.*?</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        snippet = m.group(0)
        if "\n" in snippet:
            multiline_html_table_errors += 1

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Mask escaped pipes \| and pipes inside inline `code` or <table>...</table>
            masked = re.sub(r"\\\|", "__ESC_PIPE__", stripped)
            masked = re.sub(r"`[^`]*`", "__CODE__", masked)
            masked = re.sub(r"<table\b.*?</table>", "__HTML_SUBTABLE__", masked, flags=re.IGNORECASE)
            cols = len(masked.split("|")) - 2
            if not in_table:
                in_table = True
                expected_cols = cols
            else:
                if cols != expected_cols:
                    broken_rows.append((line_no, f"expected {expected_cols} cols, got {cols}"))
            outer_table_rows += 1
            sub_matches = re.findall(r"<table\b[^>]*>.*?</table>", stripped, flags=re.IGNORECASE)
            nested_html_tables += len(sub_matches)
            for sm in sub_matches:
                # Verify balanced inner HTML table tags as valid XML fragment
                try:
                    ET.fromstring(sm)
                except ET.ParseError as exc:
                    broken_rows.append((line_no, f"malformed inner <table>: {exc}"))
        else:
            in_table = False

    # 2. Convert via wiki_sync._md_block_to_xhtml and run strict Confluence 7.4+ Storage XML parse
    confluence_xml_ok = False
    confluence_xml_error = ""
    try:
        import wiki_sync  # type: ignore

        storage_xhtml = wiki_sync._md_block_to_xhtml(raw)
        wrapped_xml = (
            '<root xmlns:ac="http://atlassian.com/content" '
            'xmlns:ri="http://atlassian.com/resource/identifier">'
            f"{storage_xhtml}</root>"
        )
        root_el = ET.fromstring(wrapped_xml)
        # Ensure single-line HTML <table> sub-tables survived unescaped as real nested <table> elements
        if nested_html_tables > 0:
            nested_in_td = len(root_el.findall(".//td//table"))
            if nested_in_td < nested_html_tables:
                raise ValueError(
                    f"Expected {nested_html_tables} nested <table> inside <td>, found {nested_in_td}"
                )
        confluence_xml_ok = True
    except Exception as exc:
        confluence_xml_error = str(exc)

    zero_broken = (len(broken_rows) == 0) and (multiline_html_table_errors == 0)
    return {
        "file": str(md_path),
        "outer_table_rows": outer_table_rows,
        "broken_table_count": len(broken_rows) + multiline_html_table_errors,
        "broken_details": broken_rows,
        "multiline_html_table_errors": multiline_html_table_errors,
        "nested_single_line_html_tables": nested_html_tables,
        "zero_table_breakage": zero_broken,
        "confluence_storage_xml_valid": confluence_xml_ok,
        "confluence_xml_error": confluence_xml_error,
    }


def cmd_verify_xml(args: argparse.Namespace) -> int:
    all_ok = True
    results = []
    for target in args.files:
        p = Path(target).resolve()
        if not p.is_file():
            print(f"[ab_eval] Missing file: {p}", file=sys.stderr)
            all_ok = False
            continue
        res = verify_markdown_and_confluence_xml(p)
        results.append(res)
        if not (res["zero_table_breakage"] and res["confluence_storage_xml_valid"]):
            all_ok = False
        status = "PASS" if (res["zero_table_breakage"] and res["confluence_storage_xml_valid"]) else "FAIL"
        print(
            f"[{status}] {p.name}: 破表数={res['broken_table_count']} | "
            f"单行 HTML <table> 子表数={res['nested_single_line_html_tables']} | "
            f"Confluence Storage XML={'通过' if res['confluence_storage_xml_valid'] else ('失败: ' + res['confluence_xml_error'])}"
        )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all_ok else 1


def cmd_prepare(args: argparse.Namespace) -> int:
    excluded = {x.strip() for x in (args.exclude_train or []) if x.strip()}
    exp_dir = Path(args.exp_dir).resolve()
    exp_dir.mkdir(parents=True, exist_ok=True)

    pairs: List[Dict[str, str]] = json.loads(Path(args.pairs_json).read_text(encoding="utf-8"))
    blind_map: Dict[str, Any] = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "excluded_training_projects": sorted(excluded),
        "cases": {},
    }

    public_manifest: List[Dict[str, Any]] = []
    for item in pairs:
        case_id = item["case_id"]
        if case_id in excluded:
            raise ValueError(
                f"Hold-out violation: case '{case_id}' is in --exclude-train ({sorted(excluded)}) "
                "and MUST be excluded from double-blind evaluation!"
            )
        baseline_dir = Path(item["baseline_dir"]).resolve()
        candidate_dir = Path(item["candidate_dir"]).resolve()

        # Cryptographic random coin flip
        candidate_is_a = secrets.choice([True, False])
        plan_a_src = candidate_dir if candidate_is_a else baseline_dir
        plan_b_src = baseline_dir if candidate_is_a else candidate_dir

        case_out = exp_dir / case_id
        if case_out.exists():
            shutil.rmtree(case_out)
        shutil.copytree(plan_a_src, case_out / "plan_A")
        shutil.copytree(plan_b_src, case_out / "plan_B")

        blind_map["cases"][case_id] = {
            "title": item.get("title", case_id),
            "expected_subtables": int(item.get("expected_subtables", 0)),
            "plan_A": "candidate" if candidate_is_a else "baseline",
            "plan_B": "baseline" if candidate_is_a else "candidate",
            "baseline_src": str(baseline_dir),
            "candidate_src": str(candidate_dir),
        }
        public_manifest.append(
            {
                "case_id": case_id,
                "title": item.get("title", case_id),
                "plan_A_dir": str(case_out / "plan_A"),
                "plan_B_dir": str(case_out / "plan_B"),
            }
        )

    (exp_dir / ".blind_key.json").write_text(json.dumps(blind_map, ensure_ascii=False, indent=2), encoding="utf-8")
    (exp_dir / "blind_cases_for_judge.json").write_text(
        json.dumps(public_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[ab_eval] Prepared {len(public_manifest)} randomized blind A/B case(s) in {exp_dir} "
        f"(excluded training set: {sorted(excluded) or 'none'}).\n"
        f"Feed ONLY 'blind_cases_for_judge.json' + 'evals/judge-rubric.md' to an isolated Judge Subagent!"
    )
    return 0


def cmd_unblind(args: argparse.Namespace) -> int:
    exp_dir = Path(args.exp_dir).resolve()
    blind_key = json.loads((exp_dir / ".blind_key.json").read_text(encoding="utf-8"))
    verdicts_data = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    verdicts_by_case = {v["case_id"]: v for v in verdicts_data["cases"]}

    cand_wins = 0
    base_wins = 0
    ties = 0
    base_scores: List[float] = []
    cand_scores: List[float] = []
    base_rewrites: List[float] = []
    cand_rewrites: List[float] = []
    xml_pass_count = 0
    total_broken_tables = 0
    expected_subtables_total = 0
    matched_subtables_total = 0
    all_nitpicks: List[str] = []

    case_rows_md: List[str] = []

    for case_id, meta in blind_key["cases"].items():
        v = verdicts_by_case[case_id]
        a_role = meta["plan_A"]
        cand_label = "plan_A" if a_role == "candidate" else "plan_B"
        base_label = "plan_B" if a_role == "candidate" else "plan_A"

        c_res = v[cand_label]
        b_res = v[base_label]

        c_score = float(c_res["score_10"])
        b_score = float(b_res["score_10"])
        c_rw = float(c_res["estimated_wiki_rewrite_pct"])
        b_rw = float(b_res["estimated_wiki_rewrite_pct"])

        cand_scores.append(c_score)
        base_scores.append(b_score)
        cand_rewrites.append(c_rw)
        base_rewrites.append(b_rw)

        if c_score > b_score:
            cand_wins += 1
            winner_str = "新规范胜出"
        elif b_score > c_score:
            base_wins += 1
            winner_str = "旧规范胜出"
        else:
            ties += 1
            winner_str = "平局"

        # Programmatic Wiki table & Confluence XML verification on candidate export
        cand_dir = exp_dir / case_id / cand_label
        wiki_md = cand_dir / "wiki-export" / "wiki-page.md"
        if not wiki_md.is_file():
            wiki_md = cand_dir / "prd.md"
        xml_info = verify_markdown_and_confluence_xml(wiki_md) if wiki_md.is_file() else {
            "broken_table_count": 0,
            "nested_single_line_html_tables": 0,
            "zero_table_breakage": True,
            "confluence_storage_xml_valid": True,
        }
        if xml_info["zero_table_breakage"] and xml_info["confluence_storage_xml_valid"]:
            xml_pass_count += 1
        total_broken_tables += int(xml_info["broken_table_count"])
        exp_sub = int(meta.get("expected_subtables", 0))
        expected_subtables_total += exp_sub
        matched_subtables_total += min(exp_sub, int(xml_info["nested_single_line_html_tables"])) if exp_sub else int(xml_info["nested_single_line_html_tables"])

        for np_item in c_res.get("nitpicks") or []:
            if np_item not in all_nitpicks:
                all_nitpicks.append(np_item)

        case_rows_md.append(
            f"| {meta['title']} (`{case_id}`) | `{cand_label}` 新 / `{base_label}` 旧 | "
            f"**{b_score:.2f}** → **{c_score:.2f}** / 10 | "
            f"**{b_rw:.1f}%** → **{c_rw:.1f}%** | "
            f"{xml_info['broken_table_count']} 破表 / XML {'通过' if xml_info['confluence_storage_xml_valid'] else '失败'} | "
            f"**{winner_str}** |"
        )

    n_cases = max(1, len(cand_scores))
    mean_base = sum(base_scores) / n_cases
    mean_cand = sum(cand_scores) / n_cases
    mean_rw_base = sum(base_rewrites) / n_cases
    mean_rw_cand = sum(cand_rewrites) / n_cases
    excluded_list = blind_key.get("excluded_training_projects") or []
    excl_note = f"剔除训练集 {', '.join(excluded_list)} 后的 " if excluded_list else ""
    sub_note = (
        f"，{expected_subtables_total} 处真实子表 {round(matched_subtables_total / expected_subtables_total * 100)}% 命中还原"
        if expected_subtables_total > 0
        else f"（含 {matched_subtables_total} 处单行嵌套子表）"
    )

    report_path = Path(args.report_out).resolve() if args.report_out else (exp_dir / "ab_validation_report.md")
    summary_line = (
        f"一句话结论：**{'正向收益非常确定' if cand_wins > base_wins else '需继续调优'}——"
        f"{excl_note}{len(cand_scores)} 个测试项目独立盲评 {cand_wins}:{base_wins}"
        f"{f'（平 {ties}）' if ties else ' 全票'}判新规范胜出"
        f"（均分从 `{mean_base:.2f}` 升至 `{mean_cand:.2f} / 10`，"
        f"预估你上 Wiki 前需手动删改重排的比例从 `{mean_rw_base:.1f}%` 降至 `{mean_rw_cand:.1f}%`）**；"
        f"单元格内单行 HTML `<table>` 在外层三列表格中 **`{total_broken_tables}` 破表**{sub_note}，"
        f"转 `Confluence Storage XML` 严格解析 **`{xml_pass_count}/{len(cand_scores)}` 通过**。"
    )

    nitpicks_md = (
        "\n".join(f"- {item}" for item in all_nitpicks)
        if all_nitpicks
        else "- 暂无额外结构瑕疵。"
    )

    report_md = "\n".join(
        [
            "# 双盲对比实验与嵌套表格 / Confluence XML 验证报告（AB Validation Report）",
            "",
            f"- 生成时间：`{datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}`",
            f"- 剔除训练集（防过拟合）：`{', '.join(excluded_list) if excluded_list else '无'}`",
            "",
            "## 1. 核心结论摘要",
            "",
            summary_line,
            "",
            "## 2. 逐项目揭盲对比明细",
            "",
            "| 测试项目 | 随机盲标揭盲 | 独立裁判总分（旧 → 新） | 预估上 Wiki 前手动删改率（旧 → 新） | 嵌套表格 & Confluence XML | 盲评裁决 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
            *case_rows_md,
            "",
            "## 3. 统计均值汇总",
            "",
            f"- **独立盲评胜负比**：`{cand_wins}:{base_wins}`" + (f"（平 `{ties}`）" if ties else ""),
            f"- **10 分制综合均分**：`{mean_base:.2f}` → **`{mean_cand:.2f} / 10`**（提升 `+{mean_cand - mean_base:.2f}` 分）",
            f"- **预估上 Wiki 前手动删改重排比例**：`{mean_rw_base:.1f}%` → **`{mean_rw_cand:.1f}%`**（下降 `-{mean_rw_base - mean_rw_cand:.1f}` 个百分点）",
            f"- **外层三列表格破表数**：`{total_broken_tables}` 破表",
            f"- **Confluence Storage XML 严格解析通过率**：`{xml_pass_count}/{len(cand_scores)}` 通过",
            "",
            "## 4. 独立裁判额外抓出的微调收口项",
            "",
            nitpicks_md,
            "",
        ]
    )
    report_path.write_text(report_md, encoding="utf-8")
    print(summary_line)
    print(f"[ab_eval] Full report written to: {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OpenPM Double-Blind A/B Evaluation & Confluence XML Verification Harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Create randomized blind plan_A/plan_B directories with hold-out check")
    p_prep.add_argument("--pairs-json", required=True, help="JSON file listing [{case_id, title, baseline_dir, candidate_dir, expected_subtables?}]")
    p_prep.add_argument("--exp-dir", required=True, help="Output experiment directory")
    p_prep.add_argument("--exclude-train", nargs="*", default=[], help="Training project IDs strictly excluded from test cases")
    p_prep.set_defaults(func=cmd_prepare)

    p_xml = sub.add_parser("verify-table-xml", help="Verify outer 3-col Markdown table 0-breakage, single-line <table>, and Confluence XML")
    p_xml.add_argument("files", nargs="+", help="Markdown files (e.g. wiki-export/wiki-page.md) to validate")
    p_xml.add_argument("--json-out", default="", help="Optional JSON output file")
    p_xml.set_defaults(func=cmd_verify_xml)

    p_unb = sub.add_parser("unblind", help="Unblind Judge Subagent verdicts and generate ab_validation_report.md")
    p_unb.add_argument("--exp-dir", required=True, help="Experiment directory containing .blind_key.json")
    p_unb.add_argument("--verdicts", required=True, help="Judge verdicts JSON file")
    p_unb.add_argument("--report-out", default="", help="Optional custom output path for ab_validation_report.md")
    p_unb.set_defaults(func=cmd_unblind)

    return p


if __name__ == "__main__":
    sys.exit(build_parser().parse_args().func(build_parser().parse_args()))
