"""
Autonomous Ingestion Scheduler
==============================

Handles the daily execution of the RAG ingestion pipeline.
Dual-logging: Console + orchestrator/scheduler.log.

Schedules the run for 09:30 AM IST daily.
"""

import os
import sys
import time
import schedule
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# ─── Bootstrap ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from orchestrator.run_pipeline import run_ingestion

# ─── Dual Logging Setup ───────────────────────────────────────────────────────
LOG_FILE = ROOT_DIR / "orchestrator" / "scheduler.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

# Console Handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# File Handler (5MB limit, 3 backups)
fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
fh.setFormatter(formatter)
logger.addHandler(fh)


def scheduled_job():
    """Execute the pipeline and log session stats."""
    logger.info("Session Start: Triggering ingestion pipeline...")
    try:
        run_ingestion()
        logger.info("Session End: Ingestion successful.")
    except Exception as e:
        logger.error(f"Session Failed: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("Orchestrator Scheduler Initialized.")
    
    # 1. Boot Run: Ensure data is fresh on start
    logger.info("Action: Boot-time ingestion starting...")
    scheduled_job()
    
    # 2. Render Handshake: Signal that boot-ingestion is done
    flag_path = ROOT_DIR / "data" / "manifests" / "initial_boot_complete.flag"
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as f:
        f.write("OK")
    logger.info(f"Signal: Handshake flag written to {flag_path}")
    
    # 3. Schedule Loop
    schedule.every().day.at("09:30").do(scheduled_job)
    logger.info("Cron: Daily schedule set for 09:30 AM (Asia/Kolkata).")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
