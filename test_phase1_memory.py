"""
Test Script for Phase 1 Memory System Migration

This script tests:
1. MemoryManager uses Memory.py backend
2. get_recent_messages() returns actual messages (not empty)
3. Facts can be stored and retrieved
4. Context building works
5. Persistence across operations
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memory.memory_manager import MemoryManager
from Memory import Memory

def test_memory_manager_initialization():
    """Test 1: MemoryManager can be initialized with Memory.py"""
    print("\n=== Test 1: MemoryManager Initialization ===")
    
    # Test with Memory.py instance
    memory = Memory()
    manager = MemoryManager(memory=memory)
    
    assert manager.memory is not None, "Memory instance should be stored"
    assert isinstance(manager.memory, Memory), "Should be a Memory.py instance"
    print("✅ MemoryManager initialized with Memory.py backend")
    return manager

def test_remember_and_retrieve():
    """Test 2: Facts can be stored and retrieved"""
    print("\n=== Test 2: Store and Retrieve Facts ===")
    
    memory = Memory()
    manager = MemoryManager(memory=memory)
    
    # Store facts
    manager.remember("person", "name", "John Doe")
    manager.remember("person", "age", "30")
    manager.remember("preference", "food", "pizza")
    
    # Retrieve facts
    name = manager.retrieve("person", "name")
    assert name is not None, "Should retrieve name fact"
    assert name.value == "John Doe", f"Expected 'John Doe', got '{name.value}'"
    
    age = manager.retrieve("person", "age")
    assert age is not None, "Should retrieve age fact"
    assert age.value == "30", f"Expected '30', got '{age.value}'"
    
    food = manager.retrieve("preference", "food")
    assert food is not None, "Should retrieve food fact"
    assert food.value == "pizza", f"Expected 'pizza', got '{food.value}'"
    
    print("✅ Facts can be stored and retrieved correctly")
    return manager

def test_get_recent_messages():
    """Test 3: get_recent_messages() returns actual messages (CRITICAL BUG FIX)"""
    print("\n=== Test 3: Recent Messages (Critical Fix) ===")
    
    memory = Memory()
    manager = MemoryManager(memory=memory)
    
    # Store some messages (using 3-parameter version: query, answer, topic)
    memory.remember_exchange("What is AI?", "AI is artificial intelligence", "General")
    memory.remember_exchange("What is Python?", "Python is a programming language", "Programming")
    memory.remember_exchange("Hello!", "Hi there!", "Greeting")
    
    # Get recent messages
    messages = manager.get_recent_messages(limit=5)
    
    print(f"Retrieved {len(messages)} messages")
    
    # This is the critical test - should return actual messages, not empty list
    assert isinstance(messages, list), "Should return a list"
    assert len(messages) > 0, "✅ CRITICAL: get_recent_messages() should return messages, not empty list!"
    
    # Check message structure
    if len(messages) > 0:
        print(f"First message: {messages[0]}")
        assert "role" in messages[0], "Should contain 'role' field"
        assert "content" in messages[0], "Should contain 'content' field"
        assert messages[0]["role"] == "assistant", "Role should be 'assistant'"
        assert len(messages[0]["content"]) > 0, "Content should not be empty"
    
    print("✅ get_recent_messages() returns actual messages (bug fixed!)")
    return manager, messages

def test_get_context():
    """Test 4: Context building works"""
    print("\n=== Test 4: Context Building ===")
    
    memory = Memory()
    manager = MemoryManager(memory=memory)
    
    # Store facts
    manager.remember("person", "name", "John Doe")
    manager.remember("person", "role", "Developer")
    
    # Get context
    context = manager.get_context()
    
    assert context is not None, "Should return context"
    assert len(context) > 0, "Context should not be empty"
    assert "John Doe" in context or "name" in context.lower(), "Context should contain facts"
    
    print(f"Context length: {len(context)} characters")
    print(f"Context preview: {context[:200]}...")
    print("✅ Context building works correctly")
    return manager, context

def test_get_all_categories():
    """Test 5: Get all categories"""
    print("\n=== Test 5: Get All Categories ===")
    
    memory = Memory()
    manager = MemoryManager(memory=memory)
    
    # Store facts in different categories
    manager.remember("person", "name", "John Doe")
    manager.remember("preference", "food", "pizza")
    manager.remember("preference", "color", "blue")
    
    # Get all categories
    categories = manager.get_all_categories()
    
    assert isinstance(categories, list), "Should return a list"
    assert "person" in categories, "Should contain 'person' category"
    assert "preference" in categories, "Should contain 'preference' category"
    
    print(f"Categories: {categories}")
    print("✅ Get all categories works correctly")
    return manager, categories

def test_persistence():
    """Test 6: Test that data persists in SQLite"""
    print("\n=== Test 6: Persistence Test ===")
    
    # Create new MemoryManager
    memory1 = Memory()
    manager1 = MemoryManager(memory=memory1)
    
    # Store facts
    manager1.remember("test", "key1", "value1")
    manager1.remember_exchange("Test Q1", "Test A1", "General")
    manager1.remember("test", "key2", "value2")
    
    # Store a message
    exchange1 = memory1.recent_messages(limit=1)[0] if memory1.recent_messages(limit=1) else None
    
    # Get number of facts
    facts_before = len(manager1.memory.facts())
    
    print(f"Facts before: {facts_before}")
    
    # Create a NEW MemoryManager (simulating fresh start)
    memory2 = Memory()
    manager2 = MemoryManager(memory=memory2)
    
    # Retrieve facts from new instance
    key1 = manager2.retrieve("test", "key1")
    key2 = manager2.retrieve("test", "key2")
    exchange2 = memory2.recent_messages(limit=1)
    
    print(f"Facts after new instance: {len(manager2.memory.facts())}")
    
    assert key1 is not None, "Fact should persist"
    assert key1.value == "value1", "Fact value should be preserved"
    assert key2 is not None, "Fact should persist"
    assert key2.value == "value2", "Fact value should be preserved"
    assert len(exchange2) > 0, "Exchange should persist"
    
    print("✅ Persistence works correctly (SQLite backend)")
    return manager2, exchange2

def test_build_context_in_memory():
    """Test 7: Test Memory.py build_context() method directly"""
    print("\n=== Test 7: Memory.py build_context() Method ===")
    
    memory = Memory()
    
    # Store messages (using 3-parameter version: query, answer, topic)
    memory.remember_exchange("What is Aura AI?", "Aura AI is a Python AI operating system", "AI")
    memory.remember_exchange("What are its features?", "Features include agent system, memory, automation", "Features")
    
    # Store facts
    memory.upsert_fact("topic", "current", "AI Operating System")
    memory.upsert_fact("topic", "architecture", "Modular")
    
    # Build context
    context = memory.build_context(
        user_input="Tell me about Aura AI",
        current_topic="AI Operating System",
        max_tokens=500
    )
    
    assert context is not None, "build_context() should return context"
    assert len(context) > 0, "Context should not be empty"
    assert "Aura AI" in context, "Context should contain 'Aura AI'"
    assert "AI Operating System" in context, "Context should contain current topic"
    
    print(f"Context length: {len(context)} characters")
    print(f"Context preview: {context[:300]}...")
    print("✅ Memory.py build_context() works correctly")
    return context

def run_all_tests():
    """Run all Phase 1 tests"""
    print("=" * 70)
    print("PHASE 1 MEMORY SYSTEM MIGRATION - TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_memory_manager_initialization,
        test_remember_and_retrieve,
        test_get_recent_messages,
        test_get_context,
        test_get_all_categories,
        test_persistence,
        test_build_context_in_memory
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            result = test_func()
            passed += 1
            print(f"\n✅ PASSED: {test_func.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ FAILED: {test_func.__name__}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"\n❌ ERROR: {test_func.__name__}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 ALL PHASE 1 TESTS PASSED! Memory migration successful!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
