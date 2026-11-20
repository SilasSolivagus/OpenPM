#!/usr/bin/env python3
"""Safe in-place upgrader for existing OpenPM workspaces (Codex / Claude Code / Cursor / Antigravity / dsh).

Updates OpenPM core engine, gate scripts, specs, adapters, and skills from origin/main
(https://github.com/SilasSolivagus/OpenPM.git) while 100% preserving user-owned files:
  - .env.local (platform credentials)
  - projects/<custom_project>/ (all user PRDs, wireframes, flowcharts, contexts, snapshots)

After updating core files, automatically recompiles user projects' walkthrough.html with the
new build_walkthrough.py and runs preflight_check.py so any newly caught topology/orientation/delta
issues are surfaced clearly for the Agent to fix.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/SilasSolivagus/OpenPM.git"
BUILTIN_DEMOS = {"b-end-approval-flow", "demo-captcha-publish"}
CORE_PATHS = [
    "AGENTS.md",
    "CLAUDE.md",
    "WORKBUDDY.md",
    ".cursorrules",
    ".gitignore",
    "README.md",
    "index.html",
    "scripts",
    "skills",
    "specs",
    "adapters",
    "templates",
    "evals/test-cases",
]


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=check)


def _sync_skill_symlinks(root: Path) -> list[str]:
    synced: list[str] = []
    skills_src = root / "skills"
    if not skills_src.is_dir():
        return synced

    home = Path.home()
    candidates = [
        home / ".dsh" / "skills",
        home / ".codex" / "skills",
    ]
    for target_dir in candidates:
        if not target_dir.is_dir():
            continue
        for skill_folder in sorted(skills_src.iterdir()):
            if not skill_folder.is_dir() or not (skill_folder / "SKILL.md").is_file():
                continue
            link_path = target_dir / skill_folder.name
            if link_path.is_symlink():
                try:
                    if link_path.resolve() == skill_folder.resolve():
                        synced.append(str(link_path))
                except OSError:
                    pass
    return synced


def upgrade_workspace(root: Path, recompile_projects: bool = True) -> int:
    git_dir = root / ".git"
    if not git_dir.exists():
        print(f"[upgrade_openpm] Error: {root} is not a git repository.", file=sys.stderr)
        return 1

    remotes = _run(["git", "remote"], root, check=False).stdout.split()
    remote_name = "openpm-upstream"
    if "origin" in remotes:
        origin_url = _run(["git", "remote", "get-url", "origin"], root, check=False).stdout.strip()
        if "OpenPM" in origin_url:
            remote_name = "origin"
        elif remote_name not in remotes:
            _run(["git", "remote", "add", remote_name, REPO_URL], root, check=True)
    else:
        _run(["git", "remote", "add", "origin", REPO_URL], root, check=True)
        remote_name = "origin"

    print(f"[upgrade_openpm] Fetching latest main from {remote_name} ({REPO_URL})...")
    fetch_res = _run(["git", "fetch", remote_name, "main"], root, check=False)
    if fetch_res.returncode != 0:
        print(f"[upgrade_openpm] Network/fetch error:\n{fetch_res.stderr.strip()}", file=sys.stderr)
        return 1

    # Safely checkout only framework/core paths from <remote_name>/main; never touch .env.local or user projects/*
    checkout_cmd = ["git", "checkout", f"{remote_name}/main", "--"] + CORE_PATHS
    co_res = _run(checkout_cmd, root, check=False)
    if co_res.returncode != 0:
        print(f"[upgrade_openpm] Checkout error:\n{co_res.stderr.strip()}", file=sys.stderr)
        return 1

    print("[upgrade_openpm] Core engine, skills, specs, and preflight gates updated successfully.")
    print("[upgrade_openpm] Preserved .env.local, evals/datasets/*, evals/taste-profile.md, and all projects/*.")
    # Seed evals/taste-profile.md from upstream only if local workspace doesn't have one yet
    taste_file = root / "evals" / "taste-profile.md"
    if not taste_file.is_file():
        _run(["git", "checkout", f"{remote_name}/main", "--", "evals/taste-profile.md"], root, check=False)
    _sync_skill_symlinks(root)

    if not recompile_projects:
        return 0

    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return 0

    gate_failures = 0
    for proj in sorted(projects_dir.iterdir()):
        if not proj.is_dir() or proj.name in BUILTIN_DEMOS or proj.name.startswith("."):
            continue
        spec_file = proj / "spec.json"
        svg_file = proj / "flow.svg"
        pages_dir = proj / "pages"
        out_html = proj / "walkthrough.html"
        if not (spec_file.is_file() and svg_file.is_file() and pages_dir.is_dir()):
            continue

        print(f"\n[upgrade_openpm] Recompiling & checking user project: {proj.name}")
        skeleton_candidates = list((proj / "references").glob("*skeleton*.css")) + list(
            (proj / "references").glob("wt-*.css")
        )
        build_cmd = [
            sys.executable,
            str(root / "scripts" / "build_walkthrough.py"),
            "--spec",
            str(spec_file),
            "--svg",
            str(svg_file),
            "--pages-dir",
            str(pages_dir),
            "--out",
            str(out_html),
        ]
        if skeleton_candidates:
            build_cmd += ["--skeleton-css", str(skeleton_candidates[0])]

        b_res = _run(build_cmd, root, check=False)
        if b_res.returncode != 0:
            print(b_res.stderr.strip(), file=sys.stderr)
            gate_failures += 1
            continue

        for target in (spec_file, out_html):
            p_res = _run(
                [sys.executable, str(root / "scripts" / "preflight_check.py"), str(target)],
                root,
                check=False,
            )
            if p_res.returncode != 0:
                print(p_res.stderr.strip(), file=sys.stderr)
                gate_failures += 1
            else:
                print(f"  {p_res.stdout.strip()}")

    if gate_failures:
        print(
            "\n[upgrade_openpm] Action required for AI Agent: fix the preflight issues reported above "
            "(e.g., redraw horizontal/diagonal flow.svg into Top-Down orthogonal layout and cap 'new'/'modified' "
            "nodes at <= 75%), then re-run build_walkthrough.py and preflight_check.py.",
            file=sys.stderr,
        )
        return 2

    print("\n[upgrade_openpm] All user projects rebuilt and passed preflight checks!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely upgrade an existing OpenPM workspace in place.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Root directory of the OpenPM workspace (defaults to parent of scripts/)",
    )
    parser.add_argument(
        "--no-recompile",
        action="store_true",
        help="Only update OpenPM core files without recompiling user projects",
    )
    args = parser.parse_args()
    return upgrade_workspace(args.root.resolve(), recompile_projects=not args.no_recompile)


if __name__ == "__main__":
    sys.exit(main())
