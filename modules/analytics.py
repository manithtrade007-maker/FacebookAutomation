"""
Module 7 — Analytics Tracker
Pulls video performance data from Facebook Insights API daily.
Stores metrics in SQLite and prints a dashboard summary.
"""

import sqlite3
import requests
from datetime import datetime
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH

FB_GRAPH_URL = "https://graph.facebook.com/v19.0"


def init_analytics_db() -> None:
    """Creates the analytics table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fb_video_id   TEXT,
            checked_at    TEXT,
            views         INTEGER DEFAULT 0,
            minutes_watched INTEGER DEFAULT 0,
            likes         INTEGER DEFAULT 0,
            comments      INTEGER DEFAULT 0,
            shares        INTEGER DEFAULT 0,
            reach         INTEGER DEFAULT 0,
            estimated_rpm REAL DEFAULT 0.0,
            estimated_revenue REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()


def get_published_videos() -> list[dict]:
    """Returns all successfully published posts from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, fb_post_id, title, topic, published_at
        FROM posts
        WHERE status = 'published' AND fb_post_id IS NOT NULL
        ORDER BY published_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_video_insights(video_id: str) -> dict:
    """Calls Facebook Insights API for a specific video."""
    metrics = [
        "total_video_views",
        "total_video_view_time_by_age_bucket_and_gender",
        "total_video_likes_by_reaction_type",
        "total_video_comments",
        "total_video_shares",
        "total_video_reach",
        "total_video_avg_time_watched",
    ]
    url = f"{FB_GRAPH_URL}/{video_id}/video_insights"
    params = {
        "metric": ",".join(metrics),
        "access_token": FB_ACCESS_TOKEN,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[Analytics] Insights error for {video_id}: {resp.text}")
            return {}

        data = resp.json().get("data", [])
        result = {}
        for item in data:
            name = item["name"]
            values = item.get("values", [{}])
            result[name] = values[-1].get("value", 0) if values else 0
        return result

    except Exception as e:
        print(f"[Analytics] Error fetching insights: {e}")
        return {}


def estimate_revenue(views: int, minutes_watched: int, niche: str = "tech") -> dict:
    """
    Estimates revenue based on views and watch time.
    RPM varies by niche — tech pays $5-12, general pays $1-4.
    """
    rpm_by_niche = {"tech": 7.0, "ai": 8.5, "finance": 10.0, "health": 5.0}
    rpm = rpm_by_niche.get(niche, 5.0)

    # Facebook pays per 1000 views (RPM model)
    ad_revenue = (views / 1000) * rpm

    # Stars revenue (viewers tipping — average $0.001 per view estimate)
    stars_revenue = views * 0.001

    return {
        "rpm": rpm,
        "estimated_ad_revenue": round(ad_revenue, 2),
        "estimated_stars_revenue": round(stars_revenue, 2),
        "estimated_total": round(ad_revenue + stars_revenue, 2),
    }


def save_analytics(fb_video_id: str, insights: dict, revenue: dict) -> None:
    """Stores a snapshot of analytics in the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO analytics
        (fb_video_id, checked_at, views, minutes_watched, likes, comments,
         shares, reach, estimated_rpm, estimated_revenue)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fb_video_id,
        datetime.utcnow().isoformat(),
        insights.get("total_video_views", 0),
        insights.get("total_video_view_time_by_age_bucket_and_gender", 0) // 60,
        insights.get("total_video_likes_by_reaction_type", 0),
        insights.get("total_video_comments", 0),
        insights.get("total_video_shares", 0),
        insights.get("total_video_reach", 0),
        revenue.get("rpm", 0),
        revenue.get("estimated_total", 0),
    ))
    conn.commit()
    conn.close()


def print_dashboard() -> None:
    """Prints a summary dashboard of all posts and their performance."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    posts = conn.execute("""
        SELECT p.title, p.published_at,
               COALESCE(a.views, 0) as views,
               COALESCE(a.minutes_watched, 0) as minutes_watched,
               COALESCE(a.likes, 0) as likes,
               COALESCE(a.estimated_revenue, 0) as revenue
        FROM posts p
        LEFT JOIN analytics a ON p.fb_post_id = a.fb_video_id
        WHERE p.status = 'published'
        ORDER BY p.published_at DESC
        LIMIT 10
    """).fetchall()

    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(estimated_revenue), 0) FROM analytics"
    ).fetchone()[0]

    total_views = conn.execute(
        "SELECT COALESCE(SUM(views), 0) FROM analytics"
    ).fetchone()[0]

    conn.close()

    print("\n" + "="*70)
    print(f"  ANALYTICS DASHBOARD — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    print(f"  Total Views:    {total_views:,}")
    print(f"  Est. Revenue:   ${total_revenue:.2f}")
    print("-"*70)
    print(f"  {'Title':<35} {'Views':>8} {'Minutes':>8} {'Revenue':>9}")
    print("-"*70)

    for row in posts:
        title = row["title"][:34] if row["title"] else "N/A"
        print(f"  {title:<35} {row['views']:>8,} {row['minutes_watched']:>8,} ${row['revenue']:>8.2f}")

    print("="*70 + "\n")


def run_daily_analytics() -> None:
    """Main function — fetches and saves insights for all published videos."""
    init_analytics_db()
    print("[Analytics] Running daily analytics check...")

    videos = get_published_videos()
    if not videos:
        print("[Analytics] No published videos found yet.")
        return

    for video in videos:
        fb_id = video["fb_post_id"]
        print(f"[Analytics] Checking: {video['title'][:40]}...")
        insights = fetch_video_insights(fb_id)
        if insights:
            revenue = estimate_revenue(
                views=insights.get("total_video_views", 0),
                minutes_watched=insights.get("total_video_view_time_by_age_bucket_and_gender", 0) // 60,
            )
            save_analytics(fb_id, insights, revenue)

    print_dashboard()


if __name__ == "__main__":
    run_daily_analytics()
