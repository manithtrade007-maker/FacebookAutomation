"""
Module 5 — Thumbnail Creator
Generates a click-worthy 1280x720 thumbnail using Pillow.
Fetches a background image from Pexels and overlays bold styled text.
"""

import os
import sys
import io
import requests
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PEXELS_API_KEY, OUTPUT_THUMBS

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
THUMB_W, THUMB_H = 1280, 720


def fetch_background_image(query: str) -> Image.Image:
    """Downloads a landscape photo from Pexels matching the query."""
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": "landscape"}

    try:
        response = requests.get(PEXELS_PHOTO_URL, headers=headers, params=params, timeout=10)
        photos = response.json().get("photos", [])
        if photos:
            photo_url = photos[0]["src"]["large2x"]
            img_data = requests.get(photo_url, timeout=15).content
            return Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as e:
        print(f"[Thumbnail] Could not fetch Pexels image: {e}")

    # fallback — dark gradient background
    img = Image.new("RGB", (THUMB_W, THUMB_H), color=(15, 15, 35))
    return img


def apply_dark_overlay(img: Image.Image, opacity: int = 140) -> Image.Image:
    """Darkens the background so text is readable."""
    img = img.resize((THUMB_W, THUMB_H)).filter(ImageFilter.GaussianBlur(2))
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.5)
    overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, opacity))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    return img


def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Loads a system font. Falls back to default if not found."""
    font_names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",    # macOS
        "/System/Library/Fonts/Helvetica.ttc",                  # macOS alt
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux
        "C:\\Windows\\Fonts\\arialbd.ttf",                      # Windows
    ]
    for font_path in font_names:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_text_with_shadow(draw: ImageDraw.Draw, text: str, position: tuple,
                           font: ImageFont.FreeTypeFont, text_color: tuple,
                           shadow_color: tuple = (0, 0, 0), shadow_offset: int = 3) -> None:
    """Draws text with a drop shadow for readability."""
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=text_color)


def create_thumbnail(title_text: str, topic: str, label: str = "output") -> str:
    """
    Main function — creates a thumbnail and saves it.
    Returns the file path to the saved JPG.
    """
    print(f"[Thumbnail] Creating thumbnail for: {title_text[:50]}")
    os.makedirs(OUTPUT_THUMBS, exist_ok=True)

    # fetch and prepare background
    bg = fetch_background_image(topic[:30])
    bg = apply_dark_overlay(bg, opacity=150)

    draw = ImageDraw.Draw(bg)

    # wrap text to fit within 1100px width
    font_large = get_font(72)
    font_small = get_font(36)

    wrapped = textwrap.wrap(title_text, width=22)

    # calculate total text block height to center it
    line_height = 85
    total_height = len(wrapped) * line_height
    start_y = (THUMB_H - total_height) // 2 - 20

    # draw each line centered
    for i, line in enumerate(wrapped):
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (THUMB_W - text_width) // 2
        y = start_y + (i * line_height)

        draw_text_with_shadow(
            draw, line, (x, y),
            font=font_large,
            text_color=(255, 255, 255),
            shadow_color=(0, 0, 0),
            shadow_offset=4,
        )

    # accent bar at bottom
    draw.rectangle([(0, THUMB_H - 8), (THUMB_W, THUMB_H)], fill=(255, 200, 0))

    # save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in "_-" else "" for c in label)[:30]
    filepath = os.path.join(OUTPUT_THUMBS, f"{timestamp}_{safe_label}.jpg")
    bg.save(filepath, "JPEG", quality=95)

    print(f"[Thumbnail] Saved: {filepath}")
    return filepath


if __name__ == "__main__":
    path = create_thumbnail(
        title_text="Why Every Programmer Needs AI in 2025",
        topic="programming artificial intelligence",
        label="test_thumbnail",
    )
    print(f"Thumbnail: {path}")
