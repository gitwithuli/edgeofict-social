import os
import tempfile
import io
import json
from datetime import datetime, timezone

import pytest

import app as app_module
from app import create_app
from core.models import Base, Post, Quote, get_session
from core import stoic_service


@pytest.fixture
def app_client():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name

    database_url = f"sqlite:///{db_path}"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": database_url,
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "secret",
            "DISABLE_AUTH": False,
            "SESSION_COOKIE_SECURE": False,
        }
    )

    Base.metadata.create_all(app.config["DB_ENGINE"])
    session = get_session(app.config["DB_ENGINE"])
    session.add(
        Quote(
            content="Follow your model and respect your risk.",
            source="test-doc",
            topic="Discipline",
            quality_score=9.1,
            approved=False,
        )
    )
    session.commit()
    session.close()

    try:
        yield app.test_client(), app
    finally:
        os.unlink(db_path)


def test_healthz(app_client):
    client, _ = app_client
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_dashboard_requires_login(app_client):
    client, _ = app_client
    response = client.get("/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_and_quote_approval(app_client):
    client, app = app_client

    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Quote Library" in response.data
    assert b"/static/app.js?v=2026-07-09-source-filter" in response.data

    response = client.post(
        "/actions/quotes/1",
        data={"action": "approve"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Approved quote #1." in response.data

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    assert quote.approved is True
    session.close()


def test_dashboard_uses_source_label_override(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    quote.source = "tmprq7h9hor"
    session.commit()
    session.close()

    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"The Sands of Time" in response.data


def test_dashboard_shows_quote_extraction_form_after_login(app_client):
    client, _ = app_client

    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Import Source Document" in response.data
    assert b"Extract Quotes" in response.data
    assert b'name="document"' in response.data
    assert b"/actions/extract-quotes" in response.data


def test_dashboard_available_pool_excludes_used_quotes(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    fresh_quote = session.query(Quote).filter(Quote.id == 1).first()
    fresh_quote.approved = True
    used_quote = Quote(
        content="Already consumed quote.",
        source="archive-doc",
        topic="Execution",
        quality_score=8.9,
        approved=True,
        used_count=1,
        last_used=datetime.now(timezone.utc),
    )
    session.add(used_quote)
    session.commit()
    session.close()

    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"1 ready for auto-posting" in response.data
    assert b"Available Quote Pool" in response.data
    assert b"Used / Archived Quotes" in response.data
    assert b"Archived" in response.data


def test_bulk_approve_pending_quotes(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    session.add(
        Quote(
            content="The patient setup pays the cleanest dividend.",
            source="second-doc",
            topic="Patience",
            quality_score=8.4,
            approved=False,
        )
    )
    session.commit()
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/quotes/approve-all",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Approved 2 quotes." in response.data

    session = get_session(app.config["DB_ENGINE"])
    approved_quotes = session.query(Quote).filter(Quote.approved.is_(True)).count()
    pending_quotes = session.query(Quote).filter(Quote.approved.is_(False)).count()
    assert approved_quotes == 2
    assert pending_quotes == 0
    session.close()


def test_extract_quotes_uses_original_upload_name(app_client, monkeypatch):
    client, _ = app_client
    captured = {}

    class FakeExtractor:
        def extract_and_save(self, file_path, source_name=None, return_quote_ids=False):
            captured["source_name"] = source_name
            captured["file_path"] = file_path
            return 9, 7, []

    monkeypatch.setattr(app_module, "ContentExtractor", FakeExtractor)

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/extract-quotes",
        data={"document": (io.BytesIO(b"hello"), "The Sands of Time.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured["source_name"] == "The Sands of Time"
    assert b"Imported 7 new quotes from The Sands of Time.txt" in response.data
    assert b"approved and ready in the pool" in response.data


def test_extract_quotes_auto_approves_without_consuming_quotes(app_client, monkeypatch):
    client, app = app_client

    class FakeExtractor:
        def extract_and_save(self, file_path, source_name=None, return_quote_ids=False):
            session = get_session(app.config["DB_ENGINE"])
            quote = Quote(
                content="Consistency is the edge.",
                source=source_name,
                topic="Discipline",
                quality_score=8.8,
                approved=False,
            )
            session.add(quote)
            session.commit()
            quote_id = quote.id
            session.close()
            return 1, 1, [quote_id]

    monkeypatch.setattr(app_module, "ContentExtractor", FakeExtractor)

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/extract-quotes",
        data={"document": (io.BytesIO(b"hello"), "Evening Quotes.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"approved and ready in the pool" in response.data

    session = get_session(app.config["DB_ENGINE"])
    posts = session.query(Post).filter(Post.status == "approved").all()
    assert len(posts) == 0
    quote = session.query(Quote).filter(Quote.content == "Consistency is the edge.").first()
    assert quote is not None
    assert quote.approved is True
    assert quote.archived is False
    assert quote.used_count == 0
    assert quote.last_used is None
    session.close()


def test_dashboard_shows_source_document_usage_counts(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    fresh_quote = session.query(Quote).filter(Quote.id == 1).first()
    fresh_quote.approved = True
    fresh_quote.source = "June 21 TGIF setup"
    session.add(
        Quote(
            content="Used quote from same doc.",
            source="June 21 TGIF setup",
            topic="Market Structure",
            quality_score=8.1,
            approved=True,
            used_count=1,
            last_used=datetime.now(timezone.utc),
        )
    )
    session.add(
        Quote(
            content="Archived quote from same doc.",
            source="June 21 TGIF setup",
            topic="Patience",
            quality_score=8.0,
            approved=True,
            archived=True,
        )
    )
    session.commit()
    session.close()

    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"June 21 TGIF setup" in response.data
    assert b"View Quotes" in response.data
    assert b'data-source-query="June 21 TGIF setup"' in response.data
    assert b'id="archive-quote-list"' in response.data
    assert b'used archived out of pool' in response.data
    assert b"Left" in response.data
    assert b"Used" in response.data
    assert b"Archived" in response.data


def test_quote_archive_restore_and_delete_actions(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    quote.approved = True
    session.commit()
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    archive_response = client.post(
        "/actions/quotes/1",
        data={"action": "archive"},
        follow_redirects=True,
    )
    assert archive_response.status_code == 200
    assert b"Archived quote #1." in archive_response.data

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    assert quote.archived is True
    session.close()

    restore_response = client.post(
        "/actions/quotes/1",
        data={"action": "restore"},
        follow_redirects=True,
    )
    assert restore_response.status_code == 200
    assert b"Restored quote #1." in restore_response.data

    delete_response = client.post(
        "/actions/quotes/1",
        data={"action": "delete"},
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert b"Deleted quote #1." in delete_response.data

    session = get_session(app.config["DB_ENGINE"])
    assert session.query(Quote).filter(Quote.id == 1).first() is None
    session.close()


def test_return_pool_resets_unposted_queued_quote(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    quote.approved = True
    quote.used_count = 1
    quote.last_used = datetime.now(timezone.utc)
    post = Post(
        quote_id=quote.id,
        platform="twitter",
        content="Queued from old import.",
        status="approved",
        render_kind="quote",
    )
    session.add(post)
    session.commit()
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/quotes/1",
        data={"action": "return-pool"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Returned quote #1 to the active pool" in response.data

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    assert quote.approved is True
    assert quote.archived is False
    assert quote.used_count == 0
    assert quote.last_used is None
    assert session.query(Post).filter(Post.quote_id == 1).count() == 0
    session.close()


def test_return_pool_keeps_posted_quote_out_of_pool(app_client):
    client, app = app_client

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    quote.approved = True
    quote.used_count = 1
    quote.last_used = datetime.now(timezone.utc)
    post = Post(
        quote_id=quote.id,
        platform="twitter",
        content="Already posted.",
        status="posted",
        render_kind="quote",
        post_id="tw-posted",
        posted_time=datetime.now(timezone.utc),
    )
    session.add(post)
    session.commit()
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/quotes/1",
        data={"action": "return-pool"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"has already been posted" in response.data

    session = get_session(app.config["DB_ENGINE"])
    quote = session.query(Quote).filter(Quote.id == 1).first()
    assert quote.used_count == 1
    assert session.query(Post).filter(Post.quote_id == 1).count() == 1
    session.close()


def test_stoic_entry_endpoint(app_client, monkeypatch):
    client, _ = app_client

    monkeypatch.setattr(
        stoic_service,
        "get_stoic_entry_for_today",
        lambda: {
            "date": "April 11",
            "title": "Control",
            "author": "Epictetus",
            "source": "Discourses",
            "quote": "Focus on what you control.",
            "body": "Ignore the noise and manage your choices.",
        },
    )

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.get("/api/stoic/entry")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["title"] == "Control"
    assert payload["author"] == "Epictetus"


def test_generate_and_queue_stoic_post(app_client, monkeypatch):
    client, app = app_client

    monkeypatch.setattr(
        stoic_service,
        "get_stoic_entry_for_today",
        lambda: {
            "date": "April 11",
            "title": "Control",
            "author": "Epictetus",
            "source": "Discourses",
            "quote": "Focus on what you control.",
            "body": "Ignore the noise and manage your choices.",
        },
    )
    monkeypatch.setattr(
        stoic_service,
        "generate_stoic_trading_content",
        lambda entry: {
            "point1_title": "Control Risk",
            "point1_meaning": "Own decisions",
            "point1_trading": "Size down fast",
            "point2_title": "Ignore Noise",
            "point2_meaning": "External chaos",
            "point2_trading": "Stick to plan",
            "point3_title": "Stay Present",
            "point3_meaning": "Act now",
            "point3_trading": "Execute cleanly",
            "closing_wisdom": "Calm process beats reactive trading.",
            "key_takeaway": "Own the next decision.",
            "tweet": "Control your choices, not the tape. #ict #trader #tradingpsychology #stoic",
        },
    )
    monkeypatch.setattr(app_module.brand_media, "render_stoic_card", lambda payload: b"fake-stoic-card")

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post("/api/stoic/generate")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["tweet"].startswith("Control your choices")
    assert payload["image_data_uri"].startswith("data:image/png;base64,")

    queue_response = client.post(
        "/api/stoic/queue",
        json={
            "tweet": payload["tweet"],
            "status": "approved",
            "image_url": payload.get("image_url"),
            "render_payload": payload,
        },
    )

    assert queue_response.status_code == 200
    queue_payload = queue_response.get_json()
    assert queue_payload["success"] is True

    session = get_session(app.config["DB_ENGINE"])
    post = session.query(Post).filter(Post.id == queue_payload["post_id"]).first()
    assert post is not None
    assert post.status == "approved"
    assert post.content == payload["tweet"]
    assert post.render_kind == "stoic"
    assert post.render_payload
    session.close()


def test_share_quote_to_x_creates_published_post(app_client, monkeypatch):
    client, app = app_client

    monkeypatch.setattr(app_module.brand_media, "render_quote_card", lambda content: b"fake-quote-card")

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def publish_content(self, text, **kwargs):
            assert text
            return {"status": "posted", "tweet_id": "tw-123", "url": "https://x.com/test/status/tw-123"}

    monkeypatch.setattr(app_module, "TwitterClient", FakeTwitterClient)

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/quotes/1",
        data={"action": "share-x", "use_ai": "true"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Shared quote #1 to X as post #1." in response.data

    session = get_session(app.config["DB_ENGINE"])
    post = session.query(Post).filter(Post.id == 1).first()
    assert post is not None
    assert post.status == "posted"
    assert post.post_id == "tw-123"
    session.close()


def test_create_manual_quote_card_queues_post_with_render_payload(app_client, monkeypatch):
    client, app = app_client

    monkeypatch.setattr(app_module.brand_media, "render_quote_card", lambda content: b"manual-quote-card")

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        "/actions/manual-quote-card",
        data={
            "quote_text": "Wait for confirmation, not comfort.",
            "post_text": "Wait for confirmation, not comfort. Trade the proof.",
            "status": "approved",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Queued manual quote card as post #1." in response.data

    session = get_session(app.config["DB_ENGINE"])
    post = session.query(Post).filter(Post.id == 1).first()
    assert post is not None
    assert post.status == "approved"
    assert post.render_kind == "quote"
    assert json.loads(post.render_payload)["quote_text"] == "Wait for confirmation, not comfort."
    assert post.content == "Wait for confirmation, not comfort. Trade the proof."
    session.close()


def test_publish_manual_quote_post_generates_media_from_render_payload(app_client, monkeypatch):
    client, app = app_client
    captured = {}

    def fake_render_quote_card(content):
        captured["rendered_text"] = content
        return b"manual-image"

    monkeypatch.setattr(app_module.brand_media, "render_quote_card", fake_render_quote_card)

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def publish_content(self, text, **kwargs):
            captured["image_bytes"] = kwargs.get("image_bytes")
            return {"status": "posted", "tweet_id": "manual-123", "url": "https://x.com/test/status/manual-123"}

    monkeypatch.setattr(app_module, "TwitterClient", FakeTwitterClient)

    session = get_session(app.config["DB_ENGINE"])
    post = Post(
        platform="twitter",
        content="Post copy that should not become the quote card.",
        status="approved",
        render_kind="quote",
        render_payload=json.dumps({"quote_text": "The card should use this quote."}),
    )
    session.add(post)
    session.commit()
    post_id = post.id
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        f"/actions/posts/{post_id}",
        data={"action": "publish-x"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured["rendered_text"] == "The card should use this quote."
    assert captured["image_bytes"] == b"manual-image"

    session = get_session(app.config["DB_ENGINE"])
    post = session.query(Post).filter(Post.id == post_id).first()
    assert post.status == "posted"
    assert post.post_id == "manual-123"
    session.close()


def test_publish_queued_stoic_post_generates_media_from_payload(app_client, monkeypatch):
    client, app = app_client

    monkeypatch.setattr(app_module.brand_media, "render_stoic_card", lambda payload: b"stoic-image")

    captured = {}

    class FakeTwitterClient:
        def __init__(self, dry_run=False):
            self.dry_run = dry_run

        def is_configured(self):
            return True

        def publish_content(self, text, **kwargs):
            captured["image_bytes"] = kwargs.get("image_bytes")
            return {"status": "posted", "tweet_id": "stoic-456", "url": "https://x.com/test/status/stoic-456"}

    monkeypatch.setattr(app_module, "TwitterClient", FakeTwitterClient)

    session = get_session(app.config["DB_ENGINE"])
    post = Post(
        platform="twitter",
        content="Stoic tweet",
        status="approved",
        render_kind="stoic",
        render_payload='{"title":"Control","author":"Epictetus","date":"April 11"}',
    )
    session.add(post)
    session.commit()
    post_id = post.id
    session.close()

    client.post("/login", data={"username": "admin", "password": "secret"})
    response = client.post(
        f"/actions/posts/{post_id}",
        data={"action": "publish-x"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured["image_bytes"] == b"stoic-image"

    session = get_session(app.config["DB_ENGINE"])
    post = session.query(Post).filter(Post.id == post_id).first()
    assert post.status == "posted"
    assert post.post_id == "stoic-456"
    session.close()
