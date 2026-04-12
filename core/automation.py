from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .models import AutomationRun, Post, PostStatus, get_session, init_db
from . import stoic_service
from integrations.twitter_client import TwitterClient

UTC = timezone.utc
DEFAULT_TASK_KEY = "daily_stoic"


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
    return now_local.hour == run_hour


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

        if not should_run_for_hour(run_hour, now_local):
            return AutomationResult(
                status="skipped",
                message=f"Current local hour is {now_local.hour}; target hour is {run_hour}.",
            )

        existing_run = (
            db_session.query(AutomationRun)
            .filter(
                AutomationRun.task_key == DEFAULT_TASK_KEY,
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

        run = (
            db_session.query(AutomationRun)
            .filter(
                AutomationRun.task_key == DEFAULT_TASK_KEY,
                AutomationRun.run_date == run_date,
            )
            .first()
        )
        if run is None:
            run = AutomationRun(
                task_key=DEFAULT_TASK_KEY,
                run_date=run_date,
                status="started",
                detail="Preparing Stoic post.",
            )
            db_session.add(run)
            db_session.flush()
        else:
            run.status = "started"
            run.detail = "Retrying Stoic post."
            run.updated_at = datetime.now(UTC)

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

        post = Post(
            platform="twitter",
            content=tweet,
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

        result = client.post_by_id(post.id, confirm=False)
        run.updated_at = datetime.now(UTC)

        if result.get("status") == "posted":
            run.status = "posted"
            run.detail = result.get("url") or "Stoic post published."
            db_session.commit()
            return AutomationResult(
                status="posted",
                message="Daily Stoic published successfully.",
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
