"""
Next-Gen Interactive Diagram & Artifact Visualizer for AuraAI
============================================================
Location: src/gui/widgets/diagram_viewer.py

Provides Claude-like interactive visual diagram rendering inside Aura's UI.
Supports:
- Mermaid.js (Flowcharts, Sequence diagrams, State machines, Class diagrams, Git graphs, Mindmaps, ER diagrams)
- Interactive Zoom, Pan, Fit-to-screen controls
- Dark Cyberpunk / Holographic Aura Theme styling (Neon Cyan, Deep Obsidian)
- Diagram View vs. Raw Code View toggle
- High-res Fullscreen / Modal Inspection pop-out
- One-click SVG / PNG Export and Clipboard Copy
"""

from __future__ import annotations

import base64
import html
import json
import logging
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal, QByteArray
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def sanitize_mermaid_code(code: str) -> str:
    """
    Auto-repairs common LLM Mermaid syntax errors:
    1. Normalizes non-breaking spaces and Unicode hyphens/dashes.
    2. Quotes unquoted node labels containing parentheses, slashes, or ampersands.
    3. Quotes unquoted edge labels containing special characters.
    """
    if not code:
        return ""

    # 1. Normalize Unicode symbols
    code = (
        code.replace("\u00a0", " ")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )

    # 2. Quote unquoted box labels: NodeID[Label with (parentheses) or special chars]
    def _quote_box(m: re.Match) -> str:
        prefix = m.group(1) or ""
        node_id = m.group(2)
        label = m.group(3).strip()
        if (label.startswith('"') and label.endswith('"')) or (label.startswith("'") and label.endswith("'")):
            return f"{prefix}{node_id}[{label}]"
        # Clean internal quotes and wrap in double quotes
        clean_label = label.replace('"', "'")
        return f'{prefix}{node_id}["{clean_label}"]'

    # Match ID[...] and subgraph ID[...]
    code = re.sub(r'(\bsubgraph\s+)?([a-zA-Z0-9_\-]+)\[([^\]\n\r]+)\]', _quote_box, code)

    # 3. Quote unquoted rounded labels: NodeID(Label with [brackets])
    def _quote_round(m: re.Match) -> str:
        node_id = m.group(1)
        label = m.group(2).strip()
        if (label.startswith('"') and label.endswith('"')) or (label.startswith("'") and label.endswith("'")):
            return f"{node_id}({label})"
        clean_label = label.replace('"', "'")
        return f'{node_id}("{clean_label}")'

    code = re.sub(r'(?<!subgraph\s)([a-zA-Z0-9_\-]+)\(([^)\n\r]+)\)', _quote_round, code)

    # 4. Quote unquoted rhombus labels: NodeID{Label with special chars}
    def _quote_rhombus(m: re.Match) -> str:
        node_id = m.group(1)
        label = m.group(2).strip()
        if (label.startswith('"') and label.endswith('"')) or (label.startswith("'") and label.endswith("'")):
            return f"{node_id}{{{label}}}"
        clean_label = label.replace('"', "'")
        return f'{node_id}{{"{clean_label}"}}'

    code = re.sub(r'([a-zA-Z0-9_\-]+)\{([^}\n\r]+)\}', _quote_rhombus, code)

    # 5. Quote unquoted edge labels: -->|Label with special chars|
    def _quote_edge(m: re.Match) -> str:
        arrow = m.group(1)
        label = m.group(2).strip()
        if (label.startswith('"') and label.endswith('"')) or (label.startswith("'") and label.endswith("'")):
            return f"{arrow}|{label}|"
        clean_label = label.replace('"', "'")
        return f'{arrow}|"{clean_label}"|'

    code = re.sub(r'(-->|---|==>|\.->)\s*\|([^|\n\r]+)\|', _quote_edge, code)

    return code


def is_svg_code(code: str) -> bool:
    """Check if snippet contains SVG markup."""
    c = code.strip().lower()
    return "<svg" in c or (c.startswith("<?xml") and "<svg" in c) or ("<path" in c and "</svg>" in c) or ("<ellipse" in c and "</svg>" in c)


