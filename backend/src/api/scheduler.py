from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from pathlib import Path
import tempfile
import atexit

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def cleanup_old_temp_files(max_age_hours: int = 24):
   """Clean up old temporary receipt files."""
   temp_dir = Path(tempfile.gettempdir())
   cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

   logger.debug(
       f"Starting temp file cleanup | max_age_hours={max_age_hours}, "
       f"temp_dir={temp_dir}"
   )

   cleaned = 0
   failed = 0
   scanned = 0

   for pattern in ['receipt_*', 'tmp*']:
       for temp_file in temp_dir.glob(pattern):
           scanned += 1
           try:
               if temp_file.is_file() and temp_file.stat().st_mtime < cutoff:
                   temp_file.unlink()
                   cleaned += 1
                   logger.debug(f"Deleted old temp file: {temp_file}")
           except Exception as e:
               failed += 1
               logger.warning(f"Failed to delete {temp_file}: {e}")

   if cleaned > 0 or failed > 0:
       logger.info(
           f"Temp file cleanup complete | scanned={scanned}, "
           f"deleted={cleaned}, failed={failed}"
       )
   else:
       logger.debug(f"Temp file cleanup: no old files found ({scanned} scanned)")

   return cleaned


def init_scheduler(app):
   """Initialize the background scheduler."""
   scheduler = BackgroundScheduler()

   scheduler.add_job(
       func=cleanup_old_temp_files,
       trigger='interval',
       hours=1,
       id='cleanup_temp_files',
       name='Clean up old temporary files',
       replace_existing=True
   )

   scheduler.start()
   logger.info("Background scheduler started | jobs: cleanup_temp_files (hourly)")

   atexit.register(lambda: _shutdown_scheduler(scheduler))

   return scheduler


def _shutdown_scheduler(scheduler):
   """Shutdown the scheduler gracefully."""
   logger.info("Shutting down background scheduler")
   scheduler.shutdown()
   logger.debug("Scheduler shutdown complete")