# Architecture (Overview)

This document outlines the high-level architecture for Aura (foundation).

- Service: FastAPI + WebSocket for background AI/messaging.
- Desktop: QML-based control center (PySide6).
- Overlay: QML frameless overlay invoked by hotkey.
- Communication: WebSocket (local), HTTP for config and control.

See docs/roadmap.md for milestone breakdown and delivery plan.
