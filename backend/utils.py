"""Shared utility functions for string normalization and matching."""

import re
import unicodedata


def simplify_string(s: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, strip accents, remove punctuation."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
