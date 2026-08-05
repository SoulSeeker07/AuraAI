# tests/architecture/conftest.py
"""
Ensure src/ is on sys.path for architecture tests.
These tests import directly from core, desktop, execution etc.
"""

import importlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
# Must be first entry so src-resident packages like 'core', 'desktop', 'execution'
# take precedence over any installed package with the same name.
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Invalidate the import caches so any previously-seen stub is replaced
importlib.invalidate_caches()
