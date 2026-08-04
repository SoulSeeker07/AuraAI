"""Test script for ProcessManager event-driven features"""
import sys
import uuid
import time
import logging
from datetime import datetime
sys.path.insert(0, 'd:/Sreekanta/VS Code Project/Desktop AI/AuraAI')

# Import modules directly to avoid package structure issues
import core.event_bus as event_bus_module
import core.logger as logger_module
sys.path.insert(1, 'd:/Sreekanta/VS Code Project/Desktop AI/AuraAI/src')

from core.event_bus import EventBus
from core.logger import get_logger
from agents.process_manager import ProcessManager, ProcessEvent, ProcessState
from agents.task_model import Task, TaskType, TaskInput

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_event_bus_integration():
    """Test EventBus integration with ProcessManager"""
    print("\n" + "=" * 70)
    print("TEST 1: Event Bus Integration")
    print("=" * 70)

    # Create EventBus
    event_bus = EventBus()
    pm = ProcessManager(event_bus=event_bus)

    # Subscribe to process events
    event_log = []

    def log_event(event):
        event_log.append({
            'time': datetime.now(),
            'event': event.name,
            'data': event.payload
        })
        print(f"\n[Event Published]: {event.name}")
        print(f"  PID: {event.payload.get('pid')}")
        print(f"  Name: {event.payload.get('name')}")
        if event.payload.get('old_status'):
            print(f"  Old Status: {event.payload.get('old_status')}")
        print(f"  New Status: {event.payload.get('new_status')}")

    event_bus.subscribe(ProcessEvent.PROCESS_STARTED, log_event)
    event_bus.subscribe(ProcessEvent.PROCESS_EXITED, log_event)
    event_bus.subscribe(ProcessEvent.PROCESS_CHANGED, log_event)
    event_bus.subscribe(ProcessEvent.PROCESS_LIST_UPDATED, log_event)

    print("\nWaiting for events (3 seconds)...")

    # Wait for events to be published
    time.sleep(3)

    # Get all process states
    states = pm.get_all_process_states()
    print(f"\nTracked processes: {len(states)}")
    for pid, state in states.items():
        print(f"  PID {pid}: {state.name} - {state.previous_status}")

    # Cleanup
    pm.cleanup()

    print(f"\nTotal events logged: {len(event_log)}")
    for i, event in enumerate(event_log, 1):
        print(f"  {i}. {event['event']}")
    print()

def test_background_monitor():
    """Test background monitor is running"""
    print("\n" + "=" * 70)
    print("TEST 2: Background Monitor Status")
    print("=" * 70)

    event_bus = EventBus()
    pm = ProcessManager(event_bus=event_bus)

    print(f"Monitor running: {pm._monitor_running}")
    print(f"Monitor thread: {pm._monitor_thread is not None}")
    print(f"Monitor thread name: {pm._monitor_thread.name if pm._monitor_thread else 'None'}")

    # Run for a moment to see if it's working
    print("\nRunning for 3 seconds to verify monitor is active...")
    import time
    time.sleep(3)

    states = pm.get_all_process_states()
    print(f"Tracked processes after scan: {len(states)}")

    pm.cleanup()
    print()

def test_process_state_tracking():
    """Test process state tracking"""
    print("\n" + "=" * 70)
    print("TEST 3: Process State Tracking")
    print("=" * 70)

    event_bus = EventBus()
    pm = ProcessManager(event_bus=event_bus)

    # Get initial state
    search_task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_SEARCH,
        title="Find Python process",
        input=TaskInput(data={"name": "python", "max_results": 1})
    )
    result = pm.execute_task(search_task)

    if result.data and result.data.get("processes"):
        pid = result.data["processes"][0]["pid"]
        print(f"\nFound process: PID {pid}")

        # Get initial state
        state1 = pm.get_process_state(pid)
        if state1:
            print(f"\nInitial State:")
            print(f"  PID: {state1.pid}")
            print(f"  Name: {state1.name}")
            print(f"  Status: {state1.previous_status}")
            print(f"  CPU: {state1.previous_cpu}%")
            print(f"  Memory: {state1.previous_memory} MB")
        elif state2:
            print("\n(No initial state was captured yet — monitor hadn't scanned this PID before the first check)")

        # Wait a moment and check again
        print("\nWaiting 2 seconds for potential changes...")
        import time
        time.sleep(2)

        state2 = pm.get_process_state(pid)
        if state2:
            print(f"\nUpdated State:")
            print(f"  PID: {state2.pid}")
            print(f"  Name: {state2.name}")
            print(f"  Status: {state2.previous_status}")
            print(f"  CPU: {state2.previous_cpu}%")
            print(f"  Memory: {state2.previous_memory} MB")

            if state1 and state2:
                if state1.has_changed(state2):
                    print("\n✓ Process state changed detected!")
                else:
                    print("\n✓ Process state unchanged (expected for idle process)")

    pm.cleanup()
    print()

def test_process_list_updated_event():
    """Test PROCESS_LIST_UPDATED event"""
    print("\n" + "=" * 70)
    print("TEST 4: Process List Updated Event")
    print("=" * 70)

    event_bus = EventBus()
    pm = ProcessManager(event_bus=event_bus)

    event_log = []

    def log_event(event):
        event_log.append(event)

    event_bus.subscribe(ProcessEvent.PROCESS_LIST_UPDATED, log_event)

    print("\nListing processes to trigger event...")
    list_task = Task(
        id=str(uuid.uuid4()),
        type=TaskType.PROCESS_LIST,
        title="List processes",
        input=TaskInput(data={"max_results": 5})
    )
    result = pm.execute_task(list_task)

    print(f"\nProcesses listed: {result.data.get('count', 0)}")

    # Wait a moment for event to be published
    import time
    time.sleep(1)

    print(f"\nEvents published: {len(event_log)}")
    for event in event_log:
        print(f"  Event: {event.name}")
        print(f"  Payload: {event.payload}")

    pm.cleanup()
    print()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PROCESS MANAGER EVENT-DRIVEN FEATURES TEST")
    print("=" * 70)

    try:
        test_event_bus_integration()
        test_background_monitor()
        test_process_state_tracking()
        test_process_list_updated_event()

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED!")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print()
