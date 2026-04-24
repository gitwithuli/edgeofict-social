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


def ellipsize_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if not cleaned:
        return ""
    if draw.textlength(cleaned, font=font) <= max_width:
        return cleaned

    suffix = "..."
    if draw.textlength(suffix, font=font) > max_width:
        return ""

    candidate = cleaned
    while candidate:
        candidate = candidate[:-1].rstrip()
        shortened = f"{candidate}{suffix}"
        if draw.textlength(shortened, font=font) <= max_width:
            return shortened

    return suffix


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    *,
    max_lines: int | None = None,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for index, word in enumerate(words[1:], start=1):
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if max_lines and len(lines) >= max_lines - 1:
                remainder = " ".join([current, word, *words[index + 1 :]])
                lines.append(ellipsize_text(draw, remainder, font, max_width))
                return lines
            lines.append(current)
            current = word if draw.textlength(word, font=font) <= max_width else ellipsize_text(draw, word, font, max_width)

    lines.append(current)
    if max_lines and len(lines) > max_lines:
        overflow = " ".join(lines[max_lines - 1 :])
        lines = lines[: max_lines - 1] + [ellipsize_text(draw, overflow, font, max_width)]
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
    max_lines: int | None = None,
):
    for size in range(starting_size, min_size - 1, -2):
        font = load_font(style, size)
        lines = wrap_text(draw, text, font, max_width, max_lines=max_lines)
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_height = (bbox[3] - bbox[1]) + line_gap
        total_height = max(1, len(lines)) * line_height - line_gap
        if total_height <= max_height:
            return font, lines, line_height

    font = load_font(style, min_size)
    lines = wrap_text(draw, text, font, max_width, max_lines=max_lines)
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


