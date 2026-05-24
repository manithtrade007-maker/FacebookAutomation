"""
status.py — Quick Dashboard
Run anytime to check:
  - Page stats (followers, likes)
  - How many videos posted
  - Each video's performance
  - Monetization progress

Usage: python3 status.py
"""

import sys
import sqlite3
import requests
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH


def get_page_stats() -> dict:
    """Fetch live page stats from Facebook."""
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}"
        params = {"fields": "name,fan_count,followers_count", "access_token": FB_ACCESS_TOKEN}
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except Exception:
        return {"_offline": True}


def get_video_stats(video_id: str) -> dict:
    """Fetch views for a specific video."""
    try:
        url = f"https://graph.facebook.com/v19.0/{video_id}"
        params = {"fields": "title,length,views", "access_token": FB_ACCESS_TOKEN}
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except Exception:
        return {}


def get_posted_videos() -> list:
    """Get all posted videos from local database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM posts
            ORDER BY created_at DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def format_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def print_dashboard():
    line = "=" * 60

    # ── Page Stats ──────────────────────────────────────────
    print(f"\n{line}")
    print(f"  PAGE DASHBOARD — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(line)

    page = get_page_stats()
    if page.get("_offline"):
        print("  Facebook API: offline/timeout — showing local data only")
        followers, likes = 0, 0
    elif "error" in page:
        print(f"  Facebook API Error: {page['error']['message']}")
        followers, likes = 0, 0
    else:
        followers = page.get("followers_count", 0)
        likes     = page.get("fan_count", 0)
        print(f"  Page:       {page.get('name')}")
        print(f"  Followers:  {followers:,}")
        print(f"  Likes:      {likes:,}")

    # monetization progress
    print(f"\n  MONETIZATION PROGRESS")
    print(f"  {'─'*40}")
    follower_pct = min(100, (followers / 5000) * 100)
    bar = '█' * int(follower_pct // 5) + '░' * (20 - int(follower_pct // 5))
    print(f"  Followers: {followers:,} / 5,000  [{bar}] {follower_pct:.0f}%")
    print(f"  Minutes:   check Insights on your FB page")
    print(f"  Goal:      60,000 minutes watched in 60 days")

    # ── Posted Videos ────────────────────────────────────────
    videos = get_posted_videos()
    print(f"\n  POSTED VIDEOS ({len(videos)} total)")
    print(f"  {'─'*56}")

    if not videos:
        print("  No videos posted yet.")
    else:
        print(f"  {'#':<3} {'Title':<35} {'Status':<12} {'Date'}")
        print(f"  {'─'*56}")
        for i, v in enumerate(videos, 1):
            title  = (v.get("title") or "N/A")[:34]
            status = v.get("status", "unknown")
            date   = (v.get("created_at") or "")[:10]
            fb_id  = v.get("fb_post_id") or ""

            status_icon = "✅" if status == "published" else "❌" if status == "failed" else "⏳"
            print(f"  {i:<3} {title:<35} {status_icon} {status:<10} {date}")

            # fetch live view count if published
            if fb_id and status == "published":
                stats = get_video_stats(fb_id)
                views = stats.get("views", 0)
                length = stats.get("length", 0)
                print(f"      └─ Views: {views:,}  |  Length: {format_duration(length)}  |  FB ID: {fb_id}")

    # ── Next Run ─────────────────────────────────────────────
    print(f"\n  AUTOMATION")
    print(f"  {'─'*40}")
    print(f"  Schedule:   Daily at 6:00 PM")
    print(f"  To start:   python3 scheduler.py")
    print(f"  To run now: python3 main.py")
    print(f"\n{line}\n")


if __name__ == "__main__":
    print_dashboard()
