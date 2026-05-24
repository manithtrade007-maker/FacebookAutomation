"""
Module 4 — Video Builder
Assembles the final MP4 by combining:
  - Stock footage from Pexels API
  - Voiceover audio (MP3)
  - Branded intro + outro
Uses MoviePy 2.x + FFmpeg.
"""

import os
import sys
import random
import requests
from datetime import datetime
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip,
    CompositeVideoClip, concatenate_videoclips, ColorClip,
)
from moviepy.video.fx import FadeIn, FadeOut

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PEXELS_API_KEY, OUTPUT_VIDEOS, ASSETS_DIR,
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
)

PEXELS_BASE_URL = "https://api.pexels.com/videos"
TEMP_DIR = os.path.join(OUTPUT_VIDEOS, "_temp")


def fetch_stock_videos(query: str, count: int = 5) -> list[str]:
    """Downloads stock videos from Pexels matching the query."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": count, "orientation": "landscape", "size": "medium"}

    response = requests.get(f"{PEXELS_BASE_URL}/search", headers=headers, params=params, timeout=15)
    if response.status_code != 200:
        print(f"[VideoBuilder] Pexels error: {response.status_code}")
        return []

    videos = response.json().get("videos", [])
    paths = []

    for i, video in enumerate(videos):
        files = video.get("video_files", [])
        hd_files = [f for f in files if f.get("height", 0) >= 720]
        if not hd_files:
            hd_files = files
        if not hd_files:
            continue

        file_url = hd_files[0]["link"]
        filepath = os.path.join(TEMP_DIR, f"stock_{i}.mp4")

        print(f"[VideoBuilder] Downloading clip {i+1}/{len(videos)}...")
        r = requests.get(file_url, stream=True, timeout=60)
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        paths.append(filepath)

    return paths


def build_intro(title: str, duration: float = 3.0) -> CompositeVideoClip:
    """Simple branded intro card."""
    bg = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(15, 15, 35), duration=duration)
    txt = (
        TextClip(
            text=title, font_size=52, color="white", font="Arial",
            method="caption", size=(VIDEO_WIDTH - 80, None),
            text_align="center",
        )
        .with_duration(duration)
        .with_position("center")
    )
    clip = CompositeVideoClip([bg, txt])
    return clip.with_effects([FadeIn(0.5), FadeOut(0.5)])


def build_outro(duration: float = 4.0) -> CompositeVideoClip:
    """Simple outro with CTA."""
    bg = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(15, 15, 35), duration=duration)
    cta = (
        TextClip(
            text="Like & Follow for more!", font_size=56, color="#FFD700",
            font="Arial", method="caption", size=(VIDEO_WIDTH - 80, None),
            text_align="center",
        )
        .with_duration(duration)
        .with_position(("center", 0.38), relative=True)
    )
    sub = (
        TextClip(
            text="Turn on notifications so you never miss a video",
            font_size=32, color="white", font="Arial",
            method="caption", size=(VIDEO_WIDTH - 80, None),
            text_align="center",
        )
        .with_duration(duration)
        .with_position(("center", 0.58), relative=True)
    )
    clip = CompositeVideoClip([bg, cta, sub])
    return clip.with_effects([FadeIn(0.5)])


def assemble_video(audio_path: str, topic: str, title: str,
                   search_query: str = None) -> str:
    """
    Main function — builds the final MP4.
    Returns path to final video file.
    """
    print(f"[VideoBuilder] Assembling video: {title[:50]}")
    os.makedirs(OUTPUT_VIDEOS, exist_ok=True)

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[VideoBuilder] Audio duration: {total_duration:.1f}s")

    query = search_query or topic[:30]
    stock_paths = fetch_stock_videos(query, count=6)

    if not stock_paths:
        print("[VideoBuilder] No stock footage — using solid background.")
        body = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 40), duration=total_duration)
    else:
        clips = []
        for p in stock_paths:
            try:
                clip = VideoFileClip(p).resized((VIDEO_WIDTH, VIDEO_HEIGHT))
                clips.append(clip)
            except Exception as e:
                print(f"[VideoBuilder] Skipping {p}: {e}")

        # loop clips to fill audio duration
        filled = []
        accumulated = 0.0
        while accumulated < total_duration and clips:
            for clip in clips:
                remaining = total_duration - accumulated
                if remaining <= 0:
                    break
                trimmed = clip.subclipped(0, min(clip.duration, remaining))
                filled.append(trimmed)
                accumulated += trimmed.duration

        body = concatenate_videoclips(filled, method="compose") if filled else \
               ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 40), duration=total_duration)

    intro = build_intro(title)
    outro = build_outro()

    full_video = concatenate_videoclips([intro, body, outro], method="compose")
    full_video = full_video.with_audio(audio)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:40].strip()
    output_path = os.path.join(OUTPUT_VIDEOS, f"{timestamp}_{safe_title}.mp4")

    print("[VideoBuilder] Rendering... (this takes a few minutes)")
    full_video.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    for p in stock_paths:
        try:
            os.remove(p)
        except Exception:
            pass

    print(f"[VideoBuilder] Video saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import glob
    audio_files = glob.glob("output/audio/*.mp3")
    if audio_files:
        latest = max(audio_files)
        assemble_video(latest, "AI tools for developers", "Top 5 AI Tools Every Developer Needs")
    else:
        print("Run voiceover.py first to generate audio.")
