from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from pathlib import Path
import tempfile
import logging
import atexit

logger = logging.getLogger(__name__)


def cleanup_old_temp_files(max_age_hours: int = 24):
    """Clean up old temporary receipt files."""
    cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
    temp_dir = Path(tempfile.gettempdir())
    cleaned = 0
    
    # Clean temp files with receipt prefix
    for pattern in ['receipt_*', 'tmp*']:
        for temp_file in temp_dir.glob(pattern):
            try:
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff:
                    temp_file.unlink()
                    cleaned += 1
                    logger.info(f'Cleaned up old temp file: {temp_file}')
            except Exception as e:
                logger.warning(f'Failed to clean up {temp_file}: {e}')
    
    if cleaned > 0:
        logger.info(f'Cleaned up {cleaned} old temporary files')
    
    return cleaned


def init_scheduler(app):
    """Initialize the background scheduler."""
    scheduler = BackgroundScheduler()
    
    # Run cleanup every hour
    scheduler.add_job(
        func=cleanup_old_temp_files,
        trigger='interval',
        hours=1,
        id='cleanup_temp_files',
        name='Clean up old temporary files',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info('Background scheduler started')
    
    # Shut down scheduler when app exits
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler