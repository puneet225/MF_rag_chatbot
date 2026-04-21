"""
Automated Ingestion Scheduler
=============================

This script runs permanently within the Docker 'ingestion' service.
It runs the ingestion pipeline once immediately on startup, 
and then schedules it to run automatically at 9:30 AM every day.

Ensure the TZ environment variable is set to Asia/Kolkata in Docker.
"""

import schedule
import time
import logging
from scripts.ingest_data import ingest_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def scheduled_job():
    """Wrapper to run the ingestion function."""
    logger.info("Starting scheduled ingestion job...")
    try:
        ingest_data()
        logger.info("Scheduled ingestion job completed successfully.")
    except Exception as e:
        logger.exception(f"Scheduled ingestion job failed: {e}")


if __name__ == "__main__":
    logger.info("Scheduler started.")
    
    # Run once immediately on boot to guarantee the API has fresh data
    logger.info("Executing initial boot ingestion...")
    scheduled_job()
    
    # Touch a flag file to signal Docker Healthcheck that API can now start safely
    import os
    flag_path = "/app/data/manifests/initial_boot_complete.flag"
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as f:
        f.write("OK")
    
    # Schedule daily at 9:30 AM
    schedule.every().day.at("09:30").do(scheduled_job)
    
    logger.info("Cron schedule set: 09:30 AM daily.")
    
    # Keep the lightweight event loop alive forever
    while True:
        schedule.run_pending()
        time.sleep(60) # Sleep for 60 seconds to save CPU cycles
