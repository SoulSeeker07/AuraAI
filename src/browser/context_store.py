"""
Browser & Task Context Store
Location: src/browser/context_store.py

Provides persistent task & application state across conversational turns.
Tracks active MediaContext and ShoppingContext so follow-up commands
("next", "previous", "only 16GB", "no HP", "add it to cart", "check the comments")
retain referents and state across turns.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MediaItem:
    title: str = ""
    url: str = ""
    index: int = 1
    duration_seconds: int = 0
    platform: str = "youtube"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "index": self.index,
            "duration_seconds": self.duration_seconds,
            "platform": self.platform,
        }


@dataclass
class MediaContext:
    platform: str = "youtube"
    current_item: MediaItem | None = None
    playlist: list[MediaItem] = field(default_factory=list)
    state: str = "stopped"  # "playing", "paused", "stopped"
    volume_percent: int = 100
    current_time_seconds: int = 0
    last_comments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "current_item": self.current_item.to_dict() if self.current_item else None,
            "playlist": [item.to_dict() for item in self.playlist],
            "state": self.state,
            "volume_percent": self.volume_percent,
            "current_time_seconds": self.current_time_seconds,
            "last_comments": self.last_comments,
        }


@dataclass
class ShoppingConstraints:
    category: str = "laptop"
    platform: str = "amazon"
    price_max: float | None = None
    price_min: float | None = None
    currency: str = "INR"
    ram_gb_min: int | None = None
    storage_gb_min: int | None = None
    storage_type: str | None = None
    processor: str | None = None
    display: str | None = None
    gpu: str | None = None
    brand_include: list[str] = field(default_factory=list)
    brand_exclude: list[str] = field(default_factory=list)
    min_rating: float | None = None
    sort_by: str | None = None  # "price_asc", "price_desc", "rating"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "platform": self.platform,
            "price_max": self.price_max,
            "price_min": self.price_min,
            "currency": self.currency,
            "ram_gb_min": self.ram_gb_min,
            "storage_gb_min": self.storage_gb_min,
            "storage_type": self.storage_type,
            "processor": self.processor,
            "display": self.display,
            "gpu": self.gpu,
            "brand_include": self.brand_include,
            "brand_exclude": self.brand_exclude,
            "min_rating": self.min_rating,
            "sort_by": self.sort_by,
        }


@dataclass
class ShoppingContext:
    constraints: ShoppingConstraints = field(default_factory=ShoppingConstraints)
    products: list[dict[str, Any]] = field(default_factory=list)
    selected_product: dict[str, Any] | None = None
    cart_items: list[dict[str, Any]] = field(default_factory=list)
    last_reviews: list[str] = field(default_factory=list)
    checkout_status: str = "idle"

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraints": self.constraints.to_dict(),
            "products_count": len(self.products),
            "products": self.products,
            "selected_product": self.selected_product,
            "cart_items": self.cart_items,
            "last_reviews": self.last_reviews,
            "checkout_status": self.checkout_status,
        }


class ContextStore:
    """
    Singleton persistent store holding active MediaContext and ShoppingContext.
    """

    _instance: ContextStore | None = None

    def __init__(self) -> None:
        self.media = MediaContext()
        self.shopping = ShoppingContext()

    @classmethod
    def get_instance(cls) -> ContextStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── SHOPPING CONSTRAINTS PARSER ──────────────────────────────────────────

    def update_shopping_constraints(self, goal_text: str) -> ShoppingConstraints:
        """
        Parses goal_text and updates active ShoppingContext constraints without wiping existing ones.
        """
        g_lower = goal_text.lower().replace(",", "")
        c = self.shopping.constraints

        # Detect category if mentioned
        for cat in ["laptop", "phone", "mobile", "headphones", "monitor", "shoes", "tv", "watch"]:
            if cat in g_lower:
                if c.category != cat and any(w in g_lower for w in ["find", "search", "looking for", "new"]):
                    # Reset constraints only when starting a brand new product search
                    c = ShoppingConstraints(category=cat)
                    self.shopping.constraints = c
                else:
                    c.category = cat
                break

        # 1. Price Max: "under 60k", "below 70000", "less than ₹60,000", "within 60k"
        m_price = re.search(r"(?:under|below|less than|within|max|<=|≤)?\s*₹?\s*(\d+)\s*(k|000|thousand)?", g_lower)
        if m_price and any(w in g_lower for w in ["under", "below", "less than", "within", "k", "max", "₹"]):
            val = float(m_price.group(1))
            multiplier = m_price.group(2)
            if multiplier and ("k" in multiplier.lower() or val < 1000):
                val *= 1000
            if val > 100:
                c.price_max = val

        # 2. RAM: "16GB", "16 gigs", "at least 16GB RAM"
        m_ram = re.search(r"(\d+)\s*(?:gb|gigs|gig)\b", g_lower)
        if not m_ram:
            m_ram = re.search(r"(\d+)\s*ram\b", g_lower)
        if m_ram:
            c.ram_gb_min = int(m_ram.group(1))

        # 3. Storage: "1TB SSD", "512GB"
        m_storage = re.search(r"(\d+)\s*(tb|gb)\s*(ssd|hdd)?", g_lower)
        if m_storage and "ram" not in m_storage.group(0):
            num = int(m_storage.group(1))
            unit = m_storage.group(2).lower()
            c.storage_gb_min = num * 1000 if unit == "tb" else num
            if m_storage.group(3):
                c.storage_type = m_storage.group(3).upper()

        # 4. Processor: "i7", "i5", "ryzen 7"
        for proc in ["i7", "i5", "i9", "i3", "ryzen 7", "ryzen 5", "m1", "m2", "m3"]:
            if proc in g_lower:
                c.processor = proc.upper()
                break

        # 5. Display: "oled", "4k", "144hz"
        for disp in ["oled", "4k", "144hz", "ips", "120hz"]:
            if disp in g_lower:
                c.display = disp.upper()
                break

        # 6. Brand Exclusion: "no HP", "don't show HP", "remove HP", "except Dell"
        m_no_brand = re.search(r"(?:no|don't show|remove|exclude|except)\s+([a-zA-Z0-9]+)", g_lower)
        if m_no_brand:
            b_ex = m_no_brand.group(1).upper()
            if b_ex not in [b.upper() for b in c.brand_exclude]:
                c.brand_exclude.append(b_ex)

        # 7. Brand Inclusion: "only Lenovo", "show Apple and Sony", "Lenovo and ASUS"
        if "only" in g_lower or "just" in g_lower:
            m_only_brand = re.search(r"(?:only|just)\s+([a-zA-Z0-9\s,&]+)", g_lower)
            if m_only_brand:
                brands = re.split(r"\sand\b|\s*,\s*", m_only_brand.group(1))
                for b in brands:
                    b_clean = b.strip().upper()
                    if b_clean and b_clean not in ["RAM", "SSD", "OLED", "LAPTOP", "UNDER", "60K", "70K", "80K"]:
                        if b_clean not in [x.upper() for x in c.brand_include]:
                            c.brand_include.append(b_clean)

        # 8. Rating: "rating above 4", "4 stars and above", "good reviews", "highly rated"
        if any(w in g_lower for w in ["rating", "stars", "good reviews", "highly rated"]):
            m_rat = re.search(r"(\d+(?:\.\d+)?)\s*(?:stars|rating)?", g_lower)
            if m_rat:
                c.min_rating = float(m_rat.group(1))
            else:
                c.min_rating = 4.0

        # 9. Sort: "sort by rating", "cheapest one", "expensive"
        if "cheapest" in g_lower or "lowest price" in g_lower:
            c.sort_by = "price_asc"
        elif "expensive" in g_lower or "highest price" in g_lower:
            c.sort_by = "price_desc"
        elif "rating" in g_lower or "best reviews" in g_lower:
            c.sort_by = "rating"

        return c

    # ── MEDIA ACTIONS PARSER ────────────────────────────────────────────────

    def update_media_state(self, action_name: str, goal_text: str = "") -> MediaContext:
        """
        Updates MediaContext state based on action (next, previous, pause, resume, seek, volume).
        """
        m = self.media
        g_lower = goal_text.lower()

        if action_name == "media.next":
            m.state = "playing"
            if m.playlist and m.current_item:
                curr_idx = m.current_item.index
                if curr_idx < len(m.playlist):
                    m.current_item = m.playlist[curr_idx]  # next index is curr_idx (1-based index)
                else:
                    m.current_item = m.playlist[0]
            elif not m.current_item:
                m.current_item = MediaItem(title="Next Video", index=2, platform=m.platform)
        elif action_name == "media.previous":
            m.state = "playing"
            if m.playlist and m.current_item:
                curr_idx = m.current_item.index
                if curr_idx > 1:
                    m.current_item = m.playlist[curr_idx - 2]
            elif not m.current_item:
                m.current_item = MediaItem(title="Previous Video", index=1, platform=m.platform)
        elif action_name == "media.pause":
            m.state = "paused"
        elif action_name == "media.resume":
            m.state = "playing"
        elif action_name == "media.seek":
            m_sec = re.search(r"(\d+)\s*(seconds|secs|second|sec|s|minutes|mins|min|m)", g_lower)
            if m_sec:
                num = int(m_sec.group(1))
                unit = m_sec.group(2).lower()
                offset = num * 60 if "min" in unit or "m" in unit else num
                if any(w in g_lower for w in ["back", "backward", "rewind"]):
                    m.current_time_seconds = max(0, m.current_time_seconds - offset)
                else:
                    m.current_time_seconds += offset
        elif action_name == "media.volume":
            m_vol = re.search(r"(\d+)\s*%", g_lower)
            if m_vol:
                m.volume_percent = int(m_vol.group(1))
            elif "mute" in g_lower:
                m.volume_percent = 0
            elif "unmute" in g_lower:
                m.volume_percent = 50

        return m

    # ── RELATIVE REFERENCE RESOLVER ──────────────────────────────────────────

    def resolve_relative_reference(self, goal_text: str) -> dict[str, Any]:
        """
        Resolves phrases like 'the first one', 'the second one', 'it', 'this', 'the cheapest one'.
        Returns resolved entity metadata or dict.
        """
        g_lower = goal_text.lower()
        res: dict[str, Any] = {}

        # 1. Shopping product references
        if self.shopping.products:
            prods = self.shopping.products
            if "first" in g_lower or "1st" in g_lower:
                res["product"] = prods[0]
                self.shopping.selected_product = prods[0]
            elif "second" in g_lower or "2nd" in g_lower and len(prods) > 1:
                res["product"] = prods[1]
                self.shopping.selected_product = prods[1]
            elif "third" in g_lower or "3rd" in g_lower and len(prods) > 2:
                res["product"] = prods[2]
                self.shopping.selected_product = prods[2]
            elif "cheapest" in g_lower:
                sorted_p = sorted(prods, key=lambda p: float(re.sub(r"[^\d.]", "", str(p.get("price", "999999"))) or 999999))
                res["product"] = sorted_p[0]
                self.shopping.selected_product = sorted_p[0]
            elif any(w in g_lower for w in ["add it", "put it", "buy it", "checkout it", "this one", "that one"]):
                res["product"] = self.shopping.selected_product or prods[0]

        # 2. Media playlist references
        if self.media.playlist:
            pl = self.media.playlist
            if "first" in g_lower:
                res["media"] = pl[0]
                self.media.current_item = pl[0]
            elif "second" in g_lower and len(pl) > 1:
                res["media"] = pl[1]
                self.media.current_item = pl[1]
            elif "third" in g_lower and len(pl) > 2:
                res["media"] = pl[2]
                self.media.current_item = pl[2]
            elif any(w in g_lower for w in ["play it", "resume it", "pause it", "summarize them", "check comments"]):
                res["media"] = self.media.current_item or pl[0]

        return res
