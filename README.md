# Aura

An AI OS companion shell for Windows. Sprint 1 focuses on the native desktop
experience: a control center window, system tray presence, dark theme,
overlay prompt, and Alt + Space activation.

## Structure
- src/ - application source code
- assets/ - images and static files
- database/ - database files and models
- plugins/ - extension/plugin modules
- tests/ - test suite
- docs/ - documentation

## Aura Shell
- `src/gui/main_window.py` - frameless desktop control center
- `src/gui/titlebar.py` - custom draggable title bar
- `src/gui/overlay.py` - Alt + Space assistant overlay
- `src/gui/tray.py` - Windows system tray integration
- `src/gui/theme.py` - shared dark theme engine
- `src/gui/animations.py` - reusable UI animation helpers
- `src/core/app.py` - application bootstrap and lifecycle
- `src/core/config.py` - app constants and runtime paths
- `src/core/event_bus.py` - decoupled app-wide messaging
- `src/core/settings.py` - persistent user settings
- `src/core/plugin_manager.py` - plugin discovery and loading
- `src/core/window_manager.py` - GUI window orchestration
- `src/core/overlay_manager.py` - overlay prompt handling
- `src/core/live_screen.py` - continuous screen capture session manager
- `src/core/screen_context.py` - screenshot and latest-frame capture helpers

## Setup
1. Activate the virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Add your API keys to `.env`

## Run
```powershell
python src/main.py
```

Close the main window to keep Aura running in the tray. Use Alt + Space to open
the overlay, or choose "Show Overlay" from the tray menu.

If the local `.venv` launcher is broken, use the bundled-runtime launcher:
```powershell
.\scripts\run_aura.ps1
```
