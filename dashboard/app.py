"""
dashboard/app.py — Web Dashboard
A browser-based control panel for the Facebook automation pipeline.
Access from any device on your network.

Usage: python3 dashboard/app.py
Then open: http://localhost:5000
"""

import sys
import os
import sqlite3
import subprocess
import requests
import threading
from flask import Flask, render_template, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH

app = Flask(__name__)
pipeline_running = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_page_stats() -> dict:
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}"
        params = {"fields": "name,fan_count,followers_count", "access_token": FB_ACCESS_TOKEN}
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception:
        return {}


def fetch_video_views(video_id: str) -> dict:
    try:
        url = f"https://graph.facebook.com/v19.0/{video_id}"
        params = {"fields": "length,views", "access_token": FB_ACCESS_TOKEN}
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception:
        return {}


def get_posted_videos() -> list:
    """Fetch videos directly from Facebook API — works on any server."""
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
        # fallback to local SQLite if available
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
    page    = fetch_page_stats()
    videos  = get_posted_videos()

    followers = page.get("followers_count", 0)
    likes     = page.get("fan_count", 0)

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

    def run():
        global pipeline_running
        pipeline_running = True
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(
            ["python3", "main.py"],
            cwd=project_root,
        )
        pipeline_running = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Pipeline started in background."})


@app.route("/api/scheduler", methods=["POST"])
def api_scheduler():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.Popen(
            ["python3", "scheduler.py"],
            cwd=project_root,
        )
        return jsonify({"success": True, "message": "Scheduler started! Videos will post daily at 6 PM."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    local_ip = "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))  # Railway sets PORT automatically
    print(f"\n{'='*50}")
    print(f"  MMO Dashboard running on port {port}!")
    print(f"{'='*50}\n")
    app.run(host=local_ip, port=port, debug=False)
