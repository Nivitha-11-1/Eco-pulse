"""EcoPulse Automated Scheduler.

Schedules daily execution of the news ingestion pipeline at 7:00 AM India Standard Time (IST).
Uses APScheduler's BlockingScheduler with timezone-aware CronTrigger.
"""

import logging
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [EcoPulse.Scheduler] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("EcoPulse.Scheduler")

IST_TIMEZONE = ZoneInfo("Asia/Kolkata")
SCHEDULE_HOUR = 7
SCHEDULE_MINUTE = 0


def scheduled_pipeline_job():
    """Execute the daily pipeline run."""
    logger.info("Triggering scheduled daily EcoPulse pipeline run (7:00 AM IST)...")
    try:
        summary = run_pipeline(verbose=True)
        logger.info(
            "Scheduled pipeline finished successfully. New articles inserted: %d",
            summary.get("articles_inserted", 0),
        )
    except Exception as exc:
        logger.exception("Scheduled pipeline encountered an error: %s", exc)


def start_scheduler(run_immediately: bool = False):
    """Start the blocking scheduler to run daily at 7:00 AM IST."""
    scheduler = BlockingScheduler(timezone=IST_TIMEZONE)

    trigger = CronTrigger(
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        timezone=IST_TIMEZONE,
    )

    scheduler.add_job(
        scheduled_pipeline_job,
        trigger=trigger,
        id="daily_ecopulse_pipeline",
        name="Daily EcoPulse News Aggregator (7:00 AM IST)",
        replace_existing=True,
    )

    logger.info(
        "EcoPulse scheduler initialized. Daily run scheduled for %02d:%02d IST.",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
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

    parser = argparse.ArgumentParser(description="EcoPulse Daily Pipeline Scheduler")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run pipeline once immediately before beginning daily schedule",
    )
    args = parser.parse_args()

    start_scheduler(run_immediately=args.now)
