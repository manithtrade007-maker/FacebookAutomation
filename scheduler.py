"""
scheduler.py — Automated Daily Runner
Runs the pipeline every day at the configured POST_TIME.
Also runs analytics check every morning at 8 AM.
Token refresh runs every 50 days automatically.

Usage:
  python scheduler.py        # start the scheduler (runs forever)
  python scheduler.py --now  # run pipeline immediately then keep scheduling
"""

import argparse
import schedule
import time
import os
from datetime import datetime, timedelta
from colorama import Fore, Style, init

init(autoreset=True)

from config import POST_TIME, VIDEOS_PER_DAY
from main import run_pipeline
from modules.analytics import run_daily_analytics

ANALYTICS_TIME = "08:00"   # check analytics every morning
TOKEN_REFRESH_DAYS = 50    # refresh before 60-day expiry


def pipeline_job():
    print(f"\n{Fore.YELLOW}[Scheduler] Triggering daily pipeline at {datetime.now().strftime('%H:%M:%S')}{Style.RESET_ALL}")
    try:
        run_pipeline()
    except Exception as e:
        print(f"{Fore.RED}[Scheduler] Pipeline error: {e}{Style.RESET_ALL}")


def analytics_job():
    print(f"\n{Fore.CYAN}[Scheduler] Running daily analytics at {datetime.now().strftime('%H:%M:%S')}{Style.RESET_ALL}")
    try:
        run_daily_analytics()
    except Exception as e:
        print(f"{Fore.RED}[Scheduler] Analytics error: {e}{Style.RESET_ALL}")


def token_refresh_job():
    print(f"\n{Fore.MAGENTA}[Scheduler] Running scheduled token refresh...{Style.RESET_ALL}")
    try:
        from token_refresh import run_refresh
        new_token = run_refresh()
        if new_token:
            print(f"{Fore.GREEN}[Scheduler] Token refreshed successfully!{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[Scheduler] Token refresh failed — check credentials.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[Scheduler] Token refresh error: {e}{Style.RESET_ALL}")


def check_token_age():
    """On startup, refresh if token is 50+ days old."""
    last_refreshed_str = os.getenv("TOKEN_LAST_REFRESHED", "")
    if not last_refreshed_str:
        return
    try:
        last_refreshed = datetime.fromisoformat(last_refreshed_str)
        days_old = (datetime.now() - last_refreshed).days
        if days_old >= TOKEN_REFRESH_DAYS:
            print(f"{Fore.MAGENTA}[Scheduler] Token is {days_old} days old — refreshing now.{Style.RESET_ALL}")
            token_refresh_job()
        else:
            print(f"{Fore.CYAN}[Scheduler] Token age: {days_old} days (refresh in {TOKEN_REFRESH_DAYS - days_old} days){Style.RESET_ALL}")
    except Exception:
        pass


def start_scheduler(run_now: bool = False):
    print(f"\n{Fore.YELLOW}{'='*55}")
    print(f"  SCHEDULER STARTED")
    print(f"  Pipeline runs daily at: {POST_TIME}")
    print(f"  Analytics runs daily at: {ANALYTICS_TIME}")
    print(f"  Token refresh: every {TOKEN_REFRESH_DAYS} days")
    print(f"  Videos per day: {VIDEOS_PER_DAY}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    # check token age on startup
    check_token_age()

    # schedule daily pipeline
    schedule.every().day.at(POST_TIME).do(pipeline_job)

    # schedule daily analytics
    schedule.every().day.at(ANALYTICS_TIME).do(analytics_job)

    # schedule token refresh every 50 days
    schedule.every(TOKEN_REFRESH_DAYS).days.do(token_refresh_job)

    if run_now:
        print(f"{Fore.GREEN}[Scheduler] --now flag detected. Running pipeline immediately...{Style.RESET_ALL}")
        pipeline_job()

    print(f"{Fore.CYAN}[Scheduler] Waiting for next scheduled run. Press Ctrl+C to stop.{Style.RESET_ALL}\n")

    while True:
        schedule.run_pending()
        time.sleep(30)   # check every 30 seconds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Automation Scheduler")
    parser.add_argument("--now", action="store_true", help="Run pipeline immediately on start")
    args = parser.parse_args()

    try:
        start_scheduler(run_now=args.now)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[Scheduler] Stopped by user.{Style.RESET_ALL}")
