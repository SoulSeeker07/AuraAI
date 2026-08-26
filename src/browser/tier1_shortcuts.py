"""
tier1_shortcuts.py

Tier 1 fast shortcuts for simple informational goals (e.g. direct Wikipedia REST API)
that do not require launching a full Chromium browser session.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def try_shortcut(goal: str) -> Optional[Dict[str, Any]]:
    """
    Check if a goal is a pure informational query matching a known REST shortcut.
    Returns a result dict if satisfied, or None to delegate to full agent loop.
    """
    g = goal.strip()

    # Wikipedia REST shortcut: e.g. "what is Python", "who is Alan Turing", "wiki search quantum computing"
    wiki_match = re.search(
        r"^(?:wiki(?:pedia)?\s+(?:search\s+|lookup\s+)?|what\s+is\s+|who\s+is\s+|tell\s+me\s+about\s+)(.+)$",
        g,
        re.IGNORECASE,
    )
    if wiki_match:
        query = wiki_match.group(1).strip().rstrip("?.")
        if query and not any(k in query.lower() for k in ("buy", "order", "price", "login", "amazon", "youtube")):
            try:
                import urllib.request
                import json

                encoded = urllib.parse.quote(query.replace(" ", "_"))
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
                req = urllib.request.Request(url, headers={"User-Agent": "AuraAI/2.0 (Desktop AI Assistant)"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        extract = data.get("extract")
                        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
                        if extract:
                            logger.info("[Tier1Shortcut] Wikipedia shortcut satisfied: '%s'", query)
                            return {
                                "status": "SUCCESS",
                                "summary": extract,
                                "url": page_url,
                                "steps": [{"step": 0, "tool": "wikipedia_rest_shortcut", "query": query}],
                            }
            except Exception as ex:
                logger.debug("[Tier1Shortcut] Wikipedia lookup bypassed: %s", ex)

    return None
