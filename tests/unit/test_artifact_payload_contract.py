"""
Unit Tests for Artifact Payload Contract and ArtifactManager Integration
Location: tests/unit/test_artifact_payload_contract.py

Verifies:
1. Artifact.has_payload strictly requires non-empty string content.
2. Artifact.has_payload returns False for empty strings, whitespace, None, dicts, lists, numbers.
3. ArtifactManager serializes step observations and dict data into strings so generated artifacts have valid payloads.
"""

from types import SimpleNamespace
import pytest

from core.orchestration.artifact import (
    Artifact,
    CodeArtifact,
    DocumentArtifact,
    ResearchArtifact,
    SessionSummaryArtifact,
)
from brain.aca.artifact_manager import ArtifactManager


def test_artifact_has_payload_strict_string_contract():
    """Verify that only non-empty strings produce has_payload == True."""
    # Valid string payloads
    assert Artifact(content="hello world").has_payload is True
    assert Artifact(content="# Markdown Title").has_payload is True
    assert Artifact(content="{}").has_payload is True

    # Empty or whitespace strings
    assert Artifact(content="").has_payload is False
    assert Artifact(content="   \n\t  ").has_payload is False

    # Non-string types must return False
    assert Artifact(content=None).has_payload is False
    assert Artifact(content={"key": "value"}).has_payload is False
    assert Artifact(content=["item1", "item2"]).has_payload is False
    assert Artifact(content=12345).has_payload is False
    assert Artifact(content=True).has_payload is False


def test_artifact_subclasses_serialize_content_to_string():
    """Verify all first-class Artifact subclasses serialize payload into string content."""
    res_art = ResearchArtifact(
        query="Quantum Computing",
        title="QC Overview",
        executive_summary="Quantum mechanics applied to computation.",
        findings=[{"topic": "Qubits", "detail": "Superposition"}],
        references=[{"source": "arXiv"}],
    )
    assert isinstance(res_art.content, str)
    assert res_art.has_payload is True
    assert "Quantum mechanics" in res_art.content

    code_art = CodeArtifact(code="def add(a, b): return a + b\n")
    assert isinstance(code_art.content, str)
    assert code_art.has_payload is True

    doc_art = DocumentArtifact(title="Doc", body="This is the document body.")
    assert isinstance(doc_art.content, str)
    assert doc_art.has_payload is True

    sum_art = SessionSummaryArtifact(summary="Completed 5 actions today.")
    assert isinstance(sum_art.content, str)
    assert sum_art.has_payload is True


def test_artifact_manager_serializes_step_data_to_string():
    """Verify ArtifactManager.collect_from_execution serializes step data to string."""
    mgr = ArtifactManager()

    mock_step_with_obs = SimpleNamespace(
        engine="desktop",
        action="desktop.click",
        data={"coords": [100, 200]},
        observations=["Clicked button at (100, 200)"],
        success=True,
    )

    mock_step_with_dict_only = SimpleNamespace(
        engine="browser",
        action="browser.extract",
        data={"title": "Test Page", "url": "https://example.com"},
        observations=[],
        success=True,
    )

    mock_coordination = SimpleNamespace(
        step_results=[mock_step_with_obs, mock_step_with_dict_only]
    )

    collected = mgr.collect_from_execution(mock_coordination, session_id="sess_test_01")
    assert len(collected) == 2

    # Step 1: from observations
    art1 = collected[0]
    assert isinstance(art1.content, str)
    assert art1.content == "Clicked button at (100, 200)"
    assert bool(art1.content.strip()) is True

    # Step 2: from dict data (stringified)
    art2 = collected[1]
    assert isinstance(art2.content, str)
    assert "Test Page" in art2.content
    assert bool(art2.content.strip()) is True
