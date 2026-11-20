#!/usr/bin/env python3
"""Version snapshot, diff, and rollback manager for PRD project workspaces."""

import argparse
import datetime
import difflib
import fnmatch
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


EXCLUDED_NAMES: Set[str] = {
    "versions",
    ".git",
    "__pycache__",
    ".DS_Store",
    "_manifest.json",
    "wiki-export",
    "wiki-remote",
}

EXCLUDED_PATTERNS = (
    "*_manifest.secret.json",
    "*.env",
    "*.env.*",
    "*.pyc",
    "*.log",
)


def _is_part_excluded(name: str) -> bool:
    if name in EXCLUDED_NAMES or name.startswith("."):
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDED_PATTERNS)


def _is_rel_excluded(rel: Path) -> bool:
    return any(_is_part_excluded(part) for part in rel.parts)


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
        if entry.is_dir() and not entry.is_symlink():
            m = re.fullmatch(r"v(\d+)", entry.name)
            if m:
                nums.append(int(m.group(1)))
    return sorted(nums)


def _iter_project_files(root: Path, warn_dangling: bool = False) -> Dict[Path, Path]:
    """Return mapping of relative_path -> absolute_path for tracked regular workspace files.

    Safely skips excluded names/patterns and dangling symlinks without crashing.
    """
    files: Dict[Path, Path] = {}
    root_resolved = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root_resolved, topdown=True, followlinks=False):
        cur_dir = Path(dirpath)
        # Prune excluded directories and directory symlinks in-place
        kept_dirs: List[str] = []
        for d in sorted(dirnames):
            if _is_part_excluded(d):
                continue
            d_path = cur_dir / d
            if d_path.is_symlink():
                if warn_dangling and not d_path.exists():
                    rel_d = d_path.relative_to(root_resolved)
                    print(f"WARNING: Skipping dangling symlink: {rel_d}", file=sys.stderr)
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            if _is_part_excluded(fname):
                continue
            fpath = cur_dir / fname
            rel = fpath.relative_to(root_resolved)
            if _is_rel_excluded(rel):
                continue
            if fpath.is_symlink():
                if not fpath.exists():
                    if warn_dangling:
                        print(f"WARNING: Skipping dangling symlink: {rel}", file=sys.stderr)
                    continue
                if fpath.is_dir():
                    continue
            if fpath.is_file():
                files[rel] = fpath

    return dict(sorted(files.items(), key=lambda kv: kv[0]))


def _iter_workspace_removable_entries(root: Path) -> Dict[Path, Path]:
    """Return all non-excluded files AND symlinks (including dangling symlinks) under root."""
    entries: Dict[Path, Path] = {}
    root_resolved = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root_resolved, topdown=True, followlinks=False):
        cur_dir = Path(dirpath)
        kept_dirs: List[str] = []
        for d in sorted(dirnames):
            if _is_part_excluded(d):
                continue
            d_path = cur_dir / d
            if d_path.is_symlink():
                rel_d = d_path.relative_to(root_resolved)
                if not _is_rel_excluded(rel_d):
                    entries[rel_d] = d_path
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            if _is_part_excluded(fname):
                continue
            fpath = cur_dir / fname
            rel = fpath.relative_to(root_resolved)
            if _is_rel_excluded(rel):
                continue
            if fpath.is_symlink() or fpath.is_file():
                entries[rel] = fpath

    return entries


def _cleanup_empty_parents(unlinked_path: Path, stop_root: Path) -> None:
    """Recursively remove empty parent directories bottom-up up to stop_root."""
    stop_resolved = stop_root.resolve()
    parent = unlinked_path.parent
    while True:
        try:
            parent_resolved = parent.resolve()
        except OSError:
            break
        if parent_resolved == stop_resolved or stop_resolved not in parent_resolved.parents:
            break
        if _is_part_excluded(parent.name) or parent.is_symlink() or not parent.is_dir():
            break
        try:
            if any(parent.iterdir()):
                break
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _prune_all_empty_subdirs(root: Path) -> None:
    """Sweep any remaining empty non-excluded subdirectories bottom-up."""
    root_resolved = root.resolve()
    for dirpath, dirnames, _ in os.walk(root_resolved, topdown=False, followlinks=False):
        cur_dir = Path(dirpath)
        if cur_dir == root_resolved:
            continue
        rel = cur_dir.relative_to(root_resolved)
        if _is_rel_excluded(rel) or cur_dir.is_symlink():
            continue
        try:
            if not any(cur_dir.iterdir()):
                cur_dir.rmdir()
        except OSError:
            pass


def _has_unsnapshotted_additions_or_edits(
    current_files: Dict[Path, Path],
    latest_files: Dict[Path, Path],
) -> bool:
    """Return True if workspace has added or modified files compared to latest snapshot."""
    for rel, cur_path in current_files.items():
        if rel not in latest_files:
            return True
        try:
            if cur_path.read_bytes() != latest_files[rel].read_bytes():
                return True
        except OSError:
            return True
    return False


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

    files = _iter_project_files(project_dir, warn_dangling=True)
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
    if not project_dir.is_dir():
        print(f"ERROR: Project directory not found: {project_dir}", file=sys.stderr)
        return 1

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

    # Dirty workspace protection against latest snapshot v_latest
    existing = _existing_versions(versions_dir)
    if existing:
        latest_tag = f"v{existing[-1]}"
        latest_dir = versions_dir / latest_tag
        current_tracked = _iter_project_files(project_dir)
        latest_tracked = _iter_project_files(latest_dir)
        if _has_unsnapshotted_additions_or_edits(current_tracked, latest_tracked):
            backup_note = f"auto-backup before rollback to {tag}"
            rc = cmd_snapshot(project_dir, backup_note)
            if rc != 0:
                return rc

    removable_entries = _iter_workspace_removable_entries(project_dir)
    snap_files = _iter_project_files(snap_dir)

    # Remove extra files and any symlinks (including dangling symlinks), then prune empty parent dirs
    for rel, cur_path in sorted(removable_entries.items(), key=lambda kv: len(kv[0].parts), reverse=True):
        if rel not in snap_files or cur_path.is_symlink():
            cur_path.unlink(missing_ok=True)
            _cleanup_empty_parents(cur_path, project_dir)

    for rel, src_path in snap_files.items():
        dst_path = project_dir / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.is_symlink():
            dst_path.unlink(missing_ok=True)
        shutil.copy2(src_path, dst_path)

    _prune_all_empty_subdirs(project_dir)

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
