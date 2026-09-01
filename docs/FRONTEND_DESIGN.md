# AuraAI Native Frontend Design Guidelines & System Specification

**Location**: `docs/FRONTEND_DESIGN.md`  
**Status**: ACTIVE / CANONICAL SPECIFICATION  
**Scope**: Windows Native Desktop Client (PyQt6 / PySide6 / Native Shell / Overlay HUDs)

---

## 1. Core Visual Philosophy

AuraAI follows a **Cyber-Industrial Minimalism** design language tailored for modern desktop power users. The user interface prioritizes high information density, deep dark-mode ergonomics, optical hierarchy, and zero visual clutter.

### Guiding Principles
1. **Dark-Mode First (OLED & Low-Eye-Strain)**: Optimized for extended engineering workflows. True dark background surfaces (`#0A0B0E`) with layered elevation rather than flat grays.
2. **Subtle Neon Semantics**: Color is used strictly for state, risk, and focus direction — never for pure decoration.
3. **Information Density without Overwhelm**: Clean typography scales, mono-spaced data tables, and collapsable telemetry drawers.
4. **Non-Blocking Interrupts**: Asynchronous non-modal HUD overlays instead of disruptive, modal Win32 alert dialogs.
5. **Fluid 60 FPS Micro-Interactions**: Hardware-accelerated transitions (150ms–250ms ease-out) for drawers, toasts, and focus thread switches.

---

## 2. Design Tokens & Color Palette (Canonical `src/gui/theme.py` Mapping)

### 2.1 Surface & Elevation Tokens

```css
/* Root Background & Elevational Surfaces (Mapped to theme.py Colors) */
--bg-deep:        #0D1117; /* Colors.BG_DEEP — Primary canvas / window background */
--bg-slate:       #121722; /* Colors.BG_SLATE — Primary cards, sidebars, dock containers */
--bg-surface:     #161C28; /* Colors.BG_SURFACE — Hover states, table headers, elevated cards */
--bg-card:        rgba(22, 28, 40, 0.85);  /* Colors.BG_CARD — Glassmorphic card surface */
--bg-card-hover:  rgba(32, 42, 60, 0.95);  /* Colors.BG_CARD_HOVER — Card hover highlight */
--bg-overlay:     rgba(16, 20, 28, 0.92);  /* Colors.BG_OVERLAY — Glassmorphic HUD overlay background */

/* Borders & Separators */
--border-subtle:  rgba(255, 255, 255, 0.08); /* Colors.BORDER_SUBTLE — Default boundary */
--border-active:  rgba(0, 229, 255, 0.40);   /* Colors.BORDER_ACTIVE — Active element border */
--border-accent:  rgba(0, 229, 255, 0.85);   /* Colors.BORDER_ACCENT — Primary selection ring */
```

### 2.2 Semantic Color Tokens

```css
/* Primary Accent & Brand (Cyber Neon Palette) */
--accent-cyan:      #00E5FF; /* Colors.CYAN — Primary cyber accent, focused inputs */
--accent-cyan-glow: #33EEFF; /* Colors.CYAN_GLOW — Glowing borders, active HUD states */
--accent-blue:      #50AAFF; /* Colors.BLUE / Colors.INFO — Informational notices & telemetry */
--accent-purple:    #818CF8; /* Colors.PURPLE — Multi-agent supervisor, memory citations */

/* Status & Risk Semantics */
--color-success:    #10B981; /* Colors.SUCCESS / Colors.EMERALD — Safe actions, green tests */
--color-warning:    #FBBF24; /* Colors.WARNING / Colors.AMBER — Medium risk, supervised mode */
--color-danger:     #F43F5E; /* Colors.ERROR / Colors.CRIMSON — High/Critical risk, failures */
--color-pending:    #818CF8; /* Colors.PURPLE — Awaiting human cryptographic approval */
```

### 2.3 Text & Foreground Tokens

```css
--text-primary:     #F3F6FC; /* Colors.TEXT_PRIMARY — High-contrast headers, active text */
--text-secondary:   #A5B4CB; /* Colors.TEXT_SECONDARY — Metadata, secondary descriptions */
--text-muted:       #627289; /* Colors.TEXT_MUTED — Subtle timestamps, placeholders */
--text-disabled:    #3E4C60; /* Colors.TEXT_DISABLED — Disabled buttons and controls */
--text-code:        #E2E8F0; /* Code blocks, file paths, tickets (JetBrains Mono) */
```

---

## 3. Typography Scale & Font Stacks

### 3.1 Font Family Hierarchy
- **Primary UI Font**: `Segoe UI Variable`, `Inter`, `-apple-system`, `sans-serif`
- **Monospace / Code / Data**: `JetBrains Mono`, `Consolas`, `Cascadia Code`, `monospace`
- **Fallback**: System Native Sans

### 3.2 Type Scale

| Level | Size | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Display Header** | `20px` | 700 (Bold) | `26px` | Window headers, overlay titles |
| **Section Title** | `15px` | 600 (Semi-Bold) | `20px` | Panel headers, card titles |
| **Body Regular** | `13px` | 400 (Regular) | `18px` | General UI text, chat messages |
| **Body Medium** | `13px` | 500 (Medium) | `18px` | Button labels, list items |
| **Caption / Meta** | `11px` | 400 (Regular) | `14px` | Timestamps, metadata badges, shortcuts |
| **Code / Monospace**| `12px` | 400 (Regular) | `16px` | Paths, tickets (`AUTH-XXXXXX`), JSON, AST |

