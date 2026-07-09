import os
import tempfile

from core.content_extractor import ContentExtractor
from core.models import Base, Quote, get_engine, get_session
from core.quote_dedupe import normalize_quote_for_matching


def build_test_session():
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    database_url = f"sqlite:///{handle.name}"
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    return handle.name, session


def test_normalize_quote_for_matching_removes_post_extras():
    signature = normalize_quote_for_matching(
        '"Wait for confirmation, not comfort."\n\nTrack your edge.\n\n#ICT #SMC'
    )

    assert signature == "wait for confirmation not comfort"


def test_save_quotes_to_db_skips_normalized_duplicates():
    db_path, session = build_test_session()
    extractor = ContentExtractor.__new__(ContentExtractor)

    session.add(
        Quote(
            content="Wait for confirmation, not comfort.",
            source="Notes",
            topic="Discipline",
            quality_score=9.0,
            approved=True,
        )
    )
    session.commit()

    saved_count, saved_ids = extractor.save_quotes_to_db(
        [
            {
                "content": '"Wait for confirmation, not comfort."',
                "source": "Export",
                "topic": "Discipline",
                "quality_score": 8.4,
            },
            {
                "content": "Preserve capital while the story is unclear.",
                "source": "Export",
                "topic": "Risk Management",
                "quality_score": 8.7,
            },
            {
                "content": "Preserve capital while the story is unclear. #ICT",
                "source": "Export",
                "topic": "Risk Management",
                "quality_score": 8.2,
            },
        ],
        session=session,
        return_quote_ids=True,
    )

    assert saved_count == 1
    assert len(saved_ids) == 1
    assert session.query(Quote).count() == 2
    saved_quote = session.query(Quote).filter(Quote.id == saved_ids[0]).first()
    assert saved_quote.approved is True
    assert saved_quote.archived is False

    session.close()
    os.unlink(db_path)
