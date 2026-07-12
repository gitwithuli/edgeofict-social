from core.hashtag_selector import (
    sanitize_caption_for_platform,
    select_hashtags,
)
from core.post_planner import build_quote_post_text


def test_x_hashtag_examples():
    examples = [
        (
            "If a new trader is met with high-resistance conditions in the marketplace, it tends to create very sporadic emotional responses in their psyche. They become agitated.",
            ["#TradingPsychology"],
        ),
        ("Price trades into a fair value gap after displacement.", ["#FairValueGap"]),
        ("Price swept sell-side liquidity before expanding higher.", ["#Liquidity"]),
        ("Protecting capital is more important than catching every move.", ["#RiskManagement"]),
        ("NQ futures took the overnight low before repricing higher.", ["#NQFutures"]),
        ("Consistency comes from understanding your model.", []),
    ]

    for text, expected in examples:
        assert select_hashtags("x", text).hashtags == expected


def test_x_caption_never_appends_legacy_bundle():
    caption = build_quote_post_text("Price trades into a fair value gap after displacement.")

    assert "#FairValueGap" in caption
    assert "#ICT #SMC #NQ #ES #Trading" not in caption
    assert caption.count("#") == 1
    assert len(caption) <= 280


def test_instagram_uses_contextual_niche_hashtags():
    caption = sanitize_caption_for_platform(
        "instagram",
        '"Price swept sell-side liquidity before expanding higher."\n\nTrack your edge.\n\n#ICT #SMC #NQ #ES #Trading',
        source_text="Price swept sell-side liquidity before expanding higher.",
    )

    assert "#Liquidity" in caption
    assert "#LiquiditySweep" in caption
    assert "#Trading" not in caption
    assert 3 <= caption.count("#") <= 5


def test_linkedin_uses_professional_contextual_tags():
    caption = sanitize_caption_for_platform(
        "linkedin",
        "Protecting capital is more important than catching every move. #ICT #Trading",
    )

    assert "#RiskManagement" in caption
    assert "#TradingEducation" in caption
    assert "#Trading " not in f"{caption} "
    assert caption.count("#") <= 3


def test_low_confidence_fallbacks_are_platform_specific():
    text = "Consistency comes from understanding your model."

    assert select_hashtags("x", text).hashtags == []
    assert select_hashtags("instagram", text).hashtags == ["#ICTTrading", "#FuturesTrading", "#PriceAction"]
    assert select_hashtags("linkedin", text).hashtags == []


def test_event_hashtags_take_priority_when_event_is_the_point():
    decision = select_hashtags(
        "x",
        "FOMC created the volatility risk; the setup needed to be planned before the release.",
    )

    assert decision.selected_category == "fomc"
    assert decision.hashtags == ["#FOMC"]


def test_market_hashtags_do_not_come_from_metadata_only():
    decision = select_hashtags(
        "x",
        "Consistency comes from understanding your model.",
        supporting_text="NQ ES account metadata",
    )

    assert decision.hashtags == []


def test_sanitizer_removes_ai_legacy_bundle_and_reclassifies():
    caption = sanitize_caption_for_platform(
        "x",
        '"Protecting capital is more important than catching every move."\n\nTrack your edge.\n\n#ICT #SMC #NQ #ES #Trading',
    )

    assert "#ICT #SMC #NQ #ES #Trading" not in caption
    assert "#RiskManagement" in caption
    assert caption.count("#") == 1
    assert len(caption) <= 280
