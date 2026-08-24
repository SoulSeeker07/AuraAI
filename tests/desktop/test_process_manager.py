"""Test script for ProcessManager integration with DesktopAgent"""

import sys
import uuid

sys.path.insert(0, "d:/Sreekanta/VS Code Project/Desktop AI/AuraAI")

from agents.desktop_agent import DesktopAgent
from agents.task_model import Task, TaskInput, TaskType


def test_process_list():
    """Test PROCESS_LIST task"""
    print("=" * 50)
    print("Testing PROCESS_LIST task")
    print("=" * 50)
    pm = DesktopAgent(task_manager=None)
    task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_LIST,
        title="List processes",
        input=TaskInput(data={"max_results": 5}),
    )
    result = pm.execute_task(task)
    print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Message: {result.message}")
    if result.data:
        print(f"Count: {result.data.get('count', 0)}")
        print(f"Total CPU: {result.data.get('total_cpu_percent', 0)}%")
        print(f"Total Memory: {result.data.get('total_memory_mb', 0)} MB")
    print()


def test_process_search():
    """Test PROCESS_SEARCH task"""
    print("=" * 50)
    print("Testing PROCESS_SEARCH task")
    print("=" * 50)
    pm = DesktopAgent(task_manager=None)
    task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_SEARCH,
        title="Search Python processes",
        input=TaskInput(data={"name": "python", "max_results": 3}),
    )
    result = pm.execute_task(task)
    print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Message: {result.message}")
    if result.data:
        print(f"Count: {result.data.get('count', 0)}")
        processes = result.data.get("processes", [])
        for p in processes:
            print(
                f"  - {p.get('name')} (PID: {p.get('pid')}): {p.get('cpu_percent')}% CPU, {p.get('memory_mb')} MB"
            )
    print()


def test_process_get():
    """Test PROCESS_GET task"""
    print("=" * 50)
    print("Testing PROCESS_GET task")
    print("=" * 50)
    pm = DesktopAgent(task_manager=None)
    # Get the PID from search first
    search_task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_SEARCH,
        title="Find Python process",
        input=TaskInput(data={"name": "python", "max_results": 1}),
    )
    search_result = pm.execute_task(search_task)

    if search_result.data and search_result.data.get("processes"):
        pid = search_result.data["processes"][0]["pid"]
        print(f"Found process with PID: {pid}")

        task = Task(
            id=str(uuid.uuid4()),
            type=TaskType.PROCESS_GET,
            title="Get process info",
            input=TaskInput(data={"pid": pid}),
        )
        result = pm.execute_task(task)
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Message: {result.message}")
        if result.data:
            print(f"Name: {result.data.get('name')}")
            print(f"PID: {result.data.get('pid')}")
            print(f"Status: {result.data.get('status')}")
            print(f"CPU: {result.data.get('cpu_percent')}%")
            print(f"Memory: {result.data.get('memory_mb')} MB")
    else:
        print("No Python process found to test PROCESS_GET")
    print()


if __name__ == "__main__":
    test_process_list()
    test_process_search()
    test_process_get()

    print("=" * 50)
    print("All tests completed!")
    print("=" * 50)
