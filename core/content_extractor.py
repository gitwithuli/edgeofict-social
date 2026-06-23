import os
import json
import requests
from typing import Optional
from datetime import datetime, timezone

from .document_parser import parse_document, get_document_name
from .models import Quote, get_session, init_db
from .quote_dedupe import normalize_quote_for_matching

EXTRACTION_PROMPT = """You are an expert at extracting impactful trading quotes from ICT (Inner Circle Trader) methodology content.

Your task is to extract memorable, educational quotes that:
1. Contain specific trading wisdom (not generic motivation)
2. Are self-contained and understandable without context
3. Are 280 characters or less (Twitter-compatible)
4. Relate to: edge tracking, discipline, risk management, market structure, patience, or trading psychology

For each quote, provide:
- The quote text (cleaned up and polished for social media)
- A topic category from: ["Discipline", "Risk Management", "Edge Tracking", "Market Structure", "Trading Psychology", "Patience", "Model Following", "Self-Improvement"]
- A quality score from 1-10 based on:
  - Clarity (is it clear and well-expressed?)
  - Actionability (can a trader apply this?)
  - Uniqueness (is it a fresh perspective?)
  - Relevance to edge tracking (does it relate to systematically tracking trading edges?)

CRITICAL GRAMMAR RULES:
- Fix ALL mid-sentence capitalization. ICT often capitalizes words for emphasis (e.g., "Scar Tissue", "Magnified", "War") - convert these to lowercase unless they start a sentence.
- Use proper punctuation: em dashes (—) instead of ellipsis (...) where appropriate
- Remove filler words and spoken artifacts ("you know", "like", "um")
- Ensure each quote is grammatically correct and reads professionally
- The quote should look like polished written content, not a transcript

IMPORTANT:
- Extract 15-25 high-quality quotes per document
- Avoid quotes that are too conversational or need context
- Prioritize quotes that demonstrate the value of tracking your trading edge systematically

Respond with a JSON array of objects with this structure:
{
  "quotes": [
    {
      "content": "The quote text here",
      "topic": "Category name",
      "quality_score": 8.5
    }
  ]
}

Only respond with valid JSON, no other text."""


class ContentExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"

    def extract_quotes_from_text(self, text: str, source_name: str) -> list[dict]:
        text_preview = text[:12000] if len(text) > 12000 else text

        response = requests.post(
            self.api_url,
            headers={
                "x-api-key": f"{self.api_key}",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "system": EXTRACTION_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Extract trading quotes from this ICT content. Source: {source_name}\n\n{text_preview}",
                    }
                ],
                "max_tokens": 4096,
                "temperature": 0.3,
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")

        payload = response.json()
        response_text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        ).strip()

        try:
            data = json.loads(response_text)
            quotes = data.get("quotes", [])
        except json.JSONDecodeError:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response_text[start:end])
                quotes = data.get("quotes", [])
            else:
                quotes = []

        for quote in quotes:
            quote["source"] = source_name

        return quotes

    def extract_from_document(self, file_path: str, source_name: Optional[str] = None) -> list[dict]:
        text = parse_document(file_path)
        source_name = source_name or get_document_name(file_path)
        return self.extract_quotes_from_text(text, source_name)

    def save_quotes_to_db(self, quotes: list[dict], session=None, return_quote_ids: bool = False):
        if session is None:
            init_db()
            session = get_session()

        existing_signatures = {
            signature
            for (content,) in session.query(Quote.content).all()
            if (signature := normalize_quote_for_matching(content))
        }
        saved_count = 0
        saved_quote_ids: list[int] = []
        for quote_data in quotes:
            content = " ".join((quote_data.get("content") or "").split()).strip()
            signature = normalize_quote_for_matching(content)
            if not signature or signature in existing_signatures:
                continue

            quote = Quote(
                content=content,
                source=quote_data.get("source", "Unknown"),
                topic=quote_data.get("topic", "General"),
                quality_score=quote_data.get("quality_score", 5.0),
                approved=False,
                created_at=datetime.now(timezone.utc)
            )
            session.add(quote)
            session.flush()
            saved_count += 1
            saved_quote_ids.append(quote.id)
            existing_signatures.add(signature)

        session.commit()
        if return_quote_ids:
            return saved_count, saved_quote_ids
        return saved_count

    def extract_and_save(self, file_path: str, source_name: Optional[str] = None, return_quote_ids: bool = False):
        quotes = self.extract_from_document(file_path, source_name=source_name)
        if return_quote_ids:
            saved, saved_quote_ids = self.save_quotes_to_db(quotes, return_quote_ids=True)
            return len(quotes), saved, saved_quote_ids
        saved = self.save_quotes_to_db(quotes)
        return len(quotes), saved
