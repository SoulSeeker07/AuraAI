"""
Message Content & Artifact Block Parser
=======================================
Location: src/gui/widgets/message_parser.py

Parses incoming AI responses into structured segments:
- TEXT: standard markdown/prose paragraphs
- CODE: code blocks (python, json, bash, etc.) with language tags
- DIAGRAM: mermaid or graphviz diagram blocks for interactive rendering
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class SegmentType(Enum):
    TEXT = auto()
    CODE = auto()
    DIAGRAM = auto()


@dataclass
class MessageSegment:
    type: SegmentType
    content: str
    language: str = ""
    title: str = ""


# Regex matching ```lang ... ``` blocks
FENCE_PATTERN = re.compile(r"```([a-zA-Z0-9_\-\+\.]+)?\s*\n(.*?)```", re.DOTALL)
DIAGRAM_LANGUAGES = {"mermaid", "mmd", "graphviz", "dot", "svg"}
DIAGRAM_KEYWORDS = (
    "graph ", "graph\n", "flowchart ", "flowchart\n",
    "sequencediagram", "statediagram", "erdiagram",
    "classdiagram", "gitgraph", "mindmap", "gantt",
    "pie", "quadrantchart", "subgraph ", "architecture"
)


def _is_diagram_content(lang: str, content: str) -> bool:
    if lang in DIAGRAM_LANGUAGES:
        return True
    content_lower = content.lower().strip()
    if content_lower.startswith("<svg") or ("<svg" in content_lower and "</svg>" in content_lower):
        return True
    return any(content_lower.startswith(kw) or f"\n{kw}" in content_lower for kw in DIAGRAM_KEYWORDS)


def parse_message_segments(raw_text: str) -> List[MessageSegment]:
    """
    Parses a raw message string into a list of MessageSegments (text, code, or diagram).
    Automatically repairs unclosed fences from streaming or truncated generation.
    """
    if not raw_text:
        return []

    # Auto-repair unclosed code fence
    fence_count = len(re.findall(r"```", raw_text))
    if fence_count % 2 != 0:
        raw_text = raw_text.rstrip() + "\n```"

    segments: List[MessageSegment] = []
    last_idx = 0

    for match in FENCE_PATTERN.finditer(raw_text):
        start, end = match.span()
        # Preceding text
        if start > last_idx:
            text_chunk = raw_text[last_idx:start].strip()
            if text_chunk:
                segments.append(MessageSegment(type=SegmentType.TEXT, content=text_chunk))

        lang = (match.group(1) or "").strip().lower()
        block_content = match.group(2).strip()

        # Check if diagram or code
        if _is_diagram_content(lang, block_content):
            is_svg = lang == "svg" or "<svg" in block_content.lower()
            title = "Aura SVG Vector Illustration" if is_svg else "Aura Architecture Diagram"
            segments.append(
                MessageSegment(
                    type=SegmentType.DIAGRAM,
                    content=block_content,
                    language=lang or ("svg" if is_svg else "mermaid"),
                    title=title,
                )
            )
        else:
            segments.append(
                MessageSegment(
                    type=SegmentType.CODE,
                    content=block_content,
                    language=lang or "code",
                )
            )

        last_idx = end

    # Remaining text
    if last_idx < len(raw_text):
        rem_chunk = raw_text[last_idx:].strip()
        if rem_chunk:
            segments.append(MessageSegment(type=SegmentType.TEXT, content=rem_chunk))

    # If no fences were found at all, return single text segment
    if not segments and raw_text.strip():
        segments.append(MessageSegment(type=SegmentType.TEXT, content=raw_text.strip()))

    return segments
