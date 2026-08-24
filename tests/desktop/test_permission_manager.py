"""Test script for PermissionManager integration with ProcessManager"""

import sys
import uuid

sys.path.insert(0, "d:/Sreekanta/VS Code Project/Desktop AI/AuraAI")
sys.path.insert(1, "d:/Sreekanta/VS Code Project/Desktop AI/AuraAI/src")

import time

from agents.permission_manager import PermissionLevel, PermissionManager
from agents.process_manager import ProcessManager
from agents.task_model import Task, TaskInput, TaskType


def test_permission_manager_basic():
    """Test basic permission manager functionality"""
    print("\n" + "=" * 70)
    print("TEST 1: Basic Permission Manager")
    print("=" * 70)

    pm = PermissionManager()

    # Test safe operation (should not ask)
    print("\nTest 1a: Safe operation should not ask for permission")
    can_execute = pm.can_execute_operation(
        "list_processes", "PID 123", PermissionLevel.MODERATE
    )
    print(f"  can_execute(list_processes): {can_execute}")
    assert can_execute == True, "Safe operation should not require permission"
    print("  ✓ Safe operation returns True")

    # Test dangerous operation (should ask)
    print("\nTest 1b: Dangerous operation should require permission")
    can_execute = pm.can_execute_operation(
        "kill_process", "PID 123", PermissionLevel.MODERATE
    )
    print(f"  can_execute(kill_process): {can_execute}")
    assert can_execute == False, "Dangerous operation should require permission"
    print("  ✓ Dangerous operation returns False")

    # Test request_permission
    print("\nTest 1c: Request permission")
    approved = pm.request_permission(
        operation="test_operation",
        target="PID 123",
        details="Test operation",
        level=PermissionLevel.MODERATE,
    )
    print(f"  Permission approved: {approved}")
    print("  ✓ Permission requested successfully")

    # Test get request log
    print("\nTest 1d: Get request log")
    log = pm.get_request_log()
    print(f"  Total requests in log: {len(log)}")
    assert len(log) == 1, "Should have 1 request in log"
    print("  ✓ Log retrieved successfully")

    # Test approved requests
    print("\nTest 1e: Get approved requests")
    approved_requests = pm.get_approved_requests()
    print(f"  Approved requests: {len(approved_requests)}")
    assert len(approved_requests) == 1, "Should have 1 approved request"
    print("  ✓ Approved requests retrieved")

    # Test denied requests
    print("\nTest 1f: Get denied requests")
    denied_requests = pm.get_denied_requests()
    print(f"  Denied requests: {len(denied_requests)}")
    assert len(denied_requests) == 0, "Should have 0 denied requests"
    print("  ✓ Denied requests retrieved")

    pm.clear_log()
    print("\n  Log cleared successfully")


def test_permission_manager_with_process_manager():
    """Test ProcessManager with PermissionManager"""
    print("\n" + "=" * 70)
    print("TEST 2: ProcessManager with PermissionManager")
    print("=" * 70)

    # Create ProcessManager with PermissionManager
    perm_mgr = PermissionManager()
    pm = ProcessManager(permission_manager=perm_mgr)

    print("\nTest 2a: Find a test process")
    search_task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_SEARCH,
        title="Find Python process",
        input=TaskInput(data={"name": "python", "max_results": 1}),
    )
    result = pm.execute_task(search_task)

    if result.data and result.data.get("processes"):
        pid = result.data["processes"][0]["pid"]
        print(f"  Found process: PID {pid}")
        print(f"  Process name: {result.data['processes'][0]['name']}")
    else:
        print("  No Python process found - test skipped")
        return

    # Test 2b: Try to stop process (this should ask for permission)
    print("\nTest 2b: Attempt to stop process (will ask for permission)")
    print("  (You should see permission request in console)")
    print("  (Type 'no' to deny permission)")
    print("  (Type 'yes' to approve permission)")

    stop_task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_STOP,
        title="Stop process",
        input=TaskInput(data={"pid": pid, "timeout": 3}),
    )
    stop_result = pm.execute_task(stop_task)

    print(f"  Process stopped successfully: {stop_result.success}")
    if stop_result.success:
        print("  ✓ Permission was approved, process was stopped")
    else:
        print("  (Permission was denied or process failed to stop)")

    # Test 2c: Verify process is no longer running
    print("\nTest 2c: Verify process status after stop")
    try:
        # Try to get process info again
        info = pm.get_process_info(pid)
        if info:
            print(f"  Process still running: {info.name}")
            print(f"  Status: {info.status}")
        else:
            print("  Process not found (correct)")
    except Exception as e:
        print(f"  Exception: {e}")
        print("  ✓ Process is no longer running")

    pm.cleanup()
    print("  ProcessManager cleaned up")


