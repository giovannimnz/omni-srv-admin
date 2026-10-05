#!/usr/bin/env python3
import os
import sys
import subprocess

def check_repo(repo_path):
    repo_name = os.path.basename(repo_path)
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return None
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        branch = "unknown"

    try:
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty_count = len(status_out.splitlines()) if status_out else 0
    except Exception:
        dirty_count = -1

    try:
        subprocess.run(
            ["git", "fetch", "origin", "--prune"],
            cwd=repo_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12
        )
    except Exception:
        pass

    ahead = "0"
    behind = "0"
    try:
        behind = subprocess.check_output(
            ["git", "rev-list", f"HEAD..origin/{branch}", "--count"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        behind = "?"

    try:
        ahead = subprocess.check_output(
            ["git", "rev-list", f"origin/{branch}..HEAD", "--count"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        ahead = "?"

    return {
        "name": repo_name,
        "path": repo_path,
        "branch": branch,
        "dirty": dirty_count,
        "ahead": ahead,
        "behind": behind
    }

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/GitHub")
    if not os.path.isdir(target_dir):
        # Fallback for Windows Documents/GitHub
        win_path = os.path.expandvars(r"%USERPROFILE%\Documents\GitHub")
        if os.path.isdir(win_path):
            target_dir = win_path
        else:
            print(f"Directory {target_dir} does not exist.")
            sys.exit(1)

    print(f"Scanning git repositories in: {target_dir}")
    print(f"{'Repository':<28} | {'Branch':<14} | {'Dirty':<6} | {'Ahead':<6} | {'Behind':<6}")
    print("-" * 72)

    found = 0
    for item in sorted(os.listdir(target_dir)):
        p = os.path.join(target_dir, item)
        if os.path.isdir(p) and os.path.isdir(os.path.join(p, ".git")):
            info = check_repo(p)
            if info:
                found += 1
                print(f"{info['name']:<28} | {info['branch']:<14} | {str(info['dirty']):<6} | {str(info['ahead']):<6} | {str(info['behind']):<6}")

    print("-" * 72)
    print(f"Total repositories found: {found}")

if __name__ == "__main__":
    main()