def draw_left_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font,
    fill: str,
    line_height: int,
):
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def fit_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    style: str,
    max_width: int,
    max_height: int,
    starting_size: int,
    min_size: int,
    line_gap: int,
    max_lines: int | None = None,
):
    cleaned = (text or "").strip()
    if not cleaned:
        font = load_font(style, max(min_size, starting_size))
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        return {
            "font": font,
            "lines": [],
            "line_height": (bbox[3] - bbox[1]) + line_gap,
            "height": 0,
        }

    font, lines, line_height = fit_wrapped_font(
        draw,
        cleaned,
        style=style,
        max_width=max_width,
        max_height=max_height,
        starting_size=starting_size,
        min_size=min_size,
        line_gap=line_gap,
        max_lines=max_lines,
    )
    return {
        "font": font,
        "lines": lines,
        "line_height": line_height,
        "height": max(1, len(lines)) * line_height - line_gap,
    }


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

    for x in range(26, width, 54):
        for y in range(26, height, 54):
            draw.ellipse((x, y, x + 2, y + 2), fill="#131313")

    card_bounds = (72, 92, width - 72, height - 92)
    draw.rounded_rectangle(card_bounds, radius=36, fill="#111111", outline="#1b1b1b", width=2)
    draw.rounded_rectangle((card_bounds[0], card_bounds[1], card_bounds[2], card_bounds[1] + 4), radius=4, fill="#c45a3b")

    inner_left = card_bounds[0] + 54
    inner_right = card_bounds[2] - 54
    inner_top = card_bounds[1] + 52
    inner_bottom = card_bounds[3] - 50
    content_width = inner_right - inner_left
    available_height = inner_bottom - inner_top

    date_text = add_letter_spacing(payload.get("date", ""), spacing=1)
    author_text = add_letter_spacing(payload.get("author", ""), spacing=1)
    title_text = payload.get("title", "") or "Daily Stoic"
    points = [
        ("1", payload.get("point1_title", ""), payload.get("point1_meaning", ""), payload.get("point1_trading", "")),
        ("2", payload.get("point2_title", ""), payload.get("point2_meaning", ""), payload.get("point2_trading", "")),
        ("3", payload.get("point3_title", ""), payload.get("point3_meaning", ""), payload.get("point3_trading", "")),
    ]

    layout = None
    for scale in (1.0, 0.94, 0.88, 0.82, 0.76, 0.7, 0.64, 0.58, 0.54):
        date_font = load_font("sans_regular", max(14, int(18 * scale)))
        author_font = load_font("serif_bold", max(20, int(28 * scale)))

        if date_text:
            date_box = draw.textbbox((0, 0), "Ag", font=date_font)
            date_height = date_box[3] - date_box[1]
        else:
            date_height = 0

        if author_text:
            author_box = draw.textbbox((0, 0), "Ag", font=author_font)
            author_height = author_box[3] - author_box[1]
        else:
            author_height = 0

        title_block = fit_text_block(
            draw,
            title_text,
            style="serif_italic",
            max_width=int(content_width * 0.8),
            max_height=int(172 * scale),
            starting_size=max(34, int(58 * scale)),
            min_size=max(26, int(36 * scale)),
            line_gap=max(8, int(12 * scale)),
            max_lines=3,
        )

        header_height = 0
        if date_text:
            header_height += date_height + int(18 * scale)
        if author_text:
            header_height += author_height + int(22 * scale)
        header_height += title_block["height"] + int(28 * scale) + 1 + int(30 * scale)

        block_gap = int(18 * scale)
        block_pad_x = int(32 * scale)
        block_pad_y = int(24 * scale)
        accent_width = max(6, int(8 * scale))
        badge_size = int(42 * scale)
        badge_gap = int(16 * scale)
        title_area_width = content_width - (block_pad_x * 2) - badge_size - badge_gap
        body_width = content_width - (block_pad_x * 2)

        point_blocks = []
        for number, title, meaning, trading in points:
            point_title = fit_text_block(
                draw,
                title or f"Point {number}",
                style="serif_bold",
                max_width=max(220, title_area_width),
                max_height=int(88 * scale),
                starting_size=max(24, int(34 * scale)),
                min_size=max(20, int(24 * scale)),
                line_gap=max(5, int(7 * scale)),
                max_lines=2,
            )
            point_meaning = fit_text_block(
                draw,
                meaning,
                style="serif_italic",
                max_width=max(220, body_width),
                max_height=int(46 * scale),
                starting_size=max(16, int(20 * scale)),
                min_size=max(14, int(16 * scale)),
                line_gap=max(3, int(4 * scale)),
                max_lines=2,
            )
            point_trading = fit_text_block(
                draw,
                trading,
                style="serif_regular",
                max_width=max(240, body_width),
                max_height=int(98 * scale),
                starting_size=max(20, int(28 * scale)),
                min_size=max(18, int(20 * scale)),
                line_gap=max(6, int(8 * scale)),
                max_lines=3,
            )

            block_height = block_pad_y + max(badge_size, point_title["height"])
            if point_meaning["height"]:
                block_height += int(10 * scale) + point_meaning["height"]
            if point_trading["height"]:
                block_height += int(12 * scale) + point_trading["height"]
            block_height += block_pad_y

            point_blocks.append(
                {
                    "number": number,
                    "title": point_title,
                    "meaning": point_meaning,
                    "trading": point_trading,
                    "height": block_height,
                    "badge_size": badge_size,
                    "badge_gap": badge_gap,
                    "block_pad_x": block_pad_x,
                    "block_pad_y": block_pad_y,
                    "accent_width": accent_width,
                }
            )

        wisdom_block = fit_text_block(
            draw,
            payload.get("closing_wisdom", ""),
            style="serif_italic",
            max_width=int(content_width * 0.84),
            max_height=int(94 * scale),
            starting_size=max(18, int(24 * scale)),
            min_size=max(16, int(18 * scale)),
            line_gap=max(6, int(8 * scale)),
            max_lines=3,
        )
        takeaway_block = fit_text_block(
            draw,
            payload.get("key_takeaway", ""),
            style="serif_bold",
            max_width=int(content_width * 0.76),
            max_height=int(84 * scale),
            starting_size=max(24, int(34 * scale)),
            min_size=max(20, int(24 * scale)),
            line_gap=max(6, int(8 * scale)),
            max_lines=2,
        )

        cta_font = load_font("serif_italic", max(18, int(20 * scale)))
        brand_font = load_font("mono_bold", max(14, int(18 * scale)))
        cta_box = draw.textbbox((0, 0), "Ag", font=cta_font)
        brand_box = draw.textbbox((0, 0), "Ag", font=brand_font)
        cta_height = cta_box[3] - cta_box[1]
        brand_height = brand_box[3] - brand_box[1]
        takeaway_box_height = takeaway_block["height"] + int(30 * scale)

        footer_height = (
            1
            + int(28 * scale)
            + wisdom_block["height"]
            + int(22 * scale)
            + takeaway_box_height
            + int(24 * scale)
            + cta_height
            + int(10 * scale)
            + brand_height
        )

        total_height = header_height + footer_height + sum(block["height"] for block in point_blocks) + (len(point_blocks) - 1) * block_gap

        layout = {
            "scale": scale,
            "date_font": date_font,
            "author_font": author_font,
            "title": title_block,
            "points": point_blocks,
            "wisdom": wisdom_block,
            "takeaway": takeaway_block,
            "cta_font": cta_font,
            "brand_font": brand_font,
            "block_gap": block_gap,
            "takeaway_box_height": takeaway_box_height,
            "total_height": total_height,
        }
        if total_height <= available_height:
            break

    y = inner_top + max(0, int((available_height - layout["total_height"]) / 2))

    if date_text:
        date_box = draw.textbbox((0, 0), date_text, font=layout["date_font"])
        draw.text(((width - (date_box[2] - date_box[0])) / 2, y), date_text, font=layout["date_font"], fill="#5f5850")
        y += (date_box[3] - date_box[1]) + int(18 * layout["scale"])

    if author_text:
        author_box = draw.textbbox((0, 0), author_text, font=layout["author_font"])
        draw.text(((width - (author_box[2] - author_box[0])) / 2, y), author_text, font=layout["author_font"], fill="#c45a3b")
        y += (author_box[3] - author_box[1]) + int(22 * layout["scale"])

    draw_centered_lines(
        draw,
        layout["title"]["lines"],
        center_x=center_x,
        y=y,
        font=layout["title"]["font"],
        fill="#ece8e2",
        line_height=layout["title"]["line_height"],
    )
    y += layout["title"]["height"] + int(28 * layout["scale"])

    draw.line((inner_left + 64, y, inner_right - 64, y), fill="#2c2a28", width=1)
    y += int(30 * layout["scale"])

    number_font = load_font("sans_bold", max(16, int(18 * layout["scale"])))
    for index, point in enumerate(layout["points"]):
        block_top = y
        block_bottom = y + point["height"]
        draw.rounded_rectangle((inner_left, block_top, inner_right, block_bottom), radius=26, fill="#141313", outline="#262321", width=1)
        draw.rounded_rectangle(
            (inner_left, block_top + 1, inner_left + point["accent_width"], block_bottom - 1),
            radius=4,
            fill="#c45a3b",
        )

        badge_left = inner_left + point["block_pad_x"]
        badge_top = block_top + point["block_pad_y"]
        badge_right = badge_left + point["badge_size"]
        badge_bottom = badge_top + point["badge_size"]
        draw.rounded_rectangle((badge_left, badge_top, badge_right, badge_bottom), radius=point["badge_size"] / 2, fill="#1d1714", outline="#5d3023", width=1)

        number_box = draw.textbbox((0, 0), point["number"], font=number_font)
        number_x = badge_left + (point["badge_size"] - (number_box[2] - number_box[0])) / 2
        number_y = badge_top + (point["badge_size"] - (number_box[3] - number_box[1])) / 2 - 1
        draw.text((number_x, number_y), point["number"], font=number_font, fill="#ece8e2")

        title_x = badge_right + point["badge_gap"]
        title_y = block_top + point["block_pad_y"] + max(0, int((point["badge_size"] - point["title"]["height"]) / 2))
        draw_left_lines(
            draw,
            point["title"]["lines"],
            x=title_x,
            y=title_y,
            font=point["title"]["font"],
            fill="#c45a3b",
            line_height=point["title"]["line_height"],
        )

        body_x = inner_left + point["block_pad_x"]
        body_y = block_top + point["block_pad_y"] + max(point["badge_size"], point["title"]["height"])
        if point["meaning"]["height"]:
            body_y += int(10 * layout["scale"])
            draw_left_lines(
                draw,
                point["meaning"]["lines"],
                x=body_x,
                y=body_y,
                font=point["meaning"]["font"],
                fill="#7a746d",
                line_height=point["meaning"]["line_height"],
            )
            body_y += point["meaning"]["height"]

        if point["trading"]["height"]:
            body_y += int(12 * layout["scale"])
            draw_left_lines(
                draw,
                point["trading"]["lines"],
                x=body_x,
                y=body_y,
                font=point["trading"]["font"],
                fill="#ece8e2",
                line_height=point["trading"]["line_height"],
            )

        y = block_bottom
        if index < len(layout["points"]) - 1:
            y += layout["block_gap"]

    y += int(10 * layout["scale"])
    draw.line((inner_left + 48, y, inner_right - 48, y), fill="#242220", width=1)
    y += int(28 * layout["scale"])

    draw_centered_lines(
        draw,
        layout["wisdom"]["lines"],
        center_x=center_x,
        y=y,
        font=layout["wisdom"]["font"],
        fill="#7a746d",
        line_height=layout["wisdom"]["line_height"],
    )
    y += layout["wisdom"]["height"] + int(22 * layout["scale"])

    takeaway_left = inner_left + int(34 * layout["scale"])
    takeaway_right = inner_right - int(34 * layout["scale"])
    draw.rounded_rectangle(
        (takeaway_left, y, takeaway_right, y + layout["takeaway_box_height"]),
        radius=26,
        fill="#16110e",
        outline="#4f2b20",
        width=1,
    )

    takeaway_y = y + int((layout["takeaway_box_height"] - layout["takeaway"]["height"]) / 2)
    draw_centered_lines(
        draw,
        layout["takeaway"]["lines"],
        center_x=center_x,
        y=takeaway_y,
        font=layout["takeaway"]["font"],
        fill="#c45a3b",
        line_height=layout["takeaway"]["line_height"],
    )
    y += layout["takeaway_box_height"] + int(24 * layout["scale"])

    cta_text = "Track your edge."
    cta_box = draw.textbbox((0, 0), cta_text, font=layout["cta_font"])
    draw.text(((width - (cta_box[2] - cta_box[0])) / 2, y), cta_text, font=layout["cta_font"], fill="#66605a")
    y += (cta_box[3] - cta_box[1]) + int(10 * layout["scale"])

    brand_text = "EDGEOFICT.COM"
    brand_box = draw.textbbox((0, 0), brand_text, font=layout["brand_font"])
    draw.text(((width - (brand_box[2] - brand_box[0])) / 2, y), brand_text, font=layout["brand_font"], fill="#ece8e2")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