def is_sketch_or_dark_line_svg(code: str) -> bool:
    """
    Detect if an SVG is a pencil sketch, mechanical drafting drawing, or dark-ink schematic
    that was designed for a light/paper background but lacks its own background element.
    """
    c = code.lower()
    
    # 1. If it already has an explicit background rect covering the canvas, don't override
    if re.search(r'<rect[^>]+(?:id=["\'](?:aura-auto-canvas|aura-canvas|canvas|background|bg)["\']|width=["\']100%["\'])[^>]*fill=', c):
        return False
    if "background-color:" in c or "background:" in c[:250]:
        return False
        
    # 2. Check for sketch / drafting keywords
    sketch_keywords = ("sketch", "pencil", "draft", "hand-drawn", "graphite", "charcoal", "cross-section", "schematic")
    has_sketch_keyword = any(k in c for k in sketch_keywords)
    
    # 3. Check for dark stroke / dark text styling
    dark_strokes = re.findall(r'stroke:\s*(#[0-4][0-9a-f]{2,5}|black|rgb\(0,\s*0,\s*0\))', c)
    dark_attrs = re.findall(r'stroke=["\'](#[0-4][0-9a-f]{2,5}|black)["\']', c)
    dark_fills = re.findall(r'fill=["\'](#[0-4][0-9a-f]{2,5}|black)["\']', c)
    
    total_dark_elements = len(dark_strokes) + len(dark_attrs) + len(dark_fills)
    
    if has_sketch_keyword and total_dark_elements > 0:
        return True
        
    if total_dark_elements >= 3:
        # Check if neon strokes dominate (e.g. Aura UI cyan/neon orange HUD SVGs)
        neon_strokes = re.findall(r'stroke:\s*(cyan|#00e5ff|#38bdf8|#f97316|#10b981|#a855f7)', c)
        if len(neon_strokes) < total_dark_elements:
            return True
            
    return False


def inject_canvas_background(svg: str, bg_color: str = "#fcfbf7") -> str:
    """
    Inject a high-contrast architectural drafting paper canvas rect behind SVG drawing elements.
    Calculates precise bounds from the SVG viewBox or width/height attributes.
    """
    vb_match = re.search(r'viewBox=["\']\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*["\']', svg, re.IGNORECASE)
    if vb_match:
        vx, vy, vw, vh = vb_match.groups()
        canvas_rect = f'<rect id="aura-auto-canvas" x="{vx}" y="{vy}" width="{vw}" height="{vh}" fill="{bg_color}" rx="8" style="transition: fill 0.25s ease;" />'
    else:
        w_match = re.search(r'<svg[^>]+width=["\']([\d.]+)["\']', svg, re.IGNORECASE)
        h_match = re.search(r'<svg[^>]+height=["\']([\d.]+)["\']', svg, re.IGNORECASE)
        if w_match and h_match:
            vw, vh = w_match.group(1), h_match.group(1)
            canvas_rect = f'<rect id="aura-auto-canvas" x="0" y="0" width="{vw}" height="{vh}" fill="{bg_color}" rx="8" style="transition: fill 0.25s ease;" />'
        else:
            canvas_rect = f'<rect id="aura-auto-canvas" x="0" y="0" width="100%" height="100%" fill="{bg_color}" rx="8" style="transition: fill 0.25s ease;" />'

    if "</defs>" in svg:
        return re.sub(r'(</defs\s*>)', r'\1\n  ' + canvas_rect, svg, count=1, flags=re.IGNORECASE)
    elif "</style>" in svg:
        return re.sub(r'(</style\s*>)', r'\1\n  ' + canvas_rect, svg, count=1, flags=re.IGNORECASE)
    else:
        return re.sub(r'(<svg\b[^>]*>)', r'\1\n  ' + canvas_rect, svg, count=1, flags=re.IGNORECASE)


