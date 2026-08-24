"""
PR Bundle Assembler & Git Governance Gate
Location: src/engineering/pr_assembler.py

Generates structured Pull Request / Patch bundles with evidence citations and
enforces human confirmation tokens for destructive Git actions and merges to main.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from core.orchestration.request_source import RequestSource
except (ImportError, ModuleNotFoundError):
    from src.core.orchestration.request_source import RequestSource

from .autonomous_loop import EngineeringTask, LoopExecutionResult
from .patch_synthesizer import CodePatch


class GitGovernanceError(Exception):
    """Raised when an autonomous task attempts a protected/destructive Git action without approval."""
    pass


@dataclass
class PRSummary:
    """Structured representation of an autonomous engineering pull request."""
    task_id: str
    title: str
    goal: str
    status: str
    files_changed: list[str] = field(default_factory=list)
    unified_diff: str = ""
    test_evidence: str = ""
    markdown_content: str = ""


# Destructive Git actions strictly requiring human authorization
PROTECTED_GIT_OPERATIONS: set[str] = {
    "merge_to_main",
    "merge_to_master",
    "git_push_force",
    "delete_branch",
    "reset_hard_main",
}


class PatchBundleAssembler:
    """
    Assembles evidence-grounded PR summaries and enforces Git governance gates.
    """

    def assemble_pr_summary(
        self,
        task: EngineeringTask,
        result: LoopExecutionResult,
    ) -> PRSummary:
        """
        Build a formatted PR summary including test citations, diffs, and outcome.
        """
        files_changed = [p.file_path for p in result.applied_patches]
        full_diff = "\n".join(p.diff_text for p in result.applied_patches)

        test_evidence_lines: list[str] = []
        for idx, tr in enumerate(result.test_results, start=1):
            status_tag = "PASSED" if tr.success else "FAILED"
            test_evidence_lines.append(
                f"- **Run #{idx}**: `{status_tag}` — {tr.passed_tests} passed, {tr.failed_tests} failed ({tr.duration_seconds:.2f}s)"
            )
        test_evidence = "\n".join(test_evidence_lines)

        md_parts = [
            f"# Pull Request: {task.goal} (Task `{task.task_id}`)",
            f"**Status:** `{result.final_status}` | **Attempts Used:** {result.attempts_used}",
            "",
            "## 1. Goal & Description",
            f"{task.goal}",
            "",
            "## 2. Modified Files",
        ]
        if files_changed:
            for f in files_changed:
                md_parts.append(f"- `{f}`")
        else:
            md_parts.append("*No files modified (clean state / rolled back).*")

        md_parts.extend([
            "",
            "## 3. Test Verification Evidence",
            test_evidence or "*No test runs recorded.*",
            "",
            "## 4. Unified Diff",
            "```diff",
            full_diff or "# No diff",
            "```",
        ])

        markdown_content = "\n".join(md_parts)

        return PRSummary(
            task_id=task.task_id,
            title=f"Fix: {task.goal}",
            goal=task.goal,
            status=result.final_status,
            files_changed=files_changed,
            unified_diff=full_diff,
            test_evidence=test_evidence,
            markdown_content=markdown_content,
        )

    def authorize_git_operation(
        self,
        operation: str,
        source: RequestSource = RequestSource.DAEMON_BACKGROUND,
        ticket_id: str | None = None,
        signature: str | None = None,
    ) -> bool:
        """
        Authorize Git operations against governance policies.
        
        Destructive operations (merge to main, push force, branch deletion)
        require human interactive source or a valid cryptographic confirmation ticket & signature.
        Strictly fail-closed: any failure to positively verify raises GitGovernanceError.
        """
        clean_op = operation.lower().strip()

        # Non-destructive Git operations pass through
        if clean_op not in PROTECTED_GIT_OPERATIONS:
            return True

        # Interactive human turn authorizes protected Git operation
        if source == RequestSource.HUMAN_INTERACTIVE:
            return True

        # Autonomous source MUST provide cryptographic approval credentials
        if not ticket_id or not signature:
            raise GitGovernanceError(
                f"Autonomous Git operation '{operation}' is blocked: merging to main or destructive "
                f"Git actions require a valid human confirmation ticket and cryptographic signature."
            )

        # CryptographicApprovalAuthority ticket & signature redemption
        try:
            from src.desktop.native.security.approval_authority import CryptographicApprovalAuthority
        except (ImportError, ModuleNotFoundError):
            try:
                from desktop.native.security.approval_authority import CryptographicApprovalAuthority
            except (ImportError, ModuleNotFoundError) as exc:
                raise GitGovernanceError(
                    f"Cryptographic approval authority is unavailable to verify '{operation}' (fail-closed): {exc}"
                )

        if not CryptographicApprovalAuthority or not hasattr(CryptographicApprovalAuthority, "get_instance"):
            raise GitGovernanceError(
                f"CryptographicApprovalAuthority instance is not accessible for '{operation}' (fail-closed)."
            )

        auth = CryptographicApprovalAuthority.get_instance()
        is_valid, msg = auth.verify_and_redeem(
            ticket_id=ticket_id,
            signature=signature,
            action_type="git_operation",
            target=clean_op,
        )
        if not is_valid:
            raise GitGovernanceError(
                f"Cryptographic ticket rejection for Git operation '{operation}': {msg}"
            )

        return True


__all__ = [
    "PRSummary",
    "GitGovernanceError",
    "PatchBundleAssembler",
    "PROTECTED_GIT_OPERATIONS",
]
