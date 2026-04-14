from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from .models import AutomationRun, Post, PostStatus, Quote, get_session, init_db
from . import brand_media, stoic_service
from .post_planner import build_quote_post_text
from integrations.cloudinary_client import CloudinaryClient
from integrations.facebook_client import FacebookClient
from integrations.instagram_client import InstagramClient
from integrations.twitter_client import TwitterClient

UTC = timezone.utc
DEFAULT_STOIC_TASK_KEY = "daily_stoic"
DEFAULT_QUOTE_TASK_KEY = "daily_quote"


@dataclass
class AutomationResult:
    status: str
    message: str
    post_id: int | None = None
    url: str | None = None


def get_automation_timezone() -> ZoneInfo:
    timezone_name = os.getenv("AUTO_STOIC_TIMEZONE", "America/New_York")
    return ZoneInfo(timezone_name)


def should_run_for_hour(run_hour: int | None, now_local: datetime) -> bool:
    if run_hour is None:
        return True
    return now_local.hour >= run_hour


def slug_fragment(value: str, fallback: str = "card") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48] or fallback


def build_stoic_image_assets(entry: dict, content: dict) -> tuple[bytes, str | None]:
    image_bytes = brand_media.render_stoic_card(
        {
            "date": entry.get("date", ""),
            "title": entry.get("title", ""),
            "author": entry.get("author", ""),
            **content,
        }
    )

    cloudinary = CloudinaryClient()
    if not cloudinary.is_configured():
        return image_bytes, None

    public_id = f"stoic-{datetime.now(UTC).date().isoformat()}-{entry.get('title', 'wisdom').lower().replace(' ', '-')[:36]}"
    result = cloudinary.upload_bytes(image_bytes, folder="edgeofict/stoic", public_id=public_id)
    return image_bytes, result.get("secure_url") or result.get("url")


def build_quote_image_assets(post: Post, quote: Quote | None) -> tuple[bytes, str | None]:
    source_text = (quote.content if quote else "") or post.content or ""
    image_bytes = brand_media.render_quote_card(source_text)

    cloudinary = CloudinaryClient()
    if not cloudinary.is_configured():
        return image_bytes, None

    public_id = f"quote-{post.id}-{slug_fragment(source_text)}"
    result = cloudinary.upload_bytes(image_bytes, folder="edgeofict/quotes", public_id=public_id)
    return image_bytes, result.get("secure_url") or result.get("url")


def get_or_create_run(db_session, *, task_key: str, run_date: str, detail: str) -> AutomationRun:
    run = (
        db_session.query(AutomationRun)
        .filter(
            AutomationRun.task_key == task_key,
            AutomationRun.run_date == run_date,
        )
        .first()
    )
    if run is None:
        run = AutomationRun(
            task_key=task_key,
            run_date=run_date,
            status="started",
            detail=detail,
        )
        db_session.add(run)
        db_session.flush()
    else:
        run.status = "started"
        run.detail = detail
        run.updated_at = datetime.now(UTC)
    return run


def publish_side_platforms(*, content: str, image_url: str | None, dry_run: bool = False) -> dict:
    results: dict[str, dict] = {}

    if dry_run:
        return {
            "facebook": {"status": "dry_run", "message": "Dry run"},
            "instagram": {"status": "dry_run", "message": "Dry run"},
        }

    facebook = FacebookClient()
    if facebook.is_configured():
        try:
            if image_url:
                response = facebook.post_image(image_url, content)
            else:
                response = facebook.post_text(content)
            results["facebook"] = {"status": "posted", "url": response.get("url")}
        except Exception as exc:
            results["facebook"] = {"status": "error", "message": str(exc)}
    else:
        results["facebook"] = {"status": "skipped", "message": "Facebook credentials not configured."}

    instagram = InstagramClient()
    if instagram.is_configured():
        if image_url:
            try:
                response = instagram.post_image(image_url, content)
                results["instagram"] = {"status": "posted", "url": response.get("url")}
            except Exception as exc:
                results["instagram"] = {"status": "error", "message": str(exc)}
        else:
            results["instagram"] = {"status": "skipped", "message": "No image URL available for Instagram."}
    else:
        results["instagram"] = {"status": "skipped", "message": "Instagram credentials not configured."}

    return results


def compose_publish_message(primary_label: str, side_results: dict) -> str:
    summary = [primary_label]
    for platform in ("facebook", "instagram"):
        payload = side_results.get(platform) or {}
        status = payload.get("status")
        if status == "posted":
            summary.append(f"{platform} posted")
        elif status == "error":
            summary.append(f"{platform} failed")
        elif status == "dry_run":
            summary.append(f"{platform} dry run")
    return ", ".join(summary)


