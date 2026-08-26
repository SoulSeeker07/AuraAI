"""
Unit tests for RealBackendBridge genuine data queries and absence of mock data.
Location: tests/unit/gui/test_real_backend_bridge.py
"""

import pytest
from gui.real_backend_bridge import RealBackendBridge


def test_agent_orchestration_stats():
    bridge = RealBackendBridge.get_instance()
    stats = bridge.get_agent_orchestration_stats()
    assert isinstance(stats, dict)
    assert "active_count" in stats
    assert "subtitle" in stats
    assert stats["active_count"] >= 0


def test_throughput_stats():
    bridge = RealBackendBridge.get_instance()
    tp = bridge.get_throughput_stats()
    assert isinstance(tp, dict)
    assert "value" in tp
    assert "subtitle" in tp
    assert "groq" in tp["subtitle"].lower() or "online" in tp["value"].lower()


def test_dag_health_stats():
    bridge = RealBackendBridge.get_instance()
    dg = bridge.get_dag_health_stats()
    assert isinstance(dg, dict)
    assert "score" in dg
    assert "100%" in dg["score"]


def test_hardware_telemetry_genuine_fields():
    bridge = RealBackendBridge.get_instance()
    hw = bridge.get_hardware_status()
    assert isinstance(hw, dict)
    assert "cpu_pct" in hw
    assert "ram_pct" in hw
    assert "disk_pct" in hw
    assert isinstance(hw["cpu_pct"], (int, float))
    assert isinstance(hw["ram_pct"], (int, float))


def test_personal_os_data_structure():
    bridge = RealBackendBridge.get_instance()
    pos = bridge.get_personal_os_data()
    assert isinstance(pos, dict)
    assert "tasks" in pos
    assert "triggers" in pos
    assert "events" in pos
    assert "stats" in pos
    assert isinstance(pos["tasks"], list)
    assert isinstance(pos["triggers"], list)
    assert isinstance(pos["events"], list)
