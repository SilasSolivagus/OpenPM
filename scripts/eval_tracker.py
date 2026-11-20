#!/usr/bin/env python3
"""Automated scoring, defect/decision logging, and periodic optimization trigger for OpenPM.

Commands:
  score <project_dir>        Compute objective rework rate (v1 vs current) & quality score, log to run-scores.jsonl
  log-defect                 Append a general skill defect or PM taste preference to skill-defects.jsonl
  log-decision               Append a project-specific business decision to project-decisions.jsonl
  digest                     Print optimization status, average North-Star rework rate, and open defects
  mark-resolved <SD-ID...>   Mark defects resolved, optionally append permanent rule to taste-profile.md
"""

import argparse
import datetime
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = ROOT_DIR / "evals" / "datasets"
RUN_SCORES_FILE = DATASETS_DIR / "run-scores.jsonl"
SKILL_DEFECTS_FILE = DATASETS_DIR / "skill-defects.jsonl"
PROJECT_DECISIONS_FILE = DATASETS_DIR / "project-decisions.jsonl"
OPTIMIZE_STATE_FILE = DATASETS_DIR / "optimize-checkpoints.jsonl"
TASTE_PROFILE_FILE = ROOT_DIR / "evals" / "taste-profile.md"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(content, encoding="utf-8")


def _next_seq_id(rows: List[Dict[str, Any]], prefix: str) -> str:
    max_num = 0
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for r in rows:
        m = pat.match(str(r.get("id", "")))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}-{max_num + 1:03d}"


def _line_change_pct(old_text: str, new_text: str) -> float:
    old_lines = [ln.strip() for ln in old_text.splitlines() if ln.strip()]
    new_lines = [ln.strip() for ln in new_text.splitlines() if ln.strip()]
    if not old_lines and not new_lines:
        return 0.0
    if not old_lines or not new_lines:
        return 100.0
    ratio = difflib.SequenceMatcher(None, old_lines, new_lines).ratio()
    return round(max(0.0, (1.0 - ratio) * 100.0), 1)


def _compute_rework_metrics(project_dir: Path) -> Tuple[int, float, float]:
    """Return (snapshot_count, prd_rewrite_pct, ui_rewrite_pct) comparing v1 snapshot to current files."""
    versions_dir = project_dir / "versions"
    v_nums: List[int] = []
    if versions_dir.is_dir():
        for d in versions_dir.iterdir():
            if d.is_dir():
                m = re.fullmatch(r"v(\d+)", d.name)
                if m:
                    v_nums.append(int(m.group(1)))
    v_nums.sort()
    snapshot_count = len(v_nums)
    if not v_nums:
        return 0, 0.0, 0.0

    v1_dir = versions_dir / f"v{v_nums[0]}"
    prd_pct = 0.0
    cur_prd = project_dir / "prd.md"
    v1_prd = v1_dir / "prd.md"
    if cur_prd.is_file() and v1_prd.is_file():
        prd_pct = _line_change_pct(
            v1_prd.read_text(encoding="utf-8", errors="ignore"),
            cur_prd.read_text(encoding="utf-8", errors="ignore"),
        )

    cur_pages_dir = project_dir / "pages"
    v1_pages_dir = v1_dir / "pages"
    ui_pct = 0.0
    if cur_pages_dir.is_dir() and v1_pages_dir.is_dir():
        all_names = sorted(
            {p.name for p in cur_pages_dir.glob("*.html")} | {p.name for p in v1_pages_dir.glob("*.html")}
        )
        if all_names:
            diffs: List[float] = []
            for name in all_names:
                p_old = v1_pages_dir / name
                p_new = cur_pages_dir / name
                t_old = p_old.read_text(encoding="utf-8", errors="ignore") if p_old.is_file() else ""
                t_new = p_new.read_text(encoding="utf-8", errors="ignore") if p_new.is_file() else ""
                diffs.append(_line_change_pct(t_old, t_new))
            ui_pct = round(sum(diffs) / len(diffs), 1)

    return snapshot_count, prd_pct, ui_pct


def _count_feedback_items(project_dir: Path) -> int:
    jsonl_fb = project_dir / "review-feedback.jsonl"
    if jsonl_fb.is_file():
        return len(_read_jsonl(jsonl_fb))
    md_fb = project_dir / "review-feedback.md"
    if md_fb.is_file():
        txt = md_fb.read_text(encoding="utf-8", errors="ignore")
        fm = re.search(r"^\s*total_comments\s*:\s*(\d+)\s*$", txt, flags=re.MULTILINE)
        if fm:
            return int(fm.group(1))
        headings = re.findall(r"^##\s+\[", txt, flags=re.MULTILINE)
        if headings:
            return len(headings)
        numbered = re.findall(r"^\s*(?:\d+\.|-\s+\*\*\[)", txt, flags=re.MULTILINE)
        return len(numbered)
    spec_f = project_dir / "spec.json"
    if spec_f.is_file():
        try:
            sp = json.loads(spec_f.read_text(encoding="utf-8"))
            memos = sp.get("memos")
            if isinstance(memos, list):
                return len(memos)
        except Exception:
            pass
    return 0


