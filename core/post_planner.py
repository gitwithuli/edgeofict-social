from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
import os
import random
import requests

from .models import Quote, Post, PostStatus, get_session, init_db

UTC = timezone.utc

POST_FORMAT_PROMPT = """You are a social media content creator for EdgeOfICT, a trading edge tracking software.

Your task is to format trading quotes into engaging social media posts for X/Twitter.

Rules:
1. Keep the post under 280 characters total (CRITICAL)
2. The quote should be the focus
3. Add a brief tie-in to EdgeOfICT's value (tracking trading edges)
4. Include 2-3 relevant hashtags
5. Keep it professional but approachable
6. No emojis in the quote itself, but 1-2 subtle emojis OK elsewhere

Format template:
"[Quote]"

[Brief tie-in to edge tracking - 1 short sentence]

#EdgeOfICT #ICTTrading [1 more relevant tag]

Respond with just the formatted post text, nothing else."""


class PostPlanner:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        init_db()
        self.session = get_session()

    def format_quote_for_twitter(self, quote: Quote, use_ai: bool = True) -> str:
        if use_ai and self.api_key:
            try:
                return self._format_quote_with_api(quote)
            except Exception:
                pass

        hashtags = self._get_hashtags_for_topic(quote.topic)
        template = f'"{quote.content}"\n\nTrack your edge.\n\n{hashtags}'

        if len(template) > 280:
            max_quote_len = 280 - len(f'"\n\nTrack your edge.\n\n{hashtags}') - 3
            truncated = quote.content[:max_quote_len] + "..."
            template = f'"{truncated}"\n\nTrack your edge.\n\n{hashtags}'

        return template

    def _format_quote_with_api(self, quote: Quote) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 500,
                "system": POST_FORMAT_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": f'Format this ICT trading quote for X/Twitter:\n\n"{quote.content}"\n\nTopic: {quote.topic}',
                    }
                ],
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise ValueError(f"Anthropic API error: {response.status_code} - {response.text}")

        payload = response.json()
        content_blocks = payload.get("content", [])
        text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text").strip()

        if not text:
            raise ValueError("Anthropic returned an empty response")

        return text

    def _get_hashtags_for_topic(self, topic: str) -> str:
        topic_tags = {
            "Discipline": "#EdgeOfICT #ICTTrading #TradingDiscipline",
            "Risk Management": "#EdgeOfICT #ICTTrading #RiskManagement",
            "Edge Tracking": "#EdgeOfICT #EdgeTracking #ICTTrading",
            "Market Structure": "#EdgeOfICT #ICTTrading #MarketStructure",
            "Trading Psychology": "#EdgeOfICT #ICTTrading #TradingPsychology",
            "Patience": "#EdgeOfICT #ICTTrading #TradingPatience",
            "Model Following": "#EdgeOfICT #ICTTrading #TradingModel",
            "Self-Improvement": "#EdgeOfICT #ICTTrading #TradingMindset",
        }
        return topic_tags.get(topic, "#EdgeOfICT #ICTTrading #SmartMoney")

    def get_next_quote(self, min_score: float = 7.0, exclude_source: Optional[str] = None) -> Optional[Quote]:
        query = self.session.query(Quote).filter(
            Quote.approved == True,
            Quote.quality_score >= min_score
        )

        if exclude_source:
            query = query.filter(Quote.source != exclude_source)

        return query.order_by(
            Quote.used_count.asc(),
            Quote.quality_score.desc()
        ).first()

    def get_shuffled_quotes(self, count: int, min_score: float = 7.0) -> list[Quote]:
        """Get quotes shuffled across different sources to avoid consecutive posts from same document."""
        all_quotes = self.session.query(Quote).filter(
            Quote.approved == True,
            Quote.quality_score >= min_score
        ).order_by(
            Quote.used_count.asc(),
            Quote.quality_score.desc()
        ).all()

        if not all_quotes:
            return []

        by_source = defaultdict(list)
        for q in all_quotes:
            by_source[q.source].append(q)

        sources = list(by_source.keys())
        random.shuffle(sources)

        result = []
        source_idx = 0

        while len(result) < count and any(by_source.values()):
            source = sources[source_idx % len(sources)]

            if by_source[source]:
                result.append(by_source[source].pop(0))

            if not by_source[source]:
                sources = [s for s in sources if by_source[s]]
                if not sources:
                    break

            source_idx += 1

        return result[:count]

    def create_post(
        self,
        quote: Quote,
        platform: str = "twitter",
        scheduled_time: Optional[datetime] = None,
        use_ai: bool = True
    ) -> Post:
        if platform == "twitter":
            content = self.format_quote_for_twitter(quote, use_ai=use_ai)
        else:
            content = self.format_quote_for_twitter(quote, use_ai=use_ai)

        post = Post(
            quote_id=quote.id,
            platform=platform,
            content=content,
            scheduled_time=scheduled_time,
            status=PostStatus.PENDING.value,
            created_at=datetime.now(UTC)
        )

        self.session.add(post)
        self.session.commit()

        return post

    def generate_posts(
        self,
        days: int = 7,
        posts_per_day: int = 1,
        platform: str = "twitter",
        start_time: Optional[datetime] = None,
        use_ai: bool = True,
        shuffle_sources: bool = True
    ) -> list[Post]:
        if start_time is None:
            start_time = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
            if start_time < datetime.now(UTC):
                start_time += timedelta(days=1)

        total_posts_needed = days * posts_per_day

        if shuffle_sources:
            quotes = self.get_shuffled_quotes(total_posts_needed)
        else:
            quotes = []
            for _ in range(total_posts_needed):
                q = self.get_next_quote()
                if q:
                    quotes.append(q)
                else:
                    break

        posts = []
        current_time = start_time
        quote_idx = 0

        for day in range(days):
            for post_num in range(posts_per_day):
                if quote_idx >= len(quotes):
                    break

                quote = quotes[quote_idx]
                quote_idx += 1

                post = self.create_post(
                    quote=quote,
                    platform=platform,
                    scheduled_time=current_time,
                    use_ai=use_ai
                )

                quote.used_count += 1
                quote.last_used = datetime.now(UTC)
                self.session.commit()

                posts.append(post)

                if posts_per_day > 1 and post_num < posts_per_day - 1:
                    current_time += timedelta(hours=8)

            current_time = (current_time + timedelta(days=1)).replace(hour=9, minute=0)

        return posts

    def get_schedule(self, days: int = 7) -> list[Post]:
        end_date = datetime.now(UTC) + timedelta(days=days)
        return self.session.query(Post).filter(
            Post.scheduled_time <= end_date,
            Post.status.in_([PostStatus.PENDING.value, PostStatus.APPROVED.value])
        ).order_by(Post.scheduled_time.asc()).all()

    def reschedule_post(self, post_id: int, new_time: datetime) -> bool:
        post = self.session.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False

        post.scheduled_time = new_time
        self.session.commit()
        return True

    def cancel_post(self, post_id: int) -> bool:
        post = self.session.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False

        post.status = PostStatus.REJECTED.value
        self.session.commit()
        return True
