"""
dashboard/app.py — Web Dashboard + Auto Scheduler
Runs the Flask dashboard AND the daily automation on Railway.
Everything starts automatically — no manual commands needed.

Access from anywhere: https://web-production-484f1.up.railway.app
"""

import sys
import os
import sqlite3
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
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH, POST_TIME

app = Flask(__name__)
pipeline_running = False


# ── Background scheduler jobs ────────────────────────────────────────────────

def _pipeline_job():
    global pipeline_running
    if pipeline_running:
        print("[Scheduler] Pipeline already running, skipping.")
        return
    print(f"[Scheduler] Starting daily pipeline at {datetime.now().strftime('%H:%M:%S')}")
    pipeline_running = True
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(["python3", "main.py"], cwd=project_root)
    except Exception as e:
        print(f"[Scheduler] Pipeline error: {e}")
    finally:
        pipeline_running = False


def _token_refresh_job():
    print(f"[Scheduler] Running token refresh at {datetime.now().strftime('%H:%M:%S')}")
    try:
        from token_refresh import run_refresh
        run_refresh()
    except Exception as e:
        print(f"[Scheduler] Token refresh error: {e}")


def _start_background_scheduler():
    """Runs in a background thread — schedules and executes all jobs."""
    print(f"[Scheduler] Background scheduler started.")
    print(f"[Scheduler] Videos will post daily at {POST_TIME}")
    print(f"[Scheduler] Token refreshes every 50 days")

    schedule.every().day.at(POST_TIME).do(_pipeline_job)
    schedule.every(50).days.do(_token_refresh_job)

    while True:
        schedule.run_pending()
        time.sleep(60)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_page_stats() -> dict:
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}"
        params = {"fields": "name,fan_count,followers_count", "access_token": FB_ACCESS_TOKEN}
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception:
        return {}


def get_posted_videos() -> list:
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
        params = {
            "fields": "title,description,length,views,created_time",
            "access_token": FB_ACCESS_TOKEN,
            "limit": 20,
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        videos = data.get("data", [])
        result = []
        for v in videos:
            result.append({
                "fb_post_id": v.get("id"),
                "title":      v.get("title") or v.get("description", "Untitled")[:60],
                "status":     "published",
                "views":      v.get("views", 0),
                "length":     format_duration(v.get("length", 0)),
                "created_at": v.get("created_time", "")[:10],
            })
        return result
    except Exception:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 20").fetchall()
            conn.close()
            return [dict(r) for r in rows]
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
    page   = fetch_page_stats()
    videos = get_posted_videos()

    followers   = page.get("followers_count", 0)
    likes       = page.get("fan_count", 0)
    total_views = 0
    est_minutes = 0
    video_rows  = []

    for v in videos:
        views  = v.get("views", 0)
        length = v.get("length", "—")
        total_views += views
        try:
            mins = int(length.split("m")[0]) if "m" in str(length) else 0
            est_minutes += int(views * mins * 0.5)
        except Exception:
            pass
        video_rows.append({
            "title":  (v.get("title") or "Untitled")[:50],
            "status": v.get("status", "published"),
            "views":  views,
            "length": length,
            "date":   (v.get("created_at") or "")[:10],
        })

    return jsonify({
        "followers":    followers,
        "likes":        likes,
        "total_videos": len([v for v in videos if v.get("status") == "published"]),
        "total_views":  total_views,
        "est_minutes":  est_minutes,
        "videos":       video_rows,
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    global pipeline_running
    if pipeline_running:
        return jsonify({"success": False, "error": "Pipeline is already running."})

    thread = threading.Thread(target=_pipeline_job, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Pipeline started in background."})


@app.route("/api/refresh-token", methods=["POST"])
def api_refresh_token():
    thread = threading.Thread(target=_token_refresh_job, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Token refresh started. Check Railway logs."})


@app.route("/api/status")
def api_status():
    next_run = None
    for job in schedule.get_jobs():
        t = job.next_run
        if t and (next_run is None or t < next_run):
            next_run = t
    return jsonify({
        "scheduler": "running",
        "pipeline_running": pipeline_running,
        "post_time": POST_TIME,
        "next_scheduled_run": next_run.isoformat() if next_run else None,
    })


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # start background scheduler automatically on launch
    scheduler_thread = threading.Thread(target=_start_background_scheduler, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", 8080))
    print(f"\n{'='*50}")
    print(f"  MMO Dashboard running on port {port}")
    print(f"  Scheduler running — posting daily at {POST_TIME}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
