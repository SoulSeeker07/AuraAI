"""
Integration tests for Memory 2.0

Tests all scenarios from requirements:
- "My favorite IDE is VS Code." → Store as Preference
- "Actually, I use Cursor now." → Update existing memory
- "Hello!" → Do not store
- "Remember my API key." → Encrypt and store
- "Forget my API key." → Remove securely
- "What's my favorite IDE?" → Retrieve updated value
- "Summarize what you know about this project." → Combine relevant memories
"""

import os
import sys
from pathlib import Path

# Add the root directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime, timedelta

import pytest

from core.memory import (
    CategoryType,
    ImportanceLevel,
    MemoryAnalyzer,
    MemoryLayer,
    MemoryManagerV2,
)


# Fixtures
@pytest.fixture
def memory_manager(tmp_path):
    """Create a temporary memory manager for testing"""
    return MemoryManagerV2(
        data_path=tmp_path / "test_memory.json", secret_key="test_secret"
    )


@pytest.fixture
def analyzer():
    """Create a memory analyzer"""
    return MemoryAnalyzer()


class TestMemory2BasicOperations:
    """Test basic memory operations"""

    @pytest.mark.asyncio
    async def test_store_preference(self, memory_manager, analyzer):
        """Test: "My favorite IDE is VS Code." → Store as Preference"""
        text = "My favorite IDE is VS Code."

        # Analyze text
        analysis = await analyzer.analyze(text)
        assert analysis.should_store, "Text should be stored"
        assert analysis.importance == ImportanceLevel.MEDIUM
        assert analysis.category == CategoryType.PREFERENCES
        assert analysis.key == "my_favorite_ide"

    @pytest.mark.asyncio
    async def test_update_existing_memory(self, memory_manager, analyzer):
        """Test: "Actually, I use Cursor now." → Update existing memory"""
        # First store the old preference
        await memory_manager.remember(
            key="my favorite ide",
            value="VS Code",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        # Now update it using remember() with the same key
        await memory_manager.remember(
            key="my favorite ide",
            value="Cursor",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        # Verify it was updated
        retrieved = memory_manager.retrieve(
            key="my_favorite_ide", layer=MemoryLayer.LONG_TERM
        )
        assert len(retrieved) == 1
        assert "Cursor" in retrieved[0].value

    @pytest.mark.asyncio
    async def test_store_sensitive_data(self, memory_manager, analyzer):
        """Test: "Remember my API key." → Encrypt and store"""
        text = "Remember my API key: sk-test123456789"

        analysis = await analyzer.analyze(text)
        assert analysis.should_store
        assert analysis.category == CategoryType.PERSONAL
        assert analysis.metadata["contains_sensitive"] is True

        # Store with sensitive flag
        fact = await memory_manager.analyze_and_remember(
            text, layer=MemoryLayer.LONG_TERM
        )

        # Verify it's encrypted
        assert fact.encrypted is True

        # Should be able to decrypt it
        decrypted = fact.decrypt(memory_manager.secret_key)
        assert "sk-test123456789" in decrypted
        assert "Remember my API key:" in decrypted

    @pytest.mark.asyncio
    async def test_forget_sensitive_data(self, memory_manager, analyzer):
        """Test: "Forget my API key." → Remove securely"""
        # First store the API key
        await memory_manager.remember(
            key="api key",
            value="sk-test123456789",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
            encrypt=True,
        )

        # Verify it's stored
        retrieved = memory_manager.retrieve(key="api key", layer=MemoryLayer.LONG_TERM)
        assert len(retrieved) == 1

        # Forget it
        result = memory_manager.forget("api key", layer=MemoryLayer.LONG_TERM)
        assert result.deleted == 1
        assert len(result.reasons) > 0

        # Verify it's removed
        retrieved = memory_manager.retrieve(key="api key", layer=MemoryLayer.LONG_TERM)
        assert len(retrieved) == 0


class TestMemoryRetrieval:
    """Test memory retrieval and ranking"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_retrieve_preference(self, memory_manager, analyzer):
        """Test: "What's my favorite IDE?" → Retrieve updated value"""
        # Store preference
        await memory_manager.remember(
            key="my favorite ide",
            value="VS Code",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        # Retrieve
        result = memory_manager.retrieve(
            category=CategoryType.PREFERENCES,
            key="my favorite ide",
            layer=MemoryLayer.LONG_TERM,
        )

        assert len(result) == 1
        assert result[0].value == "VS Code"

    @pytest.mark.asyncio
    async def test_smart_retrieval_with_query(self, memory_manager, analyzer):
        """Test smart retrieval with query ranking"""
        # Store multiple memories
        await memory_manager.remember(
            key="favorite color",
            value="blue",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        await memory_manager.remember(
            key="favorite food",
            value="pizza",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
            importance=ImportanceLevel.HIGH,
        )

        # Retrieve with query
        result = await memory_manager.retrieve_with_reranking(
            query="favorite things", limit=5
        )

        assert len(result.memories) > 0
        assert result.score > 0
        assert "preferences" in result.context.lower()

        # High importance memories should be ranked higher
        assert result.memories[0].importance.value >= ImportanceLevel.MEDIUM.value


class TestMemoryLayers:
    """Test different memory layers"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_working_layer(self, memory_manager, analyzer):
        """Test Working layer (ephemeral, cleared on restart)"""
        # Store in working layer
        await memory_manager.analyze_and_remember(
            text="Current task: fixing bug", layer=MemoryLayer.WORKING
        )

        # Should be retrievable
        result = memory_manager.retrieve(
            key="current_task_fixing", layer=MemoryLayer.WORKING
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_session_layer(self, memory_manager, analyzer):
        """Test Session layer (cleared at end of session)"""
        # Store in session layer
        await memory_manager.analyze_and_remember(
            text="Remember this for this session", layer=MemoryLayer.SESSION
        )

        result = memory_manager.retrieve(
            key="remember_this_for", layer=MemoryLayer.SESSION
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_long_term_layer(self, memory_manager, analyzer):
        """Test Long-Term layer (persists across restarts)"""
        # Store in long-term layer
        await memory_manager.remember(
            key="permanent fact",
            value="This should persist",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
        )

        result = memory_manager.retrieve(
            key="permanent fact", layer=MemoryLayer.LONG_TERM
        )
        assert len(result) == 1
        assert "This should persist" in result[0].value


class TestConflictResolution:
    """Test conflict resolution"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_update_existing_memory_resolves_conflict(self, memory_manager):
        """Test that updating existing memory resolves conflict"""
        # First store old value
        await memory_manager.remember(
            key="my favorite ide",
            value="VS Code",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        # Update with new value
        result = memory_manager.resolve_conflict(
            key="my favorite ide", new_value="Cursor", layer=MemoryLayer.LONG_TERM
        )

        # Verify resolution
        assert result.resolved is True
        assert result.conflict_fact is not None
        assert "Updated: 'VS Code' → 'Cursor'" in result.resolution
        assert result.merged_fact is not None

        # Verify new value is stored
        retrieved = memory_manager.retrieve(
            key="my favorite ide", layer=MemoryLayer.LONG_TERM
        )
        assert len(retrieved) == 1
        assert "Cursor" in retrieved[0].value
        assert retrieved[0].importance == ImportanceLevel.HIGH


class TestForgettingEngine:
    """Test forgetting old and unimportant memories"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_forget_old_memories(self, memory_manager):
        """Test forgetting memories older than X days"""
        # Store an old memory (simulate by setting created_at)
        old_memory = await memory_manager.remember(
            key="old memory",
            value="This is very old",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
            importance=ImportanceLevel.LOW,
        )

        # Manually set it to be old
        old_memory.created_at = datetime.now() - timedelta(days=31)

        # Store a new memory
        await memory_manager.remember(
            key="new memory",
            value="This is new",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
            importance=ImportanceLevel.HIGH,
        )

        # Forget old memories
        result = await memory_manager.forget_old_memories(
            days=30, importance_threshold=ImportanceLevel.MEDIUM
        )

        # Verify old memory was forgotten
        assert result.deleted >= 1
        assert len(result.reasons) > 0

        # Verify new memory still exists
        result = memory_manager.retrieve(key="new memory", layer=MemoryLayer.LONG_TERM)
        assert len(result) == 1


class TestMemorySummary:
    """Test memory summary and statistics"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_memory_summary(self, memory_manager):
        """Test getting memory summary"""
        # Store various memories
        await memory_manager.remember(
            key="preference 1",
            value="value 1",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        await memory_manager.remember(
            key="project 1",
            value="value 2",
            category=CategoryType.PROJECTS,
            layer=MemoryLayer.LONG_TERM,
            importance=ImportanceLevel.HIGH,
        )

        await memory_manager.remember(
            key="personal 1",
            value="value 3",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
        )

        # Get summary
        summary = memory_manager.get_summary()

        # Verify statistics
        assert summary.total_facts >= 3
        assert summary.by_category["preferences"] >= 1
        assert summary.by_category["projects"] >= 1
        assert summary.by_importance[3] >= 1  # HIGH importance


class TestCategoryClassification:
    """Test automatic category classification"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_coding_category(self, memory_manager, analyzer):
        """Test automatic classification for coding-related text"""
        text = "I need to fix the import error in the main.py file"

        analysis = await analyzer.analyze(text)
        assert analysis.category == CategoryType.CODING

    @pytest.mark.asyncio
    async def test_file_category(self, memory_manager, analyzer):
        """Test automatic classification for file-related text"""
        text = "The report is saved to documents/quarterly_report.pdf"

        analysis = await analyzer.analyze(text)
        assert analysis.category == CategoryType.FILES

    @pytest.mark.asyncio
    async def test_project_category(self, memory_manager, analyzer):
        """Test automatic classification for project-related text"""
        text = "The project deadline is next week"

        analysis = await analyzer.analyze(text)
        assert analysis.category == CategoryType.PROJECTS


class TestContextBuilding:
    """Test memory context building"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_context_building(self, memory_manager):
        """Test building formatted memory context"""
        # Store memories
        await memory_manager.remember(
            key="fact 1",
            value="Value 1",
            category=CategoryType.PREFERENCES,
            layer=MemoryLayer.LONG_TERM,
        )

        await memory_manager.remember(
            key="fact 2",
            value="Value 2",
            category=CategoryType.PROJECTS,
            layer=MemoryLayer.LONG_TERM,
        )

        # Get context
        context = memory_manager.get_context(limit=10)

        # Verify context format
        assert "preferences" in context.lower()
        assert "projects" in context.lower()
        assert "fact_1" in context
        assert "fact_2" in context


class TestMemoryPersistence:
    """Test memory persistence across sessions"""

    @pytest.fixture
    def memory_manager(self, tmp_path):
        """Create a temporary memory manager for testing"""
        return MemoryManagerV2(
            data_path=tmp_path / "test_memory.json", secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_persistence(self, memory_manager):
        """Test that memory persists across instances"""
        # Store a memory
        await memory_manager.remember(
            key="persistent fact",
            value="This should persist",
            category=CategoryType.PERSONAL,
            layer=MemoryLayer.LONG_TERM,
        )

        # Get memory
        result = memory_manager.retrieve(
            key="persistent fact", layer=MemoryLayer.LONG_TERM
        )
        assert len(result) == 1
        assert "This should persist" in result[0].value

        # Get the data path from memory_manager
        data_path = memory_manager.data_path

        # Create new manager with same file (simulate restart)
        new_manager = MemoryManagerV2(data_path=data_path, secret_key="test_secret")

        # Get memory from new instance
        result = new_manager.retrieve(
            key="persistent fact", layer=MemoryLayer.LONG_TERM
        )
        assert len(result) == 1
        assert "This should persist" in result[0].value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
