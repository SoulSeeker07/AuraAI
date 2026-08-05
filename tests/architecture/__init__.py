# tests/architecture/__init__.py
"""
Architecture Verification Suite for Aura v0.15.5

These tests do not check functionality. They enforce structural rules:
- Every module must be importable
- Public APIs must be accessible in isolation
- Layer dependencies must flow in one direction
- No circular imports
- Managers must not import Planners
- Planners must not import Win32 API
- Adapters must not import DesktopContext
"""
