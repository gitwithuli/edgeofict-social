from __future__ import annotations

import re
from typing import Iterable

_HASHTAG_RE = re.compile(r"#\w+")
_TAGLINE_RE = re.compile(r"\btrack your edge\b\.?", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }
)


def normalize_quote_for_matching(content: str | None) -> str:
    text = (content or "").translate(_QUOTE_TRANSLATION).lower()
    text = _HASHTAG_RE.sub(" ", text)
    text = _TAGLINE_RE.sub(" ", text)
    text = text.strip().strip('"').strip("'").strip()
    text = _NON_ALNUM_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def build_quote_signature_set(contents: Iterable[str | None]) -> set[str]:
    return {
        signature
        for content in contents
        if (signature := normalize_quote_for_matching(content))
    }
