"""
Action Vocabulary
Location: src/routing/action_vocabulary.py

Defines normalized action vocabulary across Media, Browser, Shopping, and Research domains.
Maps natural language variations to canonical actions and capabilities.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class ActionDomain(str, Enum):
    MEDIA = "media"
    BROWSER = "browser"
    SHOPPING = "shopping"
    RESEARCH = "research"
    DESKTOP = "desktop"


class NormalizedAction(NamedTuple):
    domain: ActionDomain
    action: str
    capability: str
    description: str


class UniversalActionVocabulary:
    """
    Normalized action layer converting arbitrary natural language intent into canonical actions.
    """

    ACTIONS: dict[str, NormalizedAction] = {
        # ── MEDIA ACTIONS ──────────────────────────────────────────
        "media.play": NormalizedAction(
            ActionDomain.MEDIA, "play", "media.play", "Play media, video, or track"
        ),
        "media.pause": NormalizedAction(
            ActionDomain.MEDIA, "pause", "media.pause", "Pause currently playing media"
        ),
        "media.resume": NormalizedAction(
            ActionDomain.MEDIA, "resume", "media.resume", "Resume paused media"
        ),
        "media.stop": NormalizedAction(
            ActionDomain.MEDIA, "stop", "media.stop", "Stop playback"
        ),
        "media.next": NormalizedAction(
            ActionDomain.MEDIA, "next", "media.next", "Play next video or track"
        ),
        "media.previous": NormalizedAction(
            ActionDomain.MEDIA,
            "previous",
            "media.previous",
            "Play previous video or track",
        ),
        "media.restart": NormalizedAction(
            ActionDomain.MEDIA,
            "restart",
            "media.restart",
            "Restart media from beginning",
        ),
        "media.seek": NormalizedAction(
            ActionDomain.MEDIA, "seek", "media.seek", "Seek forward or backward"
        ),
        "media.volume": NormalizedAction(
            ActionDomain.MEDIA, "volume", "media.volume", "Adjust media volume"
        ),
        # ── BROWSER ACTIONS ────────────────────────────────────────
        "browser.open": NormalizedAction(
            ActionDomain.BROWSER,
            "open",
            "browser.ensure_open",
            "Ensure browser is open",
        ),
        "browser.navigate": NormalizedAction(
            ActionDomain.BROWSER,
            "navigate",
            "browser.navigate",
            "Navigate to URL or site",
        ),
        "browser.search": NormalizedAction(
            ActionDomain.BROWSER, "search", "browser.search", "Search web or site"
        ),
        "browser.click": NormalizedAction(
            ActionDomain.BROWSER, "click", "browser.click", "Click element or link"
        ),
        "browser.type": NormalizedAction(
            ActionDomain.BROWSER, "type", "browser.type", "Type text into field"
        ),
        "browser.scroll": NormalizedAction(
            ActionDomain.BROWSER, "scroll", "browser.scroll", "Scroll page content"
        ),
        "browser.comments": NormalizedAction(
            ActionDomain.BROWSER,
            "comments",
            "browser.comments",
            "Inspect and read comments",
        ),
        "browser.reviews": NormalizedAction(
            ActionDomain.BROWSER,
            "reviews",
            "browser.reviews",
            "Inspect customer reviews",
        ),
        # ── SHOPPING ACTIONS ───────────────────────────────────────
        "shopping.search": NormalizedAction(
            ActionDomain.SHOPPING, "search", "shopping.search", "Search products"
        ),
        "shopping.filter": NormalizedAction(
            ActionDomain.SHOPPING,
            "filter",
            "shopping.filter",
            "Filter products by constraints",
        ),
        "shopping.sort": NormalizedAction(
            ActionDomain.SHOPPING, "sort", "shopping.sort", "Sort products"
        ),
        "shopping.compare": NormalizedAction(
            ActionDomain.SHOPPING,
            "compare",
            "shopping.compare",
            "Compare products side-by-side",
        ),
        "shopping.reviews": NormalizedAction(
            ActionDomain.SHOPPING,
            "reviews",
            "shopping.reviews",
            "Check product customer reviews",
        ),
        "shopping.cart_add": NormalizedAction(
            ActionDomain.SHOPPING,
            "cart_add",
            "shopping.cart.add",
            "Add product to cart",
        ),
        "shopping.cart_view": NormalizedAction(
            ActionDomain.SHOPPING,
            "cart_view",
            "shopping.cart.view",
            "View shopping cart",
        ),
        "shopping.cart_remove": NormalizedAction(
            ActionDomain.SHOPPING,
            "cart_remove",
            "shopping.cart.remove",
            "Remove item from cart",
        ),
        "shopping.checkout": NormalizedAction(
            ActionDomain.SHOPPING,
            "checkout",
            "shopping.checkout",
            "Proceed to checkout",
        ),
        # ── RESEARCH ACTIONS ───────────────────────────────────────
        "research.search": NormalizedAction(
            ActionDomain.RESEARCH, "search", "research.search", "Perform web search"
        ),
        "research.summarize": NormalizedAction(
            ActionDomain.RESEARCH,
            "summarize",
            "research.summarize",
            "Summarize text or page",
        ),
        "research.compare": NormalizedAction(
            ActionDomain.RESEARCH,
            "compare",
            "research.compare",
            "Compare research sources",
        ),
        "research.report": NormalizedAction(
            ActionDomain.RESEARCH,
            "report",
            "research.report",
            "Generate research report",
        ),
    }

    @classmethod
    def get_action(cls, capability_id: str) -> NormalizedAction | None:
        return cls.ACTIONS.get(capability_id)