def get_next_approved_quote(db_session) -> Quote | None:
    active_quote_ids = (
        db_session.query(Post.quote_id)
        .filter(
            Post.quote_id.isnot(None),
            Post.status.in_([PostStatus.PENDING.value, PostStatus.APPROVED.value]),
        )
    )

    quote = (
        db_session.query(Quote)
        .filter(
            Quote.approved.is_(True),
            ~Quote.id.in_(active_quote_ids),
        )
        .order_by(Quote.used_count.asc(), Quote.quality_score.desc(), Quote.created_at.asc())
        .first()
    )
    if quote is not None:
        return quote

    return (
        db_session.query(Quote)
        .filter(Quote.approved.is_(True))
        .order_by(Quote.used_count.asc(), Quote.quality_score.desc(), Quote.created_at.asc())
        .first()
    )


def create_approved_quote_post(db_session) -> Post | None:
    quote = get_next_approved_quote(db_session)
    if quote is None:
        return None

    now_utc = datetime.now(UTC)
    post = Post(
        quote_id=quote.id,
        platform="twitter",
        content=build_quote_post_text(quote.content),
        render_kind="quote",
        status=PostStatus.APPROVED.value,
        approved_at=now_utc,
        created_at=now_utc,
    )
    db_session.add(post)
    db_session.flush()

    quote.used_count = (quote.used_count or 0) + 1
    quote.last_used = now_utc
    return post


