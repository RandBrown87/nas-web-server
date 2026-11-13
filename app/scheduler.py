import time
import threading
from app.backup_utils import check_and_run_scheduled_backups

_scheduler_running = False

def _scheduler_loop(interval_sec=60):
    global _scheduler_running
    while _scheduler_running:
        try:
            check_and_run_scheduled_backups()
        except Exception as e:
            print(f"Scheduler exception: {e}")
        time.sleep(interval_sec)

def start_scheduler(app=None):
    global _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="NAS-Backup-Scheduler")
    t.start()
