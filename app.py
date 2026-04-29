#!/usr/bin/env python3
"""Hosted control panel for the EdgeOfICT social agent."""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from core.content_extractor import ContentExtractor
from core.models import Post, PostStatus, Quote, get_engine, get_session, init_db, resolve_db_url
from core.post_planner import PostPlanner
from core import brand_media, stoic_service
from integrations.cloudinary_client import CloudinaryClient
from integrations.facebook_client import FacebookClient
from integrations.instagram_client import InstagramClient
from integrations.twitter_client import TwitterClient

load_dotenv()

UTC = timezone.utc

PROFILE_CONFIG = {
    "picture_url": os.getenv(
        "PROFILE_PICTURE_URL",
        "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=320&q=80",
    ),
    "name": os.getenv("PROFILE_NAME", "EdgeOfICT"),
    "handle": os.getenv("PROFILE_HANDLE", "@edgeofict"),
}

SOURCE_LABEL_OVERRIDES = {
    "tmprq7h9hor": "The Sands of Time",
}


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_datetime_local(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_safe_redirect_target(target: str | None) -> bool:
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.netloc and parts.path.startswith("/")


def slug_fragment(value: str, fallback: str = "card") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48] or fallback


def display_source_label(source: str | None) -> str:
    cleaned = (source or "").strip()
    if not cleaned:
        return "Unknown"
    return SOURCE_LABEL_OVERRIDES.get(cleaned, cleaned)


def build_integration_hints():
    return {
        "anthropic": {
            "label": "Anthropic",
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "detail": "Used for quote extraction and AI post formatting.",
        },
        "twitter": {
            "label": "X / Twitter",
            "configured": TwitterClient(dry_run=True).is_configured(),
            "detail": "Publishes approved posts directly to X.",
        },
        "facebook": {
            "label": "Facebook",
            "configured": FacebookClient().is_configured(),
            "detail": "Publishes text or image posts to the connected Page.",
        },
        "instagram": {
            "label": "Instagram",
            "configured": InstagramClient().is_configured(),
            "detail": "Publishes image posts via the linked Instagram Business account.",
        },
        "cloudinary": {
            "label": "Cloudinary",
            "configured": CloudinaryClient().is_configured(),
            "detail": "Stores generated media and hosted images for social posting.",
        },
    }


def verify_service(name, verify_callable, configured):
    if not configured:
        return {
            "name": name,
            "configured": False,
            "state": "missing",
            "message": "Credentials are not configured.",
        }

    try:
        payload = verify_callable() or {}
        state = "ok"
        message = "Connection verified."

        if payload.get("status") == "error" or payload.get("configured") is False:
            state = "error"
            message = payload.get("error") or payload.get("message") or "Verification failed."
        else:
            message = (
                payload.get("name")
                or payload.get("username")
                or payload.get("page_name")
                or payload.get("cloud_name")
                or payload.get("message")
                or "Connection verified."
            )

        return {
            "name": name,
            "configured": True,
            "state": state,
            "message": message,
        }
    except Exception as exc:
        return {
            "name": name,
            "configured": True,
            "state": "error",
            "message": str(exc),
        }


