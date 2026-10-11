"""EcoPulse Automated Scheduler.

Schedules execution of the news ingestion pipeline at 30-minute intervals (or daily IST).
Uses APScheduler's BlockingScheduler with timezone-aware interval triggers.
"""

import logging
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config
from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [EcoPulse.Scheduler] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("EcoPulse.Scheduler")

IST_TIMEZONE = ZoneInfo("Asia/Kolkata")
DEFAULT_INTERVAL_MINUTES = getattr(config, "SCHEDULE_INTERVAL_MINUTES", 30)


def scheduled_pipeline_job():
    """Execute the pipeline run."""
    logger.info("Triggering scheduled EcoPulse pipeline run (30-minute cycle)...")
    try:
        summary = run_pipeline(verbose=True)
        logger.info(
            "Scheduled pipeline finished successfully. New articles inserted: %d",
            summary.get("articles_inserted", 0),
        )
    except Exception as exc:
        logger.exception("Scheduled pipeline encountered an error: %s", exc)


def start_scheduler(
    run_immediately: bool = False,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    daily_mode: bool = False,
):
    """Start the blocking scheduler to run every 30 minutes (or daily)."""
    scheduler = BlockingScheduler(timezone=IST_TIMEZONE)

    if daily_mode:
        trigger = CronTrigger(
            hour=7,
            minute=0,
            timezone=IST_TIMEZONE,
        )
        job_name = "Daily EcoPulse News Aggregator (7:00 AM IST)"
    else:
        trigger = IntervalTrigger(
            minutes=interval_minutes,
            timezone=IST_TIMEZONE,
        )
        job_name = f"EcoPulse News Aggregator (Every {interval_minutes} minutes)"

    scheduler.add_job(
        scheduled_pipeline_job,
        trigger=trigger,
        id="ecopulse_pipeline_job",
        name=job_name,
        replace_existing=True,
    )

    logger.info(
        "EcoPulse scheduler initialized. Job: '%s'",
        job_name,
    )

    if run_immediately:
        logger.info("Executing immediate initial pipeline run...")
        scheduled_pipeline_job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("EcoPulse scheduler stopped by user.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EcoPulse Pipeline Scheduler")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run pipeline once immediately before beginning schedule",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help="Interval in minutes between runs (default: 30)",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Run once daily at 7:00 AM IST instead of interval",
    )
    args = parser.parse_args()

    start_scheduler(
        run_immediately=args.now,
        interval_minutes=args.interval,
        daily_mode=args.daily,
    )

