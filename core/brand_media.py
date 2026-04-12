"""Server-side branded media rendering for quotes and Stoic cards."""

from __future__ import annotations

import base64
import re
from io import BytesIO
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

QUOTE_SIZE = (1080, 1080)
STOIC_SIZE = (1080, 1350)

FONT_PATHS = {
    "sans_regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "sans_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "serif_regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Georgia.ttf",
    ],
    "serif_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ],
    "serif_italic": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
        "/Library/Fonts/Georgia Italic.ttf",
    ],
    "mono_bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
        "/Library/Fonts/Courier New Bold.ttf",
    ],
}


@lru_cache(maxsize=64)
def load_font(style: str, size: int):
    for path in FONT_PATHS.get(style, []):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def png_data_uri(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def normalize_quote_text(content: str) -> str:
    cleaned = (content or "").replace("\u2019", "'").replace("\u2014", "-")
    cleaned = re.sub(r"#\w+", "", cleaned)
    cleaned = re.sub(r"Track your edge\.?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip('"').strip()
    return cleaned or "Track your edge."


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def fit_wrapped_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    style: str,
    max_width: int,
    max_height: int,
    starting_size: int,
    min_size: int,
    line_gap: int,
):
    for size in range(starting_size, min_size - 1, -2):
        font = load_font(style, size)
        lines = wrap_text(draw, text, font, max_width)
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_height = (bbox[3] - bbox[1]) + line_gap
        total_height = max(1, len(lines)) * line_height - line_gap
        if total_height <= max_height:
            return font, lines, line_height

    font = load_font(style, min_size)
    lines = wrap_text(draw, text, font, max_width)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return font, lines, (bbox[3] - bbox[1]) + line_gap


def draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    center_x: int,
    y: int,
    font,
    fill: str,
    line_height: int,
):
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        draw.text((center_x - line_width / 2, y), line, font=font, fill=fill)
        y += line_height
    return y


def add_letter_spacing(text: str, spacing: int = 1) -> str:
    return (text or "").upper()