def run_daily_stoic_publish(
    *,
    run_hour: int | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> AutomationResult:
    init_db()
    db_session = get_session()

    try:
        now_local = datetime.now(get_automation_timezone())
        run_date = now_local.date().isoformat()

        if not force and not should_run_for_hour(run_hour, now_local):
            return AutomationResult(
                status="skipped",
                message=f"Current local hour is {now_local.hour}; target hour is {run_hour}.",
            )

        existing_run = (
            db_session.query(AutomationRun)
            .filter(
                AutomationRun.task_key == DEFAULT_STOIC_TASK_KEY,
                AutomationRun.run_date == run_date,
                AutomationRun.status.in_(["posted", "dry_run"]),
            )
            .first()
        )
        if existing_run and not force:
            return AutomationResult(
                status="skipped",
                message=f"Daily Stoic automation already completed for {run_date}.",
                post_id=existing_run.post_id,
            )

        run = get_or_create_run(
            db_session,
            task_key=DEFAULT_STOIC_TASK_KEY,
            run_date=run_date,
            detail="Preparing Stoic post.",
        )

        entry = stoic_service.get_stoic_entry_for_date(now_local)
        if not entry:
            run.status = "failed"
            run.detail = "No Stoic entry found for today."
            run.updated_at = datetime.now(UTC)
            db_session.commit()
            return AutomationResult(status="failed", message=run.detail)

        content = stoic_service.generate_stoic_trading_content(entry)
        tweet = (content.get("tweet") or "").strip()
        if not tweet:
            run.status = "failed"
            run.detail = "Stoic generation returned no tweet text."
            run.updated_at = datetime.now(UTC)
            db_session.commit()
            return AutomationResult(status="failed", message=run.detail)

        image_bytes = None
        image_url = None
        try:
            image_bytes, image_url = build_stoic_image_assets(entry, content)
        except Exception:
            image_bytes, image_url = None, None

        post = Post(
            platform="twitter",
            content=tweet,
            media_path=image_url,
            render_kind="stoic",
            render_payload=json.dumps(
                {
                    "date": entry.get("date", ""),
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    **content,
                }
            ),
            status=PostStatus.APPROVED.value,
            approved_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
        db_session.add(post)
        db_session.flush()
        run.post_id = post.id
        run.detail = f"Prepared Stoic post #{post.id}."
        run.updated_at = datetime.now(UTC)
        db_session.commit()

        client = TwitterClient(dry_run=dry_run)
        if not client.is_configured() and not dry_run:
            run.status = "failed"
            run.detail = "Twitter credentials are not configured."
            run.updated_at = datetime.now(UTC)
            db_session.commit()
            return AutomationResult(status="failed", message=run.detail, post_id=post.id)

        result = client.post_by_id(post.id, confirm=False, image_bytes=image_bytes)
        run.updated_at = datetime.now(UTC)

        if result.get("status") == "posted":
            side_results = publish_side_platforms(content=tweet, image_url=post.media_path, dry_run=dry_run)
            run.status = "posted"
            run.detail = compose_publish_message("Stoic post published", side_results)
            db_session.commit()
            return AutomationResult(
                status="posted",
                message=run.detail,
                post_id=post.id,
                url=result.get("url"),
            )

        if result.get("status") == "dry_run":
            run.status = "dry_run"
            run.detail = "Dry run completed successfully."
            db_session.commit()
            return AutomationResult(status="dry_run", message=run.detail, post_id=post.id)

        run.status = "failed"
        run.detail = result.get("message") or "Unknown publish failure."
        db_session.commit()
        return AutomationResult(status="failed", message=run.detail, post_id=post.id)
    finally:
        db_session.close()


def run_daily_quote_publish(
    *,
    run_hour: int | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> AutomationResult:
    init_db()
    db_session = get_session()

    try:
        now_local = datetime.now(get_automation_timezone())
        run_date = now_local.date().isoformat()

        if not force and not should_run_for_hour(run_hour, now_local):
            return AutomationResult(
                status="skipped",
                message=f"Current local hour is {now_local.hour}; target hour is {run_hour}.",
            )

        existing_run = (
            db_session.query(AutomationRun)
            .filter(
                AutomationRun.task_key == DEFAULT_QUOTE_TASK_KEY,
                AutomationRun.run_date == run_date,
                AutomationRun.status.in_(["posted", "dry_run"]),
            )
            .first()
        )
        if existing_run and not force:
            return AutomationResult(
                status="skipped",
                message=f"Daily quote automation already completed for {run_date}.",
                post_id=existing_run.post_id,
            )

        run = get_or_create_run(
            db_session,
            task_key=DEFAULT_QUOTE_TASK_KEY,
            run_date=run_date,
            detail="Preparing quote post.",
        )

        post = (
            db_session.query(Post)
            .filter(
                Post.platform == "twitter",
                Post.status == PostStatus.APPROVED.value,
                or_(Post.quote_id.isnot(None), Post.render_kind == "quote"),
            )
            .order_by(Post.scheduled_time.is_(None), Post.scheduled_time.asc(), Post.created_at.asc())
            .first()
        )

        if not post:
            post = create_approved_quote_post(db_session)
            if not post:
                run.status = "skipped"
                run.detail = "No approved quote posts or approved quotes available."
                run.updated_at = datetime.now(UTC)
                db_session.commit()
                return AutomationResult(status="skipped", message=run.detail)

        quote = None
        if post.quote_id:
            quote = db_session.query(Quote).filter(Quote.id == post.quote_id).first()

        image_bytes = None
        image_url = post.media_path
        if not image_url:
            try:
                image_bytes, image_url = build_quote_image_assets(post, quote)
                if image_url:
                    post.media_path = image_url
            except Exception as exc:
                run.status = "failed"
                run.detail = f"Quote image generation failed: {exc}"
                run.updated_at = datetime.now(UTC)
                db_session.commit()
                return AutomationResult(status="failed", message=run.detail, post_id=post.id)

        client = TwitterClient(dry_run=dry_run)
        if not client.is_configured() and not dry_run:
            run.status = "failed"
            run.detail = "Twitter credentials are not configured."
            run.updated_at = datetime.now(UTC)
            db_session.commit()
            return AutomationResult(status="failed", message=run.detail, post_id=post.id)

        run.post_id = post.id
        run.updated_at = datetime.now(UTC)
        db_session.commit()

        result = client.post_by_id(post.id, confirm=False, image_bytes=image_bytes, image_url=image_url)

        if result.get("status") == "posted":
            side_results = publish_side_platforms(content=post.content, image_url=post.media_path or image_url, dry_run=dry_run)
            run.status = "posted"
            run.detail = compose_publish_message("Quote post published", side_results)
            db_session.commit()
            return AutomationResult(
                status="posted",
                message=run.detail,
                post_id=post.id,
                url=result.get("url"),
            )

        if result.get("status") == "dry_run":
            run.status = "dry_run"
            run.detail = "Daily quote dry run completed."
            db_session.commit()
            return AutomationResult(status="dry_run", message=run.detail, post_id=post.id)

        run.status = "failed"
        run.detail = result.get("message") or "Unknown quote publish failure."
        db_session.commit()
        return AutomationResult(status="failed", message=run.detail, post_id=post.id)
    finally:
        db_session.close()
