"""
Canonical Preference Keys & Validation
=======================================
Location: src/memory/canonical_keys.py

Enforces canonical key names for user preferences and profile facts to prevent
write-time key drift (e.g. editor vs favorite_editor vs favorite_ide vs preferred_ide).
"""

from __future__ import annotations

import re

# Mapping of known legacy or alias keys to their canonical form
CANONICAL_PREFERENCE_KEYS: dict[str, str] = {
    # Editor / IDE
    "editor": "favorite_editor",
    "favorite_editor": "favorite_editor",
    "favorite_ide": "favorite_editor",
    "preferred_ide": "favorite_editor",
    "ide": "favorite_editor",
    "primary_editor": "favorite_editor",
    "primary_ide": "favorite_editor",
    # Programming Language
    "language": "favorite_programming_language",
    "programming_language": "favorite_programming_language",
    "preferred_language": "favorite_programming_language",
    "favorite_language": "favorite_programming_language",
    "favorite_programming_language": "favorite_programming_language",
    "primary_language": "favorite_programming_language",
    # Color
    "color": "favorite_color",
    "preferred_color": "favorite_color",
    "favorite_color": "favorite_color",
    # Food
    "food": "favorite_food",
    "preferred_food": "favorite_food",
    "favorite_food": "favorite_food",
    # Theme
    "preferred_theme": "theme",
    "theme": "theme",
}


def normalize_preference_key(key: str) -> str:
    """
    Normalizes a preference key to its canonical form.
    E.g.: 'favorite_ide' -> 'favorite_editor', 'language' -> 'favorite_programming_language'
    """
    if not key:
        return ""
    clean = key.strip().lower().replace("-", "_").replace(" ", "_")
    return CANONICAL_PREFERENCE_KEYS.get(clean, clean)


def is_tautological_fact(key: str, value: str) -> bool:
    """
    Detects tautological junk facts where the value is simply an echo of the key.
    E.g. key='programming_language', value='programming language'
         key='editor', value='editor'
         key='editor', value='editor?'
    """
    k_clean = re.sub(r"[^a-zA-Z0-9]", "", str(key).lower())
    v_clean = re.sub(r"[^a-zA-Z0-9]", "", str(value).lower())
    return bool(k_clean and k_clean == v_clean)
