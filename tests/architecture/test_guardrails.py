"""
Architecture Guardrails — Enforced by CI
========================================

These tests enforce the Aura Cognitive Architecture rules:

    Guardrail 1: No backend can import ACA (Desktop → ACA should be impossible)
    Guardrail 2: Only ExecutionCoordinator may invoke engines
    Guardrail 3: Only StrategyEngine creates ExecutionMaps
    Guardrail 4: Only FusionEngine creates Thought
    Guardrail 5: Only LearningEngine writes long-term memory
    Guardrail 6: Only ArtifactManager creates artifacts
    Guardrail 7: All requests go through ACA.process()
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Core system files allowed to reference engines as architectural entrypoints/wiring
CORE_ALLOWED_ENGINE_FILES = {
    ROOT / "src" / "brain" / "execution_coordinator.py",
    ROOT / "src" / "brain" / "aca" / "aca_brain.py",
    ROOT / "core" / "aura_core.py",
}

# Temporary legacy exceptions allowed via strict migration tracking contract:
# Every entry MUST have a reason, an owner, and a target milestone for removal.
ENGINE_ALLOWLIST = {
    ROOT / "src" / "agents" / "browser_agent.py": {
        "reason": "Legacy browser agent direct engine instantiation",
        "owner": "Browser Team",
        "milestone": "v0.20",
    },
    ROOT / "src" / "core" / "backends" / "adapters" / "browser_backend.py": {
        "reason": "Legacy adapter direct browser engine call",
        "owner": "Integration Team",
        "milestone": "v0.20",
    },
    ROOT / "src" / "desktop" / "native" / "desktop_execution_engine.py": {
        "reason": "Native desktop execution engine legacy bootstrap",
        "owner": "Desktop Team",
        "milestone": "v0.20",
    },
    ROOT / "src" / "engineering" / "engineering_manager.py": {
        "reason": "Legacy engineering sub-engines direct instantiation",
        "owner": "DevOps Team",
        "milestone": "v0.20",
    },
    ROOT / "src" / "vision" / "vision_plugin.py": {
        "reason": "Legacy vision plugin direct instantiation",
        "owner": "Vision Team",
        "milestone": "v0.20",
    },
}

ALLOWED_MAP_FILES = {
    ROOT / "src" / "brain" / "aca" / "strategy_engine.py",
    ROOT / "src" / "brain" / "aca" / "aca_brain.py",
    # Schema definition — defines the ExecutionMap dataclass
    ROOT / "src" / "brain" / "schemas" / "execution_map.py",
    # Legacy files kept for backward compat
    ROOT / "src" / "brain" / "execution_map_generator.py",
    ROOT / "src" / "brain" / "execution_map_validator.py",
    ROOT / "src" / "brain" / "aca" / "planner.py",
}

ALLOWED_THOUGHT_FILES = {
    ROOT / "src" / "brain" / "aca" / "fusion_engine.py",
    # Schema definition — defines the Thought dataclass
    ROOT / "src" / "brain" / "schemas" / "thought.py",
}

ALLOWED_MEMORY_FILES = {
    ROOT / "src" / "brain" / "aca" / "learning.py",
    ROOT / "src" / "brain" / "learning.py",
    # Legacy files kept for backward compat
    ROOT / "src" / "brain" / "conversation_engine.py",
    ROOT / "src" / "brain" / "executive" / "learning.py",
}

ALLOWED_ARTIFACT_FILES = {
    ROOT / "src" / "brain" / "aca" / "artifact_manager.py",
    # Schema definition — defines the Artifact dataclass
    ROOT / "src" / "brain" / "schemas" / "artifact.py",
}


def _iter_py_files(directory: Path):
    """Iterate Python files in a directory, skipping __pycache__."""
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        yield py_file


# ── Guardrail 1: No backend can import ACA ────────────────────────────────

def test_guardrail_1_no_backend_imports_aca():
    """No backend/engine module may import from src.brain.aca."""
    forbidden_dirs = [
        ROOT / "src" / "desktop",
        ROOT / "src" / "browser",
        ROOT / "src" / "research",
        ROOT / "src" / "engineering",
        ROOT / "src" / "voice",
        ROOT / "src" / "vision",
    ]
    violations = []
    for directory in forbidden_dirs:
        if not directory.exists():
            continue
        for py_file in _iter_py_files(directory):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "brain.aca" in node.module:
                        violations.append(f"{py_file}: imports {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "brain.aca" in alias.name:
                            violations.append(f"{py_file}: imports {alias.name}")
    assert not violations, f"Guardrail 1 violated:\n" + "\n".join(violations)


def test_aca_migration_tracker_validity():
    """Ensure every legacy engine allowlist exception has a reason, owner, and milestone."""
    invalid_entries = []
    for file_path, metadata in ENGINE_ALLOWLIST.items():
        reason = metadata.get("reason", "").strip()
        owner = metadata.get("owner", "").strip()
        milestone = metadata.get("milestone", "").strip()
        if not reason or not owner or not milestone:
            invalid_entries.append(
                f"{file_path}: missing required metadata (reason='{reason}', owner='{owner}', milestone='{milestone}')"
            )
    assert not invalid_entries, "ACA Migration Tracker entries must have valid reason, owner, and milestone:\n" + "\n".join(invalid_entries)


# ── Guardrail 2: Only ExecutionCoordinator may invoke engines ─────────────

def test_guardrail_2_only_coordinator_invokes_engines():
    """Engine instantiation should only happen in allowed wiring files or tracked allowlist entries."""
    allowed_files = set(CORE_ALLOWED_ENGINE_FILES) | set(ENGINE_ALLOWLIST.keys())
    engine_class_names = [
        "DesktopExecutionEngine",
        "BrowserEngine",
        "ResearchEngine",
        "EngineeringManager",
        "VoiceManager",
        "VisionManager",
    ]
    violations = []
    for py_file in _iter_py_files(ROOT / "src"):
        if py_file in allowed_files:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for engine_name in engine_class_names:
            if f"{engine_name}(" in content:
                violations.append(f"{py_file}: instantiates {engine_name}")
    assert not violations, f"Guardrail 2 violated:\n" + "\n".join(violations)


# ── Guardrail 3: Only StrategyEngine creates ExecutionMaps ────────────────

def test_guardrail_3_only_strategy_engine_creates_execution_maps():
    """Only StrategyEngine should produce ExecutionMap dicts."""
    violations = []
    for py_file in _iter_py_files(ROOT / "src" / "brain"):
        if py_file in ALLOWED_MAP_FILES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if '"steps"' in content and '"verification"' in content:
            violations.append(f"{py_file}: creates ExecutionMap-like dict")
    assert not violations, f"Guardrail 3 violated:\n" + "\n".join(violations)


# ── Guardrail 4: Only FusionEngine creates Thought ────────────────────────

def test_guardrail_4_only_fusion_engine_creates_thought():
    """Only FusionEngine should instantiate Thought."""
    violations = []
    for py_file in _iter_py_files(ROOT / "src" / "brain"):
        if py_file in ALLOWED_THOUGHT_FILES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "Thought(" in content:
            violations.append(f"{py_file}: instantiates Thought")
    assert not violations, f"Guardrail 4 violated:\n" + "\n".join(violations)


# ── Guardrail 5: Only LearningEngine writes long-term memory ───────────────

def test_guardrail_5_only_learning_writes_memory():
    """Only LearningEngine should call memory write operations."""
    violations = []
    for py_file in _iter_py_files(ROOT / "src" / "brain"):
        if py_file in ALLOWED_MEMORY_FILES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "remember_exchange" in content or "add_rule" in content:
            violations.append(f"{py_file}: writes long-term memory")
    assert not violations, f"Guardrail 5 violated:\n" + "\n".join(violations)


# ── Guardrail 6: Only ArtifactManager creates artifacts ────────────────────

def test_guardrail_6_only_artifact_manager_creates_artifacts():
    """Only ArtifactManager should instantiate Artifact."""
    violations = []
    for py_file in _iter_py_files(ROOT / "src" / "brain"):
        if py_file in ALLOWED_ARTIFACT_FILES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "Artifact(" in content:
            violations.append(f"{py_file}: instantiates Artifact")
    assert not violations, f"Guardrail 6 violated:\n" + "\n".join(violations)


# ── Guardrail 7: All requests go through ACA.process() ────────────────────

def test_guardrail_7_single_entry_point():
    """AuraCore.process_request should delegate to ACA when enabled."""
    aura_core = (ROOT / "core" / "aura_core.py").read_text(encoding="utf-8")
    assert "process_via_executive_brain" in aura_core, "AuraCore missing ACA entry point"
    assert "ACABrain" in aura_core, "AuraCore missing ACABrain import"