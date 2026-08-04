#!/usr/bin/env python
"""Run Memory 2.0 tests"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
