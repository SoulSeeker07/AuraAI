"""
Gate G5 Automated Verification Suite — Human Merge Gate & PR Assembly
Location: tests/test_engineering_g5_git_governance.py

Verifies:
- G5-1: Patch bundle assembler generates structured PR summaries with test evidence & diffs.
- G5-2: Autonomous merge to main/master is strictly blocked without a human confirmation token.
- G5-3: Autonomous git push force is strictly blocked without a human confirmation token.
- G5-4: Autonomous branch deletion is strictly blocked without a human confirmation token.
- G5-5: Valid human confirmation token or HUMAN_INTERACTIVE source successfully authorizes protected Git operations.
"""

import pytest

from src.core.orchestration.request_source import RequestSource
from src.engineering.autonomous_loop import EngineeringTask, LoopExecutionResult
from src.engineering.patch_synthesizer import CodePatch
from src.engineering.pr_assembler import (
    GitGovernanceError,
    PatchBundleAssembler,
    PRSummary,
)
from src.engineering.test_runner import TestRunResult


def test_patch_bundle_assembler_generates_pr_summary():
    """G5-1: Verifies generation of structured PR markdown summary with citations."""
    assembler = PatchBundleAssembler()
    task = EngineeringTask(task_id="task_101", goal="Fix off-by-one error in parser")

    patch = CodePatch(
        file_path="src/parser.py",
        original_content="x = i + 1\n",
        new_content="x = i\n",
        diff_text="--- a/src/parser.py\n+++ b/src/parser.py\n@@ -1 +1 @@\n-x = i + 1\n+x = i\n",
    )

    test_res = TestRunResult(
        success=True,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        error_count=0,
        duration_seconds=0.45,
    )

    result = LoopExecutionResult(
        success=True,
        task_id="task_101",
        attempts_used=1,
        applied_patches=[patch],
        test_results=[test_res],
        final_status="COMPLETED",
    )

    summary = assembler.assemble_pr_summary(task, result)

    assert isinstance(summary, PRSummary)
    assert summary.task_id == "task_101"
    assert summary.status == "COMPLETED"
    assert "src/parser.py" in summary.files_changed
    assert "Fix off-by-one error in parser" in summary.markdown_content
    assert "5 passed, 0 failed (0.45s)" in summary.markdown_content
    assert "+x = i" in summary.markdown_content


def test_merge_to_main_blocked_without_human_confirmation():
    """G5-2: Verifies autonomous merge to main raises GitGovernanceError."""
    assembler = PatchBundleAssembler()

    with pytest.raises(GitGovernanceError) as exc_info:
        assembler.authorize_git_operation(
            operation="merge_to_main",
            source=RequestSource.DAEMON_BACKGROUND,
            ticket_id=None,
            signature=None,
        )
    assert "merging to main or destructive Git actions require a valid human confirmation" in str(exc_info.value)


def test_git_push_force_blocked_without_human_confirmation():
    """G5-3: Verifies autonomous git push force raises GitGovernanceError."""
    assembler = PatchBundleAssembler()

    with pytest.raises(GitGovernanceError):
        assembler.authorize_git_operation(
            operation="git_push_force",
            source=RequestSource.TRIGGER_AUTONOMOUS,
            ticket_id=None,
            signature=None,
        )


def test_branch_deletion_blocked_without_human_confirmation():
    """G5-4: Verifies autonomous branch deletion raises GitGovernanceError."""
    assembler = PatchBundleAssembler()

    with pytest.raises(GitGovernanceError):
        assembler.authorize_git_operation(
            operation="delete_branch",
            source=RequestSource.DAEMON_BACKGROUND,
            ticket_id=None,
            signature=None,
        )


def test_human_token_authorizes_pr_merge():
    """G5-5: Verifies human interactive source authorizes merge, autonomous requires ticket."""
    assembler = PatchBundleAssembler()

    # 1. Interactive human source is authorized
    authorized_human = assembler.authorize_git_operation(
        operation="merge_to_main",
        source=RequestSource.HUMAN_INTERACTIVE,
    )
    assert authorized_human is True

    # 2. Autonomous source without ticket_id/signature is blocked
    with pytest.raises(GitGovernanceError) as exc_info:
        assembler.authorize_git_operation(
            operation="merge_to_main",
            source=RequestSource.DAEMON_BACKGROUND,
            ticket_id=None,
            signature=None,
        )
    assert "require a valid human confirmation ticket and cryptographic signature" in str(exc_info.value)


def test_cryptographic_approval_authority_ticket_redemption():
    """G5-6: Verifies cryptographic ticket creation, human signing, and redemption for merge."""
    from src.desktop.native.security.approval_authority import CryptographicApprovalAuthority
    
    auth = CryptographicApprovalAuthority.get_instance()
    ticket_id = auth.create_ticket(
        action_type="git_operation",
        target="merge_to_main",
    )
    sig = auth.generate_human_signature(ticket_id)
    assert sig is not None

    assembler = PatchBundleAssembler()
    # Redeeming with valid ticket_id and signature authorizes the operation
    authorized = assembler.authorize_git_operation(
        operation="merge_to_main",
        source=RequestSource.DAEMON_BACKGROUND,
        ticket_id=ticket_id,
        signature=sig,
    )
    assert authorized is True

    # Re-redeeming the same single-use ticket fails (replay protection)
    with pytest.raises(GitGovernanceError) as exc_info:
        assembler.authorize_git_operation(
            operation="merge_to_main",
            source=RequestSource.DAEMON_BACKGROUND,
            ticket_id=ticket_id,
            signature=sig,
        )
    assert "Cryptographic ticket rejection" in str(exc_info.value)
