"""
Module 2 — Script Writer
Uses Google Gemini API (FREE) to generate a structured, engaging 4-minute video script
based on a trending topic. Includes hook, body, and CTA.

Free tier: 1,500 requests/day — no credit card needed.
Get your free API key at: aistudio.google.com
"""

import os
import sys
import json
from datetime import datetime
from google import genai

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY, NICHE, NICHE_CONFIG, OUTPUT_SCRIPTS


client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are an expert Facebook video script writer.
You write scripts for faceless educational videos that get millions of views.
Your scripts are conversational, engaging, and packed with value.
You always write in plain spoken English — no jargon, no fluff.
Format your response as valid JSON only."""

SCRIPT_TEMPLATE = """Write a Facebook video script about this topic: "{topic}"

Requirements:
- Niche: {niche}
- Tone: {tone}
- Target length: 4 minutes spoken (approx 600 words)
- Target audience: English-speaking, general public, aged 25-45
- Platform: Facebook (not YouTube, not TikTok)

Structure the script with these exact sections:
1. HOOK (first 15 seconds) — grab attention immediately, ask a question or make a bold statement
2. INTRO (30 seconds) — briefly tell them what they'll learn
3. MAIN CONTENT (3 minutes) — 3 key points, each explained clearly with an example
4. CTA (30 seconds) — tell them to like, follow, and share, ask a question to boost comments

Return ONLY a JSON object in this exact format:
{{
  "title": "Catchy Facebook video title (max 80 chars)",
  "description": "Facebook post description with 2-3 relevant hashtags (max 200 chars)",
  "thumbnail_text": "Bold 5-7 word text for thumbnail",
  "sections": {{
    "hook": "script text here",
    "intro": "script text here",
    "main_content": "script text here",
    "cta": "script text here"
  }},
  "full_script": "complete script as one continuous block",
  "word_count": 0,
  "estimated_duration_seconds": 0,
  "tags": ["tag1", "tag2", "tag3"]
}}"""


def generate_script(topic: str, niche: str = None) -> dict:
    """
    Sends a topic to Gemini and returns a fully structured video script.
    niche overrides the global NICHE setting (for multi-page support).
    """
    active_niche = niche or NICHE
    niche_cfg = NICHE_CONFIG.get(active_niche, NICHE_CONFIG["tech"])
    prompt = SYSTEM_PROMPT + "\n\n" + SCRIPT_TEMPLATE.format(
        topic=topic,
        niche=active_niche,
        tone=niche_cfg["script_tone"],
    )

    print(f"[ScriptWriter] Generating script for: {topic[:60]}...")

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = response.text.strip()

    # strip markdown code fences if Gemini wraps it
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    script = json.loads(raw)

    # auto-calculate word count and duration if Claude left them as 0
    full_script = script.get("full_script", "")
    words = len(full_script.split())
    script["word_count"] = words
    script["estimated_duration_seconds"] = int(words / 2.5)  # avg speaking pace

    print(f"[ScriptWriter] Script ready — {words} words, ~{script['estimated_duration_seconds']//60}m {script['estimated_duration_seconds']%60}s")
    return script


def save_script(script: dict, topic: str) -> str:
    """Saves the script JSON to disk and returns the file path."""
    os.makedirs(OUTPUT_SCRIPTS, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c in " _-" else "" for c in topic)[:40].strip()
    filename = f"{timestamp}_{safe_topic}.json"
    filepath = os.path.join(OUTPUT_SCRIPTS, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({**script, "topic": topic, "saved_at": datetime.utcnow().isoformat()}, f, indent=2)

    print(f"[ScriptWriter] Saved to: {filepath}")
    return filepath


def print_script(script: dict) -> None:
    """Pretty-prints the script sections for review."""
    print("\n" + "="*60)
    print(f"  TITLE: {script.get('title', 'N/A')}")
    print("="*60)
    for section, text in script.get("sections", {}).items():
        print(f"\n[{section.upper()}]\n{text}")
    print("\n" + "="*60)
    print(f"  Words: {script['word_count']} | Duration: ~{script['estimated_duration_seconds']//60}m")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_topic = "Why every programmer should learn Python in 2025"
    script = generate_script(test_topic)
    save_script(script, test_topic)
    print_script(script)
