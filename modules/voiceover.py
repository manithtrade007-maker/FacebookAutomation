"""
Module 3 — Voiceover Generator
Converts the video script to natural-sounding MP3 audio using Edge-TTS.
Edge-TTS is Microsoft's text-to-speech engine — completely FREE, no API key needed.
Quality is very close to ElevenLabs for most use cases.

Best free voices:
  en-US-AriaNeural      — warm, friendly female (best for general content)
  en-US-GuyNeural       — confident male
  en-US-JennyNeural     — clear, professional female
  en-GB-SoniaNeural     — British female (sounds premium)
"""

import os
import sys
import asyncio
from datetime import datetime
import edge_tts

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUTPUT_AUDIO

DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_RATE  = "+5%"    # slightly faster than default — sounds more natural
DEFAULT_PITCH = "+0Hz"


async def _synthesize(text: str, output_path: str,
                      voice: str, rate: str, pitch: str) -> None:
    """Internal async function that calls Edge-TTS and saves the MP3."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def generate_voiceover(script_text: str, label: str = "output",
                       voice: str = DEFAULT_VOICE) -> str:
    """
    Main function — converts full script to a single MP3 file using Edge-TTS.
    Completely free, no API key needed.
    Returns the path to the saved MP3 file.
    """
    print(f"[Voiceover] Converting script to speech ({len(script_text)} chars)...")
    print(f"[Voiceover] Voice: {voice}")
    os.makedirs(OUTPUT_AUDIO, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{label[:30]}.mp3"
    filepath = os.path.join(OUTPUT_AUDIO, filename)

    # run async edge-tts in sync context
    asyncio.run(_synthesize(script_text, filepath, voice, DEFAULT_RATE, DEFAULT_PITCH))

    size_kb = os.path.getsize(filepath) / 1024
    print(f"[Voiceover] Saved audio: {filepath} ({size_kb:.1f} KB)")
    return filepath


def list_voices() -> None:
    """Prints all available English voices from Edge-TTS."""
    async def _list():
        voices = await edge_tts.list_voices()
        en_voices = [v for v in voices if v["Locale"].startswith("en-")]
        print(f"\n{'='*55}")
        print(f"  Available English Voices ({len(en_voices)} total)")
        print(f"{'='*55}")
        for v in en_voices:
            print(f"  {v['ShortName']:<35} {v['Gender']}")
        print(f"{'='*55}\n")
    asyncio.run(_list())


if __name__ == "__main__":
    sample = (
        "Welcome back! Today we're going to talk about something that could "
        "completely change how you think about technology. Artificial intelligence "
        "is no longer science fiction — it's already in your pocket, in your home, "
        "and in the tools you use every single day. Let's break down exactly what's "
        "happening and why it matters to you. By the end of this video, you'll "
        "understand the three biggest AI breakthroughs of 2025 and how they affect "
        "your daily life. Let's get into it."
    )
    path = generate_voiceover(sample, label="test_voiceover")
    print(f"Audio saved: {path}")