def extract_svg_content(code: str) -> str:
    """Extract or wrap clean SVG content for direct interactive browser rendering."""
    code = code.strip()
    m = re.search(r"(<svg[\s\S]*?</svg>)", code, re.IGNORECASE)
    if m:
        svg = m.group(1)
    else:
        # Auto-wrap unclosed or child SVG elements
        clean_inner = re.sub(r"^```[a-zA-Z0-9_\-]*\n?", "", code).rstrip("`").strip()
        if not clean_inner.endswith("</svg>"):
            clean_inner += "\n</svg>"
        if not clean_inner.lower().startswith("<svg"):
            clean_inner = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="100%" height="100%">\n{clean_inner}'
        svg = clean_inner

    # 1. Sanitize illegal <br> or <br/> tags in SVG (causes text collapse and XML parse breakages)
    svg = re.sub(r"<br\s*/?>", " ", svg, flags=re.IGNORECASE)

    # 2. Sanitize unescaped ampersands
    svg = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", svg)

    # 3. Auto-Canvas Injection for Pencil Sketches & Dark Line Drawings
    if is_sketch_or_dark_line_svg(svg):
        svg = inject_canvas_background(svg, bg_color="#fcfbf7")

    # Ensure id="mermaid-svg" on root <svg> tag for pan/zoom integration
    if 'id="' not in svg[:80]:
        svg = re.sub(r"<svg\b", '<svg id="mermaid-svg" xmlns="http://www.w3.org/2000/svg"', svg, count=1, flags=re.IGNORECASE)
    else:
        svg = re.sub(r'id="[^"]+"', 'id="mermaid-svg"', svg, count=1)
    return svg


def build_mermaid_html(mermaid_code: str, theme: str = "dark") -> str:
    """
    Builds a standalone, responsive HTML page supporting both Mermaid.js diagrams
    and native SVG vector illustrations with pan/zoom and export.
    """
    is_svg = is_svg_code(mermaid_code)
    is_sketch = is_sketch_or_dark_line_svg(mermaid_code) if is_svg else False
    
    if is_svg:
        raw_svg = extract_svg_content(mermaid_code)
        diagram_div = f'<div id="diagram" style="opacity: 1; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">\n{raw_svg}\n</div>'
    else:
        sanitized = sanitize_mermaid_code(mermaid_code)
        safe_code = html.escape(sanitized.strip())
        diagram_div = f'<div class="mermaid" id="diagram">\n{safe_code}\n</div>'
    
    # Custom Mermaid dark theme variables tailored for AuraAI
    theme_variables = {
        "darkMode": True,
        "background": "#080d18",
        "primaryColor": "#0f233a",
        "primaryTextColor": "#f8fafc",
        "primaryBorderColor": "#00e5ff",
        "lineColor": "#00e5ff",
        "secondaryColor": "#1e293b",
        "tertiaryColor": "#0f172a",
        "noteBkgColor": "#1e293b",
        "noteTextColor": "#38bdf8",
        "noteBorderColor": "#0284c7",
        "actorBkg": "#13233c",
        "actorBorder": "#00e5ff",
        "actorTextColor": "#ffffff",
        "actorLineColor": "#00e5ff",
        "signalColor": "#00e5ff",
        "signalTextColor": "#f1f5f9",
        "messageColor": "#f1f5f9",
        "labelBoxBkgColor": "#0b1326",
        "labelBoxBorderColor": "#00e5ff",
        "labelTextColor": "#f8fafc",
        "loopTextColor": "#38bdf8",
        "activationBorderColor": "#00e5ff",
        "activationBkgColor": "#0e2238",
        "sequenceNumberColor": "#fbbf24",
        "git0": "#00e5ff",
        "git1": "#a855f7",
        "git2": "#10b981",
        "git3": "#f59e0b",
        "git4": "#ef4444",
        "fontFamily": "Segoe UI, -apple-system, system-ui, sans-serif",
    }
    theme_json = json.dumps(theme_variables)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aura Diagram Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            background: #080d18;
            color: #e2e8f0;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        #container {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            background: radial-gradient(circle at center, rgba(14, 34, 56, 0.4) 0%, rgba(8, 13, 24, 0.95) 100%);
        }}
        .mermaid, #diagram {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.25s ease-in-out;
        }}
        .mermaid svg, #diagram svg {{
            max-width: 100%;
            max-height: 100%;
            height: 100% !important;
            width: 100% !important;
        }}
        #error-overlay {{
            display: none;
            position: absolute;
            top: 20px;
            left: 20px;
            right: 20px;
            padding: 14px 18px;
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 8px;
            color: #fca5a5;
            font-family: Consolas, monospace;
            font-size: 12px;
            white-space: pre-wrap;
            z-index: 100;
        }}
        /* Futuristic node glow for Mermaid */
        .mermaid .node rect, .mermaid .node circle, .mermaid .node polygon, .mermaid .node path {{
            stroke-width: 1.5px !important;
            filter: drop-shadow(0 2px 6px rgba(0, 229, 255, 0.15));
        }}
        .edgePath path, .messageLine0, .messageLine1 {{
            stroke: #00e5ff !important;
            stroke-width: 1.8px !important;
            filter: drop-shadow(0 1px 4px rgba(56, 189, 248, 0.2));
        }}
        .mermaid text, .messageText, .loopText, .noteText, .labelText, .actor > tspan {{
            fill: #f1f5f9 !important;
            font-size: 14px !important;
            font-weight: 500 !important;
        }}
        .nodeLabel {{
            font-size: 14px !important;
            font-weight: 600 !important;
        }}
        .actor {{
            stroke: #00e5ff !important;
            fill: #0e2238 !important;
        }}
        #controls-bar {{
            position: absolute;
            bottom: 12px;
            right: 12px;
            display: flex;
            gap: 5px;
            background: rgba(13, 22, 38, 0.88);
            border: 1px solid rgba(0, 229, 255, 0.35);
            border-radius: 6px;
            padding: 4px 6px;
            z-index: 50;
            backdrop-filter: blur(8px);
        }}
        #controls-bar button {{
            background: rgba(30, 58, 90, 0.7);
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: #00e5ff;
            border-radius: 4px;
            min-width: 26px;
            height: 24px;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 4px;
            transition: all 0.15s ease;
        }}
        #controls-bar button:hover {{
            background: rgba(0, 229, 255, 0.25);
            color: #ffffff;
            border-color: #00e5ff;
        }}
        #controls-bar #btn-canvas-mode {{
            min-width: 68px;
            font-size: 11px;
            padding: 0 6px;
            color: #38bdf8;
            background: rgba(30, 58, 90, 0.85);
        }}
        #controls-bar #btn-canvas-mode:hover {{
            color: #ffffff;
            background: rgba(0, 229, 255, 0.35);
            border-color: #00e5ff;
        }}
    </style>
