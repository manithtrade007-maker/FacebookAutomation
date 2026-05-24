"""
Module 6 — Facebook Publisher
Uploads video + thumbnail to a Facebook Page using the Graph API.
Supports scheduled publishing and logs everything to SQLite.
Accepts page_id and access_token as parameters for multi-page support.
"""

import os
import sqlite3
import requests
from datetime import datetime, timedelta
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH

FB_GRAPH_URL = "https://graph.facebook.com/v19.0"


# ── Database setup ───────────────────────────────────────────────────────────

def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id        TEXT,
            page_name      TEXT,
            topic          TEXT,
            title          TEXT,
            fb_post_id     TEXT,
            video_path     TEXT,
            thumbnail_path TEXT,
            script_path    TEXT,
            status         TEXT DEFAULT 'pending',
            scheduled_at   TEXT,
            published_at   TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def log_post(topic: str, title: str, video_path: str, thumbnail_path: str,
             script_path: str, fb_post_id: str = None, status: str = "pending",
             scheduled_at: str = None, page_id: str = None, page_name: str = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        INSERT INTO posts (page_id, page_name, topic, title, fb_post_id, video_path,
                           thumbnail_path, script_path, status, scheduled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (page_id, page_name, topic, title, fb_post_id, video_path,
          thumbnail_path, script_path, status, scheduled_at))
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_post_status(post_id: int, status: str, fb_post_id: str = None) -> None:
    conn = sqlite3.connect(DB_PATH)
    if fb_post_id:
        conn.execute("""
            UPDATE posts SET status=?, fb_post_id=?, published_at=datetime('now')
            WHERE id=?
        """, (status, fb_post_id, post_id))
    else:
        conn.execute("UPDATE posts SET status=? WHERE id=?", (status, post_id))
    conn.commit()
    conn.close()


# ── Facebook API ─────────────────────────────────────────────────────────────

def upload_video_resumable(video_path: str, title: str, description: str,
                           page_id: str, access_token: str,
                           scheduled_publish_time: int = None) -> str:
    """Uploads video using the resumable upload API. Returns the video ID."""
    file_size = os.path.getsize(video_path)

    print(f"[Publisher] Starting upload to page {page_id}...")
    start_resp = requests.post(
        f"{FB_GRAPH_URL}/{page_id}/videos",
        data={
            "upload_phase":  "start",
            "file_size":     file_size,
            "access_token":  access_token,
        },
        timeout=30,
    )
    start_resp.raise_for_status()
    start_data = start_resp.json()
    upload_session_id = start_data["upload_session_id"]
    video_id = start_data["video_id"]
    print(f"[Publisher] Session: {upload_session_id} | Video: {video_id}")

    chunk_size = 10 * 1024 * 1024
    offset = 0
    with open(video_path, "rb") as f:
        while offset < file_size:
            chunk = f.read(chunk_size)
            print(f"[Publisher] Uploading {offset}/{file_size} bytes...")
            transfer_resp = requests.post(
                f"{FB_GRAPH_URL}/{page_id}/videos",
                data={
                    "upload_phase":      "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset":      offset,
                    "access_token":      access_token,
                },
                files={"video_file_chunk": chunk},
                timeout=120,
            )
            transfer_resp.raise_for_status()
            offset = int(transfer_resp.json()["start_offset"])

    print("[Publisher] Finalizing upload...")
    finish_data = {
        "upload_phase":      "finish",
        "upload_session_id": upload_session_id,
        "access_token":      access_token,
        "title":             title,
        "description":       description,
    }
    if scheduled_publish_time:
        finish_data["published"] = "false"
        finish_data["scheduled_publish_time"] = str(scheduled_publish_time)
    else:
        finish_data["published"] = "true"

    finish_resp = requests.post(
        f"{FB_GRAPH_URL}/{page_id}/videos",
        data=finish_data,
        timeout=60,
    )
    finish_resp.raise_for_status()
    print(f"[Publisher] Upload complete! Video ID: {video_id}")
    return video_id


def set_thumbnail(video_id: str, thumbnail_path: str, access_token: str) -> bool:
    print("[Publisher] Setting custom thumbnail...")
    with open(thumbnail_path, "rb") as thumb:
        resp = requests.post(
            f"{FB_GRAPH_URL}/{video_id}",
            data={"access_token": access_token},
            files={"thumb": thumb},
            timeout=30,
        )
    if resp.status_code == 200:
        print("[Publisher] Thumbnail set.")
        return True
    print(f"[Publisher] Thumbnail error: {resp.text}")
    return False


def get_next_post_time(post_time: str = "18:00") -> int:
    """Returns Unix timestamp for the next occurrence of post_time (UTC)."""
    hour, minute = map(int, post_time.split(":"))
    now = datetime.utcnow()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int(target.timestamp())


def publish_video(video_path: str, thumbnail_path: str, title: str,
                  description: str, topic: str, script_path: str,
                  schedule: bool = True, post_time: str = "18:00",
                  page_id: str = None, access_token: str = None,
                  page_name: str = None) -> dict:
    """
    Uploads and publishes (or schedules) a video to a Facebook Page.
    page_id and access_token override config defaults for multi-page support.
    """
    init_db()

    _page_id    = page_id    or FB_PAGE_ID
    _token      = access_token or FB_ACCESS_TOKEN
    _page_name  = page_name  or _page_id

    scheduled_time = get_next_post_time(post_time) if schedule else None
    scheduled_str  = datetime.utcfromtimestamp(scheduled_time).isoformat() if scheduled_time else None

    post_id = log_post(
        topic=topic, title=title,
        video_path=video_path, thumbnail_path=thumbnail_path,
        script_path=script_path, status="uploading",
        scheduled_at=scheduled_str,
        page_id=_page_id, page_name=_page_name,
    )

    try:
        fb_video_id = upload_video_resumable(
            video_path, title, description,
            page_id=_page_id, access_token=_token,
            scheduled_publish_time=scheduled_time,
        )
        set_thumbnail(fb_video_id, thumbnail_path, _token)
        update_post_status(post_id, status="published", fb_post_id=fb_video_id)

        print(f"[Publisher] Done! FB Video ID: {fb_video_id}")
        return {
            "success":      True,
            "fb_video_id":  fb_video_id,
            "scheduled_at": scheduled_str,
            "db_id":        post_id,
        }

    except Exception as e:
        update_post_status(post_id, status="failed")
        print(f"[Publisher] Upload failed: {e}")
        return {"success": False, "error": str(e), "db_id": post_id}
