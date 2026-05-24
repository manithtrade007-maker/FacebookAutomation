"""
main.py — Master Pipeline Runner
Runs the full automation pipeline:
  1. Find trending topic
  2. Generate script (Claude API)
  3. Generate voiceover (ElevenLabs)
  4. Build video (MoviePy + FFmpeg)
  5. Create thumbnail (Pillow)
  6. Publish to Facebook (Graph API)

Usage:
  python main.py              # full auto (picks best trend)
  python main.py --topic "Your Custom Topic"   # force a specific topic
  python main.py --dry-run    # run everything EXCEPT publishing
  python main.py --analytics  # show analytics dashboard only
"""

import argparse
import sys
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

from modules.trend_finder  import get_trending_topics, print_topics
from modules.script_writer import generate_script, save_script
from modules.voiceover     import generate_voiceover
from modules.video_builder import assemble_video
from modules.thumbnail     import create_thumbnail
from modules.publisher     import publish_video, init_db
from modules.analytics     import run_daily_analytics, print_dashboard


def log(step: str, msg: str, color: str = Fore.CYAN) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{step}] {msg}{Style.RESET_ALL}")


def run_pipeline(custom_topic: str = None, dry_run: bool = False) -> dict:
    """
    Runs the full content automation pipeline.
    Returns a result dict with paths and status.
    """
    start_time = time.time()
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  FACEBOOK AUTOMATION PIPELINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    result = {
        "success": False,
        "topic": None,
        "script_path": None,
        "audio_path": None,
        "video_path": None,
        "thumbnail_path": None,
        "fb_result": None,
    }

    # ── Step 1: Find Trending Topic ──────────────────────────────────────────
    if custom_topic:
        topic = custom_topic
        log("TREND", f"Using custom topic: {topic}", Fore.GREEN)
    else:
        log("TREND", "Fetching today's trending topics...", Fore.CYAN)
        topics = get_trending_topics(top_n=5)
        print_topics(topics)

        if not topics:
            log("TREND", "No topics found. Exiting.", Fore.RED)
            return result

        topic = topics[0]["title"]
        log("TREND", f"Selected: {topic[:60]}", Fore.GREEN)

    result["topic"] = topic

    # ── Step 2: Generate Script ──────────────────────────────────────────────
    log("SCRIPT", "Generating video script with Claude...", Fore.CYAN)
    script = generate_script(topic)
    script_path = save_script(script, topic)
    result["script_path"] = script_path
    log("SCRIPT", f"Script ready: {script['word_count']} words", Fore.GREEN)

    # ── Step 3: Generate Voiceover ───────────────────────────────────────────
    log("VOICE", "Converting script to speech...", Fore.CYAN)
    safe_label = "".join(c if c.isalnum() else "_" for c in topic[:30])
    audio_path = generate_voiceover(script["full_script"], label=safe_label)
    result["audio_path"] = audio_path
    log("VOICE", f"Audio saved: {audio_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 4: Build Video ──────────────────────────────────────────────────
    log("VIDEO", "Assembling video with stock footage...", Fore.CYAN)
    video_path = assemble_video(
        audio_path=audio_path,
        topic=topic,
        title=script["title"],
        search_query=topic[:40],
    )
    result["video_path"] = video_path
    log("VIDEO", f"Video saved: {video_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 5: Create Thumbnail ─────────────────────────────────────────────
    log("THUMB", "Generating thumbnail...", Fore.CYAN)
    thumbnail_path = create_thumbnail(
        title_text=script["thumbnail_text"],
        topic=topic,
        label=safe_label,
    )
    result["thumbnail_path"] = thumbnail_path
    log("THUMB", f"Thumbnail saved: {thumbnail_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 6: Publish to Facebook ──────────────────────────────────────────
    if dry_run:
        log("PUBLISH", "DRY RUN — skipping Facebook publish.", Fore.YELLOW)
        result["success"] = True
    else:
        log("PUBLISH", "Uploading to Facebook...", Fore.CYAN)
        fb_result = publish_video(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            title=script["title"],
            description=script["description"],
            topic=topic,
            script_path=script_path,
            schedule=True,
        )
        result["fb_result"] = fb_result
        result["success"] = fb_result.get("success", False)

        if result["success"]:
            log("PUBLISH", f"Published! FB ID: {fb_result['fb_video_id']}", Fore.GREEN)
            log("PUBLISH", f"Scheduled for: {fb_result.get('scheduled_at', 'now')}", Fore.GREEN)
        else:
            log("PUBLISH", f"Publish failed: {fb_result.get('error')}", Fore.RED)

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  PIPELINE COMPLETE in {elapsed:.0f}s")
    print(f"  Topic:     {result['topic'][:55]}")
    print(f"  Status:    {'SUCCESS' if result['success'] else 'FAILED'}")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Facebook Content Automation Pipeline")
    parser.add_argument("--topic", type=str, help="Force a specific video topic")
    parser.add_argument("--dry-run", action="store_true", help="Skip publishing to Facebook")
    parser.add_argument("--analytics", action="store_true", help="Show analytics dashboard and exit")
    args = parser.parse_args()

    init_db()

    if args.analytics:
        run_daily_analytics()
        return

    run_pipeline(
        custom_topic=args.topic,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
