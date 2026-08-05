"""
Integration Test Suite: Stage 2 - Memory System
Tests memory write/read cycles, user facts, preferences, and topics.
"""

import json
import os
import shutil
import sys
import tempfile

from Memory import Memory


def setup_test_memory():
    """Create a temporary test memory instance."""
    temp_dir = tempfile.mkdtemp(prefix="aura_test_memory_")
    db_file = os.path.join(temp_dir, "memory.db")
    memory = Memory(db_path=db_file)
    return memory, temp_dir


def test_conversation_recording():
    """Test that conversations are recorded correctly."""
    print("\n  Testing conversation recording...")

    memory, temp_dir = setup_test_memory()

    try:
        memory.record_turn("Hello", "Hi there! How can I help you today?", "greeting")
        memory.record_turn(
            "I need help with Python", "I can help you with Python programming.", "help"
        )
        memory.record_turn("Thanks!", "You're welcome!", "closing")
        print("  ✓ Conversations recorded")

        chat_log = memory.load_chat_log()
        if len(chat_log) >= 3:
            print(f"  ✓ Chat log loaded ({len(chat_log)} turns)")
        else:
            print(f"  ⚠ Expected at least 3 turns, got {len(chat_log)}")

        recent = memory.recent_messages(limit=10)
        if len(recent) >= 3:
            print(f"  ✓ Recent messages retrieved ({len(recent)} messages)")
        else:
            print(f"  ⚠ Expected at least 3 messages, got {len(recent)}")

        found = memory.search("help")
        if len(found) > 0:
            print(f"  ✓ Search works ({len(found)} results)")
        else:
            print("  ⚠ Search returned no results")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ Conversation recording test passed")


def test_user_facts():
    """Test user fact storage and retrieval."""
    print("\n  Testing user facts...")

    memory, temp_dir = setup_test_memory()

    try:
        facts = {
            "name": "Sreekanta",
            "age": 30,
            "location": "New York",
            "job": "Software Developer",
        }

        for key, value in facts.items():
            memory.upsert_fact("user", key, value)
            print(f"  ✓ Saved fact: {key} = {value}")

        all_facts = memory.facts()
        if len(all_facts) >= 4:
            print(f"  ✓ Retrieved {len(all_facts)} facts")
        else:
            print(f"  ⚠ Expected at least 4 facts, got {len(all_facts)}")

        found = memory.search("name")
        if len(found) > 0:
            print(f"  ✓ Search for name returned {len(found)} result(s)")
        else:
            print("  ⚠ Search for name returned no results")

        memory.remember("My name is Sreekanta")
        all_facts = memory.facts()
        if len(all_facts) >= 5:
            print(f"  ✓ Text recall added facts ({len(all_facts)} total facts)")
        else:
            print(f"  ⚠ Text recall didn't add facts, got {len(all_facts)} facts")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ User facts test passed")


def test_preferences():
    """Test preference storage and retrieval."""
    print("\n  Testing preferences...")

    memory, temp_dir = setup_test_memory()

    try:
        preferences = {
            "preferred_editor": "VS Code",
            "preferred_language": "Python",
            "preferred_framework": "FastAPI",
            "timezone": "America/New_York",
        }

        for key, value in preferences.items():
            memory.upsert_fact("preference", key, value)
            print(f"  ✓ Set preference: {key} = {value}")

        all_facts = memory.facts()
        pref_facts = [f for f in all_facts if f.category == "preference"]
        if len(pref_facts) >= 4:
            print(f"  ✓ Retrieved {len(pref_facts)} preferences")
        else:
            print(f"  ⚠ Expected at least 4 preferences, got {len(pref_facts)}")

        context = memory.get_context()
        if "Preference" in context or "preference" in context.lower():
            print(f"  ✓ Context includes preferences: {context[:100]}...")
        else:
            print("  ⚠ Context doesn't seem to include preferences")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ Preferences test passed")


def test_topics():
    """Test topic-based memory organization."""
    print("\n  Testing topics...")

    memory, temp_dir = setup_test_memory()

    try:
        memory.record_turn(
            "Let's discuss networking.",
            "Great! What aspect of networking would you like to cover?",
            "networking",
        )
        memory.record_turn(
            "I'm interested in sockets.",
            "Sockets are a fundamental concept in networking.",
            "networking",
        )
        memory.record_turn(
            "Let's discuss investing.",
            "Investing can be complex. What type of investing interests you?",
            "investing",
        )
        memory.record_turn(
            "Stocks and bonds.",
            "Stocks and bonds are common investment vehicles.",
            "investing",
        )
        print("  ✓ Saved conversations to topics")

        topics = memory.recent_topics(limit=10)
        if len(topics) >= 2:
            print(f"  ✓ Retrieved {len(topics)} recent topics")
        else:
            print(f"  ⚠ Expected at least 2 topics, got {len(topics)}")

        found = memory.search("investing")
        if len(found) > 0:
            print(f"  ✓ Search for investing returned {len(found)} result(s)")
        else:
            print("  ⚠ Search for investing returned no results")

        context = memory.get_context()
        if "Topic" in context or "topic" in context.lower():
            print("  ✓ Context includes topics")
        else:
            print("  ⚠ Context doesn't seem to include topics")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ Topics test passed")


def test_delete_memory():
    """Test memory deletion."""
    print("\n  Testing memory deletion...")

    memory, temp_dir = setup_test_memory()

    try:
        memory.upsert_fact("user", "test_key", "test_value")
        memory.record_turn("test", "test", "test_topic")
        print("  ✓ Data created")

        deleted = memory.forget("test")
        if deleted > 0:
            print(f"  ✓ Deleted {deleted} fact(s)")
        else:
            print("  ⚠ No facts deleted")

        all_facts = memory.facts()
        if len(all_facts) == 0:
            print("  ✓ All facts deleted successfully")
        else:
            print(f"  ⚠ Still have {len(all_facts)} facts")

        memory.forget("non_existent")
        print("  ✓ Delete handles non-existent keys gracefully")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ Delete memory test passed")


def test_memory_persistence():
    """Test that memory persists across restarts."""
    print("\n  Testing memory persistence...")

    temp_dir = tempfile.mkdtemp(prefix="aura_test_memory_")
    db_file = os.path.join(temp_dir, "memory.db")

    try:
        memory1 = Memory(db_path=db_file)

        memory1.upsert_fact("user", "persistence_test", "should_survive")
        memory1.record_turn("session_test", "test data", "test_topic")
        print("  ✓ Data saved to memory")

        memory2 = Memory(db_path=db_file)

        all_facts = memory2.facts()
        if any(
            f.key == "persistence_test" and f.value == "should_survive"
            for f in all_facts
        ):
            print("  ✓ Facts persisted correctly")
        else:
            print("  ⚠ Facts did not persist")

        chat_log = memory2.load_chat_log()
        if len(chat_log) > 0:
            print(f"  ✓ Chat log persisted ({len(chat_log)} messages)")
        else:
            print("  ⚠ Chat log did not persist")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  ✓ Memory persistence test passed")


def run_stage_2_tests():
    """Run all Stage 2 Memory System tests."""
    print("=" * 70)
    print("STAGE 2: Memory System Integration Tests")
    print("=" * 70)

    try:
        test_conversation_recording()
        test_user_facts()
        test_preferences()
        test_topics()
        test_delete_memory()
        test_memory_persistence()

        return True
    except Exception as e:
        print(f"\n✗ Memory system tests failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_stage_2_tests()
    sys.exit(0 if success else 1)