def _check_preflight(project_dir: Path) -> Tuple[bool, int]:
    checker = ROOT_DIR / "scripts" / "preflight_check.py"
    issues = 0
    passed = True
    for fname in ("spec.json", "walkthrough.html"):
        fpath = project_dir / fname
        if not fpath.is_file():
            passed = False
            issues += 1
            continue
        res = subprocess.run(
            [sys.executable, str(checker), str(fpath)],
            text=True,
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            passed = False
            m = re.search(r"PREFLIGHT FAILED \((\d+) issue", res.stderr)
            issues += int(m.group(1)) if m else 1
    return passed, issues


def _evaluate_trigger() -> Tuple[bool, List[str]]:
    scores = _read_jsonl(RUN_SCORES_FILE)
    defects = _read_jsonl(SKILL_DEFECTS_FILE)
    checkpoints = _read_jsonl(OPTIMIZE_STATE_FILE)

    last_cp_ts = checkpoints[-1].get("timestamp", "") if checkpoints else ""
    final_since_cp = [
        s for s in scores
        if s.get("stage") == "final" and str(s.get("timestamp", "")) > str(last_cp_ts)
    ]
    open_defects = [d for d in defects if d.get("status", "open") == "open"]

    reasons: List[str] = []
    if len(open_defects) >= 3:
        reasons.append(f"已累计 {len(open_defects)} 条未合并的通用错题/品味记录（>= 3 条阈值）")
    if len(final_since_cp) >= 3:
        reasons.append(f"距上次技能迭代已完成 {len(final_since_cp)} 个需求交付（>= 3 个周期阈值）")
    if final_since_cp and float(final_since_cp[-1].get("score_10", 10.0)) < 7.5:
        reasons.append(f"最近一次需求初稿→定稿返工率偏高（得分 {final_since_cp[-1].get('score_10')}/10 < 7.5）")

    return (len(reasons) > 0), reasons


def cmd_score(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        print(f"[eval_tracker] Error: project directory not found: {project_dir}", file=sys.stderr)
        return 1

    preflight_ok, preflight_issues = _check_preflight(project_dir)
    snapshots, prd_pct, ui_pct = _compute_rework_metrics(project_dir)
    fb_count = _count_feedback_items(project_dir)
    avg_rework_pct = round((prd_pct + ui_pct) / 2.0, 1)

    score = 10.0
    if not preflight_ok:
        score -= min(3.5, 1.5 + 0.5 * preflight_issues)
    score -= min(2.5, avg_rework_pct * 0.05)
    score -= min(2.0, fb_count * 0.25)
    score -= min(1.5, max(0, snapshots - 2) * 0.4)
    score = round(max(0.0, score), 1)

    all_scores = _read_jsonl(RUN_SCORES_FILE)
    rec = {
        "id": _next_seq_id(all_scores, "RS"),
        "timestamp": _now_iso(),
        "project": project_dir.name,
        "stage": args.stage,
        "score_10": score,
        "preflight_passed": preflight_ok,
        "preflight_issues": preflight_issues,
        "snapshots": snapshots,
        "feedback_items": fb_count,
        "prd_rewrite_pct": prd_pct,
        "ui_rewrite_pct": ui_pct,
        "north_star_rework_pct": avg_rework_pct,
        "note": args.note or "",
    }
    _append_jsonl(RUN_SCORES_FILE, rec)

    print(
        f"[eval_tracker] Recorded {rec['id']} for '{project_dir.name}' ({args.stage}): "
        f"score={score}/10 | rework={avg_rework_pct}% (PRD {prd_pct}%, UI {ui_pct}%) | "
        f"feedback_items={fb_count} | preflight={'PASS' if preflight_ok else 'FAIL'}"
    )

    should_opt, reasons = _evaluate_trigger()
    if should_opt:
        print(f"[ITERATION_TRIGGER] 建议触发 07-iterate-skills 定期优化：{'；'.join(reasons)}")

    # Non-intrusive, zero-telemetry Aha-Moment Star Nudge (fires only on 1st & 5th real user final delivery)
    builtin_demos = {"b-end-approval-flow", "demo-captcha-publish"}
    if args.stage == "final" and project_dir.name not in builtin_demos:
        nudge_file = ROOT_DIR / ".openpm" / "star_nudge.json"
        nudge_state: Dict[str, Any] = {"shown_milestones": []}
        if nudge_file.is_file():
            try:
                nudge_state = json.loads(nudge_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        real_finals = [
            s for s in (all_scores + [rec])
            if s.get("stage") == "final" and s.get("project") not in builtin_demos
        ]
        milestone = len(real_finals)
        shown = set(nudge_state.get("shown_milestones") or [])
        if milestone in (1, 5) and milestone not in shown:
            shown.add(milestone)
            nudge_state["shown_milestones"] = sorted(shown)
            nudge_file.parent.mkdir(parents=True, exist_ok=True)
            nudge_file.write_text(json.dumps(nudge_state, ensure_ascii=False), encoding="utf-8")
            print(
                "[STAR_NUDGE] 如果 OpenPM 帮你省下了画图与写文档的时间，欢迎顺手回 GitHub 点亮一颗 Star 支持开源共建："
                "https://github.com/SilasSolivagus/OpenPM"
            )
    return 0


def cmd_log_defect(args: argparse.Namespace) -> int:
    rows = _read_jsonl(SKILL_DEFECTS_FILE)
    new_id = _next_seq_id(rows, "SD")
    rec: Dict[str, Any] = {
        "id": new_id,
        "timestamp": _now_iso(),
        "skill": args.skill,
        "severity": args.severity,
        "symptom": args.symptom.strip(),
        "root_cause": args.root_cause.strip(),
        "status": "resolved" if args.taste_rule else "open",
    }
    if args.taste_rule:
        rec["taste_rule"] = args.taste_rule.strip()
        _append_taste_rule(new_id, args.skill, args.taste_rule.strip())
    _append_jsonl(SKILL_DEFECTS_FILE, rec)
    print(f"[eval_tracker] Logged skill defect {new_id} ({rec['status']}) -> {SKILL_DEFECTS_FILE.name}")

    should_opt, reasons = _evaluate_trigger()
    if should_opt:
        print(f"[ITERATION_TRIGGER] {'；'.join(reasons)}")
    return 0


def cmd_log_decision(args: argparse.Namespace) -> int:
    rows = _read_jsonl(PROJECT_DECISIONS_FILE)
    new_id = _next_seq_id(rows, "PD")
    rec = {
        "id": new_id,
        "timestamp": _now_iso(),
        "project": args.project.strip(),
        "prd_ref": args.prd_ref.strip(),
        "comp_id": args.comp_id.strip(),
        "decision": args.decision.strip(),
        "rationale": (args.rationale or "").strip(),
    }
    _append_jsonl(PROJECT_DECISIONS_FILE, rec)
    print(f"[eval_tracker] Logged project decision {new_id} for '{rec['project']}' -> {PROJECT_DECISIONS_FILE.name}")
    return 0


def _append_taste_rule(source_id: str, skill: str, rule_text: str) -> None:
    TASTE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TASTE_PROFILE_FILE.is_file():
        TASTE_PROFILE_FILE.write_text(
            "# PM 品味与高频避坑清单（Taste Profile）\n\n"
            "> 本文件由 `07-iterate-skills` 与 `scripts/eval_tracker.py` 自动沉淀更新。\n"
            "> **Agent 铁律**：执行 `02-draft-prd`、`03-prd-to-wireframe-prototype`、`04-flow-canvas` 前必须先读取本清单，严禁重犯已记录问题。\n\n"
            "## 已固化规则\n",
            encoding="utf-8",
        )
    existing = TASTE_PROFILE_FILE.read_text(encoding="utf-8")
    bullet = f"- **[{source_id} · {skill}]** {rule_text}\n"
    if rule_text not in existing:
        with TASTE_PROFILE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(bullet)


def cmd_digest(_args: argparse.Namespace) -> int:
    scores = _read_jsonl(RUN_SCORES_FILE)
    defects = _read_jsonl(SKILL_DEFECTS_FILE)
    decisions = _read_jsonl(PROJECT_DECISIONS_FILE)
    open_defects = [d for d in defects if d.get("status", "open") == "open"]
    final_scores = [s for s in scores if s.get("stage") == "final"]

    avg_score = (
        round(sum(float(s.get("score_10", 0.0)) for s in final_scores) / len(final_scores), 2)
        if final_scores
        else None
    )
    avg_rework = (
        round(sum(float(s.get("north_star_rework_pct", 0.0)) for s in final_scores) / len(final_scores), 1)
        if final_scores
        else None
    )

    print("=== OpenPM 质量评分与自我迭代摘要 ===")
    print(f"- 累计记录运行次数：{len(scores)}（其中定稿交付 {len(final_scores)} 次）")
    if avg_score is not None:
        print(f"- 定稿平均质量得分：{avg_score} / 10.0 | 北极星指标（平均返工修改率）：{avg_rework}%")
    print(f"- 单项目业务决策沉淀：{len(decisions)} 条 | 通用错题/品味沉淀：{len(defects)} 条（待消化 Open：{len(open_defects)} 条）")

    if open_defects:
        print("\n待消化的通用错题（Open Defects）：")
        for d in open_defects:
            print(f"  - [{d.get('id')}] ({d.get('skill')} / {d.get('severity')}): {d.get('symptom')}")

    should_opt, reasons = _evaluate_trigger()
    if should_opt:
        print(f"\n[ITERATION_TRIGGER] 当前已满足定期优化条件：{'；'.join(reasons)}")
    else:
        print("\n当前状态：良好（尚未触发定期合并优化阈值）。")
    return 0


def cmd_mark_resolved(args: argparse.Namespace) -> int:
    target_ids = set(args.defect_ids)
    rows = _read_jsonl(SKILL_DEFECTS_FILE)
    updated = 0
    resolved_skills: List[str] = []
    for r in rows:
        if r.get("id") in target_ids and r.get("status") != "resolved":
            r["status"] = "resolved"
            r["resolved_at"] = _now_iso()
            updated += 1
            resolved_skills.append(str(r.get("skill", "general")))
    _write_jsonl(SKILL_DEFECTS_FILE, rows)

    if args.add_taste:
        src_label = ",".join(sorted(target_ids)) if target_ids else "ITER"
        sk_label = resolved_skills[0] if resolved_skills else "general"
        _append_taste_rule(src_label, sk_label, args.add_taste.strip())

    checkpoints = _read_jsonl(OPTIMIZE_STATE_FILE)
    cp = {
        "id": _next_seq_id(checkpoints, "CP"),
        "timestamp": _now_iso(),
        "resolved_defects": sorted(target_ids),
        "added_taste": (args.add_taste or "").strip(),
    }
    _append_jsonl(OPTIMIZE_STATE_FILE, cp)
    print(f"[eval_tracker] Marked {updated} defect(s) resolved and recorded optimization checkpoint {cp['id']}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OpenPM automated scoring, defect tracker, and iteration trigger.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_score = sub.add_parser("score", help="Score a project workspace (v1 vs current) and check iteration trigger")
    p_score.add_argument("project_dir", help="Path to projects/<project>")
    p_score.add_argument("--stage", choices=("draft", "rework", "final"), default="final")
    p_score.add_argument("--note", default="", help="Optional context note")
    p_score.set_defaults(func=cmd_score)

    p_def = sub.add_parser("log-defect", help="Record a reusable skill defect or PM taste preference")
    p_def.add_argument("--skill", required=True, help="Target skill ID (e.g. 02-draft-prd, 03-wireframe, 04-flow-canvas)")
    p_def.add_argument("--severity", choices=("high", "medium", "low"), default="medium")
    p_def.add_argument("--symptom", required=True, help="Observed issue or PM correction")
    p_def.add_argument("--root-cause", required=True, help="Why the agent made this mistake")
    p_def.add_argument("--taste-rule", default="", help="Optional immediate rule to solidify into taste-profile.md")
    p_def.set_defaults(func=cmd_log_defect)

    p_dec = sub.add_parser("log-decision", help="Record a single-project business rule/decision")
    p_dec.add_argument("--project", required=True, help="Project slug")
    p_dec.add_argument("--prd-ref", required=True, help="PRD section ID, e.g. F-01")
    p_dec.add_argument("--comp-id", default="-", help="Component ID, e.g. form.submit.btn")
    p_dec.add_argument("--decision", required=True, help="Business decision content")
    p_dec.add_argument("--rationale", default="", help="Business rationale")
    p_dec.set_defaults(func=cmd_log_decision)

    p_dig = sub.add_parser("digest", help="Show scoring summary, North-Star rework rate, and open defects")
    p_dig.set_defaults(func=cmd_digest)

    p_res = sub.add_parser("mark-resolved", help="Mark SD-* defects as resolved and record iteration checkpoint")
    p_res.add_argument("defect_ids", nargs="*", help="Defect IDs to mark resolved (e.g. SD-001 SD-002)")
    p_res.add_argument("--add-taste", default="", help="Permanent rule to append to evals/taste-profile.md")
    p_res.set_defaults(func=cmd_mark_resolved)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
