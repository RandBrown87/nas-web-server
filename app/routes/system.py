import os
import psutil
import datetime
import subprocess
from flask import Blueprint, jsonify
from config import Config
from app.decorators import login_required
from app.database import get_db

system_bp = Blueprint('system', __name__)

@system_bp.route('/api/health')
def health_check():
    # Check database connectivity
    db_ok = False
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1")
        c.fetchone()
        c.close()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    # Check latest backup archive
    latest_backup = None
    latest_backup_time = None
    if os.path.exists(Config.BACKUP_DIR):
        archives = [f for f in os.listdir(Config.BACKUP_DIR) if f.endswith('.tar.gz')]
        if archives:
            archives.sort(key=lambda x: os.path.getmtime(os.path.join(Config.BACKUP_DIR, x)), reverse=True)
            latest_backup = archives[0]
            latest_backup_time = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(Config.BACKUP_DIR, latest_backup))).strftime('%Y-%m-%d %H:%M:%S')

    storage_ok = os.path.exists(Config.STORAGE_DIR) and os.path.isdir(Config.STORAGE_DIR)
    status_str = 'healthy' if (db_ok and storage_ok) else ('degraded' if storage_ok else 'unhealthy')

    return jsonify({
        'status': status_str,
        'server_role': 'primary',
        'database_online': db_ok,
        'storage_accessible': storage_ok,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'latest_backup': latest_backup,
        'latest_backup_time': latest_backup_time,
        'storage_path': Config.STORAGE_DIR
    }), (200 if status_str == 'healthy' else 503)

@system_bp.route('/api/system')
@login_required
def stats():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(Config.STORAGE_DIR if psutil.os.path.exists(Config.STORAGE_DIR) else '/')

    try:
        proc = subprocess.run(['journalctl', '-n', '15', '--no-pager'], capture_output=True, text=True)
        logs = proc.stdout.splitlines()[-15:] if proc.stdout else ["No recent logs"]
    except Exception:
        logs = ["Logs unavailable on host"]

    return jsonify({
        'cpu_percent': cpu,
        'ram_percent': ram.percent,
        'ram_used_gb': round(ram.used / (1024**3), 2),
        'ram_total_gb': round(ram.total / (1024**3), 2),
        'disk_percent': disk.percent,
        'disk_used_gb': round(disk.used / (1024**3), 2),
        'disk_total_gb': round(disk.total / (1024**3), 2),
        'logs': logs
    })