</head>
<body>
    <div id="container">
        <div id="error-overlay"></div>
        {diagram_div}
        <div id="controls-bar">
            <button id="btn-canvas-mode" onclick="cycleCanvasMode()" title="Toggle Canvas Mode (Drafting Paper / Dark / Blueprint / White)">{'📜 Paper' if is_sketch else '🌌 Dark'}</button>
            <button onclick="zoomIn()" title="Zoom In">+</button>
            <button onclick="zoomOut()" title="Zoom Out">−</button>
            <button onclick="zoomReadable()" title="Readable 100% (1:1)">1:1</button>
            <button onclick="resetZoom()" title="Fit to Container">⟲</button>
        </div>
    </div>

    <script>
        let panZoomInstance = null;

        if ({'true' if is_svg else 'false'}) {{
            try {{
                const el = document.getElementById('diagram');
                if (el) el.style.opacity = '1';
                panZoomInstance = svgPanZoom('#mermaid-svg', {{
                    zoomEnabled: true,
                    controlIconsEnabled: false,
                    fit: true,
                    center: true,
                    minZoom: 0.1,
                    maxZoom: 20,
                    zoomScaleSensitivity: 0.25,
                    dblClickZoomEnabled: false
                }});
                setTimeout(() => {{
                    if (panZoomInstance) {{
                        const currentZoom = panZoomInstance.getZoom();
                        if (currentZoom < 0.85) {{
                            panZoomInstance.zoom(1.0);
                            panZoomInstance.center();
                        }}
                    }}
                }}, 60);
            }} catch (pzErr) {{
                console.warn('SVG panZoom warning:', pzErr);
            }}
        }} else {{
            try {{
                mermaid.initialize({{
                    startOnLoad: false,
                    theme: 'base',
                    themeVariables: {theme_json},
                    securityLevel: 'loose',
                    fontFamily: 'Segoe UI, sans-serif',
                    flowchart: {{
                        htmlLabels: true,
                        curve: 'basis',
                        padding: 18,
                        nodeSpacing: 50,
                        rankSpacing: 50
                    }},
                    sequence: {{
                        mirrorActors: false,
                        bottomMarginAdj: 12
                    }}
                }});

                mermaid.run({{
                    nodes: [document.getElementById('diagram')],
                    suppressErrors: false
                }}).then(() => {{
                    const el = document.getElementById('diagram');
                    if (el) el.style.opacity = '1';
                    const svg = el ? el.querySelector('svg') : null;
                    if (svg) {{
                        svg.setAttribute('id', 'mermaid-svg');
                        try {{
                            panZoomInstance = svgPanZoom('#mermaid-svg', {{
                                zoomEnabled: true,
                                controlIconsEnabled: false,
                                fit: true,
                                center: true,
                                minZoom: 0.1,
                                maxZoom: 20,
                                zoomScaleSensitivity: 0.25,
                                dblClickZoomEnabled: false
                            }});

                            // Auto-adjust scale
                            setTimeout(() => {{
                                if (panZoomInstance) {{
                                    const currentZoom = panZoomInstance.getZoom();
                                    if (currentZoom < 0.75) {{
                                        panZoomInstance.zoom(0.95);
                                        panZoomInstance.center();
                                    }}
                                }}
                            }}, 60);

                        }} catch (pzErr) {{
                            console.warn('svgPanZoom init warning:', pzErr);
                        }}
                    }}
                }}).catch(err => {{
                    showError(err.str || err.message || String(err));
                }});
            }} catch (err) {{
                showError(err.message || String(err));
            }}
        }}

        function showError(msg) {{
            const errDiv = document.getElementById('error-overlay');
            if (errDiv) {{
                errDiv.innerText = '⚠ Diagram Syntax Error:\\n' + msg;
                errDiv.style.display = 'block';
            }}
        }}

        // Exposed functions for PySide6 communication & UI buttons
        function zoomIn() {{
            if (panZoomInstance) panZoomInstance.zoomIn();
        }}
        function zoomOut() {{
            if (panZoomInstance) panZoomInstance.zoomOut();
        }}
        function zoomReadable() {{
            if (panZoomInstance) {{
                panZoomInstance.zoom(1.0);
                panZoomInstance.center();
            }}
        }}
        function resetZoom() {{
            if (panZoomInstance) {{
                panZoomInstance.resetZoom();
                panZoomInstance.center();
            }}
        }}
        function getSvgSource() {{
            const svg = document.querySelector('#diagram svg');
            return svg ? svg.outerHTML : '';
        }}

        // Canvas Mode Cycling (Drafting Paper / Dark / Blueprint / White)
        const isPencilSketch = {'true' if is_sketch else 'false'};
        const canvasModes = [
            {{ id: 'paper', label: '📜 Paper', canvasBg: '#fcfbf7', containerBg: 'radial-gradient(circle at center, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.95) 100%)' }},
            {{ id: 'dark', label: '🌌 Dark', canvasBg: '#080d18', containerBg: 'radial-gradient(circle at center, rgba(14, 34, 56, 0.4) 0%, rgba(8, 13, 24, 0.95) 100%)' }},
            {{ id: 'blueprint', label: '📐 Blueprint', canvasBg: '#0c2340', containerBg: 'radial-gradient(circle at center, rgba(10, 37, 64, 0.6) 0%, rgba(6, 17, 34, 0.95) 100%)' }},
            {{ id: 'white', label: '⬜ White', canvasBg: '#ffffff', containerBg: '#1e293b' }}
        ];
        let currentModeIdx = isPencilSketch ? 0 : 1;

        function cycleCanvasMode() {{
            currentModeIdx = (currentModeIdx + 1) % canvasModes.length;
            applyCanvasMode(canvasModes[currentModeIdx]);
        }}

        function applyCanvasMode(mode) {{
            const btn = document.getElementById('btn-canvas-mode');
            if (btn) btn.innerText = mode.label;

            const container = document.getElementById('container');
            if (container) container.style.background = mode.containerBg;

            const canvasRect = document.getElementById('aura-auto-canvas');
            const svgEl = document.getElementById('mermaid-svg');

            if (mode.id === 'blueprint') {{
                if (canvasRect) canvasRect.setAttribute('fill', '#091e3a');
                if (svgEl && isPencilSketch) {{
                    svgEl.style.filter = 'drop-shadow(0 0 1px rgba(56, 189, 248, 0.4))';
                    document.querySelectorAll('#mermaid-svg path, #mermaid-svg line, #mermaid-svg circle, #mermaid-svg polygon').forEach(el => {{
                        if (el.id !== 'aura-auto-canvas') el.style.stroke = '#67e8f9';
                    }});
                    document.querySelectorAll('#mermaid-svg text').forEach(el => {{
                        el.style.fill = '#f0f9ff';
                    }});
                }}
            }} else if (mode.id === 'dark') {{
                if (canvasRect) canvasRect.setAttribute('fill', '#080d18');
                if (svgEl && isPencilSketch) {{
                    svgEl.style.filter = 'none';
                    document.querySelectorAll('#mermaid-svg path, #mermaid-svg line, #mermaid-svg circle, #mermaid-svg polygon').forEach(el => {{
                        if (el.id !== 'aura-auto-canvas') el.style.stroke = '#00e5ff';
                    }});
                    document.querySelectorAll('#mermaid-svg text').forEach(el => {{
                        el.style.fill = '#f8fafc';
                    }});
                }}
            }} else {{
                if (canvasRect) canvasRect.setAttribute('fill', mode.canvasBg);
                if (svgEl) {{
                    svgEl.style.filter = 'none';
                    if (!canvasRect) svgEl.style.backgroundColor = mode.canvasBg;
                }}
                document.querySelectorAll('#mermaid-svg path, #mermaid-svg line, #mermaid-svg circle, #mermaid-svg polygon').forEach(el => {{
                    if (el.id !== 'aura-auto-canvas') el.style.stroke = '';
                }});
                document.querySelectorAll('#mermaid-svg text').forEach(el => {{
                    el.style.fill = '';
                }});
            }}
        }}
    </script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# 2. DIAGRAM TYPE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_diagram_type(code: str) -> str:
    """Detects the diagram type from the first non-comment line."""
    if is_svg_code(code):
        code_low = code.lower()
        if any(k in code_low for k in ("sketch", "pencil", "graphite", "draft", "hand-drawn")):
            return "PENCIL SKETCH"
        if any(k in code_low for k in ("blueprint", "cad", "schematic")):
            return "CAD BLUEPRINT"
        if any(k in code_low for k in ("mcdu", "cockpit", "interface", "layout", "screen", "wireframe", "mockup", "dashboard")):
            return "UI INTERFACE LAYOUT"
        return "SVG VECTOR ART"

    lines = [line.strip() for line in code.strip().splitlines() if line.strip() and not line.strip().startswith("%%")]
    if not lines:
        return "DIAGRAM"
    
    first = lines[0].lower()
    if first.startswith("graph") or first.startswith("flowchart"):
        return "FLOWCHART"
    elif first.startswith("sequencediagram"):
        return "SEQUENCE"
    elif first.startswith("classdiagram"):
        return "CLASS DIAGRAM"
    elif first.startswith("statediagram"):
        return "STATE MACHINE"
    elif first.startswith("erdiagram"):
        return "ENTITY-RELATION"
    elif first.startswith("gitgraph"):
        return "GIT GRAPH"
    elif first.startswith("mindmap"):
        return "MINDMAP"
    elif first.startswith("gantt"):
        return "GANTT CHART"
    elif first.startswith("pie"):
        return "PIE CHART"
    elif first.startswith("quadrantchart"):
        return "QUADRANT CHART"
    elif first.startswith("c4context") or first.startswith("c4container"):
        return "C4 ARCHITECTURE"
    elif first.startswith("timeline"):
        return "TIMELINE"
    elif first.startswith("architecture"):
        return "ARCHITECTURE"
    return "DIAGRAM"