---

## 4. Spacing System & 8pt Grid

All margins, paddings, gap dimensions, and component heights align strictly to an **8-point geometric grid** (with 4px sub-grid allowances for dense components).

```
--space-1:   4px  /* Micro-spacing: Badge paddings, icon-text gap */
--space-2:   8px  /* Standard tight: Button padding vertical, inner list gap */
--space-3:  12px  /* Intermediate: Input field vertical padding */
--space-4:  16px  /* Standard base: Card padding, container gap */
--space-6:  24px  /* Section gap: Spacing between distinct layout panels */
--space-8:  32px  /* Window padding: Top-level container gutters */
--space-12: 48px  /* Macro: Hero empty-state spacing */
```

### Radius Tokens
- **`--radius-sm` (`4px`)**: Badges, status pills, mini-tooltips.
- **`--radius-md` (`8px`)**: Buttons, text inputs, dropdown menus, table rows.
- **`--radius-lg` (`12px`)**: Cards, approval modals, notification cards.
- **`--radius-xl` (`16px`)**: Top-level HUD windows, floating palette.

---

## 5. Core Native Component Specifications

### 5.1 Custom Frameless Window & Titlebar
- **Height**: `36px` fixed.
- **Background**: `--bg-base` with seamless client-area integration.
- **Window Controls**: Minimize, Maximize, Close styled natively with hover highlights (`#EF4444` on close hover).
- **Aero Snap & Drag**: Uses Windows native `WM_NCHITTEST` handling for native resize borders and window snapping.

### 5.2 Cryptographic Approval & Risk Ticket Card
The visual card displayed when an autonomous trigger or high-risk action requires human confirmation:

```
+-------------------------------------------------------------------------+
| [LOCK ICON] SECURITY AUTHORIZATION REQUIRED               [1h TTL: 59m] |
+-------------------------------------------------------------------------+
| Action:     file.delete                                                 |
| Target:     D:\Sreekanta\VS Code Project\Desktop AI\AuraAI\temp_log.txt  |
| Trigger ID: nightly_clean_trigger                                       |
| Risk Level: HIGH [Destructive File Mutation]                            |
| Ticket ID:  tkt_737aedbeae45                                            |
+-------------------------------------------------------------------------+
| [ View Diff / Parameters ]                                              |
|                                     [ Reject / Abort ]  [ Approve (Y) ] |
+-------------------------------------------------------------------------+
```

- **Border**: `1px solid var(--color-warning)` (for HIGH) or `1px solid var(--color-danger)` (for CRITICAL).
- **Background**: Linear gradient `var(--bg-surface-1)` to `rgba(239, 68, 68, 0.05)`.
- **Keyboard Shortcuts**: `Y` or `Enter` for Approve, `Esc` or `N` for Abort.

### 5.3 Focus Thread Switcher Dock
- **Location**: Bottom-left dock or floating top HUD.
- **Indicator**: Glowing active dot (`--accent-primary` / `--accent-glow`).
- **Unread Counter**: Numeric badge in `--color-warning` when background notifications are queued in `FocusManager`.

---

## 6. Motion & Micro-Interactions

| Transition | Duration | Easing | Usage |
| :--- | :--- | :--- | :--- |
| **Instant** | `0ms` | None | Window dragging, text typing, scroll sync |
| **Micro-Action** | `120ms` | `cubic-bezier(0.4, 0.0, 0.2, 1)` | Button press, hover scale, checkbox tick |
| **Panel Expansion** | `200ms` | `cubic-bezier(0.0, 0.0, 0.2, 1)` | Drawer slide-out, accordion open, tab fade |
| **Modal / Overlay** | `250ms` | `cubic-bezier(0.16, 1, 0.3, 1)` | Approval card pop-in, command palette |

---

## 7. Frontend Anti-Patterns & Prohibitions

1. **NO Blocking Modal Dialogs**: Never invoke `QMessageBox.exec()` or raw Win32 `MessageBox()` on worker/orchestrator threads. All approvals and alerts must route through non-blocking HUD overlays or `FocusManager`.
2. **NO Hardcoded Hex Codes**: Never write raw hex colors like `#222222` inside Python widget stylesheets. Always use canonical token references or theme manager getters.
3. **NO UI-Thread Heavy Computation**: AST parsing, repository scans, sentence embeddings, and SQLite WAL batch operations MUST run inside `QThread` / `asyncio` background tasks with progress signal dispatching.
4. **NO Unconstrained List Growth**: Chat transcripts and event logs must use virtualized list viewports (`QListView` with custom model) or ring-buffer caps to prevent DOM/widget bloat.
5. **NO Non-Standard Spacing**: Never use arbitrary pixel margins (e.g. `margin: 13px; padding: 7px;`). Adhere strictly to the 4px/8px grid.

---

## 8. High-DPI & Multi-Monitor Scaling Rules

- **Per-Monitor V2 Awareness**: All native Windows processes must declare `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)`.
- **Vector Icons**: All glyphs and icons must be SVG format rendered to logical device units with device pixel ratio scaling (`devicePixelRatioF()`).
- **Layout Margins**: Layout spacers and minimum widget dimensions must scale dynamically via `fontMetrics` or DPI scaling helpers (`scale_px(val)`).

---

*Authored for the AuraAI Engineering & Frontend Platform.*