"""
main.py — Master Pipeline Runner
Runs the full automation pipeline for one or all pages in pages.json.

Usage:
  python main.py                    # run for ALL active pages
  python main.py --page "Best Our Vibes"  # run for one specific page
  python main.py --topic "Custom Topic"   # force a topic (all pages)
  python main.py --dry-run          # skip publishing
"""

import argparse
import json
import os
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
from modules.analytics     import run_daily_analytics

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(BASE_DIR, "pages.json")


def log(step: str, msg: str, color: str = Fore.CYAN) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{step}] {msg}{Style.RESET_ALL}")


def load_pages() -> list:
    """Load all active pages from pages.json."""
    if not os.path.exists(PAGES_FILE):
        # fallback to single-page .env config
        from config import FB_PAGE_ID, FB_ACCESS_TOKEN, NICHE, POST_TIME
        return [{
            "name":         "Default Page",
            "page_id":      FB_PAGE_ID,
            "access_token": FB_ACCESS_TOKEN,
            "niche":        NICHE,
            "post_time":    POST_TIME,
            "active":       True,
        }]
    with open(PAGES_FILE) as f:
        pages = json.load(f)
    return [p for p in pages if p.get("active", True)]


def run_pipeline(page: dict, custom_topic: str = None, dry_run: bool = False) -> dict:
    """
    Runs the full content pipeline for a single page.
    page dict must have: name, page_id, access_token, niche, post_time
    """
    page_name = page["name"]
    page_id   = page["page_id"]
    token     = page["access_token"]
    niche     = page.get("niche", "tech")
    post_time = page.get("post_time", "18:00")

    start_time = time.time()
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  PIPELINE — {page_name.upper()} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Niche: {niche} | Post time: {post_time}")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    result = {"success": False, "page": page_name, "topic": None}

    # ── Step 1: Trending Topic ───────────────────────────────────────────────
    if custom_topic:
        topic = custom_topic
        log("TREND", f"Using custom topic: {topic}", Fore.GREEN)
    else:
        log("TREND", f"Finding trending topics for niche: {niche}", Fore.CYAN)
        topics = get_trending_topics(top_n=5, niche=niche)
        print_topics(topics)
        if not topics:
            log("TREND", "No topics found. Skipping this page.", Fore.RED)
            return result
        topic = topics[0]["title"]
        log("TREND", f"Selected: {topic[:60]}", Fore.GREEN)

    result["topic"] = topic

    # ── Step 2: Generate Script ──────────────────────────────────────────────
    log("SCRIPT", "Generating video script...", Fore.CYAN)
    script = generate_script(topic, niche=niche)
    script_path = save_script(script, topic)
    log("SCRIPT", f"Script ready: {script['word_count']} words", Fore.GREEN)

    # ── Step 3: Generate Voiceover ───────────────────────────────────────────
    log("VOICE", "Converting script to speech...", Fore.CYAN)
    safe_label = "".join(c if c.isalnum() else "_" for c in topic[:30])
    audio_path = generate_voiceover(script["full_script"], label=safe_label)
    log("VOICE", f"Audio saved: {audio_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 4: Build Video ──────────────────────────────────────────────────
    log("VIDEO", "Assembling video with stock footage...", Fore.CYAN)
    video_path = assemble_video(
        audio_path=audio_path,
        topic=topic,
        title=script["title"],
        search_query=topic[:40],
    )
    log("VIDEO", f"Video saved: {video_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 5: Create Thumbnail ─────────────────────────────────────────────
    log("THUMB", "Generating thumbnail...", Fore.CYAN)
    thumbnail_path = create_thumbnail(
        title_text=script["thumbnail_text"],
        topic=topic,
        label=safe_label,
    )
    log("THUMB", f"Thumbnail saved: {thumbnail_path.split('/')[-1]}", Fore.GREEN)

    # ── Step 6: Publish ──────────────────────────────────────────────────────
    if dry_run:
        log("PUBLISH", "DRY RUN — skipping Facebook publish.", Fore.YELLOW)
        result["success"] = True
    else:
        log("PUBLISH", f"Uploading to {page_name}...", Fore.CYAN)
        fb_result = publish_video(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            title=script["title"],
            description=script["description"],
            topic=topic,
            script_path=script_path,
            schedule=True,
            post_time=post_time,
            page_id=page_id,
            access_token=token,
            page_name=page_name,
        )
        result["success"] = fb_result.get("success", False)
        if result["success"]:
            log("PUBLISH", f"Published! FB ID: {fb_result['fb_video_id']}", Fore.GREEN)
        else:
            log("PUBLISH", f"Failed: {fb_result.get('error')}", Fore.RED)

    elapsed = time.time() - start_time
    print(f"\n{Fore.YELLOW}  {page_name}: {'✅ SUCCESS' if result['success'] else '❌ FAILED'} in {elapsed:.0f}s{Style.RESET_ALL}\n")
    return result


def run_all_pages(custom_topic: str = None, dry_run: bool = False,
                  filter_page: str = None) -> list:
    """Run the pipeline for all active pages (or one specific page)."""
    init_db()
    pages = load_pages()

    if filter_page:
        pages = [p for p in pages if p["name"].lower() == filter_page.lower()]
        if not pages:
            print(f"{Fore.RED}Page '{filter_page}' not found in pages.json{Style.RESET_ALL}")
            return []

    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  MULTI-PAGE PIPELINE — {len(pages)} page(s)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}{Style.RESET_ALL}")

    results = []
    for i, page in enumerate(pages, 1):
        print(f"\n{Fore.CYAN}[{i}/{len(pages)}] Starting: {page['name']}{Style.RESET_ALL}")
        result = run_pipeline(page, custom_topic=custom_topic, dry_run=dry_run)
        results.append(result)
        if i < len(pages):
            print(f"{Fore.CYAN}Waiting 30s before next page...{Style.RESET_ALL}")
            time.sleep(30)

    # summary
    success = sum(1 for r in results if r["success"])
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"  ALL DONE — {success}/{len(results)} pages published successfully")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    return results


def main():
    parser = argparse.ArgumentParser(description="Facebook Multi-Page Automation Pipeline")
    parser.add_argument("--topic",   type=str, help="Force a specific topic for all pages")
    parser.add_argument("--page",    type=str, help="Run for one specific page by name")
    parser.add_argument("--dry-run", action="store_true", help="Skip publishing")
    parser.add_argument("--analytics", action="store_true", help="Show analytics and exit")
    parser.add_argument("--list-pages", action="store_true", help="List all configured pages")
    args = parser.parse_args()

    if args.analytics:
        run_daily_analytics()
        return

    if args.list_pages:
        pages = load_pages()
        print(f"\n{'='*50}")
        print(f"  CONFIGURED PAGES ({len(pages)} active)")
        print(f"{'='*50}")
        for p in pages:
            print(f"  • {p['name']} | niche: {p['niche']} | posts at: {p['post_time']}")
        print(f"{'='*50}\n")
        return

    run_all_pages(
        custom_topic=args.topic,
        dry_run=args.dry_run,
        filter_page=args.page,
    )


if __name__ == "__main__":
    main()
