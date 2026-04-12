from functools import lru_cache
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, UniqueConstraint, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os
import enum

Base = declarative_base()
UTC = timezone.utc


def utc_now():
    """Return current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class PostStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"
    FAILED = "failed"


class Quote(Base):
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True)
    content = Column(String(500), nullable=False)
    source = Column(String(200))
    topic = Column(String(100))
    quality_score = Column(Float, default=0.0, index=True)
    used_count = Column(Integer, default=0, index=True)
    last_used = Column(DateTime)
    approved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utc_now)

    def __repr__(self):
        return f"<Quote(id={self.id}, topic='{self.topic}', score={self.quality_score})>"


class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, index=True)
    platform = Column(String(50))
    content = Column(Text)
    media_path = Column(String(500))
    render_kind = Column(String(50))
    render_payload = Column(Text)
    scheduled_time = Column(DateTime, index=True)
    posted_time = Column(DateTime)
    status = Column(String(20), default=PostStatus.PENDING.value, index=True)
    post_id = Column(String(100))
    created_at = Column(DateTime, default=utc_now)
    approved_at = Column(DateTime)

    def __repr__(self):
        return f"<Post(id={self.id}, platform='{self.platform}', status='{self.status}')>"


class Analytics(Base):
    __tablename__ = 'analytics'

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, index=True)
    platform = Column(String(50))
    impressions = Column(Integer, default=0)
    engagements = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    fetched_at = Column(DateTime, default=utc_now)

    def __repr__(self):
        return f"<Analytics(post_id={self.post_id}, engagement_rate={self.engagement_rate})>"


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        UniqueConstraint("task_key", "run_date", name="uq_automation_runs_task_date"),
    )

    id = Column(Integer, primary_key=True)
    task_key = Column(String(100), nullable=False, index=True)
    run_date = Column(String(10), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="started", index=True)
    detail = Column(Text)
    post_id = Column(Integer, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now)

    def __repr__(self):
        return f"<AutomationRun(task_key='{self.task_key}', run_date='{self.run_date}', status='{self.status}')>"


def resolve_db_url(db_url=None):
    """Resolve the database URL, normalizing hosted provider formats."""
    if db_url:
        return db_url.replace("postgres://", "postgresql://", 1)

    env_url = os.getenv('DATABASE_URL')
    if env_url:
        return env_url.replace("postgres://", "postgresql://", 1)

    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'quotes.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite:///{db_path}"


@lru_cache(maxsize=8)
def _build_engine(db_url: str):
    engine_kwargs = {
        "pool_pre_ping": True,
    }

    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(db_url, **engine_kwargs)


def get_engine(db_url=None):
    return _build_engine(resolve_db_url(db_url))


def get_session(engine=None):
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def init_db(engine=None):
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_runtime_schema(engine)
    return engine


def ensure_runtime_schema(engine):
    """Apply lightweight additive schema changes for hosted deployments."""
    inspector = inspect(engine)

    if "posts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("posts")}
    statements = []

    if "render_kind" not in existing_columns:
        statements.append("ALTER TABLE posts ADD COLUMN render_kind VARCHAR(50)")
    if "render_payload" not in existing_columns:
        statements.append("ALTER TABLE posts ADD COLUMN render_payload TEXT")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