def test_permission_manager_log():
    """Test permission manager audit log"""
    print("\n" + "=" * 70)
    print("TEST 3: Permission Manager Audit Log")
    print("=" * 70)

    perm_mgr = PermissionManager()

    # Request multiple permissions
    print("\nTest 3a: Request multiple permissions")

    perm1 = perm_mgr.request_permission(
        operation="list_processes",
        target="all processes",
        details="List all running processes",
        level=PermissionLevel.SAFE,
        requester="Test",
    )
    print(f"  Permission 1 (safe): {perm1}")
    assert perm1 == True, "Safe permission should be approved"

    perm2 = perm_mgr.request_permission(
        operation="kill_process",
        target="PID 123",
        details="Kill process 123",
        level=PermissionLevel.DANGEROUS,
        requester="Test",
    )
    print(f"  Permission 2 (dangerous): {perm2}")
    assert perm2 == False, "Should default to denying dangerous operation"

    perm3 = perm_mgr.request_permission(
        operation="stop_process",
        target="PID 456",
        details="Stop process 456",
        level=PermissionLevel.MODERATE,
        requester="Test",
    )
    print(f"  Permission 3 (moderate): {perm3}")
    assert perm3 == False, "Should default to denying moderate operation"

    # Get log
    print("\nTest 3b: Get audit log")
    log = perm_mgr.get_request_log()
    print(f"  Total requests: {len(log)}")
    assert len(log) == 3, "Should have 3 requests in log"

    print("\n  Log details:")
    for i, request in enumerate(log, 1):
        print(f"    {i}. {request.operation} on {request.target}")
        print(f"       Approved: {request.approved}")
        print(f"       Level: {request.level.value}")
        print(f"       Time: {request.timestamp}")

    # Test formatting
    print("\nTest 3c: Format log for display")
    formatted = perm_mgr.format_request_log()
    print("\n" + formatted)


def test_permission_manager_custom_handler():
    """Test custom permission confirmation handler"""
    print("\n" + "=" * 70)
    print("TEST 4: Custom Permission Handler")
    print("=" * 70)

    def custom_handler(request: PermissionManager.PermissionRequest) -> bool:
        """Custom handler that always approves after showing details"""
        print("\n  Custom handler received:")
        print(f"    Operation: {request.operation}")
        print(f"    Target: {request.target}")
        print(f"    Details: {request.details[:100]}...")
        print(f"    Level: {request.level.value}")
        return True

    perm_mgr = PermissionManager(custom_confirmation_handler=custom_handler)

    print("\nTest 4a: Request permission with custom handler")
    approved = perm_mgr.request_permission(
        operation="custom_test",
        target="PID 789",
        details="Test operation with custom handler",
        level=PermissionLevel.MODERATE,
    )
    print(f"  Permission approved: {approved}")
    assert approved == True, "Custom handler should approve"
    print("  ✓ Custom handler works correctly")

    # Test that handler can also deny
    def deny_handler(request: PermissionManager.PermissionRequest) -> bool:
        """Handler that always denies"""
        print("\n  Deny handler received")
        return False

    perm_mgr.set_confirmation_handler(deny_handler)

    print("\nTest 4b: Request permission with deny handler")
    approved = perm_mgr.request_permission(
        operation="custom_test",
        target="PID 789",
        details="Test operation with deny handler",
        level=PermissionLevel.MODERATE,
    )
    print(f"  Permission approved: {approved}")
    assert approved == False, "Deny handler should deny"
    print("  ✓ Deny handler works correctly")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PERMISSION MANAGER TESTS")
    print("=" * 70)

    try:
        test_permission_manager_basic()
        test_permission_manager_with_process_manager()
        test_permission_manager_log()
        test_permission_manager_custom_handler()

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED!")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print()
