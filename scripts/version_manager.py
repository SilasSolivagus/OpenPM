#!/usr/bin/env python3
"""Version snapshot, diff, and rollback manager for PRD project workspaces."""

import argparse
import datetime
import difflib
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional


EXCLUDED_NAMES = {"versions", ".git", "__pycache__", ".DS_Store"}


def _normalize_version(version: str) -> str:
    v = version.strip()
    if re.fullmatch(r"\d+", v):
        return f"v{v}"
    if re.fullmatch(r"v\d+", v):
        return v
    raise ValueError(f"Invalid version format '{version}'. Expected 'v1', 'v2', or '1', '2'.")


def _existing_versions(versions_dir: Path) -> List[int]:
    if not versions_dir.is_dir():
        return []
    nums: List[int] = []
    for entry in versions_dir.iterdir():
        if entry.is_dir():
            m = re.fullmatch(r"v(\d+)", entry.name)
            if m:
                nums.append(int(m.group(1)))
    return sorted(nums)


def _iter_project_files(root: Path) -> Dict[Path, Path]:
    """Return mapping of relative_path -> absolute_path for tracked workspace files."""
    files: Dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in EXCLUDED_NAMES or part.startswith(".") for part in rel.parts):
            continue
        if path.is_file():
            files[rel] = path
    return files


def _append_changelog(versions_dir: Path, entry: str) -> None:
    changelog_path = versions_dir / "changelog.md"
    if not changelog_path.exists():
        changelog_path.write_text("# Version Changelog\n\n", encoding="utf-8")
    with changelog_path.open("a", encoding="utf-8") as f:
        f.write(entry.rstrip() + "\n")


def cmd_snapshot(project_dir: Path, note: str) -> int:
    if not project_dir.is_dir():
        print(f"ERROR: Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    versions_dir = project_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    existing = _existing_versions(versions_dir)
    next_num = (existing[-1] + 1) if existing else 1
    version_tag = f"v{next_num}"
    target_dir = versions_dir / version_tag
    target_dir.mkdir(parents=True, exist_ok=False)

    files = _iter_project_files(project_dir)
    for rel, src in files.items():
        dst = target_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_text = note.strip() if note.strip() else "No note provided"
    _append_changelog(
        versions_dir,
        f"## {version_tag} ({timestamp})\n- **Note**: {note_text}\n- **Files**: {len(files)} file(s)\n",
    )

    print(f"Created snapshot {version_tag} at {target_dir} ({len(files)} file(s))")
    return 0


def cmd_diff(project_dir: Path, v1: str, v2: str) -> int:
    versions_dir = project_dir / "versions"
    try:
        tag1 = _normalize_version(v1)
        tag2 = _normalize_version(v2)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    dir1 = versions_dir / tag1
    dir2 = versions_dir / tag2
    for tag, d in ((tag1, dir1), (tag2, dir2)):
        if not d.is_dir():
            print(f"ERROR: Snapshot {tag} not found at {d}", file=sys.stderr)
            return 1

    files1 = _iter_project_files(dir1)
    files2 = _iter_project_files(dir2)
    all_rels = sorted(set(files1) | set(files2))

    has_diff = False
    for rel in all_rels:
        if rel not in files1:
            has_diff = True
            print(f"+++ ADDED: {rel.as_posix()}")
            continue
        if rel not in files2:
            has_diff = True
            print(f"--- REMOVED: {rel.as_posix()}")
            continue

        try:
            lines1 = files1[rel].read_text(encoding="utf-8").splitlines(keepends=True)
            lines2 = files2[rel].read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            if files1[rel].read_bytes() != files2[rel].read_bytes():
                has_diff = True
                print(f"~~~ BINARY CHANGED: {rel.as_posix()}")
            continue

        diff_lines = list(
            difflib.unified_diff(
                lines1,
                lines2,
                fromfile=f"{tag1}/{rel.as_posix()}",
                tofile=f"{tag2}/{rel.as_posix()}",
            )
        )
        if diff_lines:
            has_diff = True
            sys.stdout.writelines(diff_lines)
            if not diff_lines[-1].endswith("\n"):
                print()

    if not has_diff:
        print(f"No differences between {tag1} and {tag2}.")
    return 0


def cmd_rollback(project_dir: Path, version: str) -> int:
    versions_dir = project_dir / "versions"
    try:
        tag = _normalize_version(version)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    snap_dir = versions_dir / tag
    if not snap_dir.is_dir():
        print(f"ERROR: Snapshot {tag} not found at {snap_dir}", file=sys.stderr)
        return 1

    current_files = _iter_project_files(project_dir)
    snap_files = _iter_project_files(snap_dir)

    for rel, cur_path in current_files.items():
        if rel not in snap_files:
            cur_path.unlink()

    for rel, src_path in snap_files.items():
        dst_path = project_dir / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_changelog(
        versions_dir,
        f"## Rollback -> {tag} ({timestamp})\n- Restored {len(snap_files)} file(s) from {tag}\n",
    )

    print(f"Rolled back {project_dir} to {tag} ({len(snap_files)} file(s) restored)")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="version_manager.py",
        description="Manage project snapshots (v1, v2, ...), diffs, and rollbacks under <project_dir>/versions/.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_snap = subparsers.add_parser("snapshot", help="Create a new version snapshot (v1, v2, ...).")
    p_snap.add_argument("project_dir", type=Path, help="Path to the project directory.")
    p_snap.add_argument("--note", default="", help="Optional release/snapshot note for changelog.md.")

    p_diff = subparsers.add_parser("diff", help="Show unified diff between two snapshots.")
    p_diff.add_argument("project_dir", type=Path, help="Path to the project directory.")
    p_diff.add_argument("v1", help="Base version (e.g. v1 or 1).")
    p_diff.add_argument("v2", help="Target version (e.g. v2 or 2).")

    p_rb = subparsers.add_parser("rollback", help="Rollback project workspace files to a snapshot.")
    p_rb.add_argument("project_dir", type=Path, help="Path to the project directory.")
    p_rb.add_argument("version", help="Target version to restore (e.g. v1 or 1).")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "snapshot":
        return cmd_snapshot(args.project_dir, args.note)
    if args.command == "diff":
        return cmd_diff(args.project_dir, args.v1, args.v2)
    if args.command == "rollback":
        return cmd_rollback(args.project_dir, args.version)
    return 1


if __name__ == "__main__":
    sys.exit(main())
