"""
Module 1 — Trend Finder
Scrapes Google Trends + Reddit to find the best topic to make a video about today.
Returns a ranked list of topics with scores.
"""

import time
import requests
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from config import NICHE, NICHE_CONFIG, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT


def get_google_trends(keywords: list[str]) -> dict[str, int]:
    """Returns search interest score (0-100) for each keyword over the past 7 days."""
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        # Google Trends allows max 5 keywords per request
        scores = {}
        for i in range(0, len(keywords), 5):
            batch = keywords[i:i+5]
            pytrends.build_payload(batch, timeframe="now 7-d", geo="US")
            data = pytrends.interest_over_time()
            if not data.empty:
                for kw in batch:
                    if kw in data.columns:
                        scores[kw] = int(data[kw].mean())
            time.sleep(1)  # be polite to Google
        return scores
    except Exception as e:
        print(f"[TrendFinder] Google Trends error: {e}")
        return {}


def get_reddit_hot_topics(subreddits: list[str]) -> list[dict]:
    """Fetches top posts from subreddits using Reddit's public JSON API (no auth needed)."""
    topics = []
    headers = {"User-Agent": REDDIT_USER_AGENT}

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue

            posts = response.json()["data"]["children"]
            for post in posts:
                data = post["data"]
                # skip stickied mod posts
                if data.get("stickied"):
                    continue
                topics.append({
                    "title":      data["title"],
                    "score":      data["score"],
                    "comments":   data["num_comments"],
                    "subreddit":  data["subreddit"],
                    "url":        f"https://reddit.com{data['permalink']}",
                    "created":    datetime.utcfromtimestamp(data["created_utc"]),
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"[TrendFinder] Reddit error ({sub}): {e}")

    return topics


def score_reddit_topics(topics: list[dict]) -> list[dict]:
    """Scores Reddit posts by recency + engagement to find today's best topics."""
    now = datetime.utcnow()
    scored = []

    for topic in topics:
        age_hours = (now - topic["created"]).total_seconds() / 3600

        # prefer posts from last 24 hours
        recency_score = max(0, 100 - (age_hours * 4))

        # engagement score based on upvotes + comments
        engagement_score = min(100, (topic["score"] / 100) + (topic["comments"] / 10))

        final_score = (recency_score * 0.4) + (engagement_score * 0.6)

        scored.append({**topic, "final_score": round(final_score, 2)})

    return sorted(scored, key=lambda x: x["final_score"], reverse=True)


def get_trending_topics(top_n: int = 5) -> list[dict]:
    """
    Main function — combines Google Trends + Reddit to find the best topics.
    Returns top_n topics ready to be turned into video scripts.
    """
    niche_cfg = NICHE_CONFIG.get(NICHE, NICHE_CONFIG["tech"])
    print(f"[TrendFinder] Searching trends for niche: {NICHE}")

    # 1. Get Google Trends scores
    print("[TrendFinder] Fetching Google Trends...")
    trend_scores = get_google_trends(niche_cfg["trend_keywords"])

    # 2. Get Reddit hot topics
    print("[TrendFinder] Fetching Reddit hot posts...")
    reddit_topics = get_reddit_hot_topics(niche_cfg["subreddits"])

    # 3. Score and rank Reddit topics
    ranked = score_reddit_topics(reddit_topics)

    # 4. Build final output
    results = []
    for topic in ranked[:top_n]:
        results.append({
            "title":       topic["title"],
            "source":      f"r/{topic['subreddit']}",
            "score":       topic["final_score"],
            "reddit_url":  topic["url"],
            "niche":       NICHE,
            "fetched_at":  datetime.utcnow().isoformat(),
        })

    print(f"[TrendFinder] Found {len(results)} trending topics.")
    return results


def print_topics(topics: list[dict]) -> None:
    """Pretty-prints topics for review."""
    print("\n" + "="*60)
    print(f"  TOP TRENDING TOPICS — {datetime.now().strftime('%Y-%m-%d')}")
    print("="*60)
    for i, t in enumerate(topics, 1):
        print(f"\n#{i}  [{t['score']:.0f} pts] {t['title']}")
        print(f"     Source: {t['source']}")
        print(f"     URL:    {t['reddit_url']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    topics = get_trending_topics(top_n=5)
    print_topics(topics)
