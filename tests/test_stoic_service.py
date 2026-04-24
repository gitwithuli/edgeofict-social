from core.stoic_service import normalize_stoic_content


def test_normalize_stoic_content_clamps_fields():
    payload = normalize_stoic_content(
        {
            "point1_title": "Self Awareness Under Pressure And Noise",
            "point1_meaning": "Know your thoughts emotions reactions habits impulses and blind spots before they run your decision making.",
            "point1_trading": "Recognize the emotional trigger before it starts dictating entries exits revenge trades and oversized positions.",
            "closing_wisdom": "The trader who cannot govern himself will keep handing control to the market, the feed, and the last candle.",
            "key_takeaway": "Master yourself before you master the markets and before the markets embarrass you again.",
            "tweet": "A" * 280,
        }
    )

    assert len(payload["point1_title"].split()) <= 4
    assert len(payload["point1_meaning"].split()) <= 10
    assert len(payload["point1_trading"].split()) <= 12
    assert len(payload["closing_wisdom"].split()) <= 20
    assert len(payload["key_takeaway"].split()) <= 10
    assert len(payload["tweet"]) <= 250
