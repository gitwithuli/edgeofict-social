import os
import tempfile
from datetime import datetime, timezone

import pytest

from core import automation
from core.models import AutomationRun, Base, Post, PostStatus, get_engine, get_session


@pytest.fixture
def automation_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name

    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTO_STOIC_TIMEZONE", "UTC")

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

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False):
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

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def post_by_id(self, post_id, confirm=False):
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
