#!/usr/bin/env python
"""Run Memory 2.0 tests"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
