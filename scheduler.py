"""
scheduler.py — Multi-Page Automated Scheduler
Runs the pipeline for ALL pages in pages.json every day at their configured times.
Token refresh runs every 50 days automatically.

Usage:
  python scheduler.py        # start (runs forever)
  python scheduler.py --now  # run all pages immediately then keep scheduling
"""

import argparse
import json
import os
import schedule
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(BASE_DIR, "pages.json")

TOKEN_REFRESH_DAYS = 50


def load_pages() -> list:
    if not os.path.exists(PAGES_FILE):
        from config import FB_PAGE_ID, FB_ACCESS_TOKEN, NICHE, POST_TIME
        return [{"name": "Default", "page_id": FB_PAGE_ID,
                 "access_token": FB_ACCESS_TOKEN, "niche": NICHE,
                 "post_time": POST_TIME, "active": True}]
    with open(PAGES_FILE) as f:
        return [p for p in json.load(f) if p.get("active", True)]


def make_pipeline_job(page: dict):
    """Returns a job function bound to a specific page."""
    def job():
        name = page["name"]
        print(f"\n{Fore.YELLOW}[Scheduler] Running pipeline for: {name}{Style.RESET_ALL}")
        try:
            from main import run_pipeline
            run_pipeline(page)
        except Exception as e:
            print(f"{Fore.RED}[Scheduler] Error for {name}: {e}{Style.RESET_ALL}")
    return job


def token_refresh_job():
    print(f"\n{Fore.MAGENTA}[Scheduler] Running token refresh for all pages...{Style.RESET_ALL}")
    try:
        from token_refresh import run_refresh
        run_refresh()
    except Exception as e:
        print(f"{Fore.RED}[Scheduler] Token refresh error: {e}{Style.RESET_ALL}")


def check_token_age():
    """On startup, refresh if token is 50+ days old."""
    last_str = os.getenv("TOKEN_LAST_REFRESHED", "")
    if not last_str:
        return
    try:
        days_old = (datetime.now() - datetime.fromisoformat(last_str)).days
        if days_old >= TOKEN_REFRESH_DAYS:
            print(f"{Fore.MAGENTA}[Scheduler] Token is {days_old} days old — refreshing.{Style.RESET_ALL}")
            token_refresh_job()
        else:
            print(f"{Fore.CYAN}[Scheduler] Token age: {days_old} days (refresh in {TOKEN_REFRESH_DAYS - days_old} days){Style.RESET_ALL}")
    except Exception:
        pass


def start_scheduler(run_now: bool = False):
    pages = load_pages()

    print(f"\n{Fore.YELLOW}{'='*55}")
    print(f"  MULTI-PAGE SCHEDULER STARTED")
    print(f"  {len(pages)} active page(s)")
    for p in pages:
        print(f"  • {p['name']} — {p.get('niche','tech')} — posts at {p.get('post_time','18:00')}")
    print(f"  Token refresh: every {TOKEN_REFRESH_DAYS} days")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    check_token_age()

    # schedule each page at its own post_time
    for page in pages:
        post_time = page.get("post_time", "18:00")
        job_fn = make_pipeline_job(page)
        schedule.every().day.at(post_time).do(job_fn)
        print(f"{Fore.CYAN}[Scheduler] {page['name']} scheduled at {post_time}{Style.RESET_ALL}")

    # token refresh every 50 days
    schedule.every(TOKEN_REFRESH_DAYS).days.do(token_refresh_job)

    if run_now:
        print(f"\n{Fore.GREEN}[Scheduler] --now flag: running all pages immediately...{Style.RESET_ALL}")
        for page in pages:
            make_pipeline_job(page)()

    print(f"\n{Fore.CYAN}[Scheduler] Waiting... Press Ctrl+C to stop.{Style.RESET_ALL}\n")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Run all pages immediately")
    args = parser.parse_args()
    try:
        start_scheduler(run_now=args.now)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[Scheduler] Stopped.{Style.RESET_ALL}")
