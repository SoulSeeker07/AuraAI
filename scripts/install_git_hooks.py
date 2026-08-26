#!/usr/bin/env python3
"""
Install repository Git hooks for AuraAI.
Configures git to use .githooks directory for pre-commit verification.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def install_hooks() -> int:
    try:
        # Configure git to look at .githooks directory
        res = subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("[SUCCESS] Git hooks configured to '.githooks'.")
            print("[SUCCESS] Pre-commit AST method shadowing check is active on all commits.")
            return 0
        else:
            print(f"[WARN] Failed to configure core.hooksPath: {res.stderr.strip()}", file=sys.stderr)
            # Fallback: copy directly into .git/hooks/pre-commit
            git_hook_dest = PROJECT_ROOT / ".git" / "hooks" / "pre-commit"
            source_hook = PROJECT_ROOT / ".githooks" / "pre-commit"
            if source_hook.exists() and git_hook_dest.parent.exists():
                git_hook_dest.write_text(source_hook.read_text(encoding="utf-8"), encoding="utf-8")
                print("[SUCCESS] Fallback: Copied pre-commit hook directly to .git/hooks/pre-commit.")
                return 0
            return 1
    except Exception as e:
        print(f"[ERROR] Error installing Git hooks: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(install_hooks())
