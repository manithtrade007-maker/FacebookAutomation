"""
dashboard/app.py — Multi-Page Web Dashboard + Auto Scheduler
Runs the Flask dashboard AND the daily automation on Railway.
Everything starts automatically — no manual commands needed.
"""

import sys
import os
import json
import subprocess
import requests
import threading
import schedule
import time
from datetime import datetime
from flask import Flask, render_template, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from config import POST_TIME

app = Flask(__name__)
pipeline_running = False
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_FILE = os.path.join(BASE_DIR, "pages.json")


# ── Pages loader ─────────────────────────────────────────────────────────────

def load_pages() -> list:
    pages_json_env = os.getenv("PAGES_JSON", "")
    if pages_json_env:
        try:
            return [p for p in json.loads(pages_json_env) if p.get("active", True)]
        except Exception:
            pass
    if os.path.exists(PAGES_FILE):
        with open(PAGES_FILE) as f:
            return [p for p in json.load(f) if p.get("active", True)]
    return [{
        "name":         "Default Page",
        "page_id":      os.getenv("FB_PAGE_ID"),
        "access_token": os.getenv("FB_ACCESS_TOKEN"),
        "niche":        os.getenv("NICHE", "tech"),
        "post_time":    os.getenv("POST_TIME", "18:00"),
        "active":       True,
    }]


# ── Background scheduler ─────────────────────────────────────────────────────

def _pipeline_job():
    global pipeline_running
    if pipeline_running:
        return
    print(f"[Scheduler] Starting daily pipeline at {datetime.now().strftime('%H:%M:%S')}")
    pipeline_running = True
    try:
        subprocess.run(["python3", "main.py"], cwd=BASE_DIR)
    except Exception as e:
        print(f"[Scheduler] Pipeline error: {e}")
    finally:
        pipeline_running = False


def _token_refresh_job():
    print(f"[Scheduler] Running token refresh...")
    try:
        from token_refresh import run_refresh
        run_refresh()
    except Exception as e:
        print(f"[Scheduler] Token refresh error: {e}")


def _start_background_scheduler():
    print(f"[Scheduler] Started — posting daily at {POST_TIME}, token refresh every 50 days")
    schedule.every().day.at(POST_TIME).do(_pipeline_job)
    schedule.every(50).days.do(_token_refresh_job)
    while True:
        schedule.run_pending()
        time.sleep(60)


# ── Facebook API ──────────────────────────────────────────────────────────────

def fetch_page_stats(page_id: str, token: str) -> dict:
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{page_id}",
            params={"fields": "name,fan_count,followers_count", "access_token": token},
            timeout=10,
        )
        return r.json()
    except Exception:
        return {}


def fetch_page_videos(page_id: str, token: str, limit: int = 5) -> list:
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{page_id}/videos",
            params={"fields": "title,description,length,views,created_time", "access_token": token, "limit": limit},
            timeout=15,
        )
        return r.json().get("data", [])
    except Exception:
        return []


def format_duration(seconds) -> str:
    try:
        m, s = divmod(int(float(seconds)), 60)
        return f"{m}m {s}s"
    except Exception:
        return "—"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    pages           = load_pages()
    all_videos      = []
    page_rows       = []
    total_followers = 0
    total_likes     = 0
    total_views     = 0
    est_minutes     = 0

    for page in pages:
        pid   = page["page_id"]
        token = page["access_token"]
        stats  = fetch_page_stats(pid, token)
        videos = fetch_page_videos(pid, token, limit=5)

        followers = stats.get("followers_count", 0)
        likes     = stats.get("fan_count", 0)
        total_followers += followers
        total_likes     += likes

        page_views = 0
        video_rows = []
        for v in videos:
            views  = v.get("views", 0)
            length = format_duration(v.get("length", 0))
            page_views  += views
            total_views += views
            try:
                mins = int(length.split("m")[0]) if "m" in str(length) else 0
                est_minutes += int(views * mins * 0.5)
            except Exception:
                pass
            row = {
                "page":   page["name"],
                "title":  (v.get("title") or v.get("description", "Untitled"))[:50],
                "status": "published",
                "views":  views,
                "length": length,
                "date":   v.get("created_time", "")[:10],
            }
            video_rows.append(row)
            all_videos.append(row)

        page_rows.append({
            "name":      page["name"],
            "niche":     page.get("niche", "—"),
            "post_time": page.get("post_time", "—"),
            "followers": followers,
            "likes":     likes,
            "views":     page_views,
            "videos":    len(video_rows),
            "status":    "active" if stats.get("name") else "error",
        })

    return jsonify({
        "followers":    total_followers,
        "likes":        total_likes,
        "total_videos": len(all_videos),
        "total_views":  total_views,
        "est_minutes":  est_minutes,
        "pages":        page_rows,
        "videos":       all_videos,
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    global pipeline_running
    if pipeline_running:
        return jsonify({"success": False, "error": "Pipeline already running."})
    thread = threading.Thread(target=_pipeline_job, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": f"Pipeline started for all {len(load_pages())} pages."})


@app.route("/api/refresh-token", methods=["POST"])
def api_refresh_token():
    thread = threading.Thread(target=_token_refresh_job, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Token refresh started for all pages."})


@app.route("/api/status")
def api_status():
    pages = load_pages()
    return jsonify({
        "scheduler":        "running",
        "pipeline_running": pipeline_running,
        "pages_count":      len(pages),
        "post_time":        POST_TIME,
    })


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=_start_background_scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    pages = load_pages()
    print(f"\n{'='*55}")
    print(f"  MMO Dashboard — {len(pages)} page(s) configured")
    print(f"  Posting daily at {POST_TIME}")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
