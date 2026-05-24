"""
scheduler.py — Automated Daily Runner
Runs the pipeline every day at the configured POST_TIME.
Also runs analytics check every morning at 8 AM.

Usage:
  python scheduler.py        # start the scheduler (runs forever)
  python scheduler.py --now  # run pipeline immediately then keep scheduling
"""

import argparse
import schedule
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

from config import POST_TIME, VIDEOS_PER_DAY
from main import run_pipeline
from modules.analytics import run_daily_analytics

ANALYTICS_TIME = "08:00"   # check analytics every morning


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


def start_scheduler(run_now: bool = False):
    print(f"\n{Fore.YELLOW}{'='*55}")
    print(f"  SCHEDULER STARTED")
    print(f"  Pipeline runs daily at: {POST_TIME}")
    print(f"  Analytics runs daily at: {ANALYTICS_TIME}")
    print(f"  Videos per day: {VIDEOS_PER_DAY}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    # schedule daily pipeline
    schedule.every().day.at(POST_TIME).do(pipeline_job)

    # schedule daily analytics
    schedule.every().day.at(ANALYTICS_TIME).do(analytics_job)

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
