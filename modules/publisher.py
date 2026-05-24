"""
Module 6 — Facebook Publisher
Uploads video + thumbnail to a Facebook Page using the Graph API.
Supports scheduled publishing and logs everything to SQLite.
"""

import os
import sqlite3
import requests
from datetime import datetime, timedelta
from config import FB_PAGE_ID, FB_ACCESS_TOKEN, DB_PATH

FB_GRAPH_URL = "https://graph.facebook.com/v19.0"


# ── Database setup ───────────────────────────────────────────────────────────

def init_db() -> None:
    """Creates the posts table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            topic         TEXT,
            title         TEXT,
            fb_post_id    TEXT,
            video_path    TEXT,
            thumbnail_path TEXT,
            script_path   TEXT,
            status        TEXT DEFAULT 'pending',
            scheduled_at  TEXT,
            published_at  TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def log_post(topic: str, title: str, video_path: str, thumbnail_path: str,
             script_path: str, fb_post_id: str = None,
             status: str = "pending", scheduled_at: str = None) -> int:
    """Inserts a new post record and returns its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        INSERT INTO posts (topic, title, fb_post_id, video_path, thumbnail_path,
                           script_path, status, scheduled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (topic, title, fb_post_id, video_path, thumbnail_path,
          script_path, status, scheduled_at))
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_post_status(post_id: int, status: str, fb_post_id: str = None) -> None:
    """Updates a post record after publishing."""
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
                           scheduled_publish_time: int = None) -> str:
    """
    Uploads video to Facebook using the resumable upload API.
    Returns the Facebook video/post ID.
    """
    file_size = os.path.getsize(video_path)

    # Step 1 — start upload session
    print("[Publisher] Starting resumable upload session...")
    start_resp = requests.post(
        f"{FB_GRAPH_URL}/{FB_PAGE_ID}/videos",
        data={
            "upload_phase": "start",
            "file_size": file_size,
            "access_token": FB_ACCESS_TOKEN,
        },
        timeout=30,
    )
    start_resp.raise_for_status()
    start_data = start_resp.json()
    upload_session_id = start_data["upload_session_id"]
    video_id = start_data["video_id"]
    print(f"[Publisher] Session ID: {upload_session_id}, Video ID: {video_id}")

    # Step 2 — transfer video in chunks
    chunk_size = 10 * 1024 * 1024   # 10 MB chunks
    offset = 0

    with open(video_path, "rb") as f:
        while offset < file_size:
            chunk = f.read(chunk_size)
            print(f"[Publisher] Uploading chunk at offset {offset}/{file_size}...")
            transfer_resp = requests.post(
                f"{FB_GRAPH_URL}/{FB_PAGE_ID}/videos",
                data={
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": offset,
                    "access_token": FB_ACCESS_TOKEN,
                },
                files={"video_file_chunk": chunk},
                timeout=120,
            )
            transfer_resp.raise_for_status()
            offset = int(transfer_resp.json()["start_offset"])

    # Step 3 — finish upload & set metadata
    print("[Publisher] Finalizing upload...")
    finish_data = {
        "upload_phase": "finish",
        "upload_session_id": upload_session_id,
        "access_token": FB_ACCESS_TOKEN,
        "title": title,
        "description": description,
        "content_tags": "",
    }

    if scheduled_publish_time:
        finish_data["published"] = "false"
        finish_data["scheduled_publish_time"] = str(scheduled_publish_time)
    else:
        finish_data["published"] = "true"

    finish_resp = requests.post(
        f"{FB_GRAPH_URL}/{FB_PAGE_ID}/videos",
        data=finish_data,
        timeout=60,
    )
    finish_resp.raise_for_status()
    print(f"[Publisher] Upload complete! Video ID: {video_id}")
    return video_id


def set_thumbnail(video_id: str, thumbnail_path: str) -> bool:
    """Attaches a custom thumbnail to an uploaded video."""
    print("[Publisher] Setting custom thumbnail...")
    with open(thumbnail_path, "rb") as thumb:
        resp = requests.post(
            f"{FB_GRAPH_URL}/{video_id}",
            data={"access_token": FB_ACCESS_TOKEN},
            files={"thumb": thumb},
            timeout=30,
        )
    success = resp.status_code == 200
    if success:
        print("[Publisher] Thumbnail set successfully.")
    else:
        print(f"[Publisher] Thumbnail error: {resp.text}")
    return success


def get_next_post_time(hour: int = 18, minute: int = 0) -> int:
    """Returns Unix timestamp for next occurrence of the given hour:minute (US Eastern)."""
    now = datetime.utcnow()
    # UTC-5 offset for US Eastern; adjust if needed
    et_offset = timedelta(hours=5)
    target = now.replace(hour=hour + 5, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int(target.timestamp())


def publish_video(video_path: str, thumbnail_path: str, title: str,
                  description: str, topic: str, script_path: str,
                  schedule: bool = True) -> dict:
    """
    Main function — uploads and publishes (or schedules) a video to Facebook.
    Returns a result dict with status and post ID.
    """
    init_db()

    scheduled_time = get_next_post_time(hour=18) if schedule else None
    scheduled_str = datetime.utcfromtimestamp(scheduled_time).isoformat() if scheduled_time else None

    # log as pending before uploading
    post_id = log_post(
        topic=topic, title=title,
        video_path=video_path, thumbnail_path=thumbnail_path,
        script_path=script_path, status="uploading",
        scheduled_at=scheduled_str,
    )

    try:
        fb_video_id = upload_video_resumable(
            video_path, title, description, scheduled_publish_time=scheduled_time
        )
        set_thumbnail(fb_video_id, thumbnail_path)
        update_post_status(post_id, status="published", fb_post_id=fb_video_id)

        result = {
            "success": True,
            "fb_video_id": fb_video_id,
            "scheduled_at": scheduled_str,
            "db_id": post_id,
        }
        print(f"[Publisher] Done! FB Video ID: {fb_video_id}")
        return result

    except Exception as e:
        update_post_status(post_id, status="failed")
        print(f"[Publisher] Upload failed: {e}")
        return {"success": False, "error": str(e), "db_id": post_id}


if __name__ == "__main__":
    print("Publisher module loaded.")
    print("Run main.py to trigger the full pipeline.")
