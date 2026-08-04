"""
Citation Model Types

Defines types used in the Citation Builder system.
"""

from enum import Enum


class CitationStyle(Enum):
    """Citation formatting styles."""
    APA = "apa"
    MLA = "mla"
    Chicago = "chicago"
    IEEE = "ieee"
    Numerical = "numerical"
