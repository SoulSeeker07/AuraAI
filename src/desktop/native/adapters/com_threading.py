"""
COM Thread Safety Utilities
============================
Location: src/desktop/native/adapters/com_threading.py

Provides reusable COM initialization/uninitalization primitives for any adapter
that uses COM-based APIs (WMI, UIA, CoreAudio) from arbitrary threads.

Replaces the per-method boilerplate pattern:
    com_init = False
    try:
        pythoncom.CoInitialize()
        com_init = True
        ...
    finally:
        if com_init:
            pythoncom.CoUninitialize()

Usage:
    @com_thread_safe
    def my_wmi_call(self):
        import wmi
        return wmi.WMI().Win32_Battery()

    # Or as a context manager:
    with com_scope():
        import wmi
        return wmi.WMI().Win32_Battery()
"""

import functools
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def com_scope():
    """
    Context manager that ensures COM is initialized for the current thread.

    Handles the CoInitialize/CoUninitialize lifecycle safely — idempotent
    if COM was already initialized on this thread (catches and ignores
    the 'already initialized' HRESULT).

    Yields:
        None — use inside a `with` block.

    Example::

        with com_scope():
            import wmi
            c = wmi.WMI()
            batteries = c.Win32_Battery()
    """
    import pythoncom

    initialized = False
    try:
        pythoncom.CoInitialize()
        initialized = True
    except Exception:
        # COM may already be initialized on this thread (e.g. main thread,
        # or nested com_scope calls). That's fine — we just skip uninit later.
        pass

    try:
        yield
    finally:
        if initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def com_thread_safe(fn):
    """
    Decorator that wraps a function call in COM initialization/uninitalization.

    Every decorated call gets a fresh CoInitialize on entry and CoUninitialize
    on exit, making it safe to call from any thread (worker pool, executor,
    WorldModel provider, etc.) without requiring the caller to manage COM state.

    Args:
        fn: Function to wrap.

    Returns:
        Wrapped function with COM lifecycle management.

    Example::

        class WMIPowerAdapter:
            @com_thread_safe
            def get_battery_status(self):
                import wmi
                return wmi.WMI().Win32_Battery()
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with com_scope():
            return fn(*args, **kwargs)

    return wrapper