# ─────────────────────────────────────────────────────────────────────────────
# 3. FULLSCREEN / MODAL DIAGRAM INSPECTOR DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class DiagramInspectDialog(QDialog):
    """
    High-Resolution Fullscreen / Expanded Diagram Inspector Dialog.
    Allows zooming, panning, resetting, and exporting complex diagrams.
    """

    def __init__(self, mermaid_code: str, title: str = "Aura Architecture Diagram", parent=None):
        super().__init__(parent)
        self.mermaid_code = mermaid_code
        self.setWindowTitle(f"Aura Diagram Inspector // {title}")
        self.resize(1100, 720)
        self.setStyleSheet("""
            QDialog {
                background: #080d18;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header bar - Compact, sleek ribbon
        header = QFrame()
        header.setObjectName("inspectHeader")
        header.setFixedHeight(44)
        header.setStyleSheet("""
            QFrame#inspectHeader {
                background: rgba(14, 24, 42, 0.92);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 8px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        h_layout.setSpacing(10)

        dtype = detect_diagram_type(mermaid_code)
        badge = QLabel(f"[{dtype}]")
        badge.setFont(QFont("Consolas", 8, QFont.Bold))
        badge.setFixedHeight(24)
        badge.setStyleSheet("color: #00e5ff; background: rgba(0, 229, 255, 0.12); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 4px; padding: 2px 8px;")
        h_layout.addWidget(badge)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #f8fafc; background: transparent; border: none;")
        h_layout.addWidget(title_lbl)

        h_layout.addStretch()

        # Canvas & Zoom Controls
        btn_canvas = QPushButton("📜 Canvas")
        btn_zin = QPushButton("🔍+ Zoom In")
        btn_zout = QPushButton("🔍- Zoom Out")
        btn_reset = QPushButton("↺ Fit Screen")
        btn_export = QPushButton("💾 Export SVG")
        btn_close = QPushButton("✕ Close")

        for btn in (btn_canvas, btn_zin, btn_zout, btn_reset, btn_export):
            btn.setFont(QFont("Segoe UI", 9))
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(30, 58, 90, 0.5);
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    border-radius: 5px;
                    color: #e2e8f0;
                    padding: 3px 10px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.2);
                    border-color: #00e5ff;
                    color: #ffffff;
                }
            """)
            h_layout.addWidget(btn)

        btn_close.setFixedHeight(28)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 5px;
                color: #fca5a5;
                padding: 3px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.4);
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.accept)
        h_layout.addWidget(btn_close)

        layout.addWidget(header, 0)

        # WebEngine View for rendering
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: #080d18; border-radius: 8px;")
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.web_view.setHtml(build_mermaid_html(mermaid_code), QUrl("http://localhost"))
        layout.addWidget(self.web_view, 1)

        # Connect actions
        btn_canvas.clicked.connect(lambda: self.web_view.page().runJavaScript("cycleCanvasMode();"))
        btn_zin.clicked.connect(lambda: self.web_view.page().runJavaScript("zoomIn();"))
        btn_zout.clicked.connect(lambda: self.web_view.page().runJavaScript("zoomOut();"))
        btn_reset.clicked.connect(lambda: self.web_view.page().runJavaScript("resetZoom();"))
        btn_export.clicked.connect(self._export_svg)

    def _export_svg(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Diagram as SVG", "aura_diagram.svg", "SVG Files (*.svg)")
        if file_path:
            def handle_svg(svg_code):
                if svg_code:
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(svg_code)
                        logger.info(f"Successfully saved SVG diagram to {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to save SVG: {e}")

            self.web_view.page().runJavaScript("getSvgSource();", handle_svg)


# ─────────────────────────────────────────────────────────────────────────────
# 4. INLINE DIAGRAM ARTIFACT WIDGET (EMBEDDED IN CHAT)
# ─────────────────────────────────────────────────────────────────────────────

class DiagramArtifactWidget(QFrame):
    """
    Claude-Artifacts-style Interactive Diagram Card embedded directly inside chat messages.
    Provides:
    - 📊 Visual Diagram View (Rendered Mermaid.js)
    - 📝 Code View (Raw syntax with one-click copy)
    - 🔍 Expand / Fullscreen Inspector
    - 💾 Quick Export to SVG / PNG
    """

    def __init__(self, mermaid_code: str, title: str = "Aura Architecture Diagram", parent=None):
        super().__init__(parent)
        self.mermaid_code = mermaid_code.strip()
        self.title = title
        self.diagram_type = detect_diagram_type(self.mermaid_code)
        
        self.setObjectName("DiagramArtifactWidget")
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(420)
        self.setMaximumHeight(680)
        self.setStyleSheet("""
            DiagramArtifactWidget {
                background: #080d18;
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Top Ribbon Bar ──
        ribbon = QFrame()
        ribbon.setFixedHeight(38)
        ribbon.setStyleSheet("""
            QFrame {
                background: rgba(13, 22, 38, 0.9);
                border-bottom: 1px solid rgba(0, 229, 255, 0.2);
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        rb_layout = QHBoxLayout(ribbon)
        rb_layout.setContentsMargins(12, 4, 12, 4)
        rb_layout.setSpacing(8)

        # Type Badge
        badge = QLabel(f"[{self.diagram_type}]")
        badge.setFont(QFont("Consolas", 8, QFont.Bold))
        badge.setStyleSheet("""
            color: #00e5ff;
            background: rgba(0, 229, 255, 0.12);
            border: 1px solid rgba(0, 229, 255, 0.35);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        rb_layout.addWidget(badge)

        # Title
        title_lbl = QLabel(self.title)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #f1f5f9; background: transparent;")
        rb_layout.addWidget(title_lbl)

        rb_layout.addStretch()

        # View Mode Toggle (Diagram vs Code)
        self.btn_diagram = QPushButton("📊 Visual")
        self.btn_diagram.setCheckable(True)
        self.btn_diagram.setChecked(True)
        self.btn_diagram.setFont(QFont("Segoe UI", 8, QFont.Bold))

        self.btn_code = QPushButton("📝 Code")
        self.btn_code.setCheckable(True)
        self.btn_code.setFont(QFont("Segoe UI", 8, QFont.Bold))

        self.btn_inspect = QPushButton("🔍 Expand")
        self.btn_inspect.setFont(QFont("Segoe UI", 8))
        self.btn_inspect.setToolTip("Open in Fullscreen Zoomable Inspector")

        self.btn_canvas = QPushButton("📜 Canvas")
        self.btn_canvas.setFont(QFont("Segoe UI", 8))
        self.btn_canvas.setToolTip("Toggle Canvas Mode (Paper / Dark / Blueprint / White)")

        self.btn_copy = QPushButton("📋 Copy")
        self.btn_copy.setFont(QFont("Segoe UI", 8))
        self.btn_copy.setToolTip("Copy Mermaid source code to clipboard")

        self.btn_export = QPushButton("💾 Save")
        self.btn_export.setFont(QFont("Segoe UI", 8))
        self.btn_export.setToolTip("Export diagram to SVG")

        button_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                color: #94a3b8;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.15);
                border-color: #00e5ff;
                color: #ffffff;
            }
            QPushButton:checked {
                background: rgba(0, 229, 255, 0.25);
                border-color: #00e5ff;
                color: #00e5ff;
            }
        """
        for b in (self.btn_diagram, self.btn_code, self.btn_canvas, self.btn_copy, self.btn_inspect, self.btn_export):
            b.setStyleSheet(button_style)
            rb_layout.addWidget(b)

        layout.addWidget(ribbon)

        # ── 2. Content Stack (WebEngine Diagram vs Raw Code) ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        # Page 0: Rendered WebEngine Diagram
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: #080d18;")
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.web_view.setHtml(build_mermaid_html(self.mermaid_code), QUrl("http://localhost"))
        self.stack.addWidget(self.web_view)

        # Page 1: Raw Code Editor (Read Only)
        self.code_edit = QPlainTextEdit(self.mermaid_code)
        self.code_edit.setReadOnly(True)
        self.code_edit.setFont(QFont("Consolas", 9))
        self.code_edit.setStyleSheet("""
            QPlainTextEdit {
                background: #060a12;
                color: #38bdf8;
                border: none;
                padding: 12px;
                font-family: Consolas, monospace;
            }
        """)
        self.stack.addWidget(self.code_edit)

        layout.addWidget(self.stack)

        # ── Connect Button Signals ──
        self.btn_diagram.clicked.connect(self._show_diagram_view)
        self.btn_code.clicked.connect(self._show_code_view)
        self.btn_canvas.clicked.connect(lambda: self.web_view.page().runJavaScript("cycleCanvasMode();"))
        self.btn_inspect.clicked.connect(self._open_inspector)
        self.btn_copy.clicked.connect(self._copy_code)
        self.btn_export.clicked.connect(self._export_svg)

    def _show_diagram_view(self):
        self.btn_diagram.setChecked(True)
        self.btn_code.setChecked(False)
        self.stack.setCurrentIndex(0)

    def _show_code_view(self):
        self.btn_code.setChecked(True)
        self.btn_diagram.setChecked(False)
        self.stack.setCurrentIndex(1)

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.mermaid_code)
        self.btn_copy.setText("✓ Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, lambda: self.btn_copy.setText("📋 Copy"))

    def _open_inspector(self):
        dlg = DiagramInspectDialog(self.mermaid_code, title=self.title, parent=self.window())
        dlg.exec()

    def _export_svg(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagram as SVG",
            f"aura_{self.diagram_type.lower().replace(' ', '_')}.svg",
            "SVG Files (*.svg)"
        )
        if file_path:
            def handle_svg(svg_code):
                if svg_code:
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(svg_code)
                        logger.info(f"Saved diagram SVG to {file_path}")
                    except Exception as e:
                        logger.error(f"Error saving SVG: {e}")

            self.web_view.page().runJavaScript("getSvgSource();", handle_svg)
