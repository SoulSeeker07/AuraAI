"""
Sample usage of Memory 2.0 system

This script demonstrates the intelligent memory system with:
- 5 memory layers (working, session, long-term, knowledge, workspace)
- 10 categories (preferences, projects, people, skills, goals, tasks, files, devices, networking, coding, personal)
- Importance scoring (1-5 scale)
- Smart retrieval and reranking
- Sensitive data encryption
- Conflict resolution
- Automatic forgetting
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.memory import (
    MemoryManagerV2,
    MemoryLayer,
    CategoryType,
    ImportanceLevel,
    MemoryAnalyzer,
    MemoryFact,
)


async def sample_usage():
    """Demonstrate Memory 2.0 capabilities"""
    print("=" * 80)
    print("MEMORY 2.0 SAMPLE USAGE")
    print("=" * 80)
    print()

    # Create a memory manager
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    temp_file.close()
    data_path = Path(temp_file.name)

    manager = MemoryManagerV2(
        data_path=data_path,
        secret_key="sample_secret_key_123"
    )

    # Initialize analyzer
    analyzer = MemoryAnalyzer()

    # --- Example 1: Store and Retrieve Preferences ---
    print("1. Storing and Retrieving Preferences")
    print("-" * 80)

    # Analyze text and store automatically
    text1 = "My favorite IDE is VS Code."
    analysis = await analyzer.analyze(text1)
    print(f"Text: '{text1}'")
    print(f"  → Should store: {analysis.should_store}")
    print(f"  → Category: {analysis.category.value}")
    print(f"  → Importance: {analysis.importance.value}")
    print(f"  → Key: {analysis.key}")

    fact = await manager.analyze_and_remember(text1, layer=MemoryLayer.LONG_TERM)
    print(f"  → Stored with encrypted: {fact.encrypted if hasattr(fact, 'encrypted') else 'N/A'}")
    print()

    # Manual storage
    await manager.remember(
        key="favorite programming language",
        value="Python",
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM,
        importance=ImportanceLevel.HIGH
    )
    print("Manually stored: favorite programming language = Python")
    print()

    # Retrieve
    result = manager.retrieve(
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM
    )
    print(f"Retrieved {len(result)} preference(s):")
    for fact in result[:5]:  # Show first 5
        print(f"  - {fact.key}: {fact.value} (importance: {fact.importance.value})")
    print()

    # --- Example 2: Smart Retrieval with Reranking ---
    print("2. Smart Retrieval with Query Reranking")
    print("-" * 80)

    # Store multiple memories
    await manager.remember(
        key="favorite color",
        value="blue",
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM
    )

    await manager.remember(
        key="favorite food",
        value="pizza",
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM,
        importance=ImportanceLevel.HIGH
    )

    await manager.remember(
        key="favorite music",
        value="jazz",
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM
    )

    # Retrieve with query
    retrieval_result = await manager.retrieve_with_reranking(
        query="favorite things",
        limit=5
    )

    print(f"Query: 'favorite things'")
    print(f"Retrieved {len(retrieval_result.memories)} memory(ies)")
    print(f"Overall score: {retrieval_result.score:.2f}")
    print(f"Relevance: {retrieval_result.relevance}")
    print(f"Context: {retrieval_result.context}")
    print()
    print("Ranked memories:")
    for i, fact in enumerate(retrieval_result.memories, 1):
        print(f"  {i}. {fact.key}: {fact.value} (importance: {fact.importance.value})")
    print()

    # --- Example 3: Category Classification ---
    print("3. Automatic Category Classification")
    print("-" * 80)

    test_texts = [
        "I need to fix the import error in the main.py file",
        "The report is saved to documents/quarterly_report.pdf",
        "The project deadline is next week"
    ]

    for text in test_texts:
        analysis = await analyzer.analyze(text)
        print(f"Text: '{text}'")
        print(f"  → Category: {analysis.category.value}")
        print(f"  → Key: {analysis.key}")
        print()

    # --- Example 4: Sensitive Data Encryption ---
    print("4. Sensitive Data Encryption")
    print("-" * 80)

    sensitive_text = "Remember my API key: sk-test123456789"
    print(f"Text: '{sensitive_text}'")

    sensitive_analysis = await analyzer.analyze(sensitive_text)
    print(f"  → Category: {sensitive_analysis.category.value}")
    print(f"  → Contains sensitive: {sensitive_analysis.metadata.get('contains_sensitive', False)}")

    sensitive_fact = await manager.analyze_and_remember(
        sensitive_text,
        layer=MemoryLayer.LONG_TERM
    )

    if sensitive_fact and hasattr(sensitive_fact, 'encrypted') and sensitive_fact.encrypted:
        decrypted = sensitive_fact.decrypt(manager.secret_key)
        print(f"  → Encrypted: Yes")
        print(f"  → Decrypted value: {decrypted}")
        print(f"  → Original value found in decrypted: {'sk-test123456789' in decrypted}")
    print()

    # --- Example 5: Conflict Resolution ---
    print("5. Conflict Resolution")
    print("-" * 80)

    # First store old value
    await manager.remember(
        key="my favorite ide",
        value="VS Code",
        category=CategoryType.PREFERENCES,
        layer=MemoryLayer.LONG_TERM
    )

    print("Stored: my favorite ide = VS Code")

    # Try to resolve conflict with new value
    conflict_result = manager.resolve_conflict(
        key="my favorite ide",
        new_value="Cursor",
        layer=MemoryLayer.LONG_TERM
    )

    print(f"\nConflict resolution result:")
    print(f"  → Resolved: {conflict_result.resolved}")
    print(f"  → Resolution: {conflict_result.resolution}")

    if conflict_result.merged_fact:
        print(f"  → Merged value: {conflict_result.merged_fact.value}")

    # Retrieve to verify
    retrieved = manager.retrieve(
        category=CategoryType.PREFERENCES,
        key="my_favorite_ide",
        layer=MemoryLayer.LONG_TERM
    )

    if retrieved:
        print(f"  → Retrieved value: {retrieved[0].value}")
    print()

    # --- Example 6: Working and Session Layers ---
    print("6. Working and Session Layers")
    print("-" * 80)

    # Working layer (cleared on restart)
    await manager.analyze_and_remember(
        text="Current task: fixing bug #123",
        layer=MemoryLayer.WORKING
    )

    # Session layer (cleared at end of session)
    await manager.analyze_and_remember(
        text="Remember this for this session: important meeting at 3pm",
        layer=MemoryLayer.SESSION
    )

    working_results = manager.retrieve(layer=MemoryLayer.WORKING)
    session_results = manager.retrieve(layer=MemoryLayer.SESSION)

    print(f"Working layer memories: {len(working_results)}")
    for fact in working_results:
        print(f"  - {fact.key}: {fact.value}")
    print()

    print(f"Session layer memories: {len(session_results)}")
    for fact in session_results:
        print(f"  - {fact.key}: {fact.value}")
    print()

    # --- Example 7: Memory Summary ---
    print("7. Memory Summary")
    print("-" * 80)

    summary = manager.get_summary()
    print(f"Total facts: {summary.total_facts}")
    print(f"\nBy layer:")
    for layer, count in summary.by_layer.items():
        print(f"  - {layer}: {count}")
    print(f"\nBy category:")
    for category, count in summary.by_category.items():
        print(f"  - {category}: {count}")
    print(f"\nBy importance:")
    for importance, count in summary.by_importance.items():
        print(f"  - {importance}: {count}")
    print(f"\nRecent activity:")
    for fact in summary.recent_activity[:5]:
        print(f"  - {fact.key}: {fact.value[:50]}...")
    print()

    # --- Example 8: Forgetting Memories ---
    print("8: Automatic Forgetting")
    print("-" * 80)

    # Store some old memories
    from datetime import timedelta, datetime

    old_fact = MemoryFact(
        layer=MemoryLayer.LONG_TERM,
        category=CategoryType.TASKS,
        key="old task",
        value="This is an old task from 50 days ago",
        created_at=datetime.now() - timedelta(days=50),
        importance=ImportanceLevel.LOW
    )
    manager.layers[MemoryLayer.LONG_TERM].add_fact(old_fact)

    # Forget old memories
    forgetting_result = await manager.forget_old_memories(
        days=30,
        importance_threshold=ImportanceLevel.MEDIUM
    )

    print(f"Forgetting result:")
    print(f"  → Deleted: {forgetting_result.deleted} memory(ies)")
    print(f"  → Reasons: {len(forgetting_result.reasons)}")
    for reason in forgetting_result.reasons[:3]:
        print(f"    - {reason}")
    print()

    # --- Example 9: Context Building ---
    print("9. Memory Context Building")
    print("-" * 80)

    context = manager.get_context(limit=10)
    print(f"Context (first 200 chars): {context[:200]}...")
    print(f"Full context:")
    print(context)
    print()

    # --- Example 10: Key Normalization ---
    print("10. Key Normalization")
    print("-" * 80)

    # Store with spaces
    await manager.remember(
        key="api key",
        value="sk-test123",
        category=CategoryType.PERSONAL,
        layer=MemoryLayer.LONG_TERM,
        encrypt=True
    )

    # Retrieve with spaces (should work due to normalization)
    result = manager.retrieve(key="api key", layer=MemoryLayer.LONG_TERM)

    print(f"Stored with key: 'api key'")
    print(f"Retrieved with key: 'api key' (with spaces)")
    print(f"→ Found: {len(result) == 1}")
    if result:
        print(f"→ Value: {result[0].value}")
    print()

    print("=" * 80)
    print("SAMPLE USAGE COMPLETE")
    print("=" * 80)
    print(f"\nTotal facts in memory: {manager.get_summary().total_facts}")
    print(f"Memory file: {manager.data_path}")


if __name__ == "__main__":
    asyncio.run(sample_usage())
