import os
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from core import automation
from core.models import AutomationRun, Base, Post, PostStatus, Quote, get_engine, get_session


@pytest.fixture
def automation_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name

    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTO_STOIC_TIMEZONE", "UTC")
    for key in (
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
        "FACEBOOK_PAGE_ID",
        "FACEBOOK_PAGE_TOKEN",
        "INSTAGRAM_ACCOUNT_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    engine = get_engine(database_url)
    Base.metadata.create_all(engine)

    try:
        yield engine
    finally:
        os.unlink(db_path)


def test_run_daily_stoic_publish_posts_once(automation_db, monkeypatch):
    monkeypatch.setattr(
        automation.stoic_service,
        "get_stoic_entry_for_date",
        lambda now: {"title": "Control", "author": "Epictetus", "quote": "Q", "body": "B"},
    )
    monkeypatch.setattr(
        automation.stoic_service,
        "generate_stoic_trading_content",
        lambda entry: {"tweet": "Automatic Stoic post"},
    )
    monkeypatch.setattr(automation.brand_media, "render_stoic_card", lambda payload: b"stoic-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            session = get_session()
            post = session.query(Post).filter(Post.id == post_id).first()
            post.status = PostStatus.POSTED.value
            post.posted_time = datetime.now(timezone.utc)
            post.post_id = "abc123"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/abc123"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    result = automation.run_daily_stoic_publish(run_hour=datetime.now(timezone.utc).hour)

    assert result.status == "posted"
    assert result.post_id is not None

    session = get_session()
    run = session.query(AutomationRun).first()
    post = session.query(Post).filter(Post.id == result.post_id).first()
    assert run.status == "posted"
    assert post.status == "posted"
    session.close()


def test_run_daily_stoic_publish_skips_duplicate_run(automation_db, monkeypatch):
    monkeypatch.setattr(
        automation.stoic_service,
        "get_stoic_entry_for_date",
        lambda now: {"title": "Control", "author": "Epictetus", "quote": "Q", "body": "B"},
    )
    monkeypatch.setattr(
        automation.stoic_service,
        "generate_stoic_trading_content",
        lambda entry: {"tweet": "Automatic Stoic post"},
    )
    monkeypatch.setattr(automation.brand_media, "render_stoic_card", lambda payload: b"stoic-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            session = get_session()
            post = session.query(Post).filter(Post.id == post_id).first()
            post.status = PostStatus.POSTED.value
            post.posted_time = datetime.now(timezone.utc)
            post.post_id = "abc123"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/abc123"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    first = automation.run_daily_stoic_publish(run_hour=datetime.now(timezone.utc).hour)
    second = automation.run_daily_stoic_publish(run_hour=datetime.now(timezone.utc).hour)

    assert first.status == "posted"
    assert second.status == "skipped"


def test_should_run_for_hour_allows_late_scheduler_runs():
    now = datetime(2026, 4, 14, 10, 1, tzinfo=ZoneInfo("America/New_York"))

    assert automation.should_run_for_hour(9, now) is True
    assert automation.should_run_for_hour(10, now) is True
    assert automation.should_run_for_hour(19, now) is False


def test_run_daily_stoic_publish_force_bypasses_hour_gate(automation_db, monkeypatch):
    monkeypatch.setattr(
        automation.stoic_service,
        "get_stoic_entry_for_date",
        lambda now: {"title": "Control", "author": "Epictetus", "quote": "Q", "body": "B"},
    )
    monkeypatch.setattr(
        automation.stoic_service,
        "generate_stoic_trading_content",
        lambda entry: {"tweet": "Automatic Stoic post"},
    )
    monkeypatch.setattr(automation.brand_media, "render_stoic_card", lambda payload: b"stoic-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            session = get_session()
            post = session.query(Post).filter(Post.id == post_id).first()
            post.status = PostStatus.POSTED.value
            post.posted_time = datetime.now(timezone.utc)
            post.post_id = "forced123"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/forced123"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    result = automation.run_daily_stoic_publish(run_hour=23, force=True)

    assert result.status == "posted"
    assert result.post_id is not None


def test_run_daily_quote_publish_posts_next_approved_quote(automation_db, monkeypatch):
    session = get_session()
    quote = Quote(
        content="Consistency compounds faster than prediction.",
        source="The Sands of Time",
        topic="Discipline",
        quality_score=9.0,
        approved=True,
    )
    session.add(quote)
    session.commit()

    post = Post(
        quote_id=quote.id,
        platform="twitter",
        content='"Consistency compounds faster than prediction."\n\nTrack your edge.\n\n#ICT #SMC #NQ #ES #Trading',
        status=PostStatus.APPROVED.value,
    )
    session.add(post)
    session.commit()
    session.close()

    monkeypatch.setattr(automation.brand_media, "render_quote_card", lambda text: b"quote-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            assert kwargs.get("image_bytes") == b"quote-card"
            session = get_session()
            db_post = session.query(Post).filter(Post.id == post_id).first()
            db_post.status = PostStatus.POSTED.value
            db_post.posted_time = datetime.now(timezone.utc)
            db_post.post_id = "quote123"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/quote123"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    result = automation.run_daily_quote_publish(run_hour=datetime.now(timezone.utc).hour)

    assert result.status == "posted"
    assert result.post_id == 1

    session = get_session()
    run = session.query(AutomationRun).filter(AutomationRun.task_key == "daily_quote").first()
    saved_post = session.query(Post).filter(Post.id == 1).first()
    assert run.status == "posted"
    assert saved_post.status == "posted"
    session.close()


def test_run_daily_quote_publish_creates_post_from_approved_quote_when_queue_empty(automation_db, monkeypatch):
    session = get_session()
    quote = Quote(
        content="Wait for the clean draw, not the noisy candle.",
        source="The Sands of Time",
        topic="Patience",
        quality_score=9.2,
        approved=True,
    )
    session.add(quote)
    session.commit()
    session.close()

    monkeypatch.setattr(automation.brand_media, "render_quote_card", lambda text: b"quote-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            assert kwargs.get("image_bytes") == b"quote-card"
            session = get_session()
            db_post = session.query(Post).filter(Post.id == post_id).first()
            assert db_post.content.endswith("#ICT #SMC #NQ #ES #Trading")
            db_post.status = PostStatus.POSTED.value
            db_post.posted_time = datetime.now(timezone.utc)
            db_post.post_id = "quote789"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/quote789"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    result = automation.run_daily_quote_publish(run_hour=datetime.now(timezone.utc).hour)

    assert result.status == "posted"

    session = get_session()
    saved_post = session.query(Post).filter(Post.id == result.post_id).first()
    assert saved_post is not None
    assert saved_post.quote_id == quote.id
    assert saved_post.status == "posted"
    session.close()


def test_get_next_approved_quote_skips_recent_matching_content(automation_db, monkeypatch):
    monkeypatch.setenv("QUOTE_RECYCLE_DAYS", "180")

    session = get_session()
    repeated_quote = Quote(
        content="Wait for the clean draw, not the noisy candle.",
        source="The Sands of Time",
        topic="Patience",
        quality_score=9.7,
        approved=True,
    )
    fresh_quote = Quote(
        content="Preserve capital while the story is unclear.",
        source="The Sands of Time",
        topic="Risk Management",
        quality_score=8.6,
        approved=True,
    )
    session.add_all([repeated_quote, fresh_quote])
    session.commit()

    session.add(
        Post(
            quote_id=repeated_quote.id,
            platform="twitter",
            content='"Wait for the clean draw, not the noisy candle."\n\nTrack your edge.\n\n#ICT #SMC #NQ #ES #Trading',
            status=PostStatus.POSTED.value,
            posted_time=datetime.now(timezone.utc),
        )
    )
    session.commit()

    selected = automation.get_next_approved_quote(session)

    assert selected is not None
    assert selected.id == fresh_quote.id
    session.close()


def test_run_daily_quote_publish_skips_duplicate_run(automation_db, monkeypatch):
    session = get_session()
    quote = Quote(
        content="Discipline is a repeatable edge.",
        source="The Sands of Time",
        topic="Discipline",
        quality_score=8.7,
        approved=True,
    )
    session.add(quote)
    session.commit()
    session.add(
        Post(
            quote_id=quote.id,
            platform="twitter",
            content="Discipline is a repeatable edge.",
            status=PostStatus.APPROVED.value,
        )
    )
    session.commit()
    session.close()

    monkeypatch.setattr(automation.brand_media, "render_quote_card", lambda text: b"quote-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False, **kwargs):
            session = get_session()
            db_post = session.query(Post).filter(Post.id == post_id).first()
            db_post.status = PostStatus.POSTED.value
            db_post.posted_time = datetime.now(timezone.utc)
            db_post.post_id = "quote456"
            session.commit()
            session.close()
            return {"status": "posted", "url": "https://x.com/test/status/quote456"}

    monkeypatch.setattr(automation, "TwitterClient", FakeTwitterClient)

    first = automation.run_daily_quote_publish(run_hour=datetime.now(timezone.utc).hour)
    second = automation.run_daily_quote_publish(run_hour=datetime.now(timezone.utc).hour)

    assert first.status == "posted"
    assert second.status == "skipped"
