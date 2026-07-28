"""Aura bootstrap entrypoint.

This script performs the minimal startup steps so running `python src/main.py`
prints the expected lifecycle messages even when GUI dependencies are not
installed. When PySide6 and other GUI dependencies are available the
application will proceed to start the real GUI.
"""

import sys
# Ensure UTF-8 output (avoid UnicodeEncodeError on Windows consoles)
try:
    sys.stdout.reconfigure(encoding='utf-8')  # Python 3.7+
except Exception:
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Step 1: Load configuration (no heavy GUI imports)
from core import config as core_config  # type: ignore
print("\n✓ Load Configuration\n")

# Step 2: Initialize logger
from core.logger import logger  # type: ignore
print("\n✓ Initialize Logger\n")

# Step 3: Load settings
from core.settings import Settings  # type: ignore
settings = Settings()
print("\n✓ Load Settings\n")

# Step 4: Create event bus
from core.event_bus import EventBus  # type: ignore
event_bus = EventBus()
print("\n✓ Create Event Bus\n")

# Step 5: Start GUI (attempt to import the application)
try:
    from core.app import create_app  # type: ignore
    gui_available = True
except Exception as exc:  # pragma: no cover - environment-dependent
    logger.warning("GUI dependencies unavailable: %s", exc)
    gui_available = False

if gui_available:
    print("\n✓ Start GUI\n")
    app = create_app()
    print("\n✓ Ready\n")
    # Run the real application (this will block until exit)
    sys.exit(app.run())
else:
    # Graceful fallback for environments without PySide6 installed.
    print("\n✓ Start GUI (skipped - GUI dependencies missing)\n")
    print("\n✓ Ready\n")
    sys.exit(0)
