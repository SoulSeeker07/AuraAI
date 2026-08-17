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
def cleanup_world_model():
    """
    Ensure WorldModel instance thread pools are cleanly shut down after every test.
    We use reset_instance() rather than just shutdown() to ensure the next test 
    gets a fresh instance rather than a singleton with a dead executor.
    """
    yield
    try:
        from brain.world_model import WorldModel
        WorldModel.reset_instance()
    except ImportError:
        pass