def render_quote_card(content: str) -> bytes:
    quote_text = normalize_quote_text(content)
    image = Image.new("RGB", QUOTE_SIZE, "#0f231c")
    draw = ImageDraw.Draw(image)
    width, height = image.size

    for x in range(26, width, 58):
        for y in range(26, height, 58):
            draw.ellipse((x, y, x + 2, y + 2), fill="#1c4338")

    card_bounds = (108, 186, width - 108, height - 188)
    draw.rounded_rectangle(card_bounds, radius=36, fill="#203a31")
    draw.rounded_rectangle((card_bounds[0], card_bounds[1], card_bounds[2], card_bounds[1] + 5), radius=4, fill="#c8a13a")

    text_width = int(card_bounds[2] - card_bounds[0] - 176)
    max_text_height = 360
    font, lines, line_height = fit_wrapped_font(
        draw,
        quote_text,
        style="serif_regular",
        max_width=text_width,
        max_height=max_text_height,
        starting_size=62,
        min_size=40,
        line_gap=14,
    )
    text_height = max(1, len(lines)) * line_height - 14
    quote_start_y = int((card_bounds[1] + card_bounds[3]) / 2 - text_height / 2 - 34)
    draw_centered_lines(
        draw,
        lines,
        center_x=width // 2,
        y=quote_start_y,
        font=font,
        fill="#f5efe4",
        line_height=line_height,
    )

    signature_font = load_font("sans_bold", 32)
    signature_text = "Track your edge."
    signature_box = draw.textbbox((0, 0), signature_text, font=signature_font)
    draw.text(
        ((width - (signature_box[2] - signature_box[0])) / 2, card_bounds[3] - 138),
        signature_text,
        font=signature_font,
        fill="#c8a13a",
    )

    brand_font = load_font("mono_bold", 18)
    brand_text = "EDGEOFICT.COM"
    brand_box = draw.textbbox((0, 0), brand_text, font=brand_font)
    draw.text(
        ((width - (brand_box[2] - brand_box[0])) / 2, height - 110),
        brand_text,
        font=brand_font,
        fill="#b8902a",
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_stoic_card(payload: dict) -> bytes:
    image = Image.new("RGB", STOIC_SIZE, "#090909")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    center_x = width // 2

    card_bounds = (90, 120, width - 90, height - 120)
    draw.rounded_rectangle(card_bounds, radius=28, fill="#111111", outline="#1b1b1b", width=2)

    date_text = add_letter_spacing(payload.get("date", ""), spacing=1)
    author_text = add_letter_spacing(payload.get("author", ""), spacing=1)
    title_text = payload.get("title", "") or "Daily Stoic"

    y = 196

    date_font = load_font("serif_regular", 18)
    date_box = draw.textbbox((0, 0), date_text, font=date_font)
    draw.text(((width - (date_box[2] - date_box[0])) / 2, y), date_text, font=date_font, fill="#57514a")
    y += 48

    author_font = load_font("serif_bold", 24)
    author_box = draw.textbbox((0, 0), author_text, font=author_font)
    draw.text(((width - (author_box[2] - author_box[0])) / 2, y), author_text, font=author_font, fill="#c45a3b")
    y += 52

    title_font, title_lines, title_height = fit_wrapped_font(
        draw,
        title_text,
        style="serif_italic",
        max_width=620,
        max_height=120,
        starting_size=54,
        min_size=34,
        line_gap=10,
    )
    title_block_height = max(1, len(title_lines)) * title_height - 10
    draw_centered_lines(
        draw,
        title_lines,
        center_x=center_x,
        y=y,
        font=title_font,
        fill="#ece8e2",
        line_height=title_height,
    )
    y += title_block_height + 44

    draw.line((center_x - 250, y, center_x + 250, y), fill="#2c2a28", width=1)
    y += 62

    points = [
        ("1", payload.get("point1_title", ""), payload.get("point1_meaning", ""), payload.get("point1_trading", "")),
        ("2", payload.get("point2_title", ""), payload.get("point2_meaning", ""), payload.get("point2_trading", "")),
        ("3", payload.get("point3_title", ""), payload.get("point3_meaning", ""), payload.get("point3_trading", "")),
    ]

    title_font = load_font("serif_bold", 28)
    meaning_font = load_font("serif_italic", 20)
    trading_font = load_font("serif_regular", 24)

    for number, title, meaning, trading in points:
        title_lines = wrap_text(draw, f"{number}. {title}", title_font, 640)
        y = draw_centered_lines(
            draw,
            title_lines,
            center_x=center_x,
            y=y,
            font=title_font,
            fill="#c45a3b",
            line_height=34,
        )
        y += 6

        meaning_lines = wrap_text(draw, meaning, meaning_font, 640)
        y = draw_centered_lines(
            draw,
            meaning_lines,
            center_x=center_x,
            y=y,
            font=meaning_font,
            fill="#7a746d",
            line_height=28,
        )
        y += 10

        trading_lines = wrap_text(draw, trading, trading_font, 680)
        y = draw_centered_lines(
            draw,
            trading_lines,
            center_x=center_x,
            y=y,
            font=trading_font,
            fill="#e6e1da",
            line_height=34,
        )
        y += 38

    draw.line((center_x - 280, y, center_x + 280, y), fill="#242220", width=1)
    y += 44

    wisdom_font = load_font("serif_italic", 22)
    wisdom_lines = wrap_text(draw, payload.get("closing_wisdom", ""), wisdom_font, 700)
    y = draw_centered_lines(
        draw,
        wisdom_lines,
        center_x=center_x,
        y=y,
        font=wisdom_font,
        fill="#7a746d",
        line_height=32,
    )
    y += 28

    takeaway_font = load_font("serif_bold", 28)
    takeaway_lines = wrap_text(draw, payload.get("key_takeaway", ""), takeaway_font, 660)
    y = draw_centered_lines(
        draw,
        takeaway_lines,
        center_x=center_x,
        y=y,
        font=takeaway_font,
        fill="#c45a3b",
        line_height=36,
    )
    y += 42

    cta_font = load_font("serif_italic", 20)
    cta_text = "Track your edge."
    cta_box = draw.textbbox((0, 0), cta_text, font=cta_font)
    draw.text(((width - (cta_box[2] - cta_box[0])) / 2, y), cta_text, font=cta_font, fill="#66605a")
    y += 34

    brand_font = load_font("mono_bold", 18)
    brand_text = "EDGEOFICT.COM"
    brand_box = draw.textbbox((0, 0), brand_text, font=brand_font)
    draw.text(((width - (brand_box[2] - brand_box[0])) / 2, y), brand_text, font=brand_font, fill="#ece8e2")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
