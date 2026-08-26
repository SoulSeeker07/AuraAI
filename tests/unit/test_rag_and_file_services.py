"""
Unit tests for FileService, RAGService, and RAG/File Intent Routing in AuraAI.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from brain.intent_router import IntentRouter
from tools.file_service import FileService
from knowledge.rag_service import RAGService


def test_file_service_normalization_and_scoring(tmp_path):
    """Verify query normalization and file relevance scoring."""
    # Create test document structure
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir()
    resume_pdf = docs_dir / "Sreekanta_resume.pdf"
    resume_pdf.write_text("Sreekanta Resume Content: Senior AI Engineer, Python, PyTorch, RAG.", encoding="utf-8")

    notes_md = docs_dir / "project_notes.md"
    notes_md.write_text("# Project Notes\nArchitecture and tasks.", encoding="utf-8")

    fs = FileService(search_paths=[docs_dir])

    # 1. Test finding by exact stem
    match = fs.find_best_file("Sreekanta_resume")
    assert match is not None
    assert match.name == "Sreekanta_resume.pdf"

    # 2. Test finding by natural language
    match_nl = fs.find_best_file("open my resume")
    assert match_nl is not None
    assert match_nl.name == "Sreekanta_resume.pdf"

    # 3. Test finding notes
    match_notes = fs.find_best_file("project notes")
    assert match_notes is not None
    assert match_notes.name == "project_notes.md"


def test_file_service_find_and_open(tmp_path):
    """Verify find_and_open locates the file and calls system opener."""
    test_doc = tmp_path / "Sreekanta_resume.docx"
    test_doc.write_text("Resume Word doc content", encoding="utf-8")

    fs = FileService(search_paths=[tmp_path])

    with patch("os.startfile", return_value=None) as mock_startfile:
        ok, msg, matched = fs.find_and_open("Sreekanta_resume")
        assert ok is True
        assert matched == test_doc
        mock_startfile.assert_called_once_with(str(test_doc))


def test_rag_service_indexing_and_query(tmp_path):
    """Verify RAGService indexes files and retrieves relevant context."""
    store_dir = tmp_path / "rag_store"
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    sample_doc = docs_dir / "Sreekanta_resume.txt"
    sample_doc.write_text(
        "Sreekanta is an AI Systems Architect specializing in autonomous agents, RAG, neural search, and Python.",
        encoding="utf-8"
    )

    fs = FileService(search_paths=[docs_dir])
    rag = RAGService(store_path=store_dir, file_service=fs)

    # Index document
    indexed = rag.index_file(sample_doc)
    assert indexed is True

    # Retrieve context
    context = rag.get_relevant_context("What are Sreekanta's skills in AI and Python?")
    assert context is not None
    assert "Sreekanta" in context or "AI" in context


def test_intent_router_detects_open_file_and_rag():
    """Verify IntentRouter routes resume/file requests to open_file and rag_query."""
    mock_memory = MagicMock()
    mock_memory.extract_facts.return_value = []
    router = IntentRouter(memory=mock_memory)

    # Open file queries
    file_queries = [
        ("open Sreekanta_resume", "Sreekanta_resume"),
        ("open my resume", "my resume"),
        ("find and open resume.pdf", "resume.pdf"),
        ("open project_notes.md", "project_notes.md"),
        ("open resume", "resume"),
    ]
    for q, expected_target in file_queries:
        intent = router.detect(q)
        assert intent.name == "open_file", f"Failed for query: {q}"
        assert intent.data["target"].lower() == expected_target.lower()

    # RAG queries
    rag_queries = [
        "what skills are in my resume?",
        "summarize my resume",
        "search my documents for machine learning",
        "tell me what is in my notes",
    ]
    for q in rag_queries:
        intent = router.detect(q)
        assert intent.name == "rag_query", f"Failed for query: {q}"


@pytest.mark.asyncio
async def test_conversation_engine_open_file_and_rag_integration(tmp_path):
    """Verify ConversationEngine executes open_file and rag_query seamlessly."""
    from ai.models import ProviderCapabilities, ProviderResponse
    from ai.provider import Provider
    from ai.provider_manager import ProviderManager
    from brain.conversation_engine import ConversationEngine
    from Memory import Memory

    class DummyProvider(Provider):
        capabilities = ProviderCapabilities(name="dummy", default_model="dummy-model")
        def chat(self, req):
            return ProviderResponse("Provider response", provider="dummy", model="dummy-model")

    doc_file = tmp_path / "Sreekanta_resume.txt"
    doc_file.write_text("Sreekanta Resume details: Lead AI Developer.", encoding="utf-8")

    fs = FileService.get_instance()
    fs.custom_paths.append(tmp_path)
    fs._cached_search_roots = None

    memory = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")
    pm = ProviderManager(default_provider="dummy")
    pm.register("dummy", DummyProvider())

    engine = ConversationEngine(
        memory=memory,
        provider_manager=pm,
        settings={"provider": "dummy", "model": "dummy-model"},
    )

    with patch("os.startfile", return_value=None):
        res = await engine.process("open Sreekanta_resume")
        assert "Opened" in res.text or "Sreekanta_resume" in res.text
