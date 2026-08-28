"""
Test Suite for Phase 2: Hybrid Semantic Vector Memory & Self-Healing Execution
"""

import sys
import tempfile
import asyncio
from pathlib import Path

# Add src and root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

from Memory import Memory, MemoryFact
from core.context.ambient_context_builder import AmbientContextBuilder
from brain.execution_coordinator import ExecutionCoordinator, StepResult, CoordinationResult


def test_semantic_fact_similarity():
    """Verify real dense neural embeddings (all-MiniLM-L6-v2) find relevant facts conceptually."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mem = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")

        # Seed diverse facts
        mem.upsert_fact("preference", "favorite_editor", "Visual Studio Code with Dark Theme")
        mem.upsert_fact("profile", "current_role", "Principal AI Software Engineer")
        mem.upsert_fact("project", "primary_goal", "Building autonomous desktop AI OS AuraAI")
        mem.upsert_fact("hobby", "cooking", "Making authentic Italian pasta and Neapolitan pizza")
        mem.upsert_fact("pets", "animals", "Two golden retriever dogs named Luna and Max")

        # 1. Exact match
        res_exact = mem.search("Visual Studio Code")
        assert len(res_exact) >= 1
        assert res_exact[0].key == "favorite_editor"

        # 2. Adversarial Dense Semantic Match: "I work in AI" -> matches "Principal AI Software Engineer"
        # Notice: Phrasing diverges significantly, but embedding cosine similarity identifies role
        res_sem = mem.search_semantic("I work in AI", limit=2)
        assert len(res_sem) >= 1
        assert res_sem[0].key == "current_role", f"Expected current_role, got {[f.key for f in res_sem]}"

        # 3. Conceptual culinary match: "culinary dishes and recipes" -> matches cooking hobby
        res_cooking = mem.search_semantic("culinary dishes and recipes", limit=2)
        assert len(res_cooking) >= 1
        assert res_cooking[0].key == "cooking", f"Expected cooking, got {[f.key for f in res_cooking]}"

        # 4. Hybrid relevant facts
        rel_facts = mem.get_relevant_facts("engineering career and profession", limit=3)
        assert len(rel_facts) >= 1
        assert any(f.key == "current_role" for f in rel_facts)

        # 5. Deletion & Embedding Purge (Both VectorMemory and CognitiveMemory)
        assert ("profile:current_role" in mem.vector_memory._embedding_cache)
        if mem.cognitive is not None:
            cog_matches = mem.cognitive.search_memories(query="Principal AI Software Engineer")
            assert len(cog_matches) >= 1

        deleted = mem.delete_fact("profile", "current_role")
        assert deleted is True
        assert ("profile:current_role" not in mem.vector_memory._embedding_cache)
        
        # After deletion, "I work in AI" no longer returns current_role in vector search
        res_after = mem.search_semantic("I work in AI", limit=2)
        assert not any(f.key == "current_role" for f in res_after)

        # After deletion, cognitive_memories store is also purged
        if mem.cognitive is not None:
            cog_matches_after = mem.cognitive.search_memories(query="Principal AI Software Engineer")
            assert not any("Principal AI Software Engineer" in m.content for m in cog_matches_after)


def test_ambient_context_semantic_filtering():
    """Verify ambient context builder filters facts semantically for the query."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mem = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")

        mem.upsert_fact("skill", "favorite_language", "Python and Rust")
        mem.upsert_fact("profile", "coffee_preference", "Espresso with oat milk")

        class MockAuraCore:
            memory = mem

        ctx = AmbientContextBuilder.build_ambient_context(MockAuraCore(), query="programming languages")
        assert "favorite_language" in ctx or "Python" in ctx


def test_coordinator_self_healing_recovery():
    """Verify execution coordinator handles step failures with self-healing recovery trace."""
    coord = ExecutionCoordinator()

    # Mock engine that fails first then succeeds on retry
    class FlakyMockEngine:
        calls = 0
        def execute(self, action, params):
            self.calls += 1
            if params.get("recovered") or self.calls > 1:
                return {"success": True, "observations": ["Recovered via alternative selector"]}
            return {"success": False, "observations": ["Element focus timeout"]}

        def observe(self, action, params):
            return None

    from brain.aca.engine_interface import EngineRegistry
    registry = EngineRegistry.get_instance()
    mock_eng = FlakyMockEngine()
    registry.register(mock_eng, name="mock_desktop")

    execution_map = {
        "goal": "Click submit button with fallback",
        "steps": [
            {
                "engine": "mock_desktop",
                "action": "click",
                "parameters": {
                    "selector": "#btn-primary",
                    "alternative_selector": "#btn-secondary"
                }
            }
        ]
    }

    async def _run():
        res = await coord.coordinate(execution_map)
        assert len(res.step_results) == 1
        step_0 = res.step_results[0]
        assert step_0.success is True
        assert "recovery_trace" in step_0.data
        assert step_0.data["recovery_trace"]["recovery_status"] == "RECOVERED_SUCCESS"

    asyncio.run(_run())


def test_memory_manager_unified_sqlite_context():
    """Verify MemoryManager.get_context_messages() retrieves relevant facts via unified Memory.db."""
    from memory.manager.memory_manager import MemoryManager
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mem = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")
        mem.upsert_fact("profile", "editor_theme", "Monokai Pro with customized glyph icons")
        mem.upsert_fact("hobby", "gardening", "Growing organic heirloom tomatoes and basil")

        class MockProviderManager:
            def chat(self, req):
                class Resp:
                    text = "[]"
                return Resp()

        mgr = MemoryManager(provider_manager=MockProviderManager(), memory=mem)
        
        # 1. Query matching editor theme via vector search
        msgs = mgr.get_context_messages("What code editor theme do I prefer?")
        assert any("Monokai Pro" in m["content"] for m in msgs)
        assert not any("gardening" in m["content"] for m in msgs)

        # 2. Query matching gardening
        msgs_garden = mgr.get_context_messages("Tell me about my vegetable gardening hobby")
        assert any("tomatoes and basil" in m["content"] for m in msgs_garden)


if __name__ == "__main__":
    test_semantic_fact_similarity()
    print("✓ test_semantic_fact_similarity passed")
    test_ambient_context_semantic_filtering()
    print("✓ test_ambient_context_semantic_filtering passed")
    test_coordinator_self_healing_recovery()
    print("✓ test_coordinator_self_healing_recovery passed")
    test_memory_manager_unified_sqlite_context()
    print("✓ test_memory_manager_unified_sqlite_context passed")
    print("\n🎉 ALL PHASE 2 INTELLIGENCE TESTS PASSED SUCCESSFULLY!")
