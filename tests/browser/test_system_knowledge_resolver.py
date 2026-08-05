"""
Unit tests for SystemKnowledgeResolver (Deterministic System Queries).
Location: tests/browser/test_system_knowledge_resolver.py
"""

import pytest
from src.core.system.system_knowledge_resolver import SystemKnowledgeResolver


def test_resolve_identity():
    ans = SystemKnowledgeResolver.resolve("Who are you?")
    assert "I am Aura" in ans
    assert "AI Operating System" in ans


def test_resolve_limitations():
    ans = SystemKnowledgeResolver.resolve("What can't you do?")
    assert "Android & iOS mobile automation" in ans
    assert "3D CAD modeling" in ans
    assert "Physical hardware & robotics" in ans


def test_resolve_capabilities():
    ans = SystemKnowledgeResolver.resolve("What are your capabilities?")
    assert "Desktop Automation" in ans
    assert "Browser & E-Commerce Intelligence" in ans
    assert "Research & Knowledge" in ans
    assert "Autonomous Coding" in ans


def test_resolve_planners():
    ans = SystemKnowledgeResolver.resolve("What planners do you have?")
    assert "Desktop Planner" in ans
    assert "Browser Planner" in ans


def test_resolve_backends():
    ans = SystemKnowledgeResolver.resolve("What backends do you have?")
    assert "Native Desktop Engine" in ans
    assert "Playwright Browser Engine" in ans
    assert "Gemini Research Engine" in ans
    assert "Antigravity CLI" in ans
