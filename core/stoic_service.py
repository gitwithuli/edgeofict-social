import json
import os
import re
from datetime import datetime
from typing import Optional

import requests

STOIC_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "daily_stoic.json")
_WHITESPACE_RE = re.compile(r"\s+")

STOIC_FIELD_LIMITS = {
    "point1_title": {"max_words": 4, "max_chars": 42},
    "point1_meaning": {"max_words": 10, "max_chars": 72},
    "point1_trading": {"max_words": 12, "max_chars": 96},
    "point2_title": {"max_words": 4, "max_chars": 42},
    "point2_meaning": {"max_words": 10, "max_chars": 72},
    "point2_trading": {"max_words": 12, "max_chars": 96},
    "point3_title": {"max_words": 4, "max_chars": 42},
    "point3_meaning": {"max_words": 10, "max_chars": 72},
    "point3_trading": {"max_words": 12, "max_chars": 96},
    "closing_wisdom": {"max_words": 20, "max_chars": 140},
    "key_takeaway": {"max_words": 10, "max_chars": 72},
}


def load_stoic_entries() -> list[dict]:
    with open(STOIC_DATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_stoic_entry_for_date(target_date: Optional[datetime] = None) -> Optional[dict]:
    now = target_date or datetime.now()
    month = now.strftime("%B")
    day = now.day

    for entry in load_stoic_entries():
        if entry.get("month") == month and entry.get("day") == day:
            return entry

    return None


def get_stoic_entry_for_today() -> Optional[dict]:
    return get_stoic_entry_for_date()


def clean_stoic_text(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "")).strip()


def truncate_stoic_text(value: str, *, max_words: int | None = None, max_chars: int | None = None) -> str:
    cleaned = clean_stoic_text(value)
    if not cleaned:
        return ""

    if max_words is not None:
        words = cleaned.split()
        if len(words) > max_words:
            cleaned = " ".join(words[:max_words]).rstrip(" ,;:-")

    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 3].rstrip(" ,;:-")
        cleaned = f"{cleaned}..."

    return cleaned


def normalize_stoic_content(payload: dict) -> dict:
    normalized = {
        key: clean_stoic_text(value) if isinstance(value, str) else value
        for key, value in payload.items()
    }

    for key, limits in STOIC_FIELD_LIMITS.items():
        normalized[key] = truncate_stoic_text(
            normalized.get(key, ""),
            max_words=limits.get("max_words"),
            max_chars=limits.get("max_chars"),
        )

    tweet = clean_stoic_text(normalized.get("tweet", ""))
    if len(tweet) > 250:
        tweet = f"{tweet[:247].rstrip()}..."
    normalized["tweet"] = tweet
    return normalized


def generate_stoic_trading_content(entry: dict, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6") -> dict:
    resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not resolved_api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    prompt = f"""You are creating a "Stoic x Trader" card that applies ancient Stoic philosophy to trading psychology.

Today's entry from The Daily Stoic:
- Title: {entry['title']}
- Philosopher: {entry['author']}
- Quote: "{entry['quote']}"
- Reflection: {entry['body'][:1000]}

Create content for a hosted control panel preview with these elements:

1. Three principles (each with title, stoic meaning, and trading application):
   - Title: 2-4 words, captures the essence
   - Meaning: Brief stoic interpretation (under 10 words)
   - Trading: Specific trading application (under 12 words)

2. Closing wisdom: A reflective sentence connecting stoicism to trading (under 20 words)

3. Key takeaway: A punchy, memorable line (under 10 words)

4. Tweet text: A tweet (under 250 chars) with the key insight + trading angle. Include hashtags: #ict #trader #tradingpsychology #stoic

Respond in JSON format only:
{{
  "point1_title": "...",
  "point1_meaning": "...",
  "point1_trading": "...",
  "point2_title": "...",
  "point2_meaning": "...",
  "point2_trading": "...",
  "point3_title": "...",
  "point3_meaning": "...",
  "point3_trading": "...",
  "closing_wisdom": "...",
  "key_takeaway": "...",
  "tweet": "..."
}}"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": resolved_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )

    if response.status_code != 200:
        raise ValueError(f"Anthropic API error: {response.status_code} - {response.text}")

    content = "".join(
        block.get("text", "")
        for block in response.json().get("content", [])
        if block.get("type") == "text"
    )

    try:
        return normalize_stoic_content(json.loads(content))
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            return normalize_stoic_content(json.loads(content[start:end]))
        raise ValueError("Could not parse JSON from Anthropic response")
