from io import BytesIO

from PIL import Image, ImageDraw

from core import brand_media


def test_fit_text_block_respects_max_lines():
    image = Image.new("RGB", (800, 800), "#000000")
    draw = ImageDraw.Draw(image)

    block = brand_media.fit_text_block(
        draw,
        "The markets reward patience, discipline, and the ability to wait far longer than your emotions want you to.",
        style="serif_regular",
        max_width=260,
        max_height=120,
        starting_size=34,
        min_size=20,
        line_gap=6,
        max_lines=2,
    )

    assert len([line for line in block["lines"] if line]) <= 2
    assert block["lines"][-1].endswith("...")


def test_render_stoic_card_handles_long_payload():
    image_bytes = brand_media.render_stoic_card(
        {
            "date": "April 22",
            "author": "Marcus Aurelius",
            "title": "The Marks Of A Rational Person Who Studies Himself Before He Studies The Crowd",
            "point1_title": "Self-Awareness Under Pressure",
            "point1_meaning": "Know your thoughts, emotions, and reactions deeply before they run the day.",
            "point1_trading": "Recognize the emotional trigger before it starts dictating entries, exits, or revenge decisions.",
            "point2_title": "Self-Examination Without Excuses",
            "point2_meaning": "Critically analyze your decisions and their outcomes with honesty.",
            "point2_trading": "Review every trade objectively, then separate a good process from a lucky result or a bad habit.",
            "point3_title": "Self-Determination Over Noise",
            "point3_meaning": "Make decisions based on reason, not external influence or crowd pressure.",
            "point3_trading": "Execute your plan independently of market noise, online sentiment, and the fear of missing out.",
            "closing_wisdom": "The rational trader harvests wisdom from self-knowledge, not from market predictions or crowd emotion.",
            "key_takeaway": "Master yourself before you master the markets.",
        }
    )

    image = Image.open(BytesIO(image_bytes))

    assert image.format == "PNG"
    assert image.size == brand_media.STOIC_SIZE
