import os
import tempfile
from datetime import datetime, timezone
from typing import Optional
import json
import requests

try:
    import tweepy
except ImportError:
    tweepy = None

from rich.console import Console
from rich.panel import Panel

from core.models import Post, PostStatus, get_session, init_db

UTC = timezone.utc
REQUEST_TIMEOUT = 30


class TwitterClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_secret: Optional[str] = None,
        bearer_token: Optional[str] = None,
        dry_run: bool = True
    ):
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        self.api_secret = api_secret or os.getenv("TWITTER_API_SECRET")
        self.access_token = access_token or os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_secret = access_secret or os.getenv("TWITTER_ACCESS_SECRET")
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")

        self.dry_run = dry_run
        self.console = Console()
        self.client = None
        self.api = None

        if not self.dry_run:
            self._init_client()

        init_db()
        self.session = get_session()

    def _init_client(self):
        if tweepy is None:
            raise ImportError("tweepy is required for Twitter integration")

        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            raise ValueError("Twitter API credentials not fully configured")

        self.client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
            bearer_token=self.bearer_token
        )

        auth = tweepy.OAuth1UserHandler(
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_secret
        )
        self.api = tweepy.API(auth)

    def is_configured(self) -> bool:
        return all([self.api_key, self.api_secret, self.access_token, self.access_secret])

    def verify_credentials(self) -> dict:
        if self.dry_run:
            return {"status": "dry_run", "message": "Running in dry-run mode"}

        if not self.client:
            return {"status": "error", "message": "Client not initialized"}

        try:
            me = self.client.get_me()
            return {
                "status": "ok",
                "username": me.data.username,
                "id": me.data.id,
                "name": me.data.name
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _upload_media(self, image_url: Optional[str] = None, image_bytes: Optional[bytes] = None, image_filename: str = "edgeofict.png"):
        if not self.api:
            raise ValueError("Twitter upload API is not initialized")

        if not image_url and not image_bytes:
            return None

        temp_path = None
        try:
            if image_bytes is None:
                response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                image_bytes = response.content

            suffix = os.path.splitext(image_filename)[1] or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(image_bytes)
                temp_path = handle.name

            media = self.api.media_upload(filename=temp_path)
            return getattr(media, "media_id_string", None) or getattr(media, "media_id", None)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def publish_content(
        self,
        text: str,
        *,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_filename: str = "edgeofict.png",
    ) -> dict:
        if len(text) > 280:
            return {"status": "error", "message": f"Tweet too long: {len(text)} chars"}

        if self.dry_run:
            return {
                "status": "dry_run",
                "message": "Dry run completed successfully",
                "content": text,
                "char_count": len(text),
                "has_media": bool(image_url or image_bytes),
            }

        payload = {"text": text}
        media_id = self._upload_media(image_url=image_url, image_bytes=image_bytes, image_filename=image_filename)
        if media_id:
            payload["media_ids"] = [media_id]

        result = self.client.create_tweet(**payload)
        return {
            "status": "posted",
            "tweet_id": result.data["id"],
            "url": f"https://x.com/edgeofict/status/{result.data['id']}",
        }

    def post_tweet(
        self,
        post: Post,
        confirm: bool = True,
        *,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
    ) -> dict:
        if post.platform != "twitter":
            return {"status": "error", "message": "Post is not for Twitter"}

        if len(post.content) > 280:
            return {"status": "error", "message": f"Tweet too long: {len(post.content)} chars"}

        self.console.print(Panel(
            post.content,
            title="[cyan]Tweet Preview[/cyan]",
            subtitle=f"[dim]{len(post.content)}/280 chars[/dim]"
        ))

        if self.dry_run:
            self.console.print("[yellow]DRY RUN - Tweet would be posted:[/yellow]")
            self.console.print(f"[dim]Content: {post.content}[/dim]")
            self.console.print(f"[dim]Timestamp: {datetime.now(UTC).isoformat()}[/dim]")

            return {
                "status": "dry_run",
                "message": "Dry run completed successfully",
                "content": post.content,
                "char_count": len(post.content)
            }

        if confirm:
            self.console.print("\n[yellow]About to post this tweet to @edgeofict[/yellow]")
            response = input("Type 'POST' to confirm: ")
            if response != "POST":
                self.console.print("[red]Cancelled[/red]")
                return {"status": "cancelled", "message": "User cancelled"}

        try:
            result = self.publish_content(
                post.content,
                image_url=image_url or post.media_path,
                image_bytes=image_bytes,
                image_filename=f"edgeofict-{post.id}.png",
            )
            if result.get("status") != "posted":
                post.status = PostStatus.FAILED.value
                self.session.commit()
                return result

            post.status = PostStatus.POSTED.value
            post.posted_time = datetime.now(UTC)
            post.post_id = str(result["tweet_id"])
            self.session.commit()

            self.console.print(f"[green]✓ Tweet posted successfully![/green]")
            self.console.print(f"[dim]Tweet ID: {result['tweet_id']}[/dim]")

            return result

        except Exception as e:
            post.status = PostStatus.FAILED.value
            self.session.commit()

            self.console.print(f"[red]Failed to post tweet: {e}[/red]")
            return {"status": "error", "message": str(e)}

    def post_by_id(
        self,
        post_id: int,
        confirm: bool = True,
        *,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
    ) -> dict:
        post = self.session.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"status": "error", "message": f"Post #{post_id} not found"}

        if post.status == PostStatus.POSTED.value:
            return {"status": "error", "message": "Post already published"}

        if post.status != PostStatus.APPROVED.value and not self.dry_run:
            return {"status": "error", "message": "Post must be approved before posting"}

        return self.post_tweet(post, confirm=confirm, image_url=image_url, image_bytes=image_bytes)

    def post_next_approved(self, confirm: bool = True) -> dict:
        post = self.session.query(Post).filter(
            Post.platform == "twitter",
            Post.status == PostStatus.APPROVED.value
        ).order_by(Post.scheduled_time.asc()).first()

        if not post:
            return {"status": "error", "message": "No approved posts available"}

        return self.post_tweet(post, confirm=confirm)

    def get_pending_posts(self, limit: int = 10) -> list[Post]:
        return self.session.query(Post).filter(
            Post.platform == "twitter",
            Post.status.in_([PostStatus.PENDING.value, PostStatus.APPROVED.value])
        ).order_by(Post.scheduled_time.asc()).limit(limit).all()

    def dry_run_all(self):
        posts = self.get_pending_posts()
        self.console.print(f"\n[cyan]Dry run for {len(posts)} pending posts:[/cyan]\n")

        for post in posts:
            self.console.print(f"[dim]Post #{post.id} - {post.status}[/dim]")
            self.post_tweet(post, confirm=False)
            self.console.print()