def create_app(test_config=None):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32)),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD"),
        ADMIN_PASSWORD_HASH=os.getenv("ADMIN_PASSWORD_HASH"),
        DATABASE_URL=resolve_db_url(os.getenv("DATABASE_URL")),
        DISABLE_AUTH=parse_bool(os.getenv("DISABLE_AUTH"), default=False),
        SESSION_COOKIE_SECURE=parse_bool(os.getenv("SESSION_COOKIE_SECURE"), default=os.getenv("FLASK_ENV") == "production"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
        APP_TITLE="EdgeOfICT Social Control",
    )

    if test_config:
        app.config.update(test_config)

    if app.config.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = app.config["DATABASE_URL"]

    app.config["PROFILE"] = PROFILE_CONFIG
    app.config["INTEGRATION_HINTS"] = build_integration_hints()
    app.config["DB_ENGINE"] = get_engine(app.config["DATABASE_URL"])
    init_db(app.config["DB_ENGINE"])

    @contextmanager
    def db_session_scope():
        db_session = get_session(app.config["DB_ENGINE"])
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    def auth_ready():
        if current_app.config["DISABLE_AUTH"]:
            return True
        return bool(current_app.config.get("ADMIN_PASSWORD") or current_app.config.get("ADMIN_PASSWORD_HASH"))

    def verify_login(username: str, password: str) -> bool:
        expected_username = current_app.config["ADMIN_USERNAME"]
        password_hash = current_app.config.get("ADMIN_PASSWORD_HASH")
        raw_password = current_app.config.get("ADMIN_PASSWORD")

        username_ok = secrets.compare_digest(username or "", expected_username or "")

        if password_hash:
            password_ok = check_password_hash(password_hash, password or "")
        elif raw_password:
            password_ok = secrets.compare_digest(password or "", raw_password)
        else:
            password_ok = False

        return username_ok and password_ok

    def login_required(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not auth_ready():
                abort(503, description="Admin credentials are missing. Set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH.")
            if current_app.config["DISABLE_AUTH"] or session.get("admin_authenticated"):
                return view_func(*args, **kwargs)
            next_target = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=next_target))

        return wrapper

    def update_post_status(post: Post, new_status: str):
        now = datetime.now(UTC)
        post.status = new_status
        if new_status == PostStatus.APPROVED.value:
            post.approved_at = post.approved_at or now
            post.posted_time = None
        elif new_status == PostStatus.POSTED.value:
            post.approved_at = post.approved_at or now
            post.posted_time = now
        elif new_status in {PostStatus.PENDING.value, PostStatus.REJECTED.value, PostStatus.FAILED.value}:
            post.posted_time = None

    def upload_generated_image(image_bytes: bytes, *, folder: str, public_id: str) -> str | None:
        cloudinary = CloudinaryClient()
        if not cloudinary.is_configured():
            return None

        try:
            result = cloudinary.upload_bytes(image_bytes, folder=folder, public_id=public_id)
            return result.get("secure_url") or result.get("url")
        except Exception:
            return None

    def load_render_payload(post: Post) -> dict:
        if not post.render_payload:
            return {}
        try:
            payload = json.loads(post.render_payload)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def resolve_quote_source_text(post: Post, quote: Quote | None = None) -> str:
        if quote is not None and quote.content:
            return quote.content.strip()

        payload = load_render_payload(post)
        for key in ("quote_text", "source_text", "quote"):
            value = (payload.get(key) or "").strip()
            if value:
                return value

        return (post.content or "").strip()

    def ensure_quote_media(post: Post, quote: Quote | None = None) -> bytes | None:
        source_text = resolve_quote_source_text(post, quote)
        if not source_text:
            return None

        image_bytes = brand_media.render_quote_card(source_text)
        if not post.media_path:
            public_id = f"quote-{post.id}-{slug_fragment(source_text)}"
            image_url = upload_generated_image(
                image_bytes,
                folder="edgeofict/quotes",
                public_id=public_id,
            )
            if image_url:
                post.media_path = image_url
        return image_bytes

    def build_stoic_media(payload: dict) -> dict:
        image_bytes = brand_media.render_stoic_card(payload)
        public_id = f"stoic-{slug_fragment(payload.get('date', 'today'))}-{slug_fragment(payload.get('title', 'wisdom'))}"
        image_url = upload_generated_image(
            image_bytes,
            folder="edgeofict/stoic",
            public_id=public_id,
        )
        return {
            "image_bytes": image_bytes,
            "image_data_uri": brand_media.png_data_uri(image_bytes),
            "image_url": image_url,
        }

    def render_stoic_media_from_post(post: Post) -> bytes | None:
        if post.render_kind != "stoic" or not post.render_payload:
            return None

        payload = load_render_payload(post)
        if not payload:
            return None

        image_bytes = brand_media.render_stoic_card(payload)
        if not post.media_path:
            public_id = f"stoic-{post.id}-{slug_fragment(payload.get('title', 'wisdom'))}"
            image_url = upload_generated_image(
                image_bytes,
                folder="edgeofict/stoic",
                public_id=public_id,
            )
            if image_url:
                post.media_path = image_url
        return image_bytes

    def publish_post_to_x(db_session, post: Post, quote: Quote | None = None) -> dict:
        client = TwitterClient(dry_run=False)
        if not client.is_configured():
            return {"status": "error", "message": "X/Twitter credentials are not configured."}

        image_bytes = None
        if not post.media_path:
            if post.render_kind == "stoic":
                image_bytes = render_stoic_media_from_post(post)
            elif quote is None and post.quote_id:
                quote = db_session.query(Quote).filter(Quote.id == post.quote_id).first()
            if image_bytes is None and (quote is not None or post.render_kind == "quote"):
                image_bytes = ensure_quote_media(post, quote)

        try:
            result = client.publish_content(
                post.content,
                image_url=post.media_path,
                image_bytes=image_bytes,
                image_filename=f"edgeofict-{post.id}.png",
            )
        except Exception as exc:
            update_post_status(post, PostStatus.FAILED.value)
            return {"status": "error", "message": str(exc)}

        if result.get("status") == "posted":
            update_post_status(post, PostStatus.POSTED.value)
            post.post_id = str(result["tweet_id"])
            return result

        update_post_status(post, PostStatus.FAILED.value)
        return result

    def ensure_public_post_media(db_session, post: Post) -> str | None:
        if post.media_path:
            return post.media_path

        if post.render_kind == "stoic":
            try:
                render_stoic_media_from_post(post)
            except Exception:
                return post.media_path

        if not post.media_path and post.quote_id:
            quote = db_session.query(Quote).filter(Quote.id == post.quote_id).first()
            ensure_quote_media(post, quote)
        elif not post.media_path and post.render_kind == "quote":
            ensure_quote_media(post)

        return post.media_path

    def create_post_from_quote(db_session, quote: Quote, use_ai: bool, status: str = PostStatus.PENDING.value):
        planner = PostPlanner()
        content = planner.format_quote_for_twitter(quote, use_ai=use_ai)
        post = Post(
            quote_id=quote.id,
            platform="twitter",
            content=content,
            render_kind="quote",
            status=status,
            created_at=datetime.now(UTC),
        )
        if status == PostStatus.APPROVED.value:
            post.approved_at = datetime.now(UTC)
        db_session.add(post)
        db_session.flush()
        try:
            ensure_quote_media(post, quote)
        except Exception:
            pass
        quote.approved = True
        quote.used_count = (quote.used_count or 0) + 1
        quote.last_used = datetime.now(UTC)
        return post

    def auto_queue_imported_quotes(db_session, quote_ids: list[int], *, use_ai: bool = False) -> int:
        if not quote_ids:
            return 0

        quotes = (
            db_session.query(Quote)
            .filter(Quote.id.in_(quote_ids))
            .order_by(Quote.id.asc())
            .all()
        )

        created = 0
        for quote in quotes:
            create_post_from_quote(db_session, quote, use_ai=use_ai, status=PostStatus.APPROVED.value)
            created += 1

        return created

    def get_dashboard_stoic_entry():
        try:
            return stoic_service.get_stoic_entry_for_today()
        except Exception:
            return None

    def build_dashboard_posted_item(post: Post, quotes_by_id: dict[int, Quote]) -> dict:
        payload = load_render_payload(post)
        quote = quotes_by_id.get(post.quote_id) if post.quote_id else None
        post_kind = "stoic" if post.render_kind == "stoic" else "quote"

        if post_kind == "stoic":
            title = (payload.get("title") or "Stoic Post").strip()
            body_text = (
                payload.get("key_takeaway")
                or payload.get("closing_wisdom")
                or post.content
            )
            source_label = "Stoic"
            meta_label = (payload.get("author") or "Daily Stoic").strip()
            search_text = " ".join(
                filter(
                    None,
                    [
                        title,
                        body_text,
                        meta_label,
                        payload.get("date", ""),
                    ],
                )
            )
        else:
            title = resolve_quote_source_text(post, quote) or post.content or "Quote post"
            body_text = post.content or title
            source_label = display_source_label(quote.source if quote else payload.get("source"))
            meta_label = quote.topic if quote and quote.topic else "Quote"
            search_text = " ".join(filter(None, [title, body_text, source_label, meta_label]))

        return {
            "id": post.id,
            "kind": post_kind,
            "kind_label": "Stoic" if post_kind == "stoic" else "Quote",
            "title": title.strip(),
            "body_text": body_text.strip(),
            "source_label": source_label,
            "meta_label": meta_label,
            "posted_time": post.posted_time,
            "url": f"https://x.com/{PROFILE_CONFIG['handle'].lstrip('@')}/status/{post.post_id}" if post.post_id else None,
            "search_text": search_text.lower(),
        }

    def collect_dashboard_state():
        with db_session_scope() as db_session:
            quotes = (
                db_session.query(Quote)
                .order_by(
                    Quote.approved.desc(),
                    Quote.used_count.asc(),
                    Quote.quality_score.desc(),
                    Quote.created_at.desc(),
                )
                .all()
            )
            posted_posts = (
                db_session.query(Post)
                .filter(Post.status == PostStatus.POSTED.value)
                .order_by(Post.posted_time.desc(), Post.created_at.desc())
                .limit(150)
                .all()
            )
            documents = (
                db_session.query(Quote.source, func.count(Quote.id).label("quote_count"))
                .group_by(Quote.source)
                .order_by(func.count(Quote.id).desc(), Quote.source.asc())
                .all()
            )
            stats = {
                "quotes_total": db_session.query(Quote).count(),
                "quotes_pending": db_session.query(Quote).filter(Quote.approved.is_(False)).count(),
                "quotes_approved": db_session.query(Quote).filter(Quote.approved.is_(True)).count(),
                "posts_posted": db_session.query(Post).filter(Post.status == PostStatus.POSTED.value).count(),
                "sources_total": db_session.query(func.count(func.distinct(Quote.source))).scalar() or 0,
            }
            quotes_by_id = {quote.id: quote for quote in quotes}
            posted_feed = [build_dashboard_posted_item(post, quotes_by_id) for post in posted_posts]

        db_url = app.config["DATABASE_URL"]
        return {
            "quotes": quotes,
            "posted_posts": posted_posts,
            "posted_feed": posted_feed,
            "documents": documents,
            "stats": stats,
            "profile": app.config["PROFILE"],
            "database_label": "PostgreSQL" if db_url.startswith("postgresql://") else "SQLite",
            "auth_enabled": not app.config["DISABLE_AUTH"],
        }

    @app.template_filter("datetime_input")
    def datetime_input(value):
        if not value:
            return ""
        if value.tzinfo:
            value = value.astimezone().replace(tzinfo=None)
        return value.strftime("%Y-%m-%dT%H:%M")

    @app.template_filter("datetime_human")
    def datetime_human(value):
        if not value:
            return "Not scheduled"
        if value.tzinfo:
            value = value.astimezone().replace(tzinfo=None)
        return value.strftime("%b %d, %Y %H:%M")

    @app.template_filter("source_label")
    def source_label(value):
        return display_source_label(value)

    @app.errorhandler(503)
    def handle_service_config(error):
        return (
            render_template(
                "login.html",
                profile=app.config["PROFILE"],
                config_error=str(error.description),
            ),
            503,
        )

    @app.get("/healthz")
    def healthz():
        try:
            with db_session_scope() as db_session:
                db_session.execute(text("SELECT 1"))
            return jsonify(
                {
                    "status": "ok",
                    "database": "postgresql" if app.config["DATABASE_URL"].startswith("postgresql://") else "sqlite",
                    "auth_enabled": not app.config["DISABLE_AUTH"],
                }
            )
        except Exception as exc:
            return jsonify({"status": "error", "error": str(exc)}), 500

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if app.config["DISABLE_AUTH"]:
            session["admin_authenticated"] = True
            return redirect(url_for("dashboard"))

        if session.get("admin_authenticated"):
            return redirect(url_for("dashboard"))

        config_error = None if auth_ready() else "Set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH before exposing this dashboard."

        if request.method == "POST":
            if not auth_ready():
                return (
                    render_template("login.html", profile=app.config["PROFILE"], config_error=config_error),
                    503,
                )

            username = request.form.get("username", "")
            password = request.form.get("password", "")

            if verify_login(username, password):
                session["admin_authenticated"] = True
                session.permanent = True
                next_target = request.args.get("next")
                if is_safe_redirect_target(next_target):
                    return redirect(next_target)
                return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "error")

        return render_template(
            "login.html",
            profile=app.config["PROFILE"],
            config_error=config_error,
        )

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        return render_template("dashboard.html", **collect_dashboard_state())

    @app.post("/actions/extract-quotes")
    @login_required
    def extract_quotes():
        upload = request.files.get("document")
        if not upload or not upload.filename:
            flash("Choose a PDF, DOCX, or TXT file to extract quotes from.", "error")
            return redirect(url_for("dashboard"))

        ext = upload.filename.rsplit(".", 1)[-1].lower()
        source_name = Path(upload.filename).stem.strip() or "Imported Document"
        if ext not in {"pdf", "docx", "txt"}:
            flash("Unsupported file type. Use PDF, DOCX, or TXT.", "error")
            return redirect(url_for("dashboard"))

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp_file:
                upload.save(temp_file.name)
                temp_path = temp_file.name

            extractor = ContentExtractor()
            result = extractor.extract_and_save(temp_path, source_name=source_name, return_quote_ids=True)
            extracted, saved, saved_quote_ids = result

            created_posts = 0
            if saved_quote_ids:
                with db_session_scope() as db_session:
                    created_posts = auto_queue_imported_quotes(db_session, saved_quote_ids, use_ai=False)

            flash(
                f"Imported {saved} new quotes from {upload.filename} ({extracted} extracted) and queued {created_posts} ready posts.",
                "success",
            )
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            flash(f"Quote extraction failed: {exc}", "error")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

        return redirect(url_for("dashboard"))

    @app.post("/actions/generate-posts")
    @login_required
    def generate_posts():
        days = max(1, min(int(request.form.get("days", 7)), 30))
        posts_per_day = max(1, min(int(request.form.get("posts_per_day", 1)), 6))
        use_ai = parse_bool(request.form.get("use_ai"), default=False)

        try:
            planner = PostPlanner()
            posts = planner.generate_posts(days=days, posts_per_day=posts_per_day, use_ai=use_ai)
            if posts:
                flash(f"Generated {len(posts)} queued posts.", "success")
            else:
                flash("No approved quotes were available to generate posts from.", "warning")
        except Exception as exc:
            flash(f"Post generation failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/actions/quotes/approve-all")
    @login_required
    def approve_all_quotes():
        try:
            with db_session_scope() as db_session:
                pending_quotes = (
                    db_session.query(Quote)
                    .filter(Quote.approved.is_(False))
                    .all()
                )

                if not pending_quotes:
                    flash("No quotes are waiting for review.", "warning")
                    return redirect(url_for("dashboard"))

                for quote in pending_quotes:
                    quote.approved = True

                flash(f"Approved {len(pending_quotes)} quotes.", "success")
        except Exception as exc:
            flash(f"Bulk quote approval failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/actions/manual-quote-card")
    @login_required
    def create_manual_quote_card():
        quote_text = request.form.get("quote_text", "").strip()
        post_text = request.form.get("post_text", "").strip() or quote_text
        status = request.form.get("status", PostStatus.PENDING.value)

        if not quote_text:
            flash("Add quote text to create a manual quote card.", "error")
            return redirect(url_for("dashboard"))

        if status not in {PostStatus.PENDING.value, PostStatus.APPROVED.value}:
            flash("Manual quote card status must be draft or approved.", "error")
            return redirect(url_for("dashboard"))

        try:
            with db_session_scope() as db_session:
                post = Post(
                    platform="twitter",
                    content=post_text,
                    render_kind="quote",
                    render_payload=json.dumps({"quote_text": quote_text}),
                    status=status,
                    created_at=datetime.now(UTC),
                )
                if status == PostStatus.APPROVED.value:
                    post.approved_at = datetime.now(UTC)
                db_session.add(post)
                db_session.flush()
                ensure_quote_media(post)
                flash(f"Queued manual quote card as post #{post.id}.", "success")
        except Exception as exc:
            flash(f"Manual quote card creation failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/actions/quotes/<int:quote_id>")
    @login_required
    def handle_quote_action(quote_id: int):
        action = request.form.get("action")
        use_ai = parse_bool(request.form.get("use_ai"), default=False)

        try:
            with db_session_scope() as db_session:
                quote = db_session.query(Quote).filter(Quote.id == quote_id).first()
                if not quote:
                    flash("Quote not found.", "error")
                    return redirect(url_for("dashboard"))

                if action == "approve":
                    quote.approved = True
                    flash(f"Approved quote #{quote.id}.", "success")
                elif action == "reject":
                    quote.approved = False
                    flash(f"Moved quote #{quote.id} back to review.", "warning")
                elif action == "queue":
                    post = create_post_from_quote(db_session, quote, use_ai=use_ai)
                    flash(f"Queued draft post #{post.id} from quote #{quote.id}.", "success")
                elif action == "queue-approved":
                    post = create_post_from_quote(db_session, quote, use_ai=use_ai, status=PostStatus.APPROVED.value)
                    flash(f"Queued approved post #{post.id} from quote #{quote.id}.", "success")
                elif action == "share-x":
                    post = create_post_from_quote(db_session, quote, use_ai=use_ai, status=PostStatus.APPROVED.value)
                    result = publish_post_to_x(db_session, post, quote=quote)
                    if result.get("status") == "posted":
                        flash(f"Shared quote #{quote.id} to X as post #{post.id}.", "success")
                    else:
                        flash(result.get("message") or "X publish failed.", "error")
                else:
                    flash("Unknown quote action.", "error")
        except Exception as exc:
            flash(f"Quote action failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.post("/actions/posts/<int:post_id>")
    @login_required
    def handle_post_action(post_id: int):
        action = request.form.get("action")
        new_status = request.form.get("status", PostStatus.PENDING.value)

        try:
            with db_session_scope() as db_session:
                post = db_session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    flash("Post not found.", "error")
                    return redirect(url_for("dashboard"))

                content = request.form.get("content", "").strip()
                if content:
                    post.content = content
                media_path = request.form.get("media_path", "").strip()
                post.media_path = media_path or None
                post.scheduled_time = parse_datetime_local(request.form.get("scheduled_time"))

                if action == "save":
                    update_post_status(post, new_status)
                    flash(f"Saved post #{post.id}.", "success")
                elif action == "approve":
                    update_post_status(post, PostStatus.APPROVED.value)
                    flash(f"Approved post #{post.id}.", "success")
                elif action == "draft":
                    update_post_status(post, PostStatus.PENDING.value)
                    flash(f"Moved post #{post.id} back to draft.", "warning")
                elif action == "reject":
                    update_post_status(post, PostStatus.REJECTED.value)
                    flash(f"Rejected post #{post.id}.", "warning")
                elif action == "publish-x":
                    if post.status != PostStatus.APPROVED.value:
                        flash("Approve the post before publishing to X.", "error")
                        return redirect(url_for("dashboard"))
                    result = publish_post_to_x(db_session, post)
                    if result.get("status") != "posted":
                        flash(result.get("message") or "X publish failed.", "error")
                        return redirect(url_for("dashboard"))
                    flash(f"Shared post #{post.id} to X.", "success")
                elif action == "publish-facebook":
                    client = FacebookClient()
                    if not client.is_configured():
                        flash("Facebook credentials are not configured.", "error")
                        return redirect(url_for("dashboard"))
                    media_url = ensure_public_post_media(db_session, post)
                    result = client.post_image(media_url, post.content) if media_url else client.post_text(post.content)
                    flash(f"Posted to Facebook: {result.get('url')}", "success")
                elif action == "publish-instagram":
                    media_url = ensure_public_post_media(db_session, post)
                    if not media_url:
                        flash("Instagram publishing requires an image URL in the media field.", "error")
                        return redirect(url_for("dashboard"))
                    client = InstagramClient()
                    if not client.is_configured():
                        flash("Instagram credentials are not configured.", "error")
                        return redirect(url_for("dashboard"))
                    result = client.post_image(media_url, post.content)
                    flash(f"Posted to Instagram: {result.get('url')}", "success")
                else:
                    flash("Unknown post action.", "error")
        except Exception as exc:
            flash(f"Post action failed: {exc}", "error")

        return redirect(url_for("dashboard"))

    @app.get("/api/integrations")
    @login_required
    def integration_status():
        hints = app.config["INTEGRATION_HINTS"]
        statuses = {
            "twitter": verify_service(
                "X / Twitter",
                lambda: TwitterClient(dry_run=False).verify_credentials(),
                hints["twitter"]["configured"],
            ),
            "facebook": verify_service(
                "Facebook",
                lambda: FacebookClient().verify_credentials(),
                hints["facebook"]["configured"],
            ),
            "instagram": verify_service(
                "Instagram",
                lambda: InstagramClient().verify_credentials(),
                hints["instagram"]["configured"],
            ),
            "cloudinary": verify_service(
                "Cloudinary",
                lambda: CloudinaryClient().verify_credentials(),
                hints["cloudinary"]["configured"],
            ),
        }
        statuses["anthropic"] = {
            "name": "Anthropic",
            "configured": hints["anthropic"]["configured"],
            "state": "ok" if hints["anthropic"]["configured"] else "missing",
            "message": "API key loaded for extraction and formatting." if hints["anthropic"]["configured"] else "ANTHROPIC_API_KEY is missing.",
        }
        return jsonify(statuses)

    @app.get("/api/stoic/entry")
    @login_required
    def get_stoic_entry():
        entry = stoic_service.get_stoic_entry_for_today()
        if not entry:
            return jsonify({"error": "No Stoic entry found for today."}), 404

        return jsonify(
            {
                "date": entry.get("date", ""),
                "title": entry.get("title", ""),
                "author": entry.get("author", ""),
                "source": entry.get("source", ""),
                "quote": entry.get("quote", ""),
                "body": entry.get("body", ""),
            }
        )

    @app.post("/api/stoic/generate")
    @login_required
    def generate_stoic():
        try:
            entry = stoic_service.get_stoic_entry_for_today()
            if not entry:
                return jsonify({"error": "No Stoic entry found for today."}), 404

            content = stoic_service.generate_stoic_trading_content(entry)
            media = build_stoic_media(
                {
                    "date": entry.get("date", ""),
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    **content,
                }
            )
            return jsonify(
                {
                    "success": True,
                    "date": entry.get("date", ""),
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    "source": entry.get("source", ""),
                    "quote": entry.get("quote", ""),
                    "image_data_uri": media["image_data_uri"],
                    "image_url": media["image_url"],
                    **content,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            return jsonify({"error": f"Stoic generation failed: {exc}"}), 500

    @app.post("/api/stoic/queue")
    @login_required
    def queue_stoic():
        payload = request.get_json(silent=True) or {}
        tweet = (payload.get("tweet") or "").strip()
        status = payload.get("status", PostStatus.PENDING.value)
        render_payload = payload.get("render_payload") or {}

        if not tweet:
            return jsonify({"error": "Missing Stoic tweet text."}), 400

        if status not in {PostStatus.PENDING.value, PostStatus.APPROVED.value}:
            return jsonify({"error": "Invalid queue status."}), 400

        try:
            with db_session_scope() as db_session:
                post = Post(
                    platform="twitter",
                    content=tweet,
                    media_path=payload.get("image_url") or None,
                    render_kind="stoic",
                    render_payload=json.dumps(render_payload),
                    status=status,
                    created_at=datetime.now(UTC),
                )
                if status == PostStatus.APPROVED.value:
                    post.approved_at = datetime.now(UTC)
                db_session.add(post)
                db_session.flush()
                post_id = post.id

            return jsonify({"success": True, "post_id": post_id, "status": status})
        except Exception as exc:
            return jsonify({"error": f"Queue failed: {exc}"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    debug_enabled = parse_bool(os.getenv("FLASK_DEBUG"), default=False)
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )
