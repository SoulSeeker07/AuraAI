# Ensure the src/ directory is on sys.path so tests can import src-based packages
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
EXAMPLES = os.path.join(ROOT, "examples")

if SRC not in sys.path:
    sys.path.insert(0, SRC)
if ROOT not in sys.path:
    sys.path.insert(1, ROOT)
if EXAMPLES not in sys.path:
    sys.path.insert(2, EXAMPLES)

import pytest

@pytest.fixture(autouse=True)
def cleanup_singletons():
    """
    Ensure singleton registries and thread pools are cleanly shut down and reset
    after every test to prevent cross-test pollution and leaked background state.
    """
    yield
    try:
        from brain.world_model import WorldModel
        WorldModel.reset_instance()
    except ImportError:
        pass
    try:
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry
        NativeManagerRegistry.reset_instance()
    except ImportError:
        pass
    try:
        from desktop.native.desktop_execution_engine import reset_desktop_execution_engine
        reset_desktop_execution_engine()
    except ImportError:
        pass


